#!/bin/bash

# Parallel Processing - Quick Start
# Process all remaining documents concurrently

set -e

echo "🚀 Starting Parallel Document Processing..."
echo "==========================================="
echo ""

# Check GROQ_API_KEY
if [ -z "$GROQ_API_KEY" ]; then
    echo "❌ GROQ_API_KEY not set"
    echo "Set it with: export GROQ_API_KEY='your-key'"
    exit 1
fi

echo "✅ GROQ_API_KEY found"
echo ""

# Determine number of workers
if [ -z "$WORKERS" ]; then
    WORKERS=$(($(nproc) - 1))
fi

echo "📊 Configuration:"
echo "   Workers: $WORKERS (auto-detected)"
echo "   Start: ${START:-0} (skipped processed docs)"
echo "   Documents: phase1_output/normalized/"
echo ""

# Run parallel processing
python knowledge_base/process_parallel.py \
    --workers "$WORKERS" \
    --start "${START:-62}" \
    --verbose

echo ""
echo "✅ Processing complete!"
echo ""
echo "Check results:"
echo "  ls -1 knowledge_output/per_pdf/ | wc -l"
echo ""
echo "Query the data:"
echo "  python knowledge_base/test_query.py --company 'AMD'"
