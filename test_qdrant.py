from app.rag.engine import RAGEngine

def main():
    print("=== Testing Qdrant Pipeline ===")
    engine = RAGEngine(persist_dir="./data")
    
    # 1. Ingest
    chunks_count = engine.ingest_podcast(
        file_path="data/sample_podcast.srt",
        podcast_name="Lex Fridman Podcast",
        episode_id=1
    )
    print(f"Chunks indexed in Qdrant: {chunks_count}")
    assert chunks_count > 0, "No chunks indexed!"

    # 2. Retrieve (Dense + Sparse + RRF + Cross-Encoder)
    query = "What is the key challenge with AI alignment and safety?"
    results = engine.retriever.retrieve(query=query, top_k=5, top_n=2)
    print(f"\nRetrieved {len(results)} chunks from Qdrant:")
    for i, r in enumerate(results):
        rerank = r.get("rerank_score", 0.0)
        print(f" [{i+1}] (Rerank: {rerank:.4f}) {r['text'][:80]}...")

    assert len(results) > 0, "Retrieval returned 0 chunks!"
    print("\n>>> SUCCESS: Qdrant Hybrid Storage Fully Verified! <<<")

if __name__ == "__main__":
    main()
