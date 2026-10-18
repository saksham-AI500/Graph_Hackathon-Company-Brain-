<#
.SYNOPSIS
    Stops RepoBrain services (Streamlit Web UI and optionally FalkorDB container).
.DESCRIPTION
    Safely stops the Streamlit application. Optionally stops the FalkorDB
    Docker container using 'docker compose stop' (non-destructive; preserves volumes).
#>

[CmdletBinding()]
param(
    [switch]$StopDatabase
)

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$WorkspaceRoot = (Resolve-Path "$ScriptDir\..").Path

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "RepoBrain - Shutdown Manager" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Stop Streamlit Web Application
Write-Host "Locating active Streamlit processes..." -ForegroundColor Gray
$stoppedAny = $false

# Identify processes listening on port 8501
try {
    $connections = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
    if ($connections) {
        $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($procId in $pids) {
            $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if ($p) {
                Write-Host "  Stopping process $($p.ProcessName) (PID: $procId)..." -ForegroundColor Yellow
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                $stoppedAny = $true
            }
        }
    }
} catch {
    Write-Host "WARN: Could not query port 8501 listeners." -ForegroundColor Yellow
}

if ($stoppedAny) {
    Write-Host "[OK] Streamlit application stopped cleanly." -ForegroundColor Green
} else {
    Write-Host "INFO: No active Streamlit process detected on port 8501." -ForegroundColor Gray
}

# 2. Stop FalkorDB Docker Service (Optional)
if ($StopDatabase) {
    Write-Host "Stopping FalkorDB service via 'docker compose stop'..." -ForegroundColor Yellow
    Set-Location -Path $WorkspaceRoot
    & docker compose stop falkordb
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] FalkorDB container stopped (Volumes and data preserved)." -ForegroundColor Green
    } else {
        Write-Host "WARN: 'docker compose stop' returned code $LASTEXITCODE." -ForegroundColor Yellow
    }
} else {
    Write-Host "INFO: FalkorDB container left running on port 6379." -ForegroundColor Gray
    Write-Host "      (To stop database too, pass -StopDatabase flag)." -ForegroundColor Gray
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "RepoBrain Shutdown Complete." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
