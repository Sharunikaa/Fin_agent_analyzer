"""
Evaluation & Feedback Loop Configuration
Three-layer RAG evaluation: Retrieval → Context → Generation
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
EVALS_DIR = PROJECT_ROOT / "evals"
GROUND_TRUTH_DIR = EVALS_DIR / "ground_truth"
LOGS_DIR = EVALS_DIR / "logs"
RESULTS_DIR = EVALS_DIR / "results"

for dir_path in [GROUND_TRUTH_DIR, LOGS_DIR, RESULTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ── Layer 1: Retrieval Metrics ──────────────────────────────────────────
RETRIEVAL_METRICS = {
    "recall_at_k": {
        "description": "Did we retrieve the correct documents?",
        "weight": 0.15,
        "threshold": 0.7,
        "k": 10,
    },
    "precision_at_k": {
        "description": "Are retrieved documents relevant?",
        "weight": 0.10,
        "threshold": 0.5,
        "k": 10,
    },
    "mrr": {
        "description": "Mean Reciprocal Rank — ranking quality",
        "weight": 0.05,
        "threshold": 0.4,
    },
    "ndcg": {
        "description": "Normalized Discounted Cumulative Gain",
        "weight": 0.05,
        "threshold": 0.5,
    },
}

# ── Layer 2: Context Metrics ────────────────────────────────────────────
CONTEXT_METRICS = {
    "context_recall": {
        "description": "Did retrieved chunks contain necessary info?",
        "weight": 0.10,
        "threshold": 0.6,
    },
    "context_precision": {
        "description": "How much noise is present in context?",
        "weight": 0.10,
        "threshold": 0.5,
    },
    "context_relevance": {
        "description": "Are chunks useful for answering?",
        "weight": 0.05,
        "threshold": 0.5,
    },
}

# ── Layer 3: Generation Metrics ─────────────────────────────────────────
GENERATION_METRICS = {
    "faithfulness": {
        "description": "Is the answer supported by retrieved context? (1 - hallucination)",
        "weight": 0.15,
        "threshold": 0.7,
    },
    "answer_relevancy": {
        "description": "Does the answer address the query?",
        "weight": 0.10,
        "threshold": 0.7,
    },
    "answer_correctness": {
        "description": "Compared with ground truth expected output",
        "weight": 0.10,
        "threshold": 0.7,
    },
    "semantic_similarity": {
        "description": "Embedding-based similarity with ground truth",
        "weight": 0.05,
        "threshold": 0.6,
    },
}

# Combined for backward compat
EVAL_METRICS = {**RETRIEVAL_METRICS, **CONTEXT_METRICS, **GENERATION_METRICS}

# ── Metric Relationship Interpretation ──────────────────────────────────
# | Faithfulness | Correctness | Interpretation              |
# | High         | High        | Ideal system                |
# | High         | Low         | Wrong or misleading context |
# | Low          | Low         | Hallucination               |
# | Low          | High        | Lucky guess (dangerous)     |

EVAL_CATEGORIES = {
    "factual_retrieval": {
        "description": "Simple fact retrieval",
        "primary_metrics": ["recall_at_k", "answer_correctness", "faithfulness"],
    },
    "trend_analysis": {
        "description": "Trend analysis across years",
        "primary_metrics": ["recall_at_k", "context_recall", "answer_correctness"],
    },
    "comparison": {
        "description": "Company comparison",
        "primary_metrics": ["precision_at_k", "context_precision", "faithfulness"],
    },
    "semantic_search": {
        "description": "Semantic / qualitative queries",
        "primary_metrics": ["context_relevance", "answer_relevancy", "faithfulness"],
    },
}

IMPROVEMENT_THRESHOLDS = {
    "faithfulness_low": 0.5,
    "retrieval_recall_low": 0.4,
    "context_precision_low": 0.3,
    "answer_correctness_low": 0.5,
    "latency_high": 15.0,
    "error_rate_high": 0.3,
}

LOG_CONFIG = {
    "log_all_queries": True,
    "log_level": "INFO",
    "retention_days": 30,
}

print("✅ Evals config loaded (3-layer RAG evaluation)")
