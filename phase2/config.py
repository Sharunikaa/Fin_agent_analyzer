"""
Phase 2 Configuration: Intelligent Chunking & Signal Extraction
"""

from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
PHASE1_OUTPUT = PROJECT_ROOT / "phase1_output" / "normalized"
PHASE2_OUTPUT = PROJECT_ROOT / "phase2_output"

CHUNKS_DIR = PHASE2_OUTPUT / "chunks"
SIGNALS_DIR = PHASE2_OUTPUT / "signals"
CLASSIFIED_SECTIONS_DIR = PHASE2_OUTPUT / "classified_sections"
CLASSIFIED_TABLES_DIR = PHASE2_OUTPUT / "classified_tables"

# Create directories
for dir_path in [CHUNKS_DIR, SIGNALS_DIR, CLASSIFIED_SECTIONS_DIR, CLASSIFIED_TABLES_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Section Classification: 12 Canonical Types
SECTION_TYPES = {
    "cover_page": {
        "keywords": ["form 10-k", "form 10-q", "annual report", "securities and exchange"],
        "max_pages": 3,
        "priority": 1
    },
    "table_of_contents": {
        "keywords": ["table of contents", "index", "page"],
        "max_pages": 5,
        "priority": 2
    },
    "ceo_letter": {
        "keywords": ["letter to shareholders", "dear shareholders", "fellow shareholders"],
        "max_pages": 10,
        "priority": 3
    },
    "business_overview": {
        "keywords": ["item 1", "item 1.", "item 1 -", "business", "our company", "overview"],
        "exclude_keywords": ["item 1a", "item 1b"],
        "priority": 4
    },
    "risk_factors": {
        "keywords": ["item 1a", "risk factors", "risk factor"],
        "priority": 5
    },
    "mda": {
        "keywords": ["item 7", "management's discussion", "md&a", "results of operations"],
        "exclude_keywords": ["item 7a"],
        "priority": 6
    },
    "financial_statements": {
        "keywords": ["item 8", "financial statements", "consolidated statement", "consolidated balance"],
        "priority": 7
    },
    "footnotes": {
        "keywords": ["note ", "notes to", "notes to consolidated", "note 1", "note 2"],
        "priority": 8
    },
    "segment_breakdown": {
        "keywords": ["segment", "reportable segment", "operating segment"],
        "priority": 9
    },
    "esg": {
        "keywords": ["sustainability", "environmental", "social responsibility", "esg", "carbon emission"],
        "priority": 10
    },
    "legal": {
        "keywords": ["item 3", "legal proceedings", "litigation"],
        "priority": 11
    },
    "other": {
        "keywords": [],
        "priority": 12
    }
}

# Table Classification
TABLE_TYPES = {
    "income_statement": {
        "keywords": ["revenue", "income", "earnings", "profit", "loss", "operating expenses"],
        "required_keywords": ["revenue", "income"],
        "storage": "duckdb"
    },
    "balance_sheet": {
        "keywords": ["assets", "liabilities", "equity", "stockholders", "shareholders"],
        "required_keywords": ["assets", "liabilities"],
        "storage": "duckdb"
    },
    "cashflow_statement": {
        "keywords": ["cash flow", "operating activities", "investing activities", "financing activities"],
        "required_keywords": ["cash flow"],
        "storage": "duckdb"
    },
    "segment_breakdown": {
        "keywords": ["segment", "geographic", "product line", "business unit"],
        "required_keywords": ["segment"],
        "storage": "duckdb"
    },
    "other": {
        "keywords": [],
        "storage": "chromadb"
    }
}

# Chunking Configuration
CHUNKING_CONFIG = {
    "chunk_size": 512,  # tokens
    "overlap": 100,  # tokens (20% overlap)
    "min_chunk_size": 100,  # minimum tokens
    "max_chunk_size": 1000,  # maximum tokens
    "preserve_sentences": True,  # don't break mid-sentence
    "preserve_paragraphs": True,  # prefer paragraph boundaries
}

# Signal Extraction Patterns
SIGNAL_PATTERNS = {
    "risk_markers": [
        r"\bmaterial\s+(?:weakness|risk|adverse|effect)\b",
        r"\bsignificant\s+(?:risk|uncertainty|impact)\b",
        r"\bmay\s+adversely\s+affect\b",
        r"\bcould\s+have\s+a\s+material\s+adverse\b",
        r"\bsubstantial\s+(?:risk|doubt)\b",
    ],
    "commitment_keywords": [
        r"\bwe\s+will\b",
        r"\bwe\s+plan\s+to\b",
        r"\bwe\s+expect\s+to\b",
        r"\bwe\s+intend\s+to\b",
        r"\bby\s+\d{4}\b",  # by 2025, by 2030, etc.
        r"\bin\s+fiscal\s+\d{4}\b",
    ],
    "temporal_anchors": [
        r"\bfiscal\s+year\s+\d{4}\b",
        r"\bfy\s*\d{4}\b",
        r"\bq[1-4]\s+\d{4}\b",
        r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4}\b",
        r"\b\d{4}\b",  # standalone year
    ],
    "metric_mentions": [
        r"\brevenue\s+(?:increased|decreased|grew|declined)\b",
        r"\bmargin\s+(?:expanded|contracted|improved|declined)\b",
        r"\bearnings\s+(?:increased|decreased|grew|declined)\b",
        r"\bdebt\s+(?:increased|decreased|reduced)\b",
    ],
    "financial_amounts": [
        r"\$\s*\d+(?:\.\d+)?\s*(?:billion|million|thousand|B|M|K)\b",
        r"\d+(?:\.\d+)?\s*(?:billion|million|thousand)\s+dollars?\b",
    ],
}

# Named Entity Recognition (simple patterns, can be enhanced with spaCy later)
NER_PATTERNS = {
    "companies": [
        r"\b(?:Intel|NVIDIA|Qualcomm|Samsung|TSMC|Apple|Microsoft|Amazon|Google|Meta)\b",
        r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Inc\.|Corp\.|Corporation|Ltd\.|Limited|LLC)\b",
    ],
    "people": [
        r"\b(?:Dr\.|Mr\.|Ms\.|Mrs\.)\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b",
        r"\b[A-Z][a-z]+\s+[A-Z][a-z]+,\s+(?:CEO|CFO|President|Chairman|Director)\b",
    ],
}

# Hierarchical Chunking Levels
HIERARCHY_LEVELS = {
    "level_0": "document",  # Entire document
    "level_1": "part",      # Part I, Part II, Part III
    "level_2": "item",      # Item 1, Item 1A, Item 7, etc.
    "level_3": "section",   # Subsections within items
    "level_4": "chunk",     # Final chunks for embedding
}

# Validation Thresholds
VALIDATION_THRESHOLDS = {
    "min_chunks_per_doc": 50,
    "max_chunks_per_doc": 5000,
    "min_chunk_length": 50,  # characters
    "max_chunk_length": 4000,  # characters
    "min_signals_per_doc": 10,
}

print(f"✅ Phase 2 config loaded")
print(f"   Phase 1 input: {PHASE1_OUTPUT}")
print(f"   Phase 2 output: {PHASE2_OUTPUT}")
