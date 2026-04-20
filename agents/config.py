"""
Multi-Agent System Configuration
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")
DUCKDB_PATH = PROJECT_ROOT / "data" / "duckdb" / "financial_intelligence.db"
CHROMADB_PATH = PROJECT_ROOT / "data" / "chromadb"

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Neo4j Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "hyperverge-base")

# Agent Configuration
AGENT_CONFIG = {
    "planner": {
        "role": "Query Planning Specialist",
        "goal": "Understand user queries and orchestrate the right agents to fulfill them",
        "backstory": "You are an expert at breaking down complex financial queries into actionable steps. You decide which agents to call and in what order.",
        "verbose": True,
        "allow_delegation": True,
    },
    
    "retriever": {
        "role": "Financial Data Retrieval Specialist",
        "goal": "Fetch relevant financial data using Neo4j graph intelligence and semantic search",
        "backstory": """You are an expert at querying Neo4j to understand document structure (company, year, sections),
then using ChromaDB for semantic search within relevant sections, and DuckDB for numerical metrics.
You track citations (document source, section type, year) for every piece of data retrieved.
You handle multiple references across different sections and provide comprehensive source tracking.""",
        "verbose": True,
        "allow_delegation": False,
    },
    
    "analyst": {
        "role": "Financial Analysis Expert",
        "goal": "Perform calculations, identify trends, and generate insights from financial data",
        "backstory": "You are a seasoned financial analyst with expertise in calculating growth rates, margins, trends, and comparative analysis. You provide actionable insights.",
        "verbose": True,
        "allow_delegation": False,
    },
    
    "visualizer": {
        "role": "Data Visualization Specialist",
        "goal": "Create clear, insightful charts and visualizations from financial data",
        "backstory": "You are an expert at creating professional financial charts using matplotlib and plotly. You know when to use line charts, bar charts, and comparison charts.",
        "verbose": True,
        "allow_delegation": False,
    },
    
    "reporter": {
        "role": "Financial Report Writer",
        "goal": "Synthesize analysis into clear, executive-level reports",
        "backstory": "You are an expert at writing concise, insightful financial reports. You explain complex data in simple terms and highlight key takeaways.",
        "verbose": True,
        "allow_delegation": False,
    },
}

# Task Templates
TASK_TEMPLATES = {
    "planning": """
    Analyze this query and create a comprehensive execution plan:
    
    Query: {query}
    
    Determine:
    1. What company and year(s) are being asked about?
    2. What data is needed (numerical metrics, narrative context, or both)?
    3. What section types are most relevant (financial_statements, risk_factors, mda, business_overview)?
    4. What calculations/analysis are required?
    5. What visualizations would be helpful?
    6. What insights should be highlighted?
    
    For the Retriever, specify:
    - Company(ies) to query
    - Year(s) to analyze
    - Section types to focus on (Neo4j will help determine this)
    
    Create a step-by-step execution plan with specific inputs for each downstream agent.
    """,
    
    "retrieval": """
    Retrieve comprehensive financial data for this query using Neo4j → ChromaDB → DuckDB workflow:
    
    Query: {query}
    Filters: {filters}
    
    STEP 1 - Neo4j Metadata Lookup:
    ✓ Confirm company and years are available
    ✓ Get table of contents (sections metadata)
    ✓ Find sections relevant to this query
    ✓ Identify which subsections contain relevant data (may be multiple)
    
    STEP 2 - ChromaDB Semantic Search:
    ✓ Search within the relevant sections found by Neo4j
    ✓ Get narrative context (risks, strategies, management discussion, etc.)
    ✓ Track which section each chunk comes from
    
    STEP 3 - DuckDB Metrics:
    ✓ Query structured financial data (revenue, margins, cash flow, etc.)
    ✓ Filter by company and year
    ✓ Get numerical values for analysis
    
    STEP 4 - Citations & Source Tracking:
    ✓ Include document name, year, section type for each data point
    ✓ Track page numbers if available
    ✓ Note where data came from (financial_statements, management discussion, etc.)
    ✓ If data appears in multiple sections, list all sources
    
    Return complete results with citations in a structured format.
    """,
    
    "analysis": """
    Perform deep financial analysis on this retrieved data:
    
    Query: {query}
    Retrieved Data: {data}
    
    Analysis Tasks:
    ✓ Calculate growth rates (YoY, CAGR, total growth)
    ✓ Analyze margins (gross, net margins)
    ✓ Identify trends and patterns
    ✓ Compare metrics across periods
    ✓ Detect anomalies or significant changes
    ✓ Provide comparative analysis (vs. peers if available)
    
    Generate:
    - Numerical calculations with clear formulas
    - Trend interpretations
    - Pattern analysis
    - Key insights and findings
    
    Format all findings clearly with supporting numbers.
    """,
    
    "visualization": """
    Create professional visualizations for this financial data:
    
    Query: {query}
    Data: {data}
    Analysis: {analysis}
    
    Chart Selection:
    - Time series (trends) → Line charts
    - Comparisons → Bar charts
    - Multi-metric → Combination charts
    - Growth rates → Percentage charts
    
    For each visualization:
    ✓ Choose appropriate chart type
    ✓ Include clear labels and legends
    ✓ Add data labels/annotations
    ✓ Professional styling and colors
    ✓ Title that summarizes the insight
    
    Output:
    - Chart configuration (JSON)
    - Path to saved visualization
    - Description of what the chart shows
    """,
    
    "reporting": """
    Create a comprehensive financial report from all analysis:
    
    Query: {query}
    Data: {data}
    Analysis: {analysis}
    Visualizations: {visualizations}
    
    Report Structure:
    
    EXECUTIVE SUMMARY
    - 2-3 sentence overview answering the original query
    - Top 1-2 key findings
    
    KEY METRICS
    - Primary numbers: revenue, profit, margins
    - Growth rates (YoY, CAGR)
    - Any notable changes or trends
    
    DETAILED ANALYSIS
    - Trend analysis: direction, magnitude, consistency
    - Comparative analysis: vs. peers or historical
    - Pattern identification and anomalies
    - Data sources and citations
    
    VISUALIZATIONS
    - Embed chart descriptions
    - Explain what each chart shows
    - Highlight key insights from visuals
    
    INSIGHTS & RECOMMENDATIONS
    - What does the data mean?
    - What's driving these trends?
    - Potential opportunities or risks
    - Recommended actions (if relevant)
    
    DATA SOURCES
    - List all documents consulted
    - Section types used (financial statements, MD&A, etc.)
    - Years covered
    """,
}

# LLM Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_CONFIG = {
    "model": "groq/meta-llama/llama-4-scout-17b-16e-instruct",
    "temperature": 0.1,
    "max_tokens": 2000,
}

print("✅ Multi-agent config loaded")
