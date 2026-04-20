"""
Knowledge Base Configuration
Central configuration for knowledge extraction system
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "knowledge_base"
KNOWLEDGE_OUTPUT_DIR = PROJECT_ROOT / "knowledge_output"

# Input paths
PHASE1_OUTPUT = PROJECT_ROOT / "phase1_output" / "normalized"
PHASE1_METADATA = PROJECT_ROOT / "phase1_output" / "metadata"
PHASE1_TABLES = PROJECT_ROOT / "phase1_output" / "tables"

# Output subdirectories
PER_PDF_DIR = KNOWLEDGE_OUTPUT_DIR / "per_pdf"
PER_COMPANY_DIR = KNOWLEDGE_OUTPUT_DIR / "per_company"
PER_YEAR_DIR = KNOWLEDGE_OUTPUT_DIR / "per_year"
MASTER_DIR = KNOWLEDGE_OUTPUT_DIR / "master"

# Create directories
for dir_path in [KNOWLEDGE_OUTPUT_DIR, PER_PDF_DIR, PER_COMPANY_DIR, PER_YEAR_DIR, MASTER_DIR, PHASE1_OUTPUT]:
    dir_path.mkdir(parents=True, exist_ok=True)

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # For text generation
GROQ_API_KEY = os.getenv("GROQ_API_KEY")      # For Groq models

# LLM Configuration
# Can use "gemini" or "groq" as backend
# ⚠️ Gemini free tier has quotas - use Groq for unlimited requests
LLM_BACKEND = os.getenv("LLM_BACKEND", "groq")  # Default to Groq, set to "gemini" to use Gemini

LLM_CONFIG = {
    "backend": LLM_BACKEND,
    "text_model": "gemini-2.0-flash-lite" if LLM_BACKEND == "gemini" else "meta-llama/llama-4-scout-17b-16e-instruct",
    "vision_model": "gpt-4-vision" if LLM_BACKEND == "gemini" else "meta-llama/llama-4-scout-17b-16e-instruct",
    "temperature": 0.1,  # Low temperature for consistent extraction
    "max_tokens": 4000,
}

# Extraction Categories
KPI_CATEGORIES = [
    "revenue",
    "gross_profit",
    "gross_margin_pct",
    "ebitda",
    "net_income",
    "free_cash_flow",
    "total_debt",
    "cash_and_equivalents",
    "capex",
    "rd_expense",
    "employee_count",
]

RISK_CATEGORIES = [
    "operational",
    "financial",
    "regulatory",
    "geopolitical",
    "competitive",
    "ESG",
    "governance",
]

PROMISE_CATEGORIES = [
    "financial_target",
    "operational",
    "ESG",
    "capital_return",
    "product",
    "geographic_expansion",
]

ANOMALY_TYPES = [
    "accrual_spike",
    "revenue_recognition_shift",
    "margin_compression",
    "inventory_buildup",
    "receivables_spike",
    "expense_reclassification",
    "one_time_item_abuse",
    "guidance_miss",
]

# Severity Levels
SEVERITY_LEVELS = ["low", "medium", "high", "critical"]
LANGUAGE_INTENSITY = ["mild", "moderate", "strong", "alarming"]

# Database Configuration
DUCKDB_PATH = PROJECT_ROOT / "data" / "duckdb" / "financial_intelligence.db"
CHROMADB_PATH = PROJECT_ROOT / "data" / "chromadb"
NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "asdfghjkl")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "hyperverge-base")

# Processing Settings
BATCH_SIZE = 5  # Process 5 PDFs at a time
RATE_LIMIT_DELAY = 4  # seconds between LLM calls (to avoid quota)

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

print("✅ Knowledge base config loaded")
