import os
from groq import Groq
from typing import Optional, Any, Dict

from app.rag.parser import TranscriptParser
from app.rag.chunker import PodcastChunker
from app.rag.store import ChromaStore, BM25Store
from app.rag.retriever import HybridRetriever

class RAGEngine:
    def __init__(self,persist_dir: str = "./data"):
        
        self.llm_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

        self.parser = TranscriptParser()
        self.chunker = PodcastChunker()

        self.chroma_store = ChromaStore(persist_dir=persist_dir)
        self.bm25_store = BM25Store(persist_path=os.path.join(persist_dir, "bm25.pkl"))

        self.bm25_store.load()
        
        self.retriever = HybridRetriever(
            chroma_store=self.chroma_store,
            bm25_store=self.bm25_store
        )

    def ingest_podcast(
        self, file_path: str,
        podcast_name: str,
        episode_id: str,
        )->None:

        print(f"Ingesting {file_path}...")

        segments = self.parser.parse_file(file_path)

        chunks = self.chunker.chunk_segments(
            segments, 
            podcast_name=podcast_name, 
            episode_id=episode_id
        )

        self.chroma_store.add_chunks(chunks)

        self.bm25_store.add_chunks(chunks)
        self.bm25_store.save()

        print(f"Ingested {len(chunks)} chunks.")
    
    def ask_question(self, query:str,where_filter:Optional[Dict[str,Any]] = None)-> str:

        context = self.retriever.retrieve(
            query=query,
            where_filter=where_filter,
        )

        if not context: return "No relevant chunks found"
        
        formatted_chunks= []

        for i, chunk in enumerate(context):
          
            podcast = chunk.get("podcast_name", "Unknown")
            episode = chunk.get("episode_id", "Unknown")
            content = chunk.get("text", "")

            formatted = f"--- Chunk {i+1} (Source: {podcast}) ---\n{text}\n"
            formatted_chunks.append(formatted)

        context_string = "\n".join(formatted_chunks)

        system_prompt = f"""
        You are a helpful podcast assistant. 
        Use the following podcast transcripts to answer the user's question. 
        If you cannot answer the question using the provided transcripts, say "I don't have enough information to answer that." Do not guess.
        TRANSCRIPTS:
        {context_string}
        """
        response = self.llm_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.0,
        )
        return response.choices[0].message.content









        