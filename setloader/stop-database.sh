#!/bin/bash

# Stop SetLoader Database Services
echo "Stopping SetLoader database services..."

# Stop database services
docker-compose down

echo "✅ Database services stopped"
