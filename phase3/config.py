"""
Phase 3 Configuration: Storage & Retrieval
"""

from pathlib import Path
import os

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
PHASE2_OUTPUT = PROJECT_ROOT / "phase2_output"
DATA_DIR = PROJECT_ROOT / "data"

DUCKDB_PATH = DATA_DIR / "duckdb" / "financial_intelligence.db"
CHROMADB_PATH = DATA_DIR / "chromadb"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
(DATA_DIR / "duckdb").mkdir(exist_ok=True)
(DATA_DIR / "chromadb").mkdir(exist_ok=True)

# Embedding Configuration
EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"
EMBEDDING_DIMENSION = 1024  # bge-large-en-v1.5 dimension
BATCH_SIZE = 32  # For embedding batches

# ChromaDB Collections
CHROMADB_COLLECTIONS = {
    "business_overview": {
        "description": "Company strategy, products, markets, competition",
        "section_types": ["business_overview"],
    },
    "risk_factors": {
        "description": "Risk disclosures and material risks",
        "section_types": ["risk_factors"],
    },
    "mda": {
        "description": "Management discussion and analysis",
        "section_types": ["mda"],
    },
    "financial_statements": {
        "description": "Financial statements and footnotes",
        "section_types": ["financial_statements", "footnotes"],
    },
    "all_sections": {
        "description": "All document sections (fallback)",
        "section_types": ["other", "header", "cover_page", "table_of_contents", "segment_breakdown", "esg", "legal"],
    },
}

# DuckDB Schema
DUCKDB_SCHEMA = {
    "documents": """
        CREATE TABLE IF NOT EXISTS documents (
            doc_id VARCHAR PRIMARY KEY,
            company VARCHAR NOT NULL,
            ticker VARCHAR,
            full_name VARCHAR,
            sector VARCHAR,
            year INTEGER NOT NULL,
            doc_type VARCHAR NOT NULL,
            filing_date DATE,
            pages INTEGER,
            source VARCHAR,
            ingestion_method VARCHAR,
            ingest_timestamp TIMESTAMP,
            phase2_timestamp TIMESTAMP
        )
    """,
    
    "financial_metrics": """
        CREATE TABLE IF NOT EXISTS financial_metrics (
            metric_id VARCHAR PRIMARY KEY,
            doc_id VARCHAR NOT NULL,
            company VARCHAR NOT NULL,
            year INTEGER NOT NULL,
            metric_name VARCHAR NOT NULL,
            value DOUBLE,
            unit VARCHAR,
            source_table_id VARCHAR,
            fiscal_period VARCHAR,
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
        )
    """,
    
    "segment_revenue": """
        CREATE TABLE IF NOT EXISTS segment_revenue (
            segment_id VARCHAR PRIMARY KEY,
            doc_id VARCHAR NOT NULL,
            company VARCHAR NOT NULL,
            year INTEGER NOT NULL,
            segment_name VARCHAR NOT NULL,
            segment_type VARCHAR,  -- product, geographic
            revenue DOUBLE,
            operating_income DOUBLE,
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
        )
    """,
    
    "tables_metadata": """
        CREATE TABLE IF NOT EXISTS tables_metadata (
            table_id VARCHAR PRIMARY KEY,
            doc_id VARCHAR NOT NULL,
            company VARCHAR NOT NULL,
            year INTEGER NOT NULL,
            table_type VARCHAR NOT NULL,
            storage_destination VARCHAR NOT NULL,
            location VARCHAR,
            caption VARCHAR,
            row_count INTEGER,
            column_count INTEGER,
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
        )
    """,
    
    "sections_metadata": """
        CREATE TABLE IF NOT EXISTS sections_metadata (
            section_id VARCHAR PRIMARY KEY,
            doc_id VARCHAR NOT NULL,
            company VARCHAR NOT NULL,
            year INTEGER NOT NULL,
            section_type VARCHAR NOT NULL,
            level INTEGER,
            page_start INTEGER,
            page_end INTEGER,
            text_length INTEGER,
            chunk_count INTEGER,
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
        )
    """,
    
    "signals": """
        CREATE TABLE IF NOT EXISTS signals (
            signal_id VARCHAR PRIMARY KEY,
            doc_id VARCHAR NOT NULL,
            company VARCHAR NOT NULL,
            year INTEGER NOT NULL,
            signal_type VARCHAR NOT NULL,
            signal_text VARCHAR,
            context VARCHAR,
            section_id VARCHAR,
            chunk_id VARCHAR,
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
        )
    """,
}

# Query Router Patterns
QUERY_PATTERNS = {
    "structured": {
        "keywords": [
            "revenue", "income", "profit", "loss", "margin", "assets", "liabilities", 
            "equity", "debt", "cash", "earnings", "ebitda", "eps", "roe", "roa",
            "segment", "geographic", "product line", "business unit",
            "trend", "compare", "growth", "change", "increase", "decrease",
        ],
        "storage": "duckdb",
        "priority": 1,
    },
    
    "semantic": {
        "keywords": [
            "risk", "strategy", "competition", "market", "customer", "supplier",
            "product", "service", "innovation", "technology", "acquisition",
            "management", "ceo", "executive", "board", "governance",
            "sustainability", "esg", "environment", "social", "carbon",
            "explain", "describe", "summarize", "what", "why", "how",
        ],
        "storage": "chromadb",
        "priority": 2,
    },
    
    "hybrid": {
        "keywords": [
            "financial performance", "revenue growth", "margin expansion",
            "segment performance", "geographic breakdown", "competitive position",
            "market share", "pricing strategy", "cost structure",
        ],
        "storage": "both",
        "priority": 3,
    },
}

# Retrieval Configuration
RETRIEVAL_CONFIG = {
    "top_k": 10,  # Number of chunks to retrieve
    "rerank_top_k": 5,  # Number of chunks after reranking
    "min_similarity": 0.5,  # Minimum similarity score
    "context_window": 2,  # Number of surrounding chunks to include
    "max_context_length": 4000,  # Maximum context length in characters
}

print(f"✅ Phase 3 config loaded")
print(f"   DuckDB: {DUCKDB_PATH}")
print(f"   ChromaDB: {CHROMADB_PATH}")
print(f"   Embedding model: {EMBEDDING_MODEL}")
