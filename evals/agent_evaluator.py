"""
Agent Evaluator: Integrate 3-layer RAG evals with the agent system.
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict

sys.path.append(str(Path(__file__).parent.parent))

from evals.evaluator import RAGEvaluator
from evals.feedback_loop import FeedbackLoop
from evals.ground_truth import load_ground_truth


class AgentEvaluator:
    """Evaluate agent responses using 3-layer RAG metrics."""

    def __init__(self):
        self.evaluator = RAGEvaluator()
        self.feedback_loop = FeedbackLoop()

    def evaluate_query(
        self,
        query: str,
        answer: str,
        retrieved_doc_ids: list = None,
        retrieved_chunks: list = None,
        latency: float = 0.0,
        ground_truth_id: str = None,
    ) -> Dict:
        """Evaluate a single query through all 3 layers."""
        gt = None
        if ground_truth_id:
            dataset = load_ground_truth()
            gt = next((g for g in dataset if g["id"] == ground_truth_id), None)
        if not gt:
            gt = {"id": "unknown", "category": "unknown", "expected_answer": {}, "expected_sources": []}

        evaluation = self.evaluator.evaluate(
            query=query,
            answer=answer,
            retrieved_doc_ids=retrieved_doc_ids or [],
            retrieved_chunks=retrieved_chunks or [],
            ground_truth=gt,
            latency=latency,
        )

        response = {"text": answer, "sources": retrieved_doc_ids or [], "latency": latency}
        self.feedback_loop.log_query(query, response, evaluation)
        return evaluation

    def evaluate_with_retriever(self, query: str, ground_truth_id: str = None) -> Dict:
        """Run smart retriever then evaluate."""
        from agents.smart_retriever import smart_retrieve
        import logging
        logging.disable(logging.INFO)

        t0 = time.time()
        result = smart_retrieve(query)
        latency = time.time() - t0
        logging.disable(logging.NOTSET)

        doc_ids = list({r.get("doc_id", "") for r in result.text_results if r.get("doc_id")})
        chunks = [r["text"] for r in result.text_results if r.get("text")]
        answer = " ".join(chunks[:5])

        return self.evaluate_query(
            query=query,
            answer=answer,
            retrieved_doc_ids=doc_ids,
            retrieved_chunks=chunks,
            latency=latency,
            ground_truth_id=ground_truth_id,
        )

    def get_summary(self) -> Dict:
        return self.evaluator.get_statistics()

    def save(self):
        self.evaluator.save_logs()
        analysis = self.feedback_loop.analyze_performance()
        self.feedback_loop.save_performance_snapshot(analysis)


if __name__ == "__main__":
    ae = AgentEvaluator()
    result = ae.evaluate_with_retriever("What is AMD's revenue in 2021?", ground_truth_id="gt_001")
    print(json.dumps(result, indent=2))
    ae.save()
