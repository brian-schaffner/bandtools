#!/bin/bash

# Start SetLoader Database Services
echo "Starting SetLoader database services..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Start database services
echo "Starting PostgreSQL and Redis..."
docker-compose up -d

# Wait for database to be ready
echo "Waiting for database to be ready..."
sleep 10

# Check if database is accessible
echo "Testing database connection..."
python3 -c "
import sys
try:
    from database import init_database
    init_database()
    print('✅ Database initialized successfully')
except Exception as e:
    print(f'❌ Database initialization failed: {e}')
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ Database services are running and ready!"
    echo "PostgreSQL: localhost:5432"
    echo "Redis: localhost:6379"
else
    echo "❌ Database initialization failed"
    exit 1
fi
