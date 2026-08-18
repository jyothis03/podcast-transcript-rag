import chromadb
from chromadb.utils import embedding_functions
from app.models.schemas import Chunk
from typing import List, Optional, Dict, Any
import os, pickle

class ChromaStore:
    
    def __init__(self,persist_dir:str, model_name:str = "all-MiniLM-L6-v2"):
        os.makedirs(persist_dir,exist_ok=True)
        
        self.client = chromadb.PersistClient(path=persist_dir)

        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)

        self.collection = self.client.get_or_create_collection(
            name = "podcast_chunks",
            embedding_function = self.embedding_function,
            metadata={"hnsw:space": "cosine"}
        )

    def add_chunks(self, chunks: List[Chunk]) -> None:

        ids = [c.chunk_id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
        {
            "episode_id": c.episode_id,
            "podcast_name": c.podcast_name,
            "start_time": c.start_time,
            "end_time": c.end_time,
            "speakers": ", ".join(c.speakers), 
        }
        for c in chunks
         ]

        self.collection.add(
            ids = ids,
            documents = documents,
            metadatas = metadatas
        )

    def search(
                self,
                query: str,
                top_k: int = 20,
                where_filter: Optional[Dict[str, Any]] = None
            ) -> List[Dict[str, Any]]:
                
        results = self.collection.query(
        query_texts=[query],
        n_results=top_k,
        where=where_filter)
    
        formatted_results = []

        if not results or not results["ids"] or not results["ids"][0]:
            return formatted_results

        ids = results["ids"][0]
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0] if "distances" in results and results["distances"] else [0.0] * len(ids)
            
        for chunk_id, doc, meta, dist in zip(ids, documents, metadatas, distances):
            speakers_list = [s.strip() for s in meta.get("speakers", "").split(",") if s.strip()]
            formatted_results.append({
                "chunk_id": chunk_id,
                "text": doc,
                "episode_id": meta["episode_id"],
                "podcast_name": meta["podcast_name"],
                "start_time": meta["start_time"],
                "end_time": meta["end_time"],
                "speakers": speakers_list,
                "score": 1.0 - dist,
            })
        return formatted_results

class BM25Store:
    
    def __init__(self, persist_path:str):

        self.persist_path = persist_path
        self.chunks: List[Dict[str, Any]] = []
        self.tokenized_corpus: List[List[str]] = []
        self.bm25: Optional[BM25Okapi] = None
        
    def tokenize(self, text: str) -> List[str]:
        return text.lower().split()

    def add_chunks(self, chunks: List[Chunk]) -> None:
        for chunk in chunks:
        
            self.chunks.append({
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "episode_id": chunk.episode_id,
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

        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                result = self.chunks[idx].copy()
                result["score"] = float(scores[idx])
                results.append(result)

        return results
    
    def save(self)->None:
        
        data= {
            "chunks": self.chunks,
            "tokenized_corpus": self.tokenized_corpus,
        }
        with open(self.persist_path, "wb") as f:
            pickle.dump(data, f)

    def load(self)-> None:
        if not os.path.exists(self.persist_path):
            return

        with open(self.persist_path, "rb") as f:
            data = pickle.load(f)

        self.chunks = data.get("chunks", [])
        self.tokenized_corpus = data.get("tokenized_corpus", [])

        if self.tokenized_corpus:
            self.bm25 = BM25Okapi(self.tokenized_corpus)
        

        
        

