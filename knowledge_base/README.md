# Knowledge Base — Optional enrichment layer

The `knowledge_base/` package sits between Phase 1 (extraction) and Phase 3 (storage). It uses LLMs to intelligently extract **financial signals** that weren't explicitly captured during parsing: KPIs, risks, promises, anomalies, sentiment. The outputs can then be loaded into DuckDB for analytics or used to enrich your retrieval.

## What this phase does

This is an **optional** layer that adds intelligence on top of raw parsed text. Instead of just storing "what was extracted," you add "what does this mean?"

### Extraction types

**KPIs (Key Performance Indicators)**
- Revenue, earnings, margins, debt ratios, cash flow, growth rates
- Extracted directly from tables and text
- Time-series capable (track year-over-year)

**Risks**
- Legal risks (litigation, compliance, IP disputes)
- Operational risks (supply chain, staffing, geopolitical)
- Financial risks (currency exposure, credit, market volatility)
- Market risks (competition, disruption, demand)

**Forward-looking statements**
- What management says it will do ("We plan to...", "We expect...")
- Growth targets, strategic initiatives, expansion plans
- Used for trend prediction and sentiment

**Anomalies**
- Unusual changes year-over-year
- Sudden spikes or drops in metrics
- Data outliers that warrant investigation

**Sentiment**
- Tone of management discussion (optimistic, cautious, pessimistic)
- Confidence signals in guidance and plans

### Synthesis layers

After extraction, the system synthesizes results at different levels:

**Per-document** (e.g., one 10-K)
- All KPIs, risks, and signals from that one filing
- Stored as markdown in `knowledge_output/per_pdf/`

**Per-company per-year** (e.g., Apple in 2023)
- Aggregated across all filings for that company/year
- Trends compared to prior year
- Stored in `knowledge_output/per_company/` and `per_year/`

**Master view**
- Time-series across all companies/years (e.g., revenue trends for FAANG 2018–2024)
- Cross-company comparisons
- Stored in `knowledge_output/master/`

## When to run

**Timing options:**

1. **Right after Phase 1** — Extract signals while you still have the full context
2. **Before Phase 3** — Enrich the data before indexing (signals are baked into DuckDB/ChromaDB)
3. **In parallel** — Phase 2 (chunking) and knowledge extraction happen independently

Most workflows do **(1) or (2)** so enriched facts end up in your final retrieval system.

## Quick start

### Basic run

```bash
python knowledge_base/process.py --input phase1_output/ --output knowledge_output/
```

This reads normalized JSON from Phase 1 and produces markdown + enriched facts.

### Company/year filtered

```bash
python knowledge_base/process.py --company AMD NVIDIA --years 2021,2022
```

Process only specific companies and fiscal years.

### Parallel batch (faster)

```bash
./run_parallel_processing.sh
```

Uses multiple workers to process documents in parallel. Check `run_parallel_processing.sh` for configuration.

## Files and structure

| File | Purpose |
|------|---------|
| `process.py` | Main orchestrator — reads Phase 1 JSON, coordinates extraction and synthesis |
| `process_parallel.py` | Parallel variant using worker pool |
| `config.py` | Paths, LLM settings, extraction config |
| `extractors/` | Individual extractors (KPI, risk, promise, anomaly, sentiment) |
| `synthesizers/` | Synthesis logic (per-doc, per-company, master aggregation) |
| `storage/` | Optional handlers to load into DuckDB, ChromaDB, Neo4j |
| `integrate_phase3.py` | Bridge between knowledge_base outputs and Phase 3 indexing |
| `test_query.py` | Test utility for querying extracted knowledge |
| `verify_groq.py` | Verify Groq API is working |

## Extraction pipeline

### 1. Load Phase 1 data

```
phase1_output/normalized_json/*.json
  → Read document text, tables, charts, metadata
```

### 2. Run extractors on each document

For each document, spawn extractors in parallel:

- **KPI Extractor** — Scans tables + text for "Revenue = $X", "Margin = Y%", etc. Matches known KPI patterns.
- **Risk Extractor** — Uses NLP + LLM to identify "We are subject to...", "Risk factors include...", etc.
- **Promise Extractor** — Finds forward-looking statements: "We plan", "expect", "will", "guidance"
- **Anomaly Detector** — Compares year-over-year metrics, flags spikes >30% or drops >30%
- **Sentiment Analyzer** — Uses Groq (or Gemini) to classify management tone

