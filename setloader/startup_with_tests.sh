#!/bin/bash
# Startup script with automated testing
# Ensures system meets all requirements before starting

echo "🚀 STARTING SETLOADER WITH AUTOMATED TESTING"
echo "=============================================="

# Change to project directory
cd /usr/local/src/setloader

# Run the test suite first
echo "🧪 Running automated test suite..."
python3 test_suite.py

# Check if tests passed
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ All tests passed! Starting services..."
    echo ""
    
    # Start backend
    echo "🔧 Starting backend server..."
    uvicorn server:app --host 0.0.0.0 --port 8002 --reload &
    BACKEND_PID=$!
    
    # Wait for backend to start
    echo "⏳ Waiting for backend to start..."
    sleep 5
    
    # Test backend health
    if curl -s http://localhost:8002/health > /dev/null; then
        echo "✅ Backend started successfully (PID: $BACKEND_PID)"
        
        # Start frontend
        echo "🔧 Starting frontend server..."
        cd setlist-helper
        PORT=3002 npm run dev &
        FRONTEND_PID=$!
        cd ..
        
        echo "✅ Frontend started successfully (PID: $FRONTEND_PID)"
        echo ""
        echo "🎉 SETLOADER IS READY!"
        echo "Backend: http://localhost:8002"
        echo "Frontend: http://localhost:3002"
        echo ""
        echo "Press Ctrl+C to stop all services"
        
        # Keep script running and handle cleanup
        trap "echo '🛑 Stopping services...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
        wait
    else
        echo "❌ Backend failed to start"
        kill $BACKEND_PID 2>/dev/null
        exit 1
    fi
else
    echo ""
    echo "❌ Tests failed! Please fix issues before starting services."
    echo "Check the test report in pack/test_report.json"
    exit 1
fi
