# Deployment Status - RepoBrain

- **Date and Time**: 2026-10-18 23:46:00 IST (2026-10-18T18:16:00Z)
- **SOURCE Path**: `D:\grraph Hackathon\grraph Hackathon\RepoBrain`
- **Working Path**: `D:\RepoBrain-deploy`
- **Branch**: `deploy-demo`
- **Environment Variables**:
  - `OPENROUTER_MODEL`: `liquid/lfm-2.5-2.6b:free`
  - `PUBLIC_DEMO`: `1`
  - `FALKORDB_HOST`: `localhost`
  - `FALKORDB_PORT`: `6379`
  - `FALKORDB_GRAPH`: `repo_kg`

---

## 1. Prerequisites Check
- **git**: git version 2.55.0.windows.2 (PASS)
- **Python**: Python 3.14.0, pip 25.3 (PASS)
- **Node.js**: v24.18.0, npm 11.16.0 (PASS)
- **Docker**: Docker Engine 29.8.2 (`docker info` succeeded) (PASS)
- **cloudflared**: cloudflared version 2026.10.1 (PASS)
- **OPENROUTER_API_KEY**: Present in `.env` (PASS)

---

## 2. Graph Database (FalkorDB)
- **Container**: `falkordb` running on port 6379
- **Graph**: `repo_kg`
- **Status**: Connected
- **Indexed Entities**: 323 nodes
- **Indexed Relations**: 531 edges
- **Health Endpoint**: `GET /api/health` returns `status: healthy, database: connected`

---

## 3. Production Frontend & Backend Integration
- **Frontend Build**: Production bundle generated via Vite (`npm run build`) in `frontend/dist/`
- **Static Hosting**: Served directly via FastAPI single-origin mount in `src/api/server.py`
- **Routes Served**:
  - `/` -> Landing / Main Interface
  - `/ask` -> Ask Screen (Graph Augmented Layout)
  - `/compare` -> Model Comparison Screen
  - `/graph` -> Interactive Graph Visualization
  - `/evaluation` -> Benchmark Evaluation Results

---

## 4. Public Demo Hardening (`PUBLIC_DEMO=1`)
- **Write Operations**:
  - `POST /api/eval/run`: HTTP 403 Forbidden (`Disabled in public demo.`)
  - `POST /api/sync`: HTTP 403 Forbidden (`Disabled in public demo.`)
- **Rate Limiting**:
  - `POST /api/ask`: Throttled to 20 req/min per IP
- **Model Output Sanitization**:
  - Parser added for inline text tool call tokens emitted by `liquid/lfm-2.5-2.6b:free` (`<|tool_call_start|>` / `<|tool_call_end|>`)
  - Text sanitizer ensures raw tokens never leak into the user UI

---

## 5. Live Public Demo URL
- **Public URL**: `https://bidder-architectural-stopping-thats.trycloudflare.com`
- **Tunnel Provider**: Cloudflare Named Tunnel (`cloudflared`)
- **Status**: ACTIVE & VERIFIED

### Verification Matrix
| Endpoint | Method | Expected Status | Live Status | Result |
| :--- | :--- | :--- | :--- | :--- |
| `/` | GET | 200 (HTML) | 200 OK | PASS |
| `/ask` | GET | 200 (HTML) | 200 OK | PASS |
| `/compare` | GET | 200 (HTML) | 200 OK | PASS |
| `/graph` | GET | 200 (HTML) | 200 OK | PASS |
| `/evaluation` | GET | 200 (HTML) | 200 OK | PASS |
| `/api/health` | GET | 200 (JSON) | 200 OK | PASS |
| `/api/stats` | GET | 200 (JSON) | 200 OK | PASS |
| `/api/eval/results` | GET | 200 (JSON) | 200 OK | PASS |
| `/api/graph/neighborhood?entity=caleb-rivers` | GET | 200 (JSON) | 200 OK | PASS |
| `/api/eval/run` | POST | 403 (JSON) | 403 Forbidden | PASS |
| `/api/sync` | POST | 403 (JSON) | 403 Forbidden | PASS |
