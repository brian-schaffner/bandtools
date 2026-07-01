#!/bin/bash

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Start backend server with environment configuration
echo "🚀 Starting backend server on port ${BACKEND_PORT:-8002} (server_simple_db)"
python3 -m uvicorn server_simple_db:app --host 0.0.0.0 --port ${BACKEND_PORT:-8002} --reload
