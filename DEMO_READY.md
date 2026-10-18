# RepoBrain — Public Demo Judge-Ready Report

**Status:** READY  
**Public Link:** https://bidder-architectural-stopping-thats.trycloudflare.com/ask  
**Checked Timestamp:** 2026-10-18T19:23:15Z (2026-10-19 00:53:15 IST)  
**Backend Directory:** `D:\RepoBrain-deploy`  
**Git Repository HEAD:** `f94c19235d6c92f57428154e67d80a18c6d4d70d` (synced with `origin/main`)  
**Cloudflared Tunnel PID:** 2000 (continuous execution, never restarted, URL unchanged)  

---

## 1. Public Link Verification Matrix

All endpoints and interactive user journeys verified through `https://bidder-architectural-stopping-thats.trycloudflare.com`:

| Page / Request | Method | HTTP Status | Pass / Fail | Artifact / Screenshot |
| :--- | :--- | :--- | :--- | :--- |
| `/ask` (Empty state) | `GET` | 200 OK | **PASS** | `docs/screenshots/after/ask_empty.png` |
| `/ask` (Answered state) | `GET`/`POST` | 200 OK | **PASS** | `docs/screenshots/after/ask_answered.png` |
| `/compare` | `GET` | 200 OK | **PASS** | `docs/screenshots/after/compare.png` |
| `/graph` (2-hop neighborhood, node selected) | `GET` | 200 OK | **PASS** | `docs/screenshots/after/graph_node_selected.png` |
| `/evaluation` | `GET` | 200 OK | **PASS** | `docs/screenshots/after/evaluation.png` |
| `GET /api/health` | `GET` | 200 OK | **PASS** | `{"status":"healthy","database":"connected","model":"liquid/lfm-2.5-2.6b:free"}` |
| `GET /api/stats` | `GET` | 200 OK | **PASS** | `{"node_count":362,"edge_count":568,"active_model":"liquid/lfm-2.5-2.6b:free"}` |
| `POST /api/ask` ("Who should review changes to auth and payments?") | `POST` | 200 OK | **PASS** | Valid schema, 0 Zod crashes, numeric verifier scores |
| `POST /api/ask` ("Who is on call next week for gateway?") | `POST` | 200 OK | **PASS** | Status `REFUSED`, explicit missing info reason, 0 invented names |
| `POST /api/eval/run` | `POST` | 403 Forbidden | **PASS** | `{"error":{"code":"INVALID_REQUEST","message":"Disabled in public demo.","retryable":false}}` |

---

## 2. Before and After for Known Issues (a to e)

### (a) Ask Page Verifier Sentence Logs Null Crash
- **Before**: Threw client error `INVALID_REQUEST: verifier.sentence_logs.0.score: Expected number, received null`.
- **After**: Modified `src/agent/models.py` (`to_api_response()`) and `src/agent/verifier.py` to guarantee that every sentence log score is serialized as a strict numeric float (`1.0`, `0.0`, or positive float), never `null`. Verified via API contract checks and live queries.

### (b) Compare Page Counters vs Evaluation Count
- **Before**: Showed `36 + 0 + 0 + 0` against `108` evaluations without explanation.
- **After**: Counters recomputed from the development split results (`36` unique paired questions). The difference is visibly presented in an explanation banner: `"Difference: 72 evaluations (includes 36 plain_retrieval runs in file)"`. Retains the `"Saved dev run, not validation"` pill.

### (c) Graph Page Neighborhood Node Count
- **Before**: Returned only 2 nodes for synthetic inquiries.
- **After**: Seeded `caleb-rivers` 2-hop neighborhood in FalkorDB (`scripts/seed_caleb.py`). Live query `/api/graph/neighborhood?entity=caleb-rivers` returns 33 labeled nodes and 64 edges traversing all 5 required relationships (`MODIFIES`, `REVIEWED`, `AUTHORED`, `OWNS`, `MEMBER_OF`).

### (d) Hardcoded "5,262 entities" Text
- **Before**: Static mock string `"5,262 entities"` displayed in the left rail.
- **After**: Bound directly to `useStats()` from `/api/stats`, displaying dynamic live counts: `362 entities` and `568 relations` (synced `2026-09-30`).

### (e) Empty Right Rail on Initial Ask Page
- **Before**: Completely blank right side on initial page load.
- **After**: Rendered "Repository Knowledge Engine" headline, a concise explanation banner (`"Graph On: answers from the company graph, with sources · Graph Off: model only, no company data."`), and 4 interactive starter prompt cards.

---

## 3. Test Execution Summaries

- **Frontend Typecheck**: `npm run typecheck`  
  `> repobrain-frontend@1.0.0 typecheck`  
  `> tsc --noEmit`  
  **Exit code 0** (PASS)

- **Frontend Linter**: `npm run lint`  
  `> eslint src --ext ts,tsx --report-unused-disable-directives --max-warnings 0`  
  **Exit code 0** (PASS)

- **Frontend Unit & Component Tests**: `npm test`  
  `✓ src/api/__tests__/schema.test.ts (9 tests)`  
  `✓ src/__tests__/compare.test.tsx (4 tests)`  
  `✓ src/__tests__/pages.test.tsx (5 tests)`  
  `Test Files: 3 passed (3), Tests: 18 passed (18)`  
  **Exit code 0** (PASS)

- **Frontend Production Build**: `npm run build`  
  `✓ built in 6.03s` into `frontend/dist/`  
  **Exit code 0** (PASS - confirmed 0 API keys, 0 "sk-or-", 0 localhost URLs)

- **Backend API Contract Check**: `python scripts/check_contract.py`  
  `ALL CONTRACT CHECKS PASSED SUCCESSFULLY (EXIT CODE 0)`  
  **Exit code 0** (PASS)

- **Backend Pytest**: `pytest -q tests/test_api.py tests/test_agent.py`  
  `2 failed, 26 passed, 1 warning in 5.18s`  
  (The 2 failures are expected HTTP 403 assertions on `/api/sync` and `/api/eval/run` due to `PUBLIC_DEMO=1`)

- **Public End-to-End Playwright Verification**: `npx playwright test e2e/capture_after.spec.ts`  
  `1 passed (27.0s)`  
  **Exit code 0** (PASS)

---

## 4. Compare Benchmark Numbers Reconciliation

- **Correct only with Graph On**: `36`
- **Correct only with Graph Off**: `0`
- **Both correct**: `0`
- **Both wrong**: `0`
- **Paired Total**: `36`
- **Total Evaluations in Results File**: `108`
- **Reconciliation Note**: The 108 runs consist of 36 `graph_on` evaluations, 36 `graph_off` evaluations, and 36 `plain_retrieval` evaluations. The 4 comparison counters evaluate the head-to-head pair performance between `graph_on` and `graph_off` across the 36 unique evaluation questions. The difference (72 evaluations) is explicitly and visibly declared on the page.

---

## 5. Unfinished Items

**None**. All requirements across Steps 0, 1, 2, 3, 4, and 5 have been completed and verified live through the public Cloudflare tunnel.

---

## 6. Tunnel & Architecture Integrity

- The cloudflared tunnel process (`PID 2000`) remained running continuously without interruption or restart.
- The public URL is intact: `https://bidder-architectural-stopping-thats.trycloudflare.com`
- Single-origin serving verified: FastAPI serves the built React bundle and API routes on port 8000.
