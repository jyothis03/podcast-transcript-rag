from typing import Optional, List, Dict, Any
from sentence_transformers import CrossEncoder
from app.rag.store import QdrantStore


class HybridRetriever:
    def __init__(
        self,
        qdrant_store: QdrantStore,
        reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    ):
        self.qdrant_store = qdrant_store
        self.reranker = CrossEncoder(reranker_model_name)

    def reciprocal_rank_fusion(
        self,
        dense_results: List[Dict[str, Any]],
        sparse_results: List[Dict[str, Any]],
        k: int = 60,
    ) -> List[Dict[str, Any]]:
        """
        Merge results using Reciprocal Rank Fusion (RRF).
        Formula: score = 1 / (k + rank)
        """
        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, Dict[str, Any]] = {}

        for rank_idx, doc in enumerate(dense_results):
            chunk_id = doc["chunk_id"]
            rank = rank_idx + 1
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + (1.0 / (k + rank))
            chunk_map[chunk_id] = doc

        for rank_idx, doc in enumerate(sparse_results):
            chunk_id = doc["chunk_id"]
            rank = rank_idx + 1
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + (1.0 / (k + rank))
            if chunk_id not in chunk_map:
                chunk_map[chunk_id] = doc

        sorted_chunk_ids = sorted(
            rrf_scores.keys(),
            key=lambda cid: rrf_scores[cid],
            reverse=True,
        )

        candidates = []
        for cid in sorted_chunk_ids:
            chunk_data = chunk_map[cid].copy()
            chunk_data["rrf_score"] = rrf_scores[cid]
            candidates.append(chunk_data)

        return candidates

    def _rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_n: int = 5,
    ) -> List[Dict[str, Any]]:
        if not candidates:
            return []

        pairs = [[query, candidate["text"]] for candidate in candidates]

        scores = self.reranker.predict(pairs)

        for candidate, score in zip(candidates, scores):
            candidate["rerank_score"] = float(score)

        reranked = sorted(
            candidates, key=lambda c: c["rerank_score"], reverse=True
        )

        return reranked[:top_n]

    def retrieve(
        self,
        query: str,
        top_k: int = 20,
        top_n: int = 5,
        where_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        # 1. Fetch Dense Vector candidates from Qdrant
        dense_results = self.qdrant_store.dense_search(
            query=query,
            top_k=top_k,
            where_filter=where_filter,
        )

        # 2. Fetch Sparse Keyword candidates from Qdrant
        sparse_results = self.qdrant_store.sparse_search(
            query=query,
            top_k=top_k,
            where_filter=where_filter,
        )

        # 3. Fuse dense and sparse candidates using RRF
        candidates = self.reciprocal_rank_fusion(
            dense_results,
            sparse_results,
        )

        # 4. Neural rerank using Cross-Encoder
        final_chunks = self._rerank(
            query=query,
            candidates=candidates,
            top_n=top_n,
        )
        return final_chunks
