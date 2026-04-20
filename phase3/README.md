# Phase 3 — Storage, embeddings, and retrieval prep

Phase 3 **persists** everything Phase 2 produced into three complementary layers:

| Layer | Technology | Role |
|-------|------------|------|
| **Structured facts** | DuckDB | Exact numbers, metrics, signals — math and filters. |
| **Vectors** | ChromaDB | **Embeddings** over chunks and table/chart-derived text — semantic search. |
| **Graph metadata** | Neo4j | Companies, documents, sections, links for routing and multi-year context. |

Embedding happens when **ChromaDB** is populated (`chromadb_setup.py`), typically after chunks exist.

## Command (all three)

```bash
python phase3/setup.py
```

This runs Neo4j setup → DuckDB setup → ChromaDB setup (see `setup.py`).

## Inspect

```bash
python tools/view_duckdb.py
python tools/view_chromadb.py
```

## Query routing

Higher-level routing and unified retrieval live in `phase3/query_router.py` and `phase3/retrieval.py`.

## Next steps

- **API:** `python api_server.py` (Flask, port **5001**) for real queries.  
- **Agents:** `agents/smart_retriever.py` (API path) or `agents/crew.py` (multi-agent).

## Full guide

- [workflow.md](../workflow.md)  
- [knowledge_base/README.md](../knowledge_base/README.md) — optional knowledge tables/collections
