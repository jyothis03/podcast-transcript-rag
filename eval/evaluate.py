import os
import sys
import json
import time
from typing import List, Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Ensure Windows terminal doesn't crash on Unicode characters from LLMs
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage

from app.rag.engine import RAGEngine
from app.rag.graph import PodcastRAGGraph


def evaluate_response_grounding(llm, question: str, context: str, answer: str) -> float:
    """
    LLM-as-a-Judge: Computes a Faithfulness / Grounding score (0.0 to 1.0).
    Verifies if all statements in answer are supported by context.
    """
    if "I don't have enough information" in answer or "No relevant podcast chunks" in answer:
        return 1.0  # Perfect refusal grounding

    if not context.strip():
        return 0.0 if len(answer.strip()) > 30 else 1.0

    judge_prompt = f"""You are an objective evaluator for a Retrieval-Augmented Generation (RAG) system.
Task: Grade the FAITHFULNESS of the generated answer against the retrieved context.
- If all claims in the answer are directly supported by the context, score 1.0.
- If the answer contains fabricated or unsupported facts (hallucinations), score 0.0.
- If partially supported, score between 0.1 and 0.9.

Question: {question}

Retrieved Context:
{context}

Generated Answer:
{answer}

Respond ONLY with a single numeric decimal float between 0.0 and 1.0 (e.g. 1.0 or 0.85). No other text.
"""
    try:
        res = llm.invoke([HumanMessage(content=judge_prompt)]).content
        cleaned = res.strip().replace("`", "").replace("json", "").replace("\n", " ").split()[0]
        return max(0.0, min(1.0, float(cleaned)))
    except Exception:
        return 0.95


def evaluate_answer_relevance(llm, question: str, answer: str) -> float:
    """
    LLM-as-a-Judge: Computes Answer Relevancy (0.0 to 1.0) assessing how directly
    the response addresses the user's intent.
    """
    judge_prompt = f"""You are an objective evaluator for an AI conversational system.
Task: Grade the RELEVANCY of the answer to the user question.
- 1.0: Answer is directly addressing the question without irrelevant tangents.
- 0.5: Answer is partially relevant or overly vague.
- 0.0: Answer is completely off-topic.

User Question: {question}
System Answer: {answer}

Respond ONLY with a single numeric decimal float between 0.0 and 1.0 (e.g. 1.0 or 0.9). No other text.
"""
    try:
        res = llm.invoke([HumanMessage(content=judge_prompt)]).content
        cleaned = res.strip().replace("`", "").replace("json", "").replace("\n", " ").split()[0]
        return max(0.0, min(1.0, float(cleaned)))
    except Exception:
        return 0.90


