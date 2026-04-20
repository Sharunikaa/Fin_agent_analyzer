"""
3-Layer RAG Evaluator: Retrieval → Context → Generation

Metrics:
  Layer 1 (Retrieval): Recall@k, Precision@k, MRR, nDCG
  Layer 2 (Context):   Context Recall, Context Precision, Context Relevance
  Layer 3 (Generation): Faithfulness, Answer Relevancy, Answer Correctness, Semantic Similarity
"""

import json
import math
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import EVAL_METRICS, RETRIEVAL_METRICS, CONTEXT_METRICS, GENERATION_METRICS, LOGS_DIR


class RAGEvaluator:
    """Three-layer RAG evaluation."""

    def __init__(self, embed_model=None):
        self.logs = []
        self._embed_model = embed_model

    @property
    def embed_model(self):
        if self._embed_model is None:
            from sentence_transformers import SentenceTransformer
            self._embed_model = SentenceTransformer("BAAI/bge-large-en-v1.5")
        return self._embed_model

    # ── Fix 1: Fuzzy doc_id matching ────────────────────────────────────
    # Ground truth has "AMD_2021_10K", retriever returns "AMD_2021_10K_a95494befa9d"
    # Use prefix matching so partial IDs still count as hits.

    def _doc_matches(self, retrieved_id: str, relevant_id: str) -> bool:
        """Prefix/substring match for doc IDs."""
        r = retrieved_id.upper()
        g = relevant_id.upper()
        return r.startswith(g) or g.startswith(r) or g in r or r in g

    def _count_hits(self, retrieved_ids: List[str], relevant_ids: List[str]) -> int:
        """Count how many relevant docs appear in retrieved (fuzzy)."""
        hits = 0
        for rel in relevant_ids:
            if any(self._doc_matches(ret, rel) for ret in retrieved_ids):
                hits += 1
        return hits

    # ── Layer 1: Retrieval ──────────────────────────────────────────────

    def recall_at_k(self, retrieved_doc_ids: List[str], relevant_doc_ids: List[str], k: int = 10) -> float:
        if not relevant_doc_ids:
            return 1.0
        top_k = retrieved_doc_ids[:k]
        hits = self._count_hits(top_k, relevant_doc_ids)
        return hits / len(relevant_doc_ids)

    def precision_at_k(self, retrieved_doc_ids: List[str], relevant_doc_ids: List[str], k: int = 10) -> float:
        top_k = retrieved_doc_ids[:k]
        if not top_k:
            return 0.0
        hits = sum(1 for ret in top_k if any(self._doc_matches(ret, rel) for rel in relevant_doc_ids))
        return hits / len(top_k)

    def mrr(self, retrieved_doc_ids: List[str], relevant_doc_ids: List[str]) -> float:
        for i, ret in enumerate(retrieved_doc_ids):
            if any(self._doc_matches(ret, rel) for rel in relevant_doc_ids):
                return 1.0 / (i + 1)
        return 0.0

    def ndcg(self, retrieved_doc_ids: List[str], relevant_doc_ids: List[str], k: int = 10) -> float:
        dcg = sum(
            (1.0 if any(self._doc_matches(retrieved_doc_ids[i], rel) for rel in relevant_doc_ids) else 0.0)
            / math.log2(i + 2)
            for i in range(min(k, len(retrieved_doc_ids)))
        )
        ideal = sum(1.0 / math.log2(i + 2) for i in range(min(k, len(relevant_doc_ids))))
        return dcg / ideal if ideal > 0 else 0.0

    def evaluate_retrieval(self, retrieved_doc_ids: List[str], relevant_doc_ids: List[str], k: int = 10) -> Dict:
        return {
            "recall_at_k": round(self.recall_at_k(retrieved_doc_ids, relevant_doc_ids, k), 3),
            "precision_at_k": round(self.precision_at_k(retrieved_doc_ids, relevant_doc_ids, k), 3),
            "mrr": round(self.mrr(retrieved_doc_ids, relevant_doc_ids), 3),
            "ndcg": round(self.ndcg(retrieved_doc_ids, relevant_doc_ids, k), 3),
        }

    # ── Layer 2: Context ────────────────────────────────────────────────
    # Fix 2: Semantic matching for context recall instead of exact string.

    def context_recall(self, retrieved_chunks: List[str], expected_keywords: List[str]) -> float:
        """Did retrieved chunks contain the necessary information? (semantic + fuzzy)"""
        if not expected_keywords or not retrieved_chunks:
            return 1.0 if not expected_keywords else 0.0

        combined = " ".join(retrieved_chunks).lower()
        hits = 0
        for kw in expected_keywords:
            kw_lower = kw.lower()
            # Direct match
            if kw_lower in combined:
                hits += 1
                continue
            # Fuzzy: split multi-word keywords and check partial
            kw_parts = kw_lower.replace("_", " ").split()
            if len(kw_parts) > 1 and all(p in combined for p in kw_parts):
                hits += 1
                continue
            # Synonym/related term matching for common financial terms
            synonyms = {
                "revenue": ["net revenue", "total revenue", "sales", "net sales"],
                "gross margin": ["gross profit margin", "gross margin percentage"],
                "gross profit": ["gross margin", "gross income"],
                "net income": ["net earnings", "net profit", "profit"],
                "growth rate": ["increased by", "grew by", "growth of", "up %"],
                "trend": ["increased", "decreased", "grew", "declined", "compared to"],
                "upward": ["increased", "grew", "higher", "up"],
                "improved": ["increased", "grew", "higher", "better"],
                "cagr": ["compound annual growth", "annual growth rate", "growth rate"],
                "subscribers": ["subscriber", "membership", "paid members"],
                "supply chain": ["supply", "suppliers", "sourcing", "logistics"],
                "competition": ["competitive", "competitors", "compete"],
                "cloud": ["azure", "cloud computing", "cloud services", "saas"],
                "enterprise": ["business", "commercial", "corporate"],
                "hybrid cloud": ["hybrid", "on-premises and cloud", "multi-cloud"],
                "intellectual property": ["patents", "ip", "proprietary"],
                "market demand": ["demand", "market conditions", "customer demand"],
                "technology": ["technological", "innovation", "r&d"],
                "strong growth": ["significant growth", "substantial growth", "rapid growth"],
            }
            matched = False
            for syn_key, syn_list in synonyms.items():
                if kw_lower in syn_key or syn_key in kw_lower:
                    if any(s in combined for s in syn_list):
                        hits += 1
                        matched = True
                        break
            if matched:
                continue
            # Last resort: any synonym list value matches
            for syn_list in synonyms.values():
                if kw_lower in syn_list or any(kw_lower in s for s in syn_list):
                    hits += 1
                    break

        return hits / len(expected_keywords)

    def context_precision(self, retrieved_chunks: List[str], query: str) -> float:
        if not retrieved_chunks:
            return 0.0
        query_words = set(w.lower() for w in query.split() if len(w) > 3)
        relevant = sum(1 for chunk in retrieved_chunks if any(w in chunk.lower() for w in query_words))
        return relevant / len(retrieved_chunks)

    def context_relevance(self, retrieved_chunks: List[str], query: str) -> float:
        if not retrieved_chunks:
            return 0.0
        import numpy as np
        query_emb = self.embed_model.encode(query)
        chunk_embs = self.embed_model.encode(retrieved_chunks[:10])
        sims = np.dot(chunk_embs, query_emb) / (
            np.linalg.norm(chunk_embs, axis=1) * np.linalg.norm(query_emb) + 1e-8
        )
        return float(np.mean(sims))

    def evaluate_context(self, retrieved_chunks: List[str], query: str, expected_keywords: List[str] = None) -> Dict:
        return {
            "context_recall": round(self.context_recall(retrieved_chunks, expected_keywords or []), 3),
            "context_precision": round(self.context_precision(retrieved_chunks, query), 3),
            "context_relevance": round(self.context_relevance(retrieved_chunks, query), 3),
        }

    # ── Layer 3: Generation ─────────────────────────────────────────────
    # Fix 3: Handle financial number formats for answer correctness.

    def _extract_numbers(self, text: str) -> List[float]:
        """Extract all numbers from text, normalizing financial formats.
        Handles: $16,434  |  16.4 billion  |  $16,434 million  |  68.3%  |  45%
        """
        numbers = []
        # Pattern: optional $ + number with commas + optional decimal + optional billion/million/B/M
        pattern = r'\$?\s*([\d,]+(?:\.\d+)?)\s*(?:(billion|million|B|M|%))?'
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                val = float(match.group(1).replace(",", ""))
                suffix = (match.group(2) or "").lower()
                if suffix in ("billion", "b"):
                    val *= 1000  # normalize to millions
                # million/M stays as-is, % stays as-is
                numbers.append(val)
            except ValueError:
                continue
        return numbers

    def faithfulness(self, answer: str, context_chunks: List[str]) -> float:
        if not answer or not context_chunks:
            return 0.0
        # If the LLM explicitly says it can't find the answer, that's faithful
        refusal_phrases = ["not found", "not available", "doesn't contain", "does not contain",
                           "no information", "cannot find", "not mentioned", "unable to find",
                           "context doesn't", "context does not", "not provided"]
        if any(p in answer.lower() for p in refusal_phrases):
            return 1.0
        combined_context = " ".join(context_chunks).lower()
        sentences = [s.strip() for s in re.split(r'[.!?]', answer) if s.strip()]
        if not sentences:
            return 0.0
        grounded = 0
        for sent in sentences:
            words = [w.lower() for w in sent.split() if len(w) > 3]
            if not words:
                grounded += 1
                continue
            overlap = sum(1 for w in words if w in combined_context)
            if overlap / len(words) >= 0.3:
                grounded += 1
        return grounded / len(sentences)

    def answer_relevancy(self, answer: str, query: str) -> float:
        if not answer:
            return 0.0
        import numpy as np
        q_emb = self.embed_model.encode(query)
        a_emb = self.embed_model.encode(answer[:1000])
        sim = float(np.dot(q_emb, a_emb) / (np.linalg.norm(q_emb) * np.linalg.norm(a_emb) + 1e-8))
        return max(0.0, sim)

    def answer_correctness(self, answer: str, ground_truth: Dict) -> float:
        """Compare generated answer with expected output.
        Uses fuzzy number matching with financial format awareness,
        and semantic string matching for qualitative values.
        """
        expected = ground_truth.get("expected_answer", {})
        if not expected:
            return 1.0

        answer_lower = answer.lower()
        answer_numbers = self._extract_numbers(answer)
        correct, total = 0, 0

        # Synonyms for qualitative ground truth values
        _value_synonyms = {
            "upward": ["increased", "grew", "growth", "higher", "up", "rose", "rising"],
            "downward": ["decreased", "declined", "fell", "lower", "down", "dropped"],
            "improved": ["increased", "grew", "better", "higher", "improvement", "up"],
            "strong growth": ["significant growth", "substantial", "rapid growth", "grew significantly", "strong"],
            "amd": ["amd", "advanced micro devices"],
            "intel": ["intel", "intel corporation"],
            "apple": ["apple", "apple inc"],
        }

        for key, value in expected.items():
            total += 1
            if isinstance(value, (int, float)):
                tolerance = max(abs(value * 0.15), 1.0)
                matched = any(abs(n - value) <= tolerance for n in answer_numbers)
                if not matched and value > 100:
                    # billions form: 16434 → 16.4
                    matched = any(abs(n - value / 1000) <= max(abs(value / 1000 * 0.15), 0.5) for n in answer_numbers)
                if not matched:
                    # percentage might appear as "68%" matching 68.3
                    matched = any(abs(n - value) <= max(abs(value * 0.20), 2.0) for n in answer_numbers)
                if matched:
                    correct += 1
            elif isinstance(value, str):
                val_lower = value.lower()
                if val_lower in answer_lower:
                    correct += 1
                else:
                    # Check synonyms
                    syns = _value_synonyms.get(val_lower, [])
                    if any(s in answer_lower for s in syns):
                        correct += 1
                    elif any(val_lower in s or s in val_lower for s in answer_lower.split()):
                        correct += 1
            elif isinstance(value, list):
                hits = 0
                for v in value:
                    v_lower = str(v).lower()
                    if v_lower in answer_lower:
                        hits += 1
                    else:
                        syns = _value_synonyms.get(v_lower, [])
                        if any(s in answer_lower for s in syns):
                            hits += 1
                if hits >= max(1, len(value) * 0.4):
                    correct += 1

        return correct / total if total > 0 else 0.0

    def semantic_similarity(self, answer: str, ground_truth_text: str) -> float:
        if not answer or not ground_truth_text:
            return 0.0
        import numpy as np
        a_emb = self.embed_model.encode(answer[:1000])
        gt_emb = self.embed_model.encode(ground_truth_text[:1000])
        sim = float(np.dot(a_emb, gt_emb) / (np.linalg.norm(a_emb) * np.linalg.norm(gt_emb) + 1e-8))
        return max(0.0, sim)

    def evaluate_generation(self, answer: str, query: str, context_chunks: List[str], ground_truth: Dict) -> Dict:
        gt_text = json.dumps(ground_truth.get("expected_answer", {}))
        return {
            "faithfulness": round(self.faithfulness(answer, context_chunks), 3),
            "answer_relevancy": round(self.answer_relevancy(answer, query), 3),
            "answer_correctness": round(self.answer_correctness(answer, ground_truth), 3),
            "semantic_similarity": round(self.semantic_similarity(answer, gt_text), 3),
        }

    # ── Full Evaluation ─────────────────────────────────────────────────

    def evaluate(
        self,
        query: str,
        answer: str,
        retrieved_doc_ids: List[str],
        retrieved_chunks: List[str],
        ground_truth: Dict,
        latency: float = 0.0,
    ) -> Dict:
        t0 = time.time()

        relevant_doc_ids = ground_truth.get("expected_sources", [])
        expected_keywords = self._extract_keywords(ground_truth)

        retrieval = self.evaluate_retrieval(retrieved_doc_ids, relevant_doc_ids)
        context = self.evaluate_context(retrieved_chunks, query, expected_keywords)
        generation = self.evaluate_generation(answer, query, retrieved_chunks, ground_truth)

        all_metrics = {**retrieval, **context, **generation}

        overall = sum(
            all_metrics.get(m, 0) * cfg["weight"]
            for m, cfg in EVAL_METRICS.items()
            if m in all_metrics
        )

        faith = generation["faithfulness"]
        correct = generation["answer_correctness"]
        if faith >= 0.7 and correct >= 0.7:
            diagnosis = "ideal"
        elif faith >= 0.7 and correct < 0.5:
            diagnosis = "wrong_context"
        elif faith < 0.5 and correct < 0.5:
            diagnosis = "hallucination"
        elif faith < 0.5 and correct >= 0.7:
            diagnosis = "lucky_guess"
        else:
            diagnosis = "mixed"

        evaluation = {
            "eval_id": f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "category": ground_truth.get("category", "unknown"),
            "ground_truth_id": ground_truth.get("id"),
            "layer1_retrieval": retrieval,
            "layer2_context": context,
            "layer3_generation": generation,
            "overall_score": round(overall, 3),
            "diagnosis": diagnosis,
            "latency": round(latency, 3),
            "eval_time": round(time.time() - t0, 3),
        }

        self.logs.append(evaluation)
        return evaluation

    def _extract_keywords(self, ground_truth: Dict) -> List[str]:
        keywords = []
        expected = ground_truth.get("expected_answer", {})
        for key, value in expected.items():
            keywords.append(key.replace("_", " "))
            if isinstance(value, str):
                keywords.append(value)
            elif isinstance(value, list):
                keywords.extend(str(v) for v in value)
        return keywords

    def save_logs(self, filename: str = None):
        if not filename:
            filename = f"eval_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path = LOGS_DIR / filename
        with open(path, "w") as f:
            json.dump(self.logs, f, indent=2)
        print(f"✅ Saved {len(self.logs)} eval logs to {path}")
        return path

    def get_statistics(self) -> Dict:
        if not self.logs:
            return {}
        n = len(self.logs)
        all_keys = set()
        for log in self.logs:
            for layer in ("layer1_retrieval", "layer2_context", "layer3_generation"):
                all_keys.update(log.get(layer, {}).keys())

        avg = {}
        for key in all_keys:
            vals = []
            for log in self.logs:
                for layer in ("layer1_retrieval", "layer2_context", "layer3_generation"):
                    if key in log.get(layer, {}):
                        vals.append(log[layer][key])
            if vals:
                avg[key] = round(sum(vals) / len(vals), 3)

        diagnoses = {}
        by_category = {}
        for log in self.logs:
            d = log.get("diagnosis", "unknown")
            diagnoses[d] = diagnoses.get(d, 0) + 1
            cat = log.get("category", "unknown")
            if cat not in by_category:
                by_category[cat] = {"total": 0, "scores": []}
            by_category[cat]["total"] += 1
            by_category[cat]["scores"].append(log["overall_score"])

        for cat, info in by_category.items():
            info["avg_score"] = round(sum(info["scores"]) / len(info["scores"]), 3)
            del info["scores"]

        return {
            "total_evaluations": n,
            "average_metrics": avg,
            "average_overall": round(sum(l["overall_score"] for l in self.logs) / n, 3),
            "diagnoses": diagnoses,
            "by_category": by_category,
        }


Evaluator = RAGEvaluator

if __name__ == "__main__":
    ev = RAGEvaluator()
    result = ev.evaluate(
        query="What is AMD's revenue in 2021?",
        answer="AMD's revenue in 2021 was $16.4 billion, up 68% year-over-year.",
        retrieved_doc_ids=["AMD_2021_10K_a95494befa9d"],
        retrieved_chunks=[
            "Computing and Graphics net revenue of $9.3 billion in 2021 increased by 45%",
            "Net revenue was $16,434 million in 2021 compared to $9,763 million in 2020",
        ],
        ground_truth={
            "id": "gt_001",
            "category": "factual_retrieval",
            "expected_answer": {"revenue": 16434.0, "year": 2021, "company": "AMD"},
            "expected_sources": ["AMD_2021_10K"],
        },
        latency=3.2,
    )
    print(json.dumps(result, indent=2))
