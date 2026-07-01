#!/bin/bash

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

echo "🚀 Starting Set Loader Application"
echo "=================================="
echo "Backend Port: ${BACKEND_PORT:-8002}"
echo "Frontend Port: ${FRONTEND_PORT:-3002}"
echo ""

# Kill any existing processes
echo "🧹 Cleaning up existing processes..."
pkill -f "python3 server.py" 2>/dev/null || true
pkill -f "uvicorn server:app" 2>/dev/null || true
pkill -f "npm run dev" 2>/dev/null || true
sleep 2

# Start backend
echo "🔧 Starting backend server..."
uvicorn server:app --host 0.0.0.0 --port ${BACKEND_PORT:-8002} --reload &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start frontend
echo "🎨 Starting frontend..."
cd setlist-helper
export PORT=${FRONTEND_PORT:-3002}
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Services started!"
echo "Backend: http://localhost:${BACKEND_PORT:-8002}"
echo "Frontend: http://localhost:${FRONTEND_PORT:-3002}"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for interrupt
trap 'echo "🛑 Stopping services..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit' INT
wait
