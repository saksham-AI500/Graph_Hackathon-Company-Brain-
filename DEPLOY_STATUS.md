# RepoBrain Deployment Status & Final Verification Report

- **Date and Time**: 2026-10-18 23:44:00 IST (2026-10-18T18:14:00Z)
- **SOURCE Path**: `D:\grraph Hackathon\grraph Hackathon\RepoBrain`
- **Working Path**: `D:\RepoBrain-deploy`
- **Branch**: `deploy-demo`
- **Environment Variables Found in .env**:
  - `OPENROUTER_API_KEY`
  - `OPENROUTER_MODEL`

---

## A. Public Demo Link
- **PUBLIC_URL**: `https://bidder-architectural-stopping-thats.trycloudflare.com`
- **Backend Process PID**: 11708
- **Tunnel Status**: Active (Cloudflare Tunnel to `http://localhost:8000`)

---

## B. Verification Check Results

| Check Name | Command or Request | HTTP Status | Result | Evidence (Short) |
| :--- | :--- | :--- | :--- | :--- |
| **Local GET /** | `GET http://localhost:8000/` | **200** | PASS | Returns HTML index document (`<!doctype html>`) |
| **Local GET /ask** | `GET http://localhost:8000/ask` | **200** | PASS | Returns HTML index document for SPA route |
| **Local GET /compare** | `GET http://localhost:8000/compare` | **200** | PASS | Returns HTML index document for SPA route |
| **Local GET /api/health** | `GET http://localhost:8000/api/health` | **200** | PASS | `{"status":"healthy","database":"connected","model":"liquid/lfm-2.5-2.6b:free"}` |
| **Local GET /api/stats** | `GET http://localhost:8000/api/stats` | **200** | PASS | `{"node_count":323,"edge_count":531}` |
| **Local POST /api/eval/run** | `POST http://localhost:8000/api/eval/run` | **403** | PASS | `{"error":{"code":"INVALID_REQUEST","message":"Disabled in public demo.","retryable":false}}` |
| **Local POST /api/ask** | `POST http://localhost:8000/api/ask` | **200** | PASS | Evidence verification refused unbacked claims; structured answer returned |
| **Tunnel GET /** | `GET https://bidder-architectural-stopping-thats.trycloudflare.com/` | **200** | PASS | Returns HTML index document over public tunnel |
| **Tunnel GET /ask** | `GET https://bidder-architectural-stopping-thats.trycloudflare.com/ask` | **200** | PASS | Returns HTML index document over public tunnel |
| **Tunnel GET /api/health** | `GET https://bidder-architectural-stopping-thats.trycloudflare.com/api/health` | **200** | PASS | `status: healthy, database: connected` via public HTTPS |
| **Tunnel POST /api/eval/run** | `POST https://bidder-architectural-stopping-thats.trycloudflare.com/api/eval/run` | **403** | PASS | Public demo restriction enforced (`Disabled in public demo.`) |
| **Tunnel POST /api/ask** | `POST https://bidder-architectural-stopping-thats.trycloudflare.com/api/ask` | **200** | PASS | Response received through public tunnel with rate-limiting active |
| **External Request** | Public HTTPS GET `/api/health` | **200** | PASS | External verified status code 200 via Cloudflare edge |

---

## C. Test Summary Lines

- **Before Changes (Step 4.2)**: `319 passed in 30.47s`
- **After Changes (Step 4.4)**: `319 passed in 33.32s`

---

## D. Frontend Build & Secret Search Results

- **Frontend Build**:
  - Exit code: `0`
  - Output summary:
    ```
    dist/index.html                                                     0.54 kB │ gzip:   0.35 kB
    dist/assets/index-DG_G_I3x.css                                     58.93 kB │ gzip:  21.00 kB
    dist/assets/index-DtKCUakG.js                                     513.69 kB │ gzip: 150.81 kB
    ✓ built in 7.48s
    ```
- **Secret Search**:
  - Search for `"sk-or-"` in deploy files: **0 matches** (Passed)
  - Search for raw API key value in deploy files: **0 matches** (Passed)
  - Search in `frontend/dist/`: **0 matches** (Passed)

---

## E. Docker Container Image Result

- **Image Name**: `repobrain-demo`
- **Build Status**: Exit code `0`
- **Build Evidence**:
  ```
  #22 naming to docker.io/library/repobrain-demo:latest done
  #22 unpacking to docker.io/library/repobrain-demo:latest done
  ```
- **Container Execution Verification**:
  - Container started mapped to port 8001 with `--env-file .env`
  - `GET http://localhost:8001/api/health` returned HTTP `200` with `database: connected` and `model: liquid/lfm-2.5-2.6b:free`

---

## F. Git Deployment Status

- **Branch**: `deploy-demo`
- **Commit Message**: `deploy: single-origin demo serving frontend and API with public-demo limits`
- **Active GitHub Account**: `saksham-AI500`

---

## G. Known Issues / Error Log

- OpenRouter free tier (`liquid/lfm-2.5-2.6b:free`) has daily rate limits on the free key (`error: free-models-per-day: rate limit exceeded`). The backend gracefully catches and surfaces this according to API error contracts (`retryable: true` or error response).
- The public tunnel is ephemeral; restarting `cloudflared` generates a new tunnel URL (documented in `DEMO_LINK.md` and `DEPLOY.md`).

---

## H. Restart Commands

1. **FalkorDB**:
   ```bash
   docker start falkordb
   ```
2. **Backend**:
   ```powershell
   $env:PUBLIC_DEMO="1"
   .\.venv\Scripts\python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000
   ```
3. **Tunnel**:
   ```powershell
   cloudflared tunnel --url http://localhost:8000
   ```
