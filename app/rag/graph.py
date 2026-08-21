from typing import Annotated, Sequence, TypedDict, Optional, List, Dict, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

from app.rag.engine import RAGEngine
from app.rag.guardrails import InputGuardrail


class ConversationState(TypedDict):
    """
    State container for LangGraph Corrective RAG (CRAG) workflow.
    - messages: Multi-turn message history.
    - context: Retrieved & formatted transcript chunks.
    - rerank_score: Top Cross-Encoder score for zero-token retrieval grading.
    - retry_count: Safeguard counter to prevent infinite self-correction loops.
    - current_query: The active search query (original or rewritten).
    - is_safe: Boolean flag indicating if input passed guardrails.
    - refusal_reason: Message explanation if blocked by guardrails.
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    context: str
    podcast_name: Optional[str]
    route: str
    rerank_score: float
    retry_count: int
    current_query: str
    is_safe: bool
    refusal_reason: Optional[str]


class PodcastRAGGraph:
    def __init__(self, engine: RAGEngine):
        self.engine = engine
        self.guardrail = InputGuardrail()
        self.checkpointer = MemorySaver()
        self.app = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(ConversationState)

        # 1. Define Nodes
        workflow.add_node("guardrail", self._guardrail_node)
        workflow.add_node("refuse_unsafe", self._refuse_unsafe_node)
        workflow.add_node("router", self._router_node)
        workflow.add_node("retrieve", self._retrieve_node)
        workflow.add_node("rewrite_query", self._rewrite_query_node)
        workflow.add_node("generate", self._generate_node)

        # 2. Define Edges & Flow
        workflow.add_edge(START, "guardrail")

        # Edge from guardrail -> Check safety before routing or retrieval
        workflow.add_conditional_edges(
            "guardrail",
            self._guardrail_decision,
            {
                "safe": "router",
                "unsafe": "refuse_unsafe",
            },
        )

        # Edge from refuse_unsafe -> Terminate immediately
        workflow.add_edge("refuse_unsafe", END)

        # Edge from router -> Search vs Memory
        workflow.add_conditional_edges(
            "router",
            self._route_decision,
            {
                "search": "retrieve",
                "respond_from_history": "generate",
            },
        )

        # Edge from retrieve -> Grade retrieval confidence (Zero-Token Heuristic)
        workflow.add_conditional_edges(
            "retrieve",
            self._grade_retrieval_confidence,
            {
                "rewrite_query": "rewrite_query",  # Low confidence -> Self-correct!
                "generate": "generate",            # High confidence -> Generate answer
            },
        )

        # Cyclic edge: rewrite_query loops BACK to retrieve!
        workflow.add_edge("rewrite_query", "retrieve")

        # Terminal edge
        workflow.add_edge("generate", END)

        # 3. Compile with in-memory checkpointer for session tracking
        return workflow.compile(checkpointer=self.checkpointer)

    def _guardrail_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        Validates user input against prompt injection and jailbreak attacks (< 1ms, 0 tokens).
        """
        messages = state.get("messages", [])
        query = state.get("current_query") or (messages[-1].content if messages else "")

        is_safe, refusal_reason = self.guardrail.validate(query)
        if not is_safe:
            print(f"[Guardrail Intercepted]: {refusal_reason}")

        return {
            "is_safe": is_safe,
            "refusal_reason": refusal_reason,
            "current_query": query,
        }

    def _guardrail_decision(self, state: ConversationState) -> str:
        return "safe" if state.get("is_safe", True) else "unsafe"

    def _refuse_unsafe_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        Returns a deterministic safety refusal message without invoking the LLM.
        """
        refusal_msg = state.get(
            "refusal_reason",
            "Security Alert: Your request was flagged as a potential policy violation or injection attempt.",
        )
        return {"messages": [AIMessage(content=refusal_msg)]}

    def _router_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        Classifies whether the user question requires searching podcast transcripts
        or can be answered directly from the existing chat conversation history.
        """
        messages = state.get("messages", [])
        if not messages:
            return {"route": "search", "context": "", "retry_count": 0, "current_query": ""}

        last_user_msg = messages[-1].content

        # Initial query assignment
        current_query = state.get("current_query") or last_user_msg

        # If first turn, always search transcripts
        if len(messages) <= 1:
            return {
                "route": "search",
                "context": "",
                "retry_count": 0,
                "current_query": current_query,
            }

        # Asymmetric Router: Biased towards SEARCH to prevent hallucinations
        router_prompt = f"""You are a query routing classifier.
Analyze the user question and prior conversation.
Determine if answering requires searching the podcast database for facts, or if it is a conversational follow-up / summary.

Conversation turns: {len(messages)}
Latest User Question: "{last_user_msg}"

Reply ONLY with one word:
"SEARCH" - If this is a question about facts, transcripts, or new topics. (WHEN IN DOUBT, DEFAULT TO SEARCH).
"MEMORY" - If this is simple chit-chat, a thank-you, or asking to clarify/reformat prior answers.
"""
        try:
            decision = self.engine.llm.invoke([HumanMessage(content=router_prompt)]).content.strip().upper()
            route = "search" if "SEARCH" in decision else "respond_from_history"
        except Exception:
            route = "search"

        return {
            "route": route,
            "context": "",
            "retry_count": 0,
            "current_query": current_query,
        }

    def _route_decision(self, state: ConversationState) -> str:
        return state.get("route", "search")

    def _retrieve_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        Executes hybrid dense + sparse retrieval in Qdrant and neural reranking.
        """
        messages = state.get("messages", [])
        query = state.get("current_query") or (messages[-1].content if messages else "")

        where_filter = None
        if state.get("podcast_name"):
            where_filter = {"podcast_name": state["podcast_name"]}

        # Execute Hybrid Retrieval (Qdrant Dense + Sparse -> RRF -> Cross-Encoder)
        chunks = self.engine.retriever.retrieve(
            query=query,
            top_k=self.engine.settings.RAG_TOP_K,
            top_n=self.engine.settings.RAG_TOP_N,
            where_filter=where_filter,
        )

        top_rerank_score = chunks[0].get("rerank_score", 0.0) if chunks else -10.0

        formatted_chunks = []
        for i, chunk in enumerate(chunks):
            podcast = chunk.get("podcast_name", "Unknown")
            episode = chunk.get("episode_id", "Unknown")
            content = chunk.get("text", "")
            start_t = chunk.get("start_time", -1.0)
            time_str = f" [at {start_t:.1f}s]" if start_t >= 0 else ""

            formatted = f"--- Chunk {i+1} (Podcast: {podcast}, Ep: {episode}{time_str}) ---\n{content}\n"
            formatted_chunks.append(formatted)

        context_string = "\n".join(formatted_chunks)
        return {
            "context": context_string,
            "rerank_score": top_rerank_score,
        }

    def _grade_retrieval_confidence(self, state: ConversationState) -> str:
        """
        Zero-Token Grader: Uses the Cross-Encoder neural rerank score.
        If score is low (< 0.0) and we haven't retried yet, trigger query expansion!
        """
        score = state.get("rerank_score", 0.0)
        retry_count = state.get("retry_count", 0)

        # If retrieval confidence is low (< 0.0) and max 1 retry allowed
        if score < 0.0 and retry_count < 1:
            print(f"[LangGraph CRAG] Low retrieval confidence (Score: {score:.2f}). Triggering query rewrite loop...")
            return "rewrite_query"

        return "generate"

    def _rewrite_query_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        Self-Correction Node: Formulates an optimized keyword query to recover from poor retrieval.
        """
        messages = state.get("messages", [])
        original_query = messages[-1].content if messages else state.get("current_query", "")

        rewrite_prompt = f"""You are a search query optimizer for a podcast transcript database.
The initial search for: "{original_query}" yielded low relevance.
Rephrase and expand this query into clear, keyword-rich search terms representing the core topic, speakers, or technical acronyms.

Return ONLY the rewritten search string, nothing else.
"""
        try:
            rewritten = self.engine.llm.invoke([HumanMessage(content=rewrite_prompt)]).content.strip()
            print(f"[LangGraph CRAG] Rewrote query to: '{rewritten}'")
        except Exception:
            rewritten = original_query

        return {
            "current_query": rewritten,
            "retry_count": state.get("retry_count", 0) + 1,
        }

    def _generate_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        Generates the grounded answer using the multi-provider LLM.
        """
        messages = state.get("messages", [])
        context = state.get("context", "")

        system_instruction = (
            "You are a helpful, accurate podcast AI assistant.\n"
            "Answer the user's question clearly using the provided podcast transcripts and conversation history.\n"
            "When citing facts, include timestamps in brackets like [at 12.5s] if available.\n"
            "If the answer is not in the transcripts or conversation, say 'I don't have enough information in the transcripts to answer that.'"
        )

        if context:
            system_instruction += f"\n\nPODCAST TRANSCRIPTS:\n{context}"

        full_prompt = [SystemMessage(content=system_instruction)] + list(messages)

        response = self.engine.llm.invoke(full_prompt)
        text_content = response.content
        if isinstance(text_content, list):
            text_content = "".join(
                p.get("text", "") if isinstance(p, dict) else str(p) for p in text_content
            )
        elif not isinstance(text_content, str):
            text_content = str(text_content)

        return {"messages": [AIMessage(content=text_content)]}

    def chat(
        self,
        query: str,
        thread_id: str = "default_session",
        podcast_name: Optional[str] = None,
    ) -> str:
        """
        Public entrypoint for multi-turn chat with thread_id session tracking.
        """
        config = {"configurable": {"thread_id": thread_id}}
        inputs = {
            "messages": [HumanMessage(content=query)],
            "podcast_name": podcast_name,
            "current_query": query,
            "retry_count": 0,
            "is_safe": True,
            "refusal_reason": None,
        }

        final_state = self.app.invoke(inputs, config=config)
        last_message = final_state["messages"][-1].content
        if isinstance(last_message, list):
            last_message = "".join(
                p.get("text", "") if isinstance(p, dict) else str(p) for p in last_message
            )
        return str(last_message)
