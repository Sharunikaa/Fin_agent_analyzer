# Evals — Quality measurements for RAG systems

The `evals/` package measures how well your RAG pipeline is actually working. It runs queries against known good answers (ground truth), scores retrieval quality, context relevance, and generation accuracy, then logs everything and produces improvement recommendations.

## What this phase does

This is your **quality control** layer. After you've indexed everything in Phase 3, you run evals to answer questions like:

- **Are we retrieving the right documents?** (retrieval layer)
- **Is the retrieved context actually useful?** (context layer)  
- **Are the final answers correct and faithful?** (generation layer)

Instead of just eyeballing results, evals gives you metrics you can track over time and spot problems.

### Three-layer evaluation system

The evaluation happens in three stages, matching the RAG pipeline:

#### Layer 1: Retrieval (Did we find the right documents?)

- **Recall@K** — Of the documents that contain the answer, how many did we actually retrieve?
- **Precision@K** — Of the top K documents we retrieved, how many were relevant?
- **MRR (Mean Reciprocal Rank)** — How high in the ranking was the first correct document?
- **nDCG (Normalized Discounted Cumulative Gain)** — How well-ranked were all the relevant documents?

#### Layer 2: Context (Is the retrieved text actually helpful?)

- **Context Recall** — Did the chunks we pulled actually contain the information needed to answer?
- **Context Precision** — How much of what we retrieved was relevant vs noise?
- **Context Relevance** — Are the chunks actually useful for this specific question?

#### Layer 3: Generation (Is the final answer correct?)

- **Faithfulness** — Does the answer stay true to what's in the retrieved context? (No hallucinations?)
- **Answer Relevancy** — Does the answer actually address the question asked?
- **Answer Correctness** — When compared to the ground truth, is it right?
- **Semantic Similarity** — Is the meaning close to the expected answer?

## How it works

1. **Load ground truth** — You have a file like `ground_truth/queries.json` with questions and expected answers
2. **Run smart retriever** — For each query, retrieve documents from your indexed data
3. **Synthesize an answer** — Use the LLM to turn retrieved chunks into a complete answer
4. **Score each layer** — Run the three-layer evaluation
5. **Log everything** — Save results so you can see trends
6. **Generate report** — Identify bottlenecks and suggest improvements

## Files and structure

| File | Purpose |
|------|---------|
| `run_evals.py` | Main entry point — loads ground truth, runs queries, collects scores |
| `evaluator.py` | RAGEvaluator class — implements all three layers of metrics |
| `agent_evaluator.py` | AgentEvaluator class — evaluates API responses and agent outputs |
| `feedback_loop.py` | FeedbackLoop class — logs results, analyzes performance, suggests improvements |
| `config.py` | Thresholds, weights, metric definitions |
| `ground_truth/` | Your test dataset (queries + expected answers + doc IDs) |
| `logs/` | Daily feedback logs (JSONL format, one per day) |
| `results/` | Evaluation run results and summaries |

## Quick start

### Run evals

```bash
cd evals
python run_evals.py
```

This will:
1. Load all your ground truth queries
2. Run smart_retriever on each one
3. Evaluate each query against the three layers
4. Print a summary with overall scores and per-category breakdown
5. Save logs to `logs/` and results to `results/`

Expected output looks like:

```
🧪 RAG EVALUATION SUITE (3-Layer)
=======================================

📋 42 ground truth examples loaded

[1/42] What was AMD's revenue in 2021?
   Category: financials | Difficulty: medium
   Retrieval  → Recall@k=0.95  Precision@k=0.88  MRR=0.92  nDCG=0.90
   Context    → Recall=0.89  Precision=0.82  Relevance=0.85
   Generation → Faith=0.91  Relevancy=0.93  Correct=0.87  SimSim=0.89
   Overall=0.890  Diagnosis=OK  Latency=1.2s

...

📊 EVALUATION SUMMARY
=======================================

   Total: 42
   Overall Score: 0.863

   Layer 1 (Retrieval):
     recall_at_k         : 0.872
     precision_at_k      : 0.811
     mrr                 : 0.856
     ndcg                : 0.823

   Layer 2 (Context):
     context_recall      : 0.847
     context_precision   : 0.789
     context_relevance   : 0.801

   Layer 3 (Generation):
     faithfulness        : 0.891
     answer_relevancy    : 0.904
     answer_correctness  : 0.872
     semantic_similarity : 0.818

   By Category:
     financials              : avg=0.878 (15 queries)
     risks                   : avg=0.832 (12 queries)
     trends                  : avg=0.851 (15 queries)

   📋 Improvement Report:
   • Low context precision (0.789) — consider reducing chunk overlap or improving section boundaries
   • Semantic similarity lags other metrics — may need better embedding model or reranking
   • Risk queries underperforming (0.832) — check if risk-specific language is in training set
```

