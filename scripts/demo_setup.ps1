# RepoBrain Demo Setup Script (Windows PowerShell)
# Sets up environment, FalkorDB, graph seeding, and boots the backend API server.

$ErrorActionPreference = "Stop"

Write-Host "=== Step 1: Checking Python Virtual Environment ===" -ForegroundColor Cyan
if (Test-Path ".venv\Scripts\python.exe") {
    $PYTHON = ".venv\Scripts\python.exe"
    Write-Host "Using virtual environment: $PYTHON"
} else {
    $PYTHON = "python"
    Write-Host "Using system python: $PYTHON"
}

Write-Host "`n=== Step 2: Installing Dependencies ===" -ForegroundColor Cyan
& $PYTHON -m pip install -r requirements.txt --quiet

Write-Host "`n=== Step 3: Checking FalkorDB Container ===" -ForegroundColor Cyan
$containerRunning = docker ps --filter "name=falkordb" --filter "status=running" -q
if (-not $containerRunning) {
    $containerExists = docker ps -a --filter "name=falkordb" -q
    if ($containerExists) {
        Write-Host "Starting existing falkordb container..."
        docker start falkordb
    } else {
        Write-Host "Launching new falkordb container on port 6379..."
        docker run -d --name falkordb -p 6379:6379 falkordb/falkordb:latest
    }
    Start-Sleep -Seconds 3
} else {
    Write-Host "FalkorDB container is already running on port 6379."
}

Write-Host "`n=== Step 4: Seeding Graph Knowledge Base ===" -ForegroundColor Cyan
& $PYTHON src/ingestion/run.py --seed

Write-Host "`n=== Step 5: Starting RepoBrain FastAPI Server ===" -ForegroundColor Cyan
Write-Host "API will be accessible at: http://localhost:8000"
Write-Host "API Documentation available at: http://localhost:8000/docs"
Write-Host "Press Ctrl+C to terminate the server." -ForegroundColor Yellow
& $PYTHON -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000 --reload
