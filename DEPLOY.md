# RepoBrain — Deployment Guide

RepoBrain is an evidence-backed repository knowledge engine built for **FalkorDB Graph Hacks 2026** (Track 03: Company Brain). It connects contributors, PRs, issues, files, and architectural decisions into FalkorDB (`repo_kg`), serving both a modern React frontend and a FastAPI backend on a single origin.

---

## 1. Environment Variables

The system is configured via environment variables. **Never commit secret values to version control.**

- `OPENROUTER_API_KEY`: API key for OpenRouter LLM inference (`liquid/lfm-2.5-2.6b:free`).
- `OPENROUTER_MODEL`: LLM model identifier (default: `liquid/lfm-2.5-2.6b:free`).
- `FALKORDB_HOST`: Hostname of the FalkorDB instance (default: `localhost`).
- `FALKORDB_PORT`: Port number of the FalkorDB instance (default: `6379`).
- `FALKORDB_PASSWORD`: Optional authentication password for FalkorDB / FalkorDB Cloud.
- `FALKORDB_TLS`: Enables TLS encryption for FalkorDB connections (`1` or `0`, default: `0`).
- `FALKORDB_GRAPH`: Target graph identifier (default: `repo_kg`).
- `PORT`: HTTP port for the FastAPI server (default: `8000`).
- `PUBLIC_DEMO`: Enables public demo restrictions when set to `1` (default: `0`).

---

## 2. Start Commands in Order

### Step 1: Start FalkorDB
```bash
# Launch FalkorDB in Docker with persistent named volume
docker run -d --name falkordb -p 6379:6379 -v repobrain_falkordb-data:/var/lib/falkordb/data falkordb/falkordb:latest

# Seed the graph if not already populated (idempotent MERGE)
python -m src.ingestion.run --seed
```

### Step 2: Start Backend Server (with Public-Demo Mode)
```bash
# Powershell
$env:PUBLIC_DEMO="1"
python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000

# Bash
PUBLIC_DEMO=1 python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```

### Step 3: Start Cloudflare Tunnel
```bash
cloudflared tunnel --url http://localhost:8000
```

---

## 3. Public-Demo Mode Limits

When `PUBLIC_DEMO=1` is active:
- `POST /api/eval/run` returns HTTP `403 Forbidden` (`{"error": {"code": "INVALID_REQUEST", "message": "Disabled in public demo.", "retryable": false}}`).
- `POST /api/sync` returns HTTP `403 Forbidden` (`{"error": {"code": "INVALID_REQUEST", "message": "Disabled in public demo.", "retryable": false}}`).
- `POST /api/ask` is strictly rate-limited to **20 requests per minute** per client IP. Requests exceeding this limit receive HTTP `429 Too Many Requests` (`{"error": {"code": "PROVIDER_RATE_LIMIT", "message": "Rate limit exceeded. Maximum 20 requests per minute in public demo.", "retryable": true}}`).

---

## 4. Hosted Deployment Steps (e.g. Cloud Run / Render / VPS)

1. Build the production container image:
   ```bash
   docker build -t repobrain-demo .
   ```
2. Configure the deployment environment with the required environment variables:
   - Point `FALKORDB_HOST` to your FalkorDB Cloud endpoint (e.g., `xyz.falkordb.cloud`).
   - Set `FALKORDB_PORT` and `FALKORDB_PASSWORD`.
   - Set `FALKORDB_TLS=1` only if the cloud instance requires TLS/SSL encryption.
   - Provide `OPENROUTER_API_KEY`.
   - Set `PORT` (assigned by cloud host) and `PUBLIC_DEMO=1`.
3. Run the container:
   ```bash
   docker run -d -p 8000:8000 --env-file .env repobrain-demo
   ```