## Ground truth format

Create `ground_truth/queries.json` with your test cases:

```json
[
  {
    "id": "q_001",
    "query": "What was AMD's revenue in 2021?",
    "category": "financials",
    "difficulty": "easy",
    "expected_answer": "AMD reported revenue of $16.434 billion in 2021.",
    "expected_sources": ["AMD_2021_10K", "AMD_2021_10Q"],
    "expected_keywords": ["16.434", "billion", "revenue", "2021"]
  },
  {
    "id": "q_002",
    "query": "What are the main risks facing NVIDIA?",
    "category": "risks",
    "difficulty": "medium",
    "expected_answer": "Key risks include competition from AMD, supply chain disruptions, and regulatory scrutiny.",
    "expected_sources": ["NVIDIA_2023_10K"]
  }
]
```

## Integration with API responses

To evaluate responses from your API or Flask backend:

```python
from evals.agent_evaluator import AgentEvaluator

evaluator = AgentEvaluator()

# After you get a response from your API:
result = evaluator.evaluate_query(
    query="What was Apple's gross margin in 2022?",
    answer="Apple's gross margin was 46.2% in fiscal 2022.",
    retrieved_doc_ids=["AAPL_2022_10K"],
    retrieved_chunks=["...", "..."],
    latency=1.23,
    ground_truth_id="q_apple_margin"
)

print(f"Overall score: {result['overall_score']:.3f}")
print(f"Diagnoses: {result['diagnosis']}")
```

## Configuration

`config.py` defines:

- **Metric thresholds** — what score counts as "passing" (default: 0.5–0.8 depending on metric)
- **Metric weights** — how much each metric contributes to overall score
- **Layer weights** — how much each layer (retrieval, context, generation) matters

Edit these based on your priorities. For example, if faithfulness is critical, increase its weight.

## Performance interpretation

Scores range from 0.0 (worst) to 1.0 (best):

- **0.9–1.0**: Excellent. This query works well.
- **0.75–0.89**: Good. Room for improvement but acceptable.
- **0.5–0.74**: Warn. This should be investigated.
- **<0.5**: Poor. Fix this before deploying.

If a specific layer is low (e.g., context_recall = 0.4), it points to the bottleneck:
- Low retrieval → your indexing or search isn't finding the right chunks
- Low context → retrieved chunks don't contain needed info (maybe chunk size is wrong)
- Low generation → LLM synthesis is hallucinating or off-topic (maybe temperature is too high)

## Feedback loop & improvements

The `FeedbackLoop` class analyzes results and suggests improvements:

```
Improvement Report:
• Retrieval: nDCG is 0.812 vs target 0.85 — consider better reranking
• Context: Context precision 0.76 — improve chunk overlap settings
• Generation: Faithfulness is good (0.91) but answer_relevancy at 0.85 — try different LLM prompts
```

These suggestions come from analyzing which layers are weakest and comparing against thresholds.

## Logging

Every evaluation run creates a log file in `logs/`:

```
logs/
├── feedback_log_20260415.jsonl
├── feedback_log_20260416.jsonl
└── ...
```

Format (JSONL, one log per line):

```json
{
  "log_id": "log_20260415_143022_123456",
  "timestamp": "2026-04-15T14:30:22.123456",
  "query": "What was AMD's revenue in 2021?",
  "response": {
    "text": "AMD reported revenue of $16.434 billion...",
    "sources": ["AMD_2021_10K"],
    "latency": 1.23
  },
  "evaluation": {
    "overall_score": 0.891,
    "layer1_retrieval": {...},
    "layer2_context": {...},
    "layer3_generation": {...},
    "diagnosis": "OK"
  }
}
```

## When to run evals

- **After Phase 3** — When all your data is indexed and retrieval is working
- **Before deploying** — To confirm quality meets requirements
- **Regularly** — Set up a nightly or weekly eval run to catch regressions
- **After schema changes** — If you modify chunking or indexing, re-eval to confirm quality didn't drop

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "No ground truth found" | Create `ground_truth/queries.json` with test cases |
| Smart retriever errors | Check that Phase 3 (Neo4j/ChromaDB/DuckDB) is fully set up |
| Low scores everywhere | Likely an indexing problem — check chunk quality in Phase 3 |
| Some categories low, others high | May be dataset imbalance — add more examples for weak categories |
| LLM synthesis errors | Check GROQ_API_KEY is set; increase `max_tokens` in config if answers are cut off |

## Next steps

1. Create your ground truth file with representative queries
2. Run `python run_evals.py`
3. Review the summary and identify weak layers
4. Make improvements (reindex, adjust chunk size, try different LLM, etc.)
5. Re-run evals to confirm improvement
6. Set up regular eval runs to monitor quality over time
