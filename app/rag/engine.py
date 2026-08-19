import os
from typing import Optional, Any, Dict, Union, List
from groq import Groq

from app.config import get_settings
from app.rag.parser import TranscriptParser
from app.rag.chunker import PodcastChunker
from app.rag.store import ChromaStore, BM25Store
from app.rag.retriever import HybridRetriever
from app.models.schemas import Chunk


class RAGEngine:
    def __init__(self, persist_dir: str = "./data"):
        self.settings = get_settings()
        self.persist_dir = persist_dir

        # Initialize Groq client with settings or env fallback
        api_key = os.getenv("GROQ_API_KEY") or self.settings.GROQ_API_KEY
        self.llm_client = Groq(api_key=api_key) if api_key else None

        self.parser = TranscriptParser()
        self.chunker = PodcastChunker(
            chunk_size=self.settings.RAG_CHUNK_SIZE,
            chunk_overlap=self.settings.RAG_CHUNK_OVERLAP,
        )

        self.chroma_store = ChromaStore(
            persist_dir=persist_dir,
            model_name=self.settings.EMBEDDING_MODEL_NAME,
        )
        self.bm25_store = BM25Store(
            persist_path=os.path.join(persist_dir, "bm25.pkl")
        )

        # Load BM25 from disk if present
        self.bm25_store.load()

        self.retriever = HybridRetriever(
            chroma_store=self.chroma_store,
            bm25_store=self.bm25_store,
            reranker_model_name=self.settings.RERANKER_MODEL_NAME,
        )

    def ingest_podcast(
        self,
        file_path: str,
        podcast_name: str = "Unknown Podcast",
        episode_id: Union[int, str] = 1,
    ) -> int:
        print(f"Ingesting {file_path}...")

        segments = self.parser.parse_file(file_path)
        chunks: List[Chunk] = self.chunker.chunk_segments(
            segments,
            podcast_name=podcast_name,
            episode_id=episode_id,
        )

        if not chunks:
            print(f"No chunks extracted from {file_path}")
            return 0

        self.chroma_store.add_chunks(chunks)
        self.bm25_store.add_chunks(chunks)
        self.bm25_store.save()

        print(f"Successfully ingested {len(chunks)} chunks from {podcast_name} (Episode {episode_id}).")
        return len(chunks)

    def ask_question(
        self,
        query: str,
        where_filter: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None,
        top_n: Optional[int] = None,
    ) -> str:
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

        if not self.llm_client:
            # If no API key is configured yet, dynamically check env again
            api_key = os.getenv("GROQ_API_KEY")
            if api_key:
                self.llm_client = Groq(api_key=api_key)
            else:
                return (
                    "Error: GROQ_API_KEY environment variable is not set. "
                    "Please set your GROQ_API_KEY in your .env file or environment."
                )

        try:
            response = self.llm_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
                temperature=0.0,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error communicating with Groq LLM: {str(e)}"