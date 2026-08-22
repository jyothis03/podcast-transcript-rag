import os
import uuid
from typing import List, Optional, Dict, Any
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer
from fastembed import SparseTextEmbedding

from app.models.schemas import Chunk


class QdrantStore:
    """
    Unified vector database supporting both Dense Vector Search (SentenceTransformers)
    and Sparse BM25 Keyword Search (FastEmbed) inside a single Qdrant collection.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        path: Optional[str] = "./data/qdrant_db",
        collection_name: str = "podcast_transcripts",
        dense_model_name: str = "all-MiniLM-L6-v2",
    ):
        self.collection_name = collection_name

        # 1. Initialize Qdrant Client (Cloud URL or Local Disk)
        if url:
            self.client = QdrantClient(url=url, api_key=api_key)
        else:
            os.makedirs(path, exist_ok=True)
            self.client = QdrantClient(path=path)

        # 2. Initialize Dense & Sparse Embedders
        self.dense_model = SentenceTransformer(dense_model_name)
        self.sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")

        # 3. Create Collection with Named Vector configurations if it doesn't exist
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense": models.VectorParams(
                        size=384,
                        distance=models.Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    "bm25": models.SparseVectorParams(
                        index=models.SparseIndexParams(on_disk=False)
                    )
                },
            )

    def add_chunks(self, chunks: List[Chunk]) -> None:
        if not chunks:
            return

        texts = [c.text for c in chunks]

        # Generate 384-dim Dense Embeddings
        dense_vectors = self.dense_model.encode(texts).tolist()

        # Generate BM25 Sparse Embeddings
        sparse_vectors = list(self.sparse_model.embed(texts))

        points = []
        for chunk, dense_vec, sparse_vec in zip(chunks, dense_vectors, sparse_vectors):
            # Deterministic UUID from chunk_id
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id))

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector={
                        "dense": dense_vec,
                        "bm25": models.SparseVector(
                            indices=sparse_vec.indices.tolist(),
                            values=sparse_vec.values.tolist(),
                        ),
                    },
                    payload={
                        "chunk_id": chunk.chunk_id,
                        "text": chunk.text,
                        "episode_id": str(chunk.episode_id),
                        "podcast_name": str(chunk.podcast_name),
                        "start_time": float(chunk.start_time),
                        "end_time": float(chunk.end_time),
                        "speakers": chunk.speakers,
                    },
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

    def dense_search(
        self,
        query: str,
        top_k: int = 20,
        where_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        query_vector = self.dense_model.encode(query).tolist()

        qdrant_filter = None
        if where_filter and "podcast_name" in where_filter:
            qdrant_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="podcast_name",
                        match=models.MatchValue(value=where_filter["podcast_name"]),
                    )
                ]
            )

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            using="dense",
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
        ).points

        formatted = []
        for p in results:
            payload = p.payload or {}
            formatted.append({
                "chunk_id": payload.get("chunk_id", str(p.id)),
                "text": payload.get("text", ""),
                "episode_id": payload.get("episode_id", "1"),
                "podcast_name": payload.get("podcast_name", "Unknown"),
                "start_time": payload.get("start_time", -1.0),
                "end_time": payload.get("end_time", -1.0),
                "speakers": payload.get("speakers", []),
                "score": float(p.score),
            })
        return formatted

    def sparse_search(
        self,
        query: str,
        top_k: int = 20,
        where_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        sparse_query = list(self.sparse_model.embed([query]))[0]
        sparse_vec = models.SparseVector(
            indices=sparse_query.indices.tolist(),
            values=sparse_query.values.tolist(),
        )

        qdrant_filter = None
        if where_filter and "podcast_name" in where_filter:
            qdrant_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="podcast_name",
                        match=models.MatchValue(value=where_filter["podcast_name"]),
                    )
                ]
            )

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=sparse_vec,
            using="bm25",
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
        ).points

        formatted = []
        for p in results:
            payload = p.payload or {}
            formatted.append({
                "chunk_id": payload.get("chunk_id", str(p.id)),
                "text": payload.get("text", ""),
                "episode_id": payload.get("episode_id", "1"),
                "podcast_name": payload.get("podcast_name", "Unknown"),
                "start_time": payload.get("start_time", -1.0),
                "end_time": payload.get("end_time", -1.0),
                "speakers": payload.get("speakers", []),
                "score": float(p.score),
            })
        return formatted

    def get_podcasts(self) -> List[Dict[str, Any]]:
        """
        Returns summary of unique podcasts and their indexed chunk count.
        """
        try:
            results = self.client.scroll(
                collection_name=self.collection_name,
                limit=1000,
                with_payload=True,
                with_vectors=False,
            )[0]
            counts = {}
            for p in results:
                payload = p.payload or {}
                name = payload.get("podcast_name", "Unknown")
                counts[name] = counts.get(name, 0) + 1
            return [{"podcast_name": k, "chunk_count": v} for k, v in counts.items()]
        except Exception:
            return []
