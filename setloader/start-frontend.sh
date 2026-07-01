#!/bin/bash

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Start frontend with environment configuration
echo "🚀 Starting frontend on port ${FRONTEND_PORT:-3002}"
cd setlist-helper

# Set Next.js port from environment
export PORT=${FRONTEND_PORT:-3002}

npm run dev
