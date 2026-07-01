#!/bin/bash

# Start the UI development server
cd /usr/local/src/setloader/setlist-helper

# Set environment variables
export NEXT_PUBLIC_API_URL=http://localhost:8002
export NEXT_PUBLIC_API_SECRET=change-me

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# Start the development server
echo "Starting UI development server..."
npm run dev
