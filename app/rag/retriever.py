from sentence_transformers import CrossEncoder
from app.rag.store import ChromaStore, BM25Store
from typing import Optional, List, Dict, Any

class HybridRetriever:

    def __init__(
        self,
        chroma_store: ChromaStore,
        bm25_store: BM25Store,
        reranker_model_name:str = 'cross-encoder/ms-marco-MiniLM-L-6-v2'     
     ):
        self.chroma_store = chroma_store
        self.bm25_store = bm25_store
        self.reranker = CrossEncoder(reranker_model_name)

    def reciprocal_rank_fusion(
        self,
        dense_results : list[Dict[str, Any]],
        sparse_results : list[Dict[str, Any]],
        k:int = 60
    ) -> list[Dict[str, Any]]:

        """
        Merge results using Reciprocal Rank Fusion (RRF).
        Formula: score = 1 / (k + rank)
        """

        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, Dict[str, Any]] = {}

        for rank_idx, doc in enumerate(dense_results):
            chunk_id = doc["chunk_id"]
            rank = rank_idx + 1  
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id,0.0) + (1.0/(k+rank))
            chunk_map[chunk_id] = doc

        for rank_idx, doc in enumerate(sparse_results):
            chunk_id = doc["chunk_id"]
            rank = rank_idx + 1
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + (1.0 / (k + rank))
            if chunk_id not in chunk_map:
                chunk_map[chunk_id] = doc

        sorted_chunk_ids = sorted(
            rrf_scores.keys(),
            key=lambda cid:rrf_scores[cid],
            reverse=True,
        )
        
        candidates=[]
        for cid in sorted_chunk_ids:
            chunk_data = chunk_map[cid].copy()
            chunk_data["rrf_score"] = rrf_scores[cid]
            candidates.append(chunk_data)

        return candidates

    def _rerank(
        self,
        query:str,
        candidates: List[Dict[str, Any]],
        top_n: int = 5
        )->List[Dict[str, Any]]:

        if not candidates:
            return []
        
        pairs = [[query,canditates["text"]] for canditates in candidates]
        
        scores = self.reranker.predict(pairs)

        for candidate, score in zip(candidates, scores):
            candidate["rerank_score"] = float(score)

        reranked = sorted(candidates, key = lambda c: c["rerank_score"], reverse=True)

        return reranked[:top_n]

    def retrieve(
        self,
        query: str,
        top_k: int = 20,
        top_n: int = 5,
        where_filter: Optional[Dict[str,Any]] = None
    ) -> List[Dict[str, Any]]:

        dense_results = self.chroma_store.search(
            query=query,
            top_k=top_k,
            where_filter=where_filter,
        )
    
        sparse_results = self.bm25_store.search(
            query=query,
            top_k=top_k,
        )

        candidates = self.reciprocal_rank_fusion(
            dense_results,
            sparse_results,
        )

        final_chunks = self._rerank(
            query=query,
            candidates=candidates,
            top_n=top_n,
        )
        return final_chunks