### 3. Structure results

Each extraction produces structured data:

```json
{
  "doc_id": "AMD_2021_10K_abc123",
  "company": "AMD",
  "year": 2021,
  "kpis": [
    {"name": "Revenue", "value": 16434, "unit": "USD_millions", "source": "Item 8 - Financials"},
    {"name": "Gross Margin", "value": 48.2, "unit": "percent", "source": "MD&A"}
  ],
  "risks": [
    {"category": "operational", "description": "Supply chain disruptions", "severity": "high"},
    {"category": "legal", "description": "Antitrust investigations", "severity": "medium"}
  ],
  "forward_looking": [
    "We expect data center revenue to grow 25% in 2022",
    "We plan to expand manufacturing capacity in Taiwan"
  ],
  "anomalies": [
    {"metric": "gross_margin", "change_pct": -2.1, "flag": "watch", "note": "Slight margin compression vs prior year"}
  ],
  "sentiment": {
    "tone": "cautiously_optimistic",
    "confidence": 0.82,
    "key_phrases": ["strong demand", "supply constraints", "strategic investments"]
  }
}
```

## Output structure

```
knowledge_output/
├── per_pdf/
│   ├── AMD_2021_10K_abc123.json          # Per-document extractions
│   ├── AMD_2021_10K_abc123_summary.md
│   └── ...
├── per_company/
│   ├── AMD/
│   │   ├── 2021_kpis.json
│   │   ├── 2021_risks.json
│   │   ├── 2022_kpis.json
│   │   └── AMD_profile.md
│   └── NVIDIA/
├── per_year/
│   ├── 2021_all_companies.json
│   ├── 2022_all_companies.json
│   └── ...
├── master/
│   ├── revenue_timeseries.json
│   ├── risk_heatmap.json
│   ├── sentiment_trends.json
│   └── master_synthesis.md
└── logs/
    └── extraction_log_20260415.jsonl
```

## Configuration

Key settings in `config.py`:

```python
# LLM provider for extractors
EXTRACTION_LLM = "groq"  # or "gemini"

# Which extractors to run
EXTRACTORS = {
    "kpis": True,
    "risks": True,
    "promises": True,
    "anomalies": True,
    "sentiment": True,
}

# Thresholds
ANOMALY_THRESHOLD_PCT = 30  # Flag changes >30%
SENTIMENT_CONFIDENCE_MIN = 0.6

# Parallel workers
PARALLEL_WORKERS = 4
```

## Integration with Phase 3

### Option A: Load findings into DuckDB

```bash
python knowledge_base/integrate_phase3.py --target duckdb
```

Creates/populates additional DuckDB tables:
- `kpi_extractions` — Structured KPI facts
- `risk_extractions` — Risk inventory
- `forward_looking_statements` — Management guidance
- `anomalies` — Detected outliers

### Option B: Augment ChromaDB with extracted context

Enrich each chunk's metadata with relevant signals so retrieval benefits from financial context.

## Typical workflow

1. **Phase 1** → Ingest PDFs, get normalized JSON
2. **Knowledge extraction** → Extract signals and enrich
3. **Phase 2** → Create chunks (text + enriched metadata)
4. **Phase 3** → Index into DuckDB + ChromaDB + Neo4j
5. **Query** → Retrieval now benefits from extracted signals

## Parallel processing

For large datasets, use parallel extraction:

```bash
export GROQ_API_KEY=your_key
export NUM_WORKERS=8
./run_parallel_processing.sh
```

This spawns 8 worker processes and distributes documents across them. Much faster than single-threaded.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "No documents found" | Verify Phase 1 outputs exist in `phase1_output/normalized_json/` |
| LLM extraction errors | Check GROQ_API_KEY (or GEMINI_API_KEY); verify API quota |
| Empty KPI results | Some 10-Ks may not have structured financial tables; check `per_pdf/` logs |
| Slow processing | Use `process_parallel.py` or increase `PARALLEL_WORKERS` in config |
| Integration with Phase 3 fails | Verify `integrate_phase3.py` can access DuckDB/ChromaDB paths |

## Next steps

- Run `process.py` on your Phase 1 data
- Inspect `knowledge_output/` for signal quality
- Integrate results into Phase 3 indexing if desired
- Use `test_query.py` to validate extracted knowledge
