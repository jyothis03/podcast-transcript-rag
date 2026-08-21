import os
from typing import Optional, Any, Dict, Union, List

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from app.config import get_settings
from app.rag.parser import TranscriptParser
from app.rag.chunker import PodcastChunker
from app.rag.store import QdrantStore
from app.rag.retriever import HybridRetriever
from app.rag.guardrails import InputGuardrail
from app.models.schemas import Chunk


class RAGEngine:
    def __init__(self, persist_dir: str = "./data"):
        self.settings = get_settings()
        self.persist_dir = persist_dir

        self.parser = TranscriptParser()
        self.guardrail = InputGuardrail()
        self.chunker = PodcastChunker(
            chunk_size=self.settings.RAG_CHUNK_SIZE,
            chunk_overlap=self.settings.RAG_CHUNK_OVERLAP,
        )

        # 1. Initialize unified Qdrant Storage
        self.qdrant_store = QdrantStore(
            url=self.settings.QDRANT_URL,
            api_key=self.settings.QDRANT_API_KEY,
            path=os.path.join(persist_dir, "qdrant_db"),
            collection_name=self.settings.QDRANT_COLLECTION_NAME,
            dense_model_name=self.settings.EMBEDDING_MODEL_NAME,
        )

        self.retriever = HybridRetriever(
            qdrant_store=self.qdrant_store,
            reranker_model_name=self.settings.RERANKER_MODEL_NAME,
        )

        # 2. Setup Multi-Provider LangChain LLM with automatic failover
        self._setup_llm()

    def _setup_llm(self) -> None:
        gemini_key = os.getenv("GEMINI_API_KEY") or self.settings.GEMINI_API_KEY
        groq_key = os.getenv("GROQ_API_KEY") or self.settings.GROQ_API_KEY

        fallbacks = []

        # Groq Backup LLM
        groq_llm = None
        if groq_key:
            groq_llm = ChatGroq(
                model=self.settings.GROQ_MODEL_NAME,
                groq_api_key=groq_key,
                temperature=0.0,
            )
            fallbacks.append(groq_llm)

        # Gemini Primary LLM
        if gemini_key:
            gemini_llm = ChatGoogleGenerativeAI(
                model=self.settings.GEMINI_MODEL_NAME,
                google_api_key=gemini_key,
                max_retries=2,
                temperature=0.0,
            )
            # If Groq is available, chain it as an automatic fallback!
            if fallbacks:
                self.llm = gemini_llm.with_fallbacks(fallbacks)
            else:
                self.llm = gemini_llm
        elif groq_llm:
            # If only Groq key is present, use Groq directly
            self.llm = groq_llm
        else:
            self.llm = None

    def ingest_podcast(
        self,
        file_path: str,
        podcast_name: str = "Unknown Podcast",
        episode_id: Union[int, str] = 1,
    ) -> int:
        print(f"Ingesting {file_path} into Qdrant...")

        segments = self.parser.parse_file(file_path)
        chunks: List[Chunk] = self.chunker.chunk_segments(
            segments,
            podcast_name=podcast_name,
            episode_id=episode_id,
        )

        if not chunks:
            print(f"No chunks extracted from {file_path}")
            return 0

        self.qdrant_store.add_chunks(chunks)
        print(
            f"Successfully ingested {len(chunks)} chunks from '{podcast_name}' (Ep: {episode_id}) into Qdrant."
        )
        return len(chunks)

    def ask_question(
        self,
        query: str,
        where_filter: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None,
        top_n: Optional[int] = None,
    ) -> str:
        # Pre-retrieval Input Guardrail check
        is_safe, refusal_reason = self.guardrail.validate(query)
        if not is_safe:
            return refusal_reason or "Security Alert: Prompt injection pattern detected."

        k = top_k or self.settings.RAG_TOP_K
        n = top_n or self.settings.RAG_TOP_N

        context = self.retriever.retrieve(
            query=query,
            top_k=k,
            top_n=n,
            where_filter=where_filter,
        )

        if not context:
            return "No relevant podcast chunks found for your question."

        formatted_chunks = []
        for i, chunk in enumerate(context):
            podcast = chunk.get("podcast_name", "Unknown")
            episode = chunk.get("episode_id", "Unknown")
            content = chunk.get("text", "")
            start_t = chunk.get("start_time", -1.0)
            time_str = f" [at {start_t:.1f}s]" if start_t >= 0 else ""

            formatted = f"--- Chunk {i+1} (Podcast: {podcast}, Ep: {episode}{time_str}) ---\n{content}\n"
            formatted_chunks.append(formatted)

        context_string = "\n".join(formatted_chunks)

        system_prompt = f"""You are a knowledgeable and helpful podcast AI assistant.
Use the following podcast transcripts to answer the user's question accurately.
If you cannot answer the question using the provided transcripts, say "I don't have enough information in the transcripts to answer that." Do not guess or hallucinate facts outside the provided context.

PODCAST TRANSCRIPTS:
{context_string}
"""

        # Re-check LLM setup dynamically if env keys were updated
        if not self.llm:
            self._setup_llm()

        if not self.llm:
            return (
                "Error: No LLM API key configured. Please set GEMINI_API_KEY or GROQ_API_KEY in your .env file."
            )

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=query),
            ]
            response = self.llm.invoke(messages)
            content = response.content
            if isinstance(content, list):
                content = "".join(
                    p.get("text", "") if isinstance(p, dict) else str(p) for p in content
                )
            return str(content)
        except Exception as e:
            return f"Error communicating with LLM: {str(e)}"