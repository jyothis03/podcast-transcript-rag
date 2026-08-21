import os
import sys
import uuid

from app.rag.engine import RAGEngine
from app.rag.graph import PodcastRAGGraph


def main():
    print("==================================================")
    print("      🎙️ PODCAST RAG INTERACTIVE CLI CHAT        ")
    print("==================================================")
    print("Initializing Engine, Qdrant Vector Store & LangGraph...")

    engine = RAGEngine(persist_dir="./data")
    graph = PodcastRAGGraph(engine=engine)

    # Ingest default sample podcast if available
    sample_srt = "data/sample_podcast.srt"
    if os.path.exists(sample_srt):
        engine.ingest_podcast(sample_srt, podcast_name="Lex Fridman Podcast", episode_id=1)

    thread_id = str(uuid.uuid4())[:8]
    print(f"\nSession initialized (thread_id: {thread_id}).")
    print("Type your question below (or 'exit' / 'quit' to end):\n")

    while True:
        try:
            user_input = input("You > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("\nGoodbye!")
                break

            response = graph.chat(query=user_input, thread_id=thread_id)
            print(f"\nAI > {response}\n")

        except (KeyboardInterrupt, EOFError):
            print("\nSession ended.")
            break
        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    main()
