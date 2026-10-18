# RepoBrain — Verification & Publishing Report

**Execution Timestamp:** 2026-10-18T18:49:30Z (2026-10-19 00:19:30 IST)  
**Assessor:** Autonomous Verification Pipeline (Google Antigravity IDE)  
**Target Repository:** [https://github.com/saksham-AI500/Graph_Hackathon-Company-Brain-](https://github.com/saksham-AI500/Graph_Hackathon-Company-Brain-)  
**Target Branch:** `main`  
**Active Account:** `saksham-AI500`  

---

## A. Repository State & Integrity

| Property | Value | Match |
| :--- | :--- | :---: |
| **Repository URL** | `https://github.com/saksham-AI500/Graph_Hackathon-Company-Brain-` | YES |
| **Visibility** | `PUBLIC` | YES |
| **Default Branch** | `main` | YES |
| **Local HEAD SHA** | `d49c68666871a8ed5de5a71b98df015f571266b0` | YES |
| **Remote HEAD SHA** | `d49c68666871a8ed5de5a71b98df015f571266b0` | YES |
| **Working Tree Status** | Clean (0 uncommitted changes, 0 untracked files) | YES |

---

## B. Commits Published in this Session

```
d49c686 docs: enhance README with live public demo, Stitch UI screenshots, 344 automated test metrics, and single-origin serving
ef1ce30 docs: publish final end-to-end verification report
69e24c5 merge: integrate deploy-demo single-origin serving, dockerfile, and deployment guides into main
aef037a docs: update verified screenshots, stitch reference assets, and verification scripts
0ce1999 feat(frontend): implement Stitch Ask screen 2 layout, Compare aggregate counters, and Playwright verification
0730720 feat(agent): support liquid tool call syntax, sanitize output tokens, and enforce grounded fallback on provider 429
0f7b5a8 docs: align README and reports with verified results
701171d chore: harden gitignore and untrack local secrets
f7ffa7d fix(agent): parse inline tool call tokens, strip raw markup, and fall back cleanly on provider daily quota exhaustion
d6a6e25 deploy: single-origin demo serving frontend and API with public-demo limits
7d48ecb feat(frontend): complete RepoBrain frontend with all pages, vitest, playwright e2e, and screenshots
05b8e84 feat(frontend): implement /evaluation page with benchmark stat cards, results table, and required disclaimer
79e3416 feat(frontend): implement /graph page with 80-node neighborhood canvas, inspect card, and animated SVG path
c1e0b61 feat(frontend): implement /compare page with dual columns and comparative metrics strip
511c849 feat(frontend): implement /ask page with verified badges, verifier countup, and evidence citations
602a076 feat(frontend): scaffold frontend and implement API schema layer with tests
f1ce035 feat(api): contract fixes, sample verification, and stitch asset export
```

---

## C. Verification Matrix (Every Step Checked)

| # | Check Name | Command | Result | Evidence File / Log |
| :-: | :--- | :--- | :---: | :--- |
| 1 | **Prerequisites & Auth** | `gh auth status` | **PASS** | Log: `saksham-AI500` active token verified |
| 2 | **Secrets & Hygiene Audit** | `git ls-files \| grep -Ei "\.env\|secret\|key\|token\|\.pem\|\.p12"` | **PASS** | Only `.env.example` and `design-tokens.json` tracked |
| 3 | **Git History Secret Scan** | Scan 49 commits for `sk-or-`, `gho_`, `ghp_` patterns | **PASS** | Only mock test fixtures found (`supersecretkey998877`), zero real secrets |
| 4 | **Python Test Suite** | `pytest -q` | **PASS** | 319 passed in 33.94s (`project_context/test_runs/20261018_183818Z/pytest.log`, SHA-256: `19e8cc8fa712f56bb3f1bd27675d4605633dc8fb42058313e094a69a76525696`) |
| 5 | **API Contract Verification** | `python scripts/check_contract.py` | **PASS** | Zero contract mismatches; all live & sample responses valid |
| 6 | **Ground-Truth Check** | `python scripts/verify_grounding.py` | **PASS** | 25/25 fixture entities, line numbers, and quotes verified (0 failed) |
| 7 | **Adversarial Verifier Tests** | `pytest tests/test_verifier_adversarial.py` | **PASS** | 14/14 adversarial boundary tests passed |
| 8 | **Control Verifier Tests** | `pytest tests/test_verifier_adversarial.py` | **PASS** | 20/20 control equivalence & timezone tests passed |
| 9 | **Compare Counter Audit** | `summary_development.json` verification | **PASS** | Recomputed: 12 on wins + 0 plain wins + 24 ties + 0 failed = 36 sum |
| 10 | **FalkorDB Running** | `docker ps -a --filter "name=falkordb"` | **PASS** | Container `0adfc551b896` healthy on port 6379 |
| 11 | **Graph Seed & Stats** | `GET /api/stats` | **PASS** | 325 indexed nodes, 531 indexed relations; 5,262 FalkorDB nodes |
| 12 | **Read-Only Answer Path** | Cypher write query AST audit | **PASS** | 0 `CREATE`/`MERGE`/`DELETE`/`SET` queries in answering path |
| 13 | **Graph Neighborhood** | `GET /api/graph/neighborhood` | **PASS** | `caleb-rivers`: 33 nodes, 37 edges; `payments/refund.py`: 2 nodes, 1 edge |
| 14 | **Frontend Typecheck** | `npm run typecheck` | **PASS** | `tsc --noEmit` exited with code 0 |
| 15 | **Frontend Lint** | `npm run lint` | **PASS** | ESLint 0 errors, 0 warnings |
| 16 | **Frontend Unit Tests** | `npm test -- --run` | **PASS** | 18/18 tests passed across 3 test files (Vitest) |
| 17 | **Frontend Build** | `npm run build` | **PASS** | Production bundle generated in 5.69s (`dist/`) |
| 18 | **Playwright E2E & Screens** | `npx playwright test` | **PASS** | 7/7 tests passed (29.0s); 9 screenshots saved to `docs/screenshots/` |
| 19 | **End-to-End graph_on** | `POST /api/ask` (`graph_on`) | **PASS** | Latency 779.8ms, verified claims, 0 fabricated citations |
| 20 | **End-to-End graph_off** | `POST /api/ask` (`graph_off`) | **PASS** | `status: ANSWERED_UNCERTAIN`, 0 fabricated citations |
| 21 | **Refusal Behavior** | `POST /api/ask` (on-call query) | **PASS** | `status: REFUSED`, 0 claims, clean non-hallucinating refusal |
| 22 | **Documentation Audit** | Review of `README.md` & `AI_DISCLOSURE.md` | **PASS** | Forbidden hype terms removed; accurate model and counts recorded |
| 23 | **Remote Branch Push** | `git push origin main` | **PASS** | `bd6dfc7..69e24c5 main -> main` pushed and verified |

---

## D. Test Suite Quantities

| Suite | Before Session | After Session | Status |
| :--- | :---: | :---: | :---: |
| **Pytest Full Suite** | 318 | **319** | PASS |
| **Adversarial Gate 2R Tests** | 14 | **14** | PASS |
| **Control Equivalence Tests** | 20 | **20** | PASS |
| **Mutation & Unit Tests** | 24 | **24** | PASS |
| **Frontend Vitest Tests** | 14 | **18** | PASS |
| **Playwright E2E Tests** | 6 | **7** | PASS |

---

## E. Ground-Truth and Contract Results

- **Contract Check (`scripts/check_contract.py`):**
  - Live and sample payloads verified for `/api/health`, `/api/stats`, `/api/ask` (`graph_on` & `graph_off`), `/api/compare`, `/api/eval/results`, and standardized error structures.
  - Result: **0 mismatches, 100% compliance**.
- **Ground-Truth Integrity (`scripts/verify_grounding.py`):**
  - 25 reference entities (issues, PR titles, review bodies, runbook lines, CODEOWNERS patterns, people logins, ADR decision quotes) verified.
  - Result: **25/25 Found: YES (PASS)**.

---

## F. Graph Database Metrics

- **Container:** Docker `falkordb` (`falkordb/falkordb:latest`)
- **Total FalkorDB Graph Nodes:** 5,262 (`PullRequest: 720`, `Issue: 350`, `Person: 56`, `Document: 47`, `Decision: 25`, `Comment: 4064`)
- **Total FalkorDB Graph Edges:** 11,340 (`REVIEWED: 4929`, `MODIFIES: 2840`, `RESOLVES: 350`, `AUTHORED: 720`, `REPORTED: 350`, `MEMBER_OF: 56`, `DISCUSSES: 2095`)
- **Fast Indexed Subgraph Cache:** 325 entities, 531 relations
- **Neighborhood Query (`caleb-rivers`):** 33 nodes, 37 edges returned (HTTP 200)

---

## G. Failures or Skipped Checks

- **None.** All 23 verification phases and tests passed cleanly.

---

## H. Known Risks & Disclosures

1. **Free Model Daily Rate Limits (`liquid/lfm-2.5-2.6b:free`):**
   - OpenRouter imposes a 50 requests/day limit on free-tier keys.
   - **Remediation implemented in this session:** The client immediately detects `free-models-per-day` throttling and falls back seamlessly to the deterministic grounded reasoning planner in under 1 second, ensuring public demo queries never crash or leak raw JSON.
2. **Holdout Set Status:**
   - Per Track 03 rules, the 30-question holdout evaluation must be conducted by an independent assessor and remains sealed (`Q2, Q4, Q6, Q8, Q10, Q12, Q16, Q20`).
3. **API Keys:**
   - No real API keys are committed or tracked in version control. All `.env` files are excluded by `.gitignore`.

---

## I. Commands to Run Demo from Clean Clone

```bash
# 1. Clone repository
git clone https://github.com/saksham-AI500/Graph_Hackathon-Company-Brain-.git
cd Graph_Hackathon-Company-Brain-

# 2. Start FalkorDB container (Docker)
docker run -d --name falkordb -p 6379:6379 -v repobrain_data:/var/lib/falkordb/data falkordb/falkordb:latest

# 3. Setup Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # (or source .venv/bin/activate on Linux/macOS)
pip install -r requirements.txt

# 4. Seed the Graph (offline deterministic seed)
python -m src.ingestion.run --seed

# 5. Build Frontend (if modifying sources)
cd frontend
npm install
npm run build
cd ..

# 6. Start Single-Origin Server (FastAPI serving React SPA + API)
python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000

# App will be accessible at: http://localhost:8000
```
