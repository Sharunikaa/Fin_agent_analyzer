# Agents — retrieval, smart RAG, and multi-agent crew

This directory contains:

1. **`smart_retriever.py`** — Used by the **Flask API** (`api_server.py`) to combine **Neo4j + ChromaDB + DuckDB** and return ranked context for LLM synthesis.

2. **`crew.py` + `tools/`** — **CrewAI** workflow: Planner → Retriever (Neo4j metadata + `retriever_tool`) → Analyst → Visualizer → Reporter.

3. **`config.py`** — Model and Neo4j settings for agents.

## Quick tests

Default CLI run (uses the built-in test query in `main()`):

```bash
python agents/crew.py
```

Custom query in Python:

```python
from agents.crew import FinancialAnalysisCrew
FinancialAnalysisCrew().analyze_query("What was AMD's revenue in 2021?")
```

Individual tools (when developing):

```bash
cd agents/tools
python neo4j_tool.py
python retriever_tool.py
```

## Documentation

- [workflow.md](../workflow.md)
