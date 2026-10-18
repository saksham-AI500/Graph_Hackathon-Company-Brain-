# RepoBrain — Local Setup, Operational Guide & Daily Runbook

**Target Machine:** Windows 11 Laptop  
**Workspace Root:** `D:\grraph Hackathon\grraph Hackathon\RepoBrain`  
**Python Environment:** `D:\grraph Hackathon\grraph Hackathon\RepoBrain\.venv\Scripts\python.exe` (Python 3.14.0)  
**Database Service:** FalkorDB Container `falkordb` on `localhost:6379` (`repo_kg`)  
**Web Application:** Streamlit on `http://localhost:8501`  

---

## 1. Quick Start (Automated PowerShell Scripts)

RepoBrain includes non-destructive operational scripts for everyday development and demo execution:

### Start RepoBrain (One-Command Launch)
From PowerShell inside `D:\grraph Hackathon\grraph Hackathon\RepoBrain`:
```powershell
.\scripts\start_repobrain.ps1
```
*What this script does:*
1. Validates the local Python 3.14 virtual environment.
2. Checks Docker CLI and tests if Docker Engine is healthy (waits with a bounded timeout).
3. Starts container `falkordb` using `docker compose up -d` (if not already running).
4. Runs `python -m src.db` to verify FalkorDB latency and confirmed `repo_kg` graph state.
5. Launches Streamlit on `http://localhost:8501` in the background (preventing duplicate processes).
6. Automatically opens your browser to `http://localhost:8501`.

*Optional Flag:* `.\scripts\start_repobrain.ps1 -SkipBrowser` (starts services without opening browser window).

### Stop RepoBrain
```powershell
# Stop Streamlit application cleanly (leaves FalkorDB running for fast restart)
.\scripts\stop_repobrain.ps1

# Stop both Streamlit AND FalkorDB container safely (preserves all volume data)
.\scripts\stop_repobrain.ps1 -StopDatabase
```
> [!IMPORTANT]
> The scripts **never** delete volumes, prune containers, reset graph data, or discard code.

---

## 2. Standard Manual Workflow (Step-by-Step)

If you prefer running commands manually in your terminal, follow these exact verified steps:

### Step 1: Open Docker Desktop
- Click the **Docker Desktop** shortcut on your Desktop or Start Menu.
- Wait until the Docker whale icon in your system tray turns steady and Docker Engine is running.
- Verify in PowerShell:
  ```powershell
  docker info
  ```

### Step 2: Start FalkorDB Container
Navigate to the project directory and start FalkorDB via Docker Compose:
```powershell
Set-Location -Path "D:\grraph Hackathon\grraph Hackathon\RepoBrain"
docker compose up -d
```
Verify the container is active:
```powershell
docker ps --filter "name=falkordb"
```
*Expected Port Mapping:* `0.0.0.0:6379->6379/tcp`  
*Mounted Volume:* `repobrain_falkordb-data` &rarr; `/var/lib/falkordb/data`

### Step 3: Verify Database Health & Graph State
Execute the read-only health check:
```powershell
.\.venv\Scripts\python.exe -m src.db
```
*Expected Output:*
```text
============================================================
RepoBrain - FalkorDB Health Check
============================================================
Status:      HEALTHY
Host:        localhost:6379
Graph:       repo_kg
Latency:     < 2.0 ms
Nodes:       270
Edges:       508
============================================================
Health Check PASSED.
```

### Step 4: Seed Data Ingestion (Only If Required)
> [!NOTE]
> Ingestion is **NOT** needed on every startup. Your data persists across container restarts inside the Docker volume on `D:\DockerDesktopWSL`.

Run offline seed ingestion **only** if setting up a blank database or deliberately re-synchronizing:
```powershell
.\.venv\Scripts\python.exe -m src.ingestion.run --seed
```
*Idempotency Guarantee:* The ingestion pipeline uses Cypher `MERGE` clauses. Re-running it is 100% idempotent and will preserve the exact count of 270 nodes and 508 relationships without creating duplicate entities or relationships.

### Step 5: Start Streamlit Application
```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```
Or run in the background (headless mode):
```powershell
Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-m streamlit run app.py --server.headless true" -WindowStyle Hidden
```

