"""
Run Evaluations: Test smart retriever pipeline against ground truth.
Uses 3-layer RAG evaluation (Retrieval → Context → Generation).
"""

import json
import sys
import time
from typing import List
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from evals.ground_truth import load_ground_truth
from evals.evaluator import RAGEvaluator
from evals.feedback_loop import FeedbackLoop
from evals.config import RESULTS_DIR


def _llm_synthesize(query: str, chunks: List[str]) -> str:
    """Use Groq LLM to synthesize a proper answer from retrieved chunks."""
    import os
    from groq import Groq

    context = "\n\n".join(chunks[:8])
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    resp = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {"role": "system", "content": (
                "You are a financial analyst. Answer the question using ONLY the provided context. "
                "Include specific numbers, percentages, and dollar amounts from the context. "
                "If the context doesn't contain the answer, say so. Be concise and precise. "
                "Always cite which company and year the data comes from."
            )},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
        ],
        temperature=0.1,
        max_tokens=500,
    )
    return resp.choices[0].message.content


def run_retrieval(query: str) -> dict:
    """Run smart retriever and return structured results."""
    from agents.smart_retriever import smart_retrieve
    import logging
    logging.getLogger("agents.smart_retriever").setLevel(logging.WARNING)
    logging.getLogger("__main__").setLevel(logging.WARNING)

    t0 = time.time()
    result = smart_retrieve(query)
    latency = time.time() - t0

    # Collect doc_ids from text results
    doc_ids = list({r.get("doc_id", "") for r in result.text_results if r.get("doc_id")})
    chunks = [r["text"] for r in result.text_results if r.get("text")]

    # Build answer via LLM synthesis from top chunks
    top_chunks = chunks[:8]
    try:
        answer = _llm_synthesize(query, top_chunks)
    except Exception as e:
        answer = " ".join(top_chunks[:5])  # fallback to raw chunks

    return {
        "answer": answer,
        "doc_ids": doc_ids,
        "chunks": chunks,
        "latency": latency,
        "result": result,
    }


def run_evaluation_suite() -> dict:
    print("\n" + "=" * 80)
    print("🧪 RAG EVALUATION SUITE (3-Layer)")
    print("=" * 80)

    ground_truth_dataset = load_ground_truth()
    print(f"\n📋 {len(ground_truth_dataset)} ground truth examples loaded")

    evaluator = RAGEvaluator()
    feedback_loop = FeedbackLoop()
    results = []

    for i, gt in enumerate(ground_truth_dataset, 1):
        query = gt["query"]
        print(f"\n[{i}/{len(ground_truth_dataset)}] {query}")
        print(f"   Category: {gt['category']} | Difficulty: {gt.get('difficulty', '?')}")

        try:
            ret = run_retrieval(query)
        except Exception as e:
            print(f"   ❌ Retrieval error: {e}")
            results.append({"ground_truth_id": gt["id"], "error": str(e)})
            continue

        evaluation = evaluator.evaluate(
            query=query,
            answer=ret["answer"],
            retrieved_doc_ids=ret["doc_ids"],
            retrieved_chunks=ret["chunks"],
            ground_truth=gt,
            latency=ret["latency"],
        )

        # Log
        response = {"text": ret["answer"], "sources": ret["doc_ids"], "latency": ret["latency"]}
        feedback_loop.log_query(query, response, evaluation)

        # Print per-layer scores
        r = evaluation["layer1_retrieval"]
        c = evaluation["layer2_context"]
        g = evaluation["layer3_generation"]
        diag = evaluation["diagnosis"]

        print(f"   Retrieval  → Recall@k={r['recall_at_k']:.2f}  Precision@k={r['precision_at_k']:.2f}  MRR={r['mrr']:.2f}  nDCG={r['ndcg']:.2f}")
        print(f"   Context    → Recall={c['context_recall']:.2f}  Precision={c['context_precision']:.2f}  Relevance={c['context_relevance']:.2f}")
        print(f"   Generation → Faith={g['faithfulness']:.2f}  Relevancy={g['answer_relevancy']:.2f}  Correct={g['answer_correctness']:.2f}  SimSim={g['semantic_similarity']:.2f}")
        print(f"   Overall={evaluation['overall_score']:.3f}  Diagnosis={diag}  Latency={ret['latency']:.1f}s")

        results.append({"ground_truth_id": gt["id"], "query": query, "category": gt["category"], "evaluation": evaluation})

    # Summary
    stats = evaluator.get_statistics()
    analysis = feedback_loop.analyze_performance()
    report = feedback_loop.generate_improvement_report(analysis)

    print("\n" + "=" * 80)
    print("📊 EVALUATION SUMMARY")
    print("=" * 80)
    print(f"\n   Total: {stats['total_evaluations']}")
    print(f"   Overall Score: {stats['average_overall']:.3f}")
    print(f"\n   Layer 1 (Retrieval):")
    for m in ("recall_at_k", "precision_at_k", "mrr", "ndcg"):
        print(f"     {m:20s}: {stats['average_metrics'].get(m, 0):.3f}")
    print(f"   Layer 2 (Context):")
    for m in ("context_recall", "context_precision", "context_relevance"):
        print(f"     {m:20s}: {stats['average_metrics'].get(m, 0):.3f}")
    print(f"   Layer 3 (Generation):")
    for m in ("faithfulness", "answer_relevancy", "answer_correctness", "semantic_similarity"):
        print(f"     {m:20s}: {stats['average_metrics'].get(m, 0):.3f}")
    print(f"\n   Diagnoses: {stats.get('diagnoses', {})}")
    print(f"\n   By Category:")
    for cat, info in stats.get("by_category", {}).items():
        print(f"     {cat:25s}: avg={info['avg_score']:.3f} ({info['total']} queries)")

    print("\n" + report)

    # Save
    evaluator.save_logs()
    feedback_loop.save_performance_snapshot(analysis)

    results_file = RESULTS_DIR / f"eval_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, "w") as f:
        json.dump({"timestamp": datetime.now().isoformat(), "statistics": stats, "results": results}, f, indent=2)
    print(f"\n✅ Results saved: {results_file}")

    return {"statistics": stats, "results": results}


if __name__ == "__main__":
    run_evaluation_suite()
