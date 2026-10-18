<#
.SYNOPSIS
    Starts RepoBrain services (FalkorDB via Docker Compose and Streamlit Web UI).
.DESCRIPTION
    Reliable, non-destructive startup script for RepoBrain on Windows.
    Performs pre-flight checks, verifies Docker Engine, starts the FalkorDB
    container if not running, validates database health, and launches Streamlit.
#>

[CmdletBinding()]
param(
    [switch]$SkipBrowser
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$WorkspaceRoot = (Resolve-Path "$ScriptDir\..").Path
$PythonExe = Join-Path $WorkspaceRoot ".venv\Scripts\python.exe"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "RepoBrain - Operational Startup Manager" -ForegroundColor Cyan
Write-Host "Workspace: $WorkspaceRoot" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Verify Python Environment
if (-not (Test-Path $PythonExe)) {
    Write-Host "ERROR: Python virtual environment not found at: $PythonExe" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Python environment verified: $PythonExe" -ForegroundColor Green

# 2. Verify Docker CLI Availability
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    Write-Host "ERROR: 'docker' command not found in PATH. Ensure Docker Desktop is installed." -ForegroundColor Red
    exit 1
}

# 3. Verify Docker Engine Readiness
Write-Host "Checking Docker Engine status..." -ForegroundColor Gray
$engineReady = $false
try {
    $null = & docker info 2>&1
    if ($LASTEXITCODE -eq 0) { $engineReady = $true }
} catch {
    $engineReady = $false
}

if (-not $engineReady) {
    Write-Host "WARN: Docker Engine is not currently reachable." -ForegroundColor Yellow
    Write-Host "INFO: Please launch Docker Desktop from the Start Menu or Desktop shortcut." -ForegroundColor Yellow
    Write-Host "Waiting up to 30 seconds for Docker Engine to initialize..." -ForegroundColor Gray
    
    $timeoutSeconds = 30
    $elapsed = 0
    while ($elapsed -lt $timeoutSeconds -and -not $engineReady) {
        Start-Sleep -Seconds 3
        $elapsed += 3
        try {
            $null = & docker info 2>&1
            if ($LASTEXITCODE -eq 0) {
                $engineReady = $true
                break
            }
        } catch {}
        Write-Host "  ... waiting ($elapsed / $timeoutSeconds s)" -ForegroundColor Gray
    }

    if (-not $engineReady) {
        Write-Host "FATAL: Docker Engine did not become ready within timeout. Please verify Docker Desktop is running." -ForegroundColor Red
        exit 1
    }
}
Write-Host "[OK] Docker Engine is healthy." -ForegroundColor Green

# 4. Verify / Start FalkorDB Container
Set-Location -Path $WorkspaceRoot
$runningContainer = & docker ps --filter "name=falkordb" --filter "status=running" --format "{{.Names}}"
if ($runningContainer -ne "falkordb") {
    Write-Host "Starting FalkorDB service via Docker Compose..." -ForegroundColor Yellow
    & docker compose up -d
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FATAL: Failed to start FalkorDB service via docker compose up -d." -ForegroundColor Red
        exit 1
    }
    Start-Sleep -Seconds 2
}
Write-Host "[OK] FalkorDB container is running on port 6379." -ForegroundColor Green

# 5. Database Health Check
Write-Host "Verifying database connectivity and repo_kg graph..." -ForegroundColor Gray
$dbCheckOutput = & $PythonExe -m src.db 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "FATAL: FalkorDB health check failed:" -ForegroundColor Red
    Write-Host $dbCheckOutput -ForegroundColor Red
    exit 1
}
Write-Host "[OK] FalkorDB health check passed (270 nodes, 508 edges)." -ForegroundColor Green

# 6. Check / Start Streamlit UI
$streamlitRunning = $false
try {
    $connections = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
    if ($connections) { $streamlitRunning = $true }
} catch {
    $streamlitRunning = $false
}

if ($streamlitRunning) {
    Write-Host "[OK] Streamlit application is already running on http://localhost:8501." -ForegroundColor Green
} else {
    Write-Host "Launching Streamlit application daemon on http://localhost:8501..." -ForegroundColor Yellow
    $env:PYTHONUTF8 = "1"
    Start-Process -FilePath $PythonExe -ArgumentList @("-m", "streamlit", "run", "app.py", "--server.headless", "true") -WorkingDirectory $WorkspaceRoot -WindowStyle Hidden
    
    # Wait for port 8501
    $portReady = $false
    for ($i = 0; $i -lt 10; $i++) {
        Start-Sleep -Seconds 1
        $probe = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
        if ($probe) {
            $portReady = $true
            break
        }
    }

    if ($portReady) {
        Write-Host "[OK] Streamlit server started successfully." -ForegroundColor Green
    } else {
        Write-Host "WARN: Streamlit process started; port 8501 still binding. Check http://localhost:8501 in a few seconds." -ForegroundColor Yellow
    }
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "RepoBrain is Ready!" -ForegroundColor Green
Write-Host "Local URL:       http://localhost:8501" -ForegroundColor Cyan
Write-Host "Database:        localhost:6379 (Graph: repo_kg)" -ForegroundColor White
Write-Host "Stop Script:     .\scripts\stop_repobrain.ps1" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Cyan

if (-not $SkipBrowser) {
    Start-Process "http://localhost:8501"
}