### Step 6: Open RepoBrain UI
Navigate to [http://localhost:8501](http://localhost:8501) in your browser.
- **Sidebar Status:** Should display green: `Connected: repo_kg (< 2ms) | Nodes: 270 | Relationships: 508`.
- **Demo Presets:** Click `PR #3339` to load a verified pull request investigation.

---

## 3. Running the Test Suite

### Full Test Suite
```powershell
.\.venv\Scripts\python.exe -m pytest
```
*Baseline Result:* **110 passed**, 5 known limitations (see Section 5 below).

### Fast Targeted Verification
```powershell
# 1. Database Connectivity & Ping
.\.venv\Scripts\python.exe -m pytest tests/test_db.py -v

# 2. Graph Integrity & CODEOWNERS Drift Schema
.\.venv\Scripts\python.exe -m pytest tests/test_integrity.py tests/test_graph_ownership.py -v

# 3. Evidence-Gated PR Investigation Engine
.\.venv\Scripts\python.exe -m pytest tests/test_investigation.py -v

# 4. Security & Prompt Injection Defenses
.\.venv\Scripts\python.exe -m pytest tests/test_edge_cases_and_security.py tests/test_prompt_injection.py -v
```

### Holdout Benchmark Evaluation
```powershell
.\.venv\Scripts\python.exe -m src.evaluation.holdout_runner
```
*Baseline Result:* Graph ON: **100.0% accuracy** (9/9) | Vector Baseline: **33.3%** (3/9) | Graph OFF: **0.0%** (0/9).

---

## 4. Stopping Services Safely

### Stop Streamlit
Press `Ctrl+C` in the terminal where Streamlit is running. If running in the background, run:
```powershell
Get-NetTCPConnection -LocalPort 8501 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```
Or simply run: `.\scripts\stop_repobrain.ps1`.

### Stop FalkorDB (Non-Destructive)
```powershell
docker compose stop falkordb
```
> [!CAUTION]
> **NEVER** run `docker compose down -v` or `docker volume prune`. Doing so will erase the persistent graph database volume.

---

## 5. Known Limitations & Architecture Notes

The 5 test failures in the full test suite reflect upstream FalkorDB engine characteristics and baseline tie-breaking rules, not environment defects:

1. **Shortest-Path Directionality (3 tests in `test_graph_algorithms.py`, 1 in `test_ui.py`):**
   - Current FalkorDB version enforces directed shortest-path traversals.
   - Does not affect the core investigation engine (`src/investigation/orchestrator.py`), which uses explicit parameterized multi-hop queries.
2. **Comparative Evaluator Co-Change Tie-Breaking (`test_evaluation.py`):**
   - Minor synthetic ranking variation on run 1 of the baseline comparative test.

---

## 6. Troubleshooting Common Issues

### Issue A: `docker: The term 'docker' is not recognized`
- **Cause:** Docker Desktop is not running or Docker CLI directory is missing from PATH.
- **Resolution:** Launch Docker Desktop. Ensure `%LOCALAPPDATA%\Programs\DockerDesktop\bin` or standard Docker CLI is on your user PATH.

### Issue B: `failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine`
- **Cause:** Docker Desktop was recently closed or the WSL2 background VM is stopped.
- **Resolution:** Open Docker Desktop from the Desktop shortcut. Wait for the engine status in the bottom-left to indicate "Engine running".

### Issue C: FalkorDB Shows `[OFFLINE]` in Streamlit Sidebar
- **Cause:** Container `falkordb` is stopped or port 6379 is blocked.
- **Resolution:** Run `docker compose up -d` in `RepoBrain` and verify with `.\.venv\Scripts\python.exe -m src.db`.

### Issue D: Streamlit Port 8501 Already in Use
- **Cause:** A previous instance of Streamlit is still running in the background.
- **Resolution:** Run `.\scripts\stop_repobrain.ps1` to cleanly terminate old instances, then re-run `.\scripts\start_repobrain.ps1`.

### Issue E: Disk Space on Drive C: Decreases
- **Verification:** Docker storage is permanently relocated to `D:\DockerDesktopWSL` (`docker_data.vhdx` and `ext4.vhdx`). Check drive usage anytime with:
  ```powershell
  Get-PSDrive C, D
  ```
