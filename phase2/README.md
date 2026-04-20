# Phase 2 — Intelligent chunking and signals

Phase 2 reads **Phase 1 normalized JSON** and prepares data for **retrieval and analytics**: it classifies sections and tables, builds **hierarchical chunks** (parent/child with overlap), and extracts **signals** (risks, forward-looking language, metrics mentions, etc.).

## What runs here

- **Section classifier** — maps content to canonical types (e.g. risk, MD&A, financial statements).
- **Table classifier** — routes tables toward SQL vs vector-friendly descriptions.
- **Chunker** — parent chunks (~context) and child chunks (~retrieval); tables kept intact where configured.
- **Signal extractor** — structured snippets for downstream DuckDB / analysis.

## Command

From project root (paths are set in `phase2/config.py` to read `phase1_output/`):

```bash
python phase2/process.py
```

## Outputs

`phase2_output/` — classified sections/tables, **chunks**, **signals**, reports.

## Next step

**Phase 3** (`python phase3/setup.py`) loads DuckDB, Neo4j metadata, and **ChromaDB embeddings**.

## Full guide

- [workflow.md](../workflow.md) — chunking parameters and storage routing
