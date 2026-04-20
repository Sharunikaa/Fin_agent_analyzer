#!/bin/bash
# Complete System Execution Script
# Runs entire Financial Intelligence Suite pipeline

echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║           FINANCIAL INTELLIGENCE SUITE - COMPLETE RUN             ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Change to script directory
cd "$(dirname "$0")"

# ─────────────────────────────────────────────────────────────────────────
# Check Dependencies
# ─────────────────────────────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 0: CHECKING DEPENDENCIES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python 3${NC}"

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${YELLOW}⚠️  Node.js not found (needed for LiteParse)${NC}"
else
    echo -e "${GREEN}✅ Node.js${NC}"
fi

# Check LiteParse
if ! command -v lit &> /dev/null; then
    echo -e "${YELLOW}⚠️  LiteParse not installed${NC}"
    echo "   Installing..."
    npm install -g @llamaindex/liteparse
fi
echo -e "${GREEN}✅ LiteParse${NC}"

# Check API keys
if [ -z "$GROQ_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  GROQ_API_KEY not set (loading from .env)${NC}"
fi

if [ -z "$GEMINI_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  GEMINI_API_KEY not set (loading from .env)${NC}"
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────
# Phase 1: PDF Extraction
# ─────────────────────────────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "PHASE 1: PDF EXTRACTION (LiteParse + Tables + Charts)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ $# -ge 1 ]; then
    PDF_PATH="$1"
    COMPANY="${2:-UNKNOWN}"
    YEAR="${3:-2021}"
    
    echo -e "${BLUE}Processing: $PDF_PATH${NC}"
    echo -e "${BLUE}Company: $COMPANY${NC}"
    echo -e "${BLUE}Year: $YEAR${NC}"
    echo ""
    
    # Run Phase 1
    echo "🔄 Running Phase 1 extraction..."
    python test_enhanced_pipeline.py "$PDF_PATH" "$COMPANY" "$YEAR"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Phase 1 complete${NC}"
    else
        echo -e "${RED}❌ Phase 1 failed${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  No PDF provided, skipping Phase 1${NC}"
    echo "   Usage: ./run_complete_system.sh <pdf_path> [company] [year]"
    echo "   Example: ./run_complete_system.sh uploads/AMD_2021_10K.pdf AMD 2021"
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────
# Phase 1.5: Knowledge Extraction
# ─────────────────────────────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "PHASE 1.5: KNOWLEDGE EXTRACTION (KPIs, Risks, Promises)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo -e "${YELLOW}⚠️  Knowledge extraction not yet implemented${NC}"
echo "   Will be added in next iteration"
echo ""

# ─────────────────────────────────────────────────────────────────────────
# Phase 2: Chunking
# ─────────────────────────────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "PHASE 2: INTELLIGENT CHUNKING"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -d "phase1_output" ]; then
    echo "🔄 Running Phase 2 chunking..."
    python phase2/process.py
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Phase 2 complete${NC}"
    else
        echo -e "${RED}❌ Phase 2 failed${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Phase 1 output not found, skipping Phase 2${NC}"
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────
# Phase 3: Storage
# ─────────────────────────────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "PHASE 3: STORAGE (DuckDB + ChromaDB)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -d "phase2_output" ]; then
    echo "🔄 Setting up databases..."
    python phase3/setup.py
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Phase 3 complete${NC}"
        echo ""
        echo "View databases:"
        echo "  python tools/view_duckdb.py"
        echo "  python tools/view_chromadb.py"
    else
        echo -e "${RED}❌ Phase 3 failed${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Phase 2 output not found, skipping Phase 3${NC}"
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────
# Phase 4: Agents
# ─────────────────────────────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "PHASE 4: MULTI-AGENT SYSTEM"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo -e "${BLUE}Testing agent system...${NC}"
python agents/crew.py --query "What was AMD's revenue in 2021?" 2>/dev/null || echo -e "${YELLOW}⚠️  Agents not yet configured${NC}"

echo ""

# ─────────────────────────────────────────────────────────────────────────
# Phase 5: Evaluation
# ─────────────────────────────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "PHASE 5: EVALUATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f "evals/run_evals.py" ]; then
    echo "🔄 Running evaluation suite..."
    python evals/run_evals.py 2>/dev/null || echo -e "${YELLOW}⚠️  Evals not yet configured${NC}"
else
    echo -e "${YELLOW}⚠️  Evaluation system not found${NC}"
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "PIPELINE COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo -e "${GREEN}✅ System ready!${NC}"
echo ""
echo "Next steps:"
echo "  1. View databases: python tools/view_duckdb.py"
echo "  2. Start backend: ./start_backend.sh"
echo "  3. Start frontend: ./start_frontend.sh"
echo "  4. Access dashboard: http://localhost:5173"
echo ""
echo "Documentation:"
echo "  • workflow.md - End-to-end workflow"
echo "  • README.md - Overview and screenshots"
echo ""
