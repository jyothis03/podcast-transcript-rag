from typing import Annotated, Sequence, TypedDict, Optional, List, Dict, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

from app.rag.engine import RAGEngine


class ConversationState(TypedDict):
    """
    State container for LangGraph conversation workflow.
    `messages` uses `add_messages` to automatically append turns without overwriting history.
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    context: str
    podcast_name: Optional[str]
    route: str


class PodcastRAGGraph:
    def __init__(self, engine: RAGEngine):
        self.engine = engine
        self.checkpointer = MemorySaver()
        self.app = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(ConversationState)

        # 1. Define Nodes
        workflow.add_node("router", self._router_node)
        workflow.add_node("retrieve", self._retrieve_node)
        workflow.add_node("generate", self._generate_node)

        # 2. Define Edges & Flow
        workflow.add_edge(START, "router")

        workflow.add_conditional_edges(
            "router",
            self._route_decision,
            {
                "search": "retrieve",
                "respond_from_history": "generate",
            },
        )

        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)

        # 3. Compile with in-memory checkpointer for session tracking
        return workflow.compile(checkpointer=self.checkpointer)

    def _router_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        Classifies whether the user question requires searching podcast transcripts
        or can be answered directly from the existing chat conversation history.
        """
        messages = state.get("messages", [])
        if not messages:
            return {"route": "search", "context": ""}

        last_user_msg = messages[-1].content

        # If this is the very first turn, always search transcripts
        if len(messages) <= 1:
            return {"route": "search", "context": ""}

        # Use the LLM as a fast binary router
        router_prompt = f"""You are a query routing classifier.
Analyze the following user question and the prior conversation.
Determine if answering requires searching the podcast database for facts, or if it is a conversational follow-up / summary of what was already discussed.

Conversation turns: {len(messages)}
Latest User Question: "{last_user_msg}"

Reply ONLY with one word:
"SEARCH" - If this is a question about facts, transcripts, or new topics.
"MEMORY" - If this is simple chit-chat, a thank-you, or asking to clarify/reformat prior answers.
"""
        try:
            decision = self.engine.llm.invoke([HumanMessage(content=router_prompt)]).content.strip().upper()
            route = "search" if "SEARCH" in decision else "respond_from_history"
        except Exception:
            route = "search"  # Safe fallback

        return {"route": route, "context": ""}

    def _route_decision(self, state: ConversationState) -> str:
        return state.get("route", "search")

    def _retrieve_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        Executes hybrid dense + sparse retrieval in Qdrant and neural reranking.
        """
        messages = state.get("messages", [])
        if not messages:
            return {"context": ""}

        query = messages[-1].content
        where_filter = None
        if state.get("podcast_name"):
            where_filter = {"podcast_name": state["podcast_name"]}

        # Call our HybridRetriever (Qdrant Dense + Sparse -> RRF -> CrossEncoder)
        chunks = self.engine.retriever.retrieve(
            query=query,
            top_k=self.engine.settings.RAG_TOP_K,
            top_n=self.engine.settings.RAG_TOP_N,
            where_filter=where_filter,
        )

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
        return {"context": context_string}

    def _generate_node(self, state: ConversationState) -> Dict[str, Any]:
        """
        Generates the grounded answer using the unified LLM (Gemini 3.7 Flash with Groq fallback).
        """
        messages = state.get("messages", [])
        context = state.get("context", "")

        system_instruction = (
            "You are a helpful, accurate podcast AI assistant.\n"
            "Answer the user's question clearly using the provided podcast transcripts and conversation history.\n"
            "When citing facts, include timestamps in brackets like [at 12.5s] if available.\n"
            "If the answer is not in the transcripts or conversation, say 'I don't have enough information to answer that.'"
        )

        if context:
            system_instruction += f"\n\nPODCAST TRANSCRIPTS:\n{context}"

        # Combine system prompt with full conversation history
        full_prompt = [SystemMessage(content=system_instruction)] + list(messages)

        response = self.engine.llm.invoke(full_prompt)
        return {"messages": [AIMessage(content=response.content)]}

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
        }

        final_state = self.app.invoke(inputs, config=config)
        return final_state["messages"][-1].content
