import os
import pickle
from typing import List, Optional, Dict, Any
import chromadb
from chromadb.utils import embedding_functions
from rank_bm25 import BM25Okapi
from app.models.schemas import Chunk


class ChromaStore:
    def __init__(self, persist_dir: str, model_name: str = "all-MiniLM-L6-v2"):
        os.makedirs(persist_dir, exist_ok=True)

        # PersistentClient is the standard ChromaDB client
        self.client = chromadb.PersistentClient(path=persist_dir)

        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=model_name
        )

        self.collection = self.client.get_or_create_collection(
            name="podcast_chunks",
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, chunks: List[Chunk]) -> None:
        if not chunks:
            return

        ids = [c.chunk_id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {
                "episode_id": str(c.episode_id),
                "podcast_name": str(c.podcast_name),
                "start_time": float(c.start_time),
                "end_time": float(c.end_time),
                "speakers": ", ".join(c.speakers),
            }
            for c in chunks
        ]

        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

    def search(
        self,
        query: str,
        top_k: int = 20,
        where_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        # If collection is empty, return empty list
        if self.collection.count() == 0:
            return []

        # Ensure n_results does not exceed total count in collection
        n_results = min(top_k, self.collection.count())
        if n_results <= 0:
            return []

        query_kwargs = {
            "query_texts": [query],
            "n_results": n_results,
        }
        if where_filter:
            query_kwargs["where"] = where_filter

        results = self.collection.query(**query_kwargs)

        formatted_results = []

        if not results or not results["ids"] or not results["ids"][0]:
            return formatted_results

        ids = results["ids"][0]
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = (
            results["distances"][0]
            if "distances" in results and results["distances"]
            else [0.0] * len(ids)
        )

        for chunk_id, doc, meta, dist in zip(ids, documents, metadatas, distances):
            speakers_list = [
                s.strip() for s in meta.get("speakers", "").split(",") if s.strip()
            ]
            formatted_results.append({
                "chunk_id": chunk_id,
                "text": doc,
                "episode_id": meta.get("episode_id", "1"),
                "podcast_name": meta.get("podcast_name", "Unknown"),
                "start_time": meta.get("start_time", -1.0),
                "end_time": meta.get("end_time", -1.0),
                "speakers": speakers_list,
                "score": 1.0 - dist,
            })
        return formatted_results


class BM25Store:
    def __init__(self, persist_path: str):
        self.persist_path = persist_path
        self.chunks: List[Dict[str, Any]] = []
        self.tokenized_corpus: List[List[str]] = []
        self.bm25: Optional[BM25Okapi] = None

    def tokenize(self, text: str) -> List[str]:
        return text.lower().split()

    def add_chunks(self, chunks: List[Chunk]) -> None:
        if not chunks:
            return

        for chunk in chunks:
            self.chunks.append({
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "episode_id": str(chunk.episode_id),
                "podcast_name": chunk.podcast_name,
                "start_time": chunk.start_time,
                "end_time": chunk.end_time,
                "speakers": chunk.speakers,
            })

            self.tokenized_corpus.append(self.tokenize(chunk.text))

        self.bm25 = BM25Okapi(self.tokenized_corpus)

    def search(self, query: str, top_k: int = 20) -> List[Dict[str, Any]]:
        if not self.bm25 or not self.chunks:
            return []

        tokenized_query = self.tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        top_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                result = self.chunks[idx].copy()
                result["score"] = float(scores[idx])
                results.append(result)

        return results

    def save(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.persist_path)), exist_ok=True)
        data = {
            "chunks": self.chunks,
            "tokenized_corpus": self.tokenized_corpus,
        }
        with open(self.persist_path, "wb") as f:
            pickle.dump(data, f)

    def load(self) -> None:
        if not os.path.exists(self.persist_path):
            return

        with open(self.persist_path, "rb") as f:
            data = pickle.load(f)

        self.chunks = data.get("chunks", [])
        self.tokenized_corpus = data.get("tokenized_corpus", [])

        if self.tokenized_corpus:
            self.bm25 = BM25Okapi(self.tokenized_corpus)