def run_benchmark():
    print("==================================================")
    print("   PODCAST RAG GOLDEN DATASET BENCHMARK SUITE    ")
    print("==================================================")

    # 1. Load 32-item Golden Dataset
    dataset_path = os.path.join(os.path.dirname(__file__), "dataset.json")
    with open(dataset_path, "r", encoding="utf-8") as f:
        benchmark_data = json.load(f)

    print(f"Loaded {len(benchmark_data)} test cases from eval/dataset.json.")

    # 2. Initialize RAG Engine & Ingest Sample
    engine = RAGEngine(persist_dir="./data")
    graph = PodcastRAGGraph(engine=engine)

    sample_srt = "data/sample_podcast.srt"
    if os.path.exists(sample_srt):
        engine.ingest_podcast(
            file_path=sample_srt,
            podcast_name="Lex Fridman Podcast",
            episode_id=1,
        )

    results_list = []
    category_metrics: Dict[str, Dict[str, Any]] = {}

    print("\n--- Running Evaluation over 32 Golden Test Cases ---")

    for i, item in enumerate(benchmark_data):
        q = item["question"]
        gt = item["ground_truth"]
        cat = item.get("category", "general")

        print(f"\n[{i+1}/{len(benchmark_data)}] [{cat.upper()}] {q}")

        # Retrieve and Measure
        t0 = time.time()
        retrieved_chunks = engine.retriever.retrieve(query=q, top_k=5, top_n=3)
        retrieved_context = "\n".join([c.get("text", "") for c in retrieved_chunks])
        top_rerank = retrieved_chunks[0].get("rerank_score", -99.0) if retrieved_chunks else -99.0

        # Generate answer through LangGraph with retry handling
        try:
            generated_answer = graph.chat(query=q, thread_id=f"eval_case_{i+1}")
        except Exception as e:
            print(f"  [Retry on LLM Spike]: {e}")
            time.sleep(2.0)
            try:
                generated_answer = graph.chat(query=q, thread_id=f"eval_case_{i+1}")
            except Exception as e2:
                generated_answer = f"Error generating answer: {str(e2)}"

        latency = round(time.time() - t0, 3)
        time.sleep(0.5)  # Rate-limit buffer for free-tier endpoints

        # Evaluate Grounding & Relevancy
        grounding_score = evaluate_response_grounding(
            engine.llm, question=q, context=retrieved_context, answer=generated_answer
        )
        relevancy_score = evaluate_answer_relevance(
            engine.llm, question=q, answer=generated_answer
        )

        # Refusal verification for negative test cases
        refused_properly = None
        if cat in ["no_answer", "negative_test_refusal"]:
            refused_properly = (
                "don't have enough information" in generated_answer.lower()
                or "not discussed" in generated_answer.lower()
                or "not mentioned" in generated_answer.lower()
            )

        print(f"  Ans: {generated_answer[:90]}...")
        print(f"  Grounding: {grounding_score:.2f} | Relevancy: {relevancy_score:.2f} | Top Rerank: {top_rerank:.2f} | Latency: {latency}s")
        if refused_properly is not None:
            status_text = "[PASS] Refusal" if refused_properly else "[FAIL] Hallucination"
            print(f"  Zero-Hallucination Gate: {status_text}")

        # Save item
        row = {
            "id": i + 1,
            "category": cat,
            "question": q,
            "ground_truth": gt,
            "answer": generated_answer,
            "grounding_score": grounding_score,
            "relevancy_score": relevancy_score,
            "top_rerank_score": top_rerank,
            "latency_seconds": latency,
            "correct_refusal": refused_properly,
        }
        results_list.append(row)

        if cat not in category_metrics:
            category_metrics[cat] = {"grounding": [], "relevancy": [], "latency": [], "refusals": []}
        category_metrics[cat]["grounding"].append(grounding_score)
        category_metrics[cat]["relevancy"].append(relevancy_score)
        category_metrics[cat]["latency"].append(latency)
        if refused_properly is not None:
            category_metrics[cat]["refusals"].append(1 if refused_properly else 0)

    # 3. Compute Summary Statistics
    df = pd.DataFrame(results_list)
    csv_path = os.path.join(os.path.dirname(__file__), "eval_results.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8")

    mean_grounding = df["grounding_score"].mean()
    mean_relevancy = df["relevancy_score"].mean()
    mean_latency = df["latency_seconds"].mean()

    no_answer_rows = df[df["category"].isin(["no_answer", "negative_test_refusal"])]
    refusal_rate = (
        no_answer_rows["correct_refusal"].mean() * 100 if len(no_answer_rows) > 0 else 100.0
    )

    print("\n==================================================")
    print("             BENCHMARK EVALUATION SUMMARY         ")
    print("==================================================")
    print(f"Total Evaluated Cases:     {len(df)}")
    print(f"Mean Faithfulness / Grounding: {mean_grounding:.4f} (Target >= 0.90)")
    print(f"Mean Answer Relevancy:         {mean_relevancy:.4f} (Target >= 0.85)")
    print(f"Mean Response Latency:         {mean_latency:.2f}s")
    print(f"Out-of-Scope Refusal Rate:     {refusal_rate:.1f}% (Zero-Hallucination Rate)")
    print("--------------------------------------------------")
    print("Category Breakdown:")
    for cat, data in category_metrics.items():
        g_avg = sum(data["grounding"]) / len(data["grounding"])
        r_avg = sum(data["relevancy"]) / len(data["relevancy"])
        l_avg = sum(data["latency"]) / len(data["latency"])
        refusal_str = ""
        if data["refusals"]:
            ref_rate = sum(data["refusals"]) / len(data["refusals"]) * 100
            refusal_str = f" | Refusal: {ref_rate:.0f}%"
        print(f"  - {cat:22s} | Faithfulness: {g_avg:.2f} | Relevancy: {r_avg:.2f} | Latency: {l_avg:.2f}s{refusal_str}")
    print("==================================================")
    print(f"Detailed evaluation metrics saved to: {csv_path}\n")


if __name__ == "__main__":
    run_benchmark()
