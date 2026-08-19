import os
import sys

from app.rag.engine import RAGEngine
from app.models.schemas import IngestRequest, QueryRequest

def main():
    print("=== 1. Initializing RAGEngine ===")
    persist_dir = "./test_data"
    engine = RAGEngine(persist_dir=persist_dir)

    print("\n=== 2. Ingesting Sample SRT Transcript ===")
    sample_file = "data/sample_podcast.srt"
    num_chunks = engine.ingest_podcast(
        file_path=sample_file,
        podcast_name="Lex Fridman Podcast",
        episode_id=1
    )
    print(f"Chunks created & indexed: {num_chunks}")
    assert num_chunks > 0, "No chunks were indexed!"

    print("\n=== 3. Testing Hybrid Retrieval (Dense + BM25 + RRF + Cross-Encoder) ===")
    query = "What is the key challenge with AI alignment and safety?"
    results = engine.retriever.retrieve(query=query, top_k=5, top_n=2)
    print(f"Retrieved {len(results)} chunks:")
    for i, r in enumerate(results):
        score = r.get("rerank_score", 0.0)
        print(f" [{i+1}] (Rerank Score: {score:.4f}) {r['text']}")

    assert len(results) > 0, "Retriever returned 0 results!"

    print("\n=== 4. Testing End-to-End ask_question ===")
    answer = engine.ask_question(query=query)
    print(f"Answer Output:\n{answer}")

    print("\n>>> ALL TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    main()
