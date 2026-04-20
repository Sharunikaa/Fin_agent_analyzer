#!/bin/bash
# Start both API backend and React frontend
cd "$(dirname "$0")"

echo "🚀 Starting Financial Intelligence Dashboard"
echo "============================================"

# Start API server in background
source hyperverge/bin/activate
echo "📡 Starting API server on http://localhost:5001..."
python api_server.py &
API_PID=$!

# Start frontend
echo "🎨 Starting frontend on http://localhost:3000..."
cd frontend
npx vite --host &
FE_PID=$!

echo ""
echo "✅ Dashboard ready!"
echo "   Frontend: http://localhost:3000"
echo "   API:      http://localhost:5001"
echo ""
echo "Press Ctrl+C to stop both servers"

trap "kill $API_PID $FE_PID 2>/dev/null; exit" INT TERM
wait
