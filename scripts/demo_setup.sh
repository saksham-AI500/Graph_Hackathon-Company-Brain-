#!/usr/bin/env bash
# RepoBrain Demo Setup Script (Unix / macOS / Linux)
# Sets up environment, FalkorDB, graph seeding, and boots the backend API server.

set -e

echo "=== Step 1: Checking Python Virtual Environment ==="
if [ -d ".venv" ]; then
    PYTHON=".venv/bin/python"
    echo "Using virtual environment: $PYTHON"
else
    PYTHON="python3"
    echo "Using system python: $PYTHON"
fi

echo ""
echo "=== Step 2: Installing Dependencies ==="
$PYTHON -m pip install -r requirements.txt --quiet

echo ""
echo "=== Step 3: Checking FalkorDB Container ==="
if [ -z "$(docker ps -q -f name=falkordb -f status=running)" ]; then
    if [ -n "$(docker ps -aq -f name=falkordb)" ]; then
        echo "Starting existing falkordb container..."
        docker start falkordb
    else
        echo "Launching new falkordb container on port 6379..."
        docker run -d --name falkordb -p 6379:6379 falkordb/falkordb:latest
    fi
    sleep 3
else
    echo "FalkorDB container is already running on port 6379."
fi

echo ""
echo "=== Step 4: Seeding Graph Knowledge Base ==="
$PYTHON src/ingestion/run.py --seed

echo ""
echo "=== Step 5: Starting RepoBrain FastAPI Server ==="
echo "API will be accessible at: http://localhost:8000"
echo "API Documentation available at: http://localhost:8000/docs"
echo "Press Ctrl+C to terminate the server."
$PYTHON -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000 --reload
