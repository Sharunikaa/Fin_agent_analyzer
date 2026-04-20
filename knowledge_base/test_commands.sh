#!/bin/bash

# Knowledge Base Query Test - Quick Reference
# 
# This script contains common test commands for the unified query engine
# 
# Usage: bash knowledge_base/test_commands.sh

echo "📚 Knowledge Base Query Test Commands"
echo "========================================"
echo ""

# 1. Discovery Mode
echo "1️⃣  DISCOVERY MODE (Show all data)"
echo "   python knowledge_base/test_query.py"
echo ""

# 2. Semantic Search Examples
echo "2️⃣  SEMANTIC SEARCH (ChromaDB)"
echo "   python knowledge_base/test_query.py --query 'revenue growth'"
echo "   python knowledge_base/test_query.py --query 'risk management'"
echo "   python knowledge_base/test_query.py --query 'profitability analysis'"
echo "   python knowledge_base/test_query.py --query 'capital expenditure plans'"
echo ""

# 3. Structured Query Examples
echo "3️⃣  STRUCTURED QUERY (DuckDB + Neo4j)"
echo "   python knowledge_base/test_query.py --company 'AMD'"
echo "   python knowledge_base/test_query.py --company 'Apple' --year 2021"
echo "   python knowledge_base/test_query.py --company 'Microsoft' --year 2022"
echo ""

# 4. Combined Queries
echo "4️⃣  COMBINED QUERIES"
echo "   python knowledge_base/test_query.py --query 'expansion strategy' --company 'Amazon'"
echo "   python knowledge_base/test_query.py --query 'margin improvement' --company 'Apple' --year 2021"
echo ""

# 5. Interactive Mode
echo "5️⃣  INTERACTIVE MODE"
echo "   python knowledge_base/test_query.py --interactive"
echo "   # Then enter queries like:"
echo "   # > revenue growth"
echo "   # > company:AMD year:2021"
echo "   # > exit"
echo ""

# Example execution
echo "📌 EXAMPLE TEST RUN"
echo "==================="
echo ""
echo "Running: python knowledge_base/test_query.py --query 'revenue growth'"
echo ""

cd "$(dirname "$0")/.." || exit
python knowledge_base/test_query.py --query "revenue growth"
