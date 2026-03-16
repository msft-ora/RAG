#!/bin/bash
# Start RAG system locally

set -e

echo "🚀 Starting RAG MSSQL Query System..."

# Check if required tools are installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "❌ Node.js/npm is required but not installed"
    exit 1
fi

# Start backend in background
echo "📦 Starting backend..."
cd backend
pip install --break-system-packages -q -r requirements.txt
python3 main.py &
BACKEND_PID=$!
echo "✓ Backend started (PID: $BACKEND_PID)"

# Give backend time to start
sleep 3

# Start frontend
echo "🎨 Starting frontend..."
cd ../frontend
npm install -q
npm run dev &
FRONTEND_PID=$!
echo "✓ Frontend started (PID: $FRONTEND_PID)"

echo ""
echo "✨ RAG System is running!"
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:5173"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services..."

# Wait for Ctrl+C and cleanup
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped'; exit 0" INT

wait
