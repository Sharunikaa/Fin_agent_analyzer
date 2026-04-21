"""
Feedback Tuner: Reads eval logs, analyzes diagnosis patterns,
and adjusts retrieval parameters to improve RAG quality.

Tunable parameters:
  - top_k: number of chunks to retrieve from ChromaDB
  - min_similarity: minimum cosine similarity threshold
  - context_window: surrounding chunks to include
  - max_context_length: max chars sent to LLM
"""

import json
import time
from pathlib import Path
from datetime import datetime, timedelta

EVALS_DIR = Path(__file__).parent.parent / "evals"
TUNER_STATE_FILE = EVALS_DIR / "tuner_state.json"

# Defaults (match phase3/config.py RETRIEVAL_CONFIG)
DEFAULTS = {
    "top_k": 10,
    "rerank_top_k": 5,
    "min_similarity": 0.5,
    "context_window": 2,
    "max_context_length": 4000,
}

# Hard bounds — never go outside these
BOUNDS = {
    "top_k":              (3, 25),
    "rerank_top_k":       (2, 15),
    "min_similarity":     (0.15, 0.75),
    "context_window":     (0, 5),
    "max_context_length": (2000, 8000),
}


def _clamp(val, lo, hi):
    return max(lo, min(hi, val))


def load_state() -> dict:
    """Load current tuner state (params + history)."""
    if TUNER_STATE_FILE.exists():
        with open(TUNER_STATE_FILE) as f:
            return json.load(f)
    return {"params": dict(DEFAULTS), "history": [], "last_tuned": None}


def save_state(state: dict):
    TUNER_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TUNER_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_params() -> dict:
    """Get current retrieval parameters (called by retriever at query time)."""
    return load_state()["params"]


def read_recent_logs(hours: int = 6) -> list:
    """Read eval log entries from the last N hours."""
    logs_dir = EVALS_DIR / "logs"
    cutoff = datetime.now() - timedelta(hours=hours)
    entries = []
    for lf in sorted(logs_dir.glob("feedback_log_*.jsonl"), reverse=True)[:3]:
        with open(lf) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts = entry.get("timestamp", "")
                    if ts and datetime.fromisoformat(ts) >= cutoff:
                        ev = entry.get("evaluation", {})
                        if ev.get("diagnosis"):
                            entries.append(ev)
                except (json.JSONDecodeError, ValueError):
                    continue
    return entries


def compute_adjustments(evals: list) -> dict:
    """Analyze diagnosis patterns and compute parameter deltas."""
    if len(evals) < 3:
        return {}  # not enough data

    total = len(evals)
    counts = {}
    avg_retrieval = 0
    avg_context = 0
    avg_gen = 0

    for ev in evals:
        d = ev.get("diagnosis", "mixed")
        counts[d] = counts.get(d, 0) + 1
        avg_retrieval += ev.get("layer1_retrieval", {}).get("recall_at_k", 0)
        avg_context += ev.get("layer2_context", {}).get("context_recall", 0)
        avg_gen += ev.get("layer3_generation", {}).get("faithfulness", 0)

    avg_retrieval /= total
    avg_context /= total
    avg_gen /= total

    hallucination_rate = (counts.get("hallucination", 0) + counts.get("lucky_guess", 0)) / total
    wrong_context_rate = counts.get("wrong_context", 0) / total
    ideal_rate = counts.get("ideal", 0) / total

    adjustments = {}

    # High hallucination → retrieval is failing, increase top_k, lower min_similarity
    if hallucination_rate > 0.3:
        adjustments["top_k"] = 3
        adjustments["min_similarity"] = -0.05
        adjustments["reason_hallucination"] = f"hallucination rate {hallucination_rate:.0%}"

    # Low retrieval scores → widen search
    if avg_retrieval < 0.4:
        adjustments["top_k"] = adjustments.get("top_k", 0) + 2
        adjustments["min_similarity"] = adjustments.get("min_similarity", 0) - 0.05
        adjustments["reason_low_retrieval"] = f"avg retrieval {avg_retrieval:.2f}"

    # Wrong context → retrieval finds docs but wrong ones, tighten similarity
    if wrong_context_rate > 0.3:
        adjustments["min_similarity"] = adjustments.get("min_similarity", 0) + 0.05
        adjustments["rerank_top_k"] = -1
        adjustments["reason_wrong_context"] = f"wrong_context rate {wrong_context_rate:.0%}"

    # Low generation but good retrieval → increase context sent to LLM
    if avg_gen < 0.4 and avg_retrieval > 0.5:
        adjustments["max_context_length"] = 500
        adjustments["context_window"] = 1
        adjustments["reason_low_gen"] = f"gen {avg_gen:.2f} with retrieval {avg_retrieval:.2f}"

    # Everything is great → tighten slightly to reduce noise
    if ideal_rate > 0.7 and total >= 5:
        adjustments["min_similarity"] = adjustments.get("min_similarity", 0) + 0.02
        adjustments["top_k"] = adjustments.get("top_k", 0) - 1
        adjustments["reason_optimize"] = f"ideal rate {ideal_rate:.0%}, tightening"

    return adjustments


def tune() -> dict:
    """Main tuning function. Reads logs, computes adjustments, saves new params."""
    state = load_state()
    params = state["params"]
    evals = read_recent_logs(hours=6)

    if len(evals) < 3:
        return {"status": "skipped", "reason": f"only {len(evals)} evals, need 3+", "params": params}

    adjustments = compute_adjustments(evals)
    if not adjustments:
        return {"status": "no_change", "reason": "metrics within acceptable range", "params": params}

    # Apply deltas
    old_params = dict(params)
    reasons = []
    for key in DEFAULTS:
        delta = adjustments.get(key, 0)
        if delta:
            lo, hi = BOUNDS[key]
            if isinstance(DEFAULTS[key], float):
                params[key] = round(_clamp(params[key] + delta, lo, hi), 3)
            else:
                params[key] = _clamp(int(params[key] + delta), lo, hi)

    # Collect reasons
    reasons = [v for k, v in adjustments.items() if k.startswith("reason_")]

    # Save
    entry = {
        "timestamp": datetime.now().isoformat(),
        "evals_analyzed": len(evals),
        "old_params": old_params,
        "new_params": dict(params),
        "reasons": reasons,
    }
    state["params"] = params
    state["history"].append(entry)
    state["history"] = state["history"][-20:]  # keep last 20
    state["last_tuned"] = entry["timestamp"]
    save_state(state)

    return {"status": "tuned", "changes": entry, "params": params}


if __name__ == "__main__":
    result = tune()
    print(json.dumps(result, indent=2))
