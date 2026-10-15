# RepoBrain — Risks, Blockers & Mitigations Matrix

**Status:** Pre-Kickoff Risk Assessment  
**Standard:** Proactive Failure Prevention (Ponytail & Superpowers)  

---

## Technical & Operational Risk Matrix

| Risk ID | Risk Description | Severity | Concrete Mitigation | Reverification / Test Step |
| :--- | :--- | :--- | :--- | :--- |
| **RSK-001** | **Python 3.14 Library Incompatibility**<br>New runtime lacks wheels for compiled packages. | **MEDIUM** | Verified pure-Python status of `falkordb` and official 3.14 wheels for `pydantic >= 2.12.0` and `streamlit`. Avoid legacy `pydantic.v1`. | Run import check (`falkordb`, `pydantic`, `streamlit`) immediately after virtualenv activation at kickoff. |
| **RSK-002** | **GitHub API Rate Limits**<br>Unauthenticated REST API calls capped at 60 requests/hour per IP. | **HIGH** | Ingest bounded batch (30 PRs, 30 issues). Save raw JSON in `.cache/` for offline repeatability. Set optional read-only `GITHUB_TOKEN` in system environment variables. | Ingestion script verifies local cache presence before issuing remote HTTP calls. |
| **RSK-003** | **Cypher Injection & Malformed Content**<br>PR descriptions contain unescaped quotes or markdown. | **HIGH** | Never format strings into Cypher. Pass all values via query parameters (`$param`). | Automated test passing PR titles containing double quotes and Cypher keywords. |
| **RSK-004** | **FalkorDB Read-Only Guard Bypass**<br>Agent tool accidentally attempts state mutation (`CREATE`, `SET`). | **CRITICAL** | Route all investigation queries through FalkorDB's native `GRAPH.RO_QUERY` command. | Automated test in Phase 7 (`test_safety_readonly.py`) asserting write rejection. |
| **RSK-005** | **Missing or Weak Evidence Paths**<br>Query returns an answer without connecting to verifiable PR or issue URLs. | **CRITICAL** | Mandatory absence rule: Non-LLM verifier returns `"Evidence path not found: [missing entity/relationship]"` whenever a path is absent. Never extrapolate. | Automated test asserting every record returned by `get_experts_for_file` contains valid URLs. |
| **RSK-006** | **Credential Exposure**<br>Tokens accidentally committed or printed. | **CRITICAL** | Zero tokens in code. Use `.gitignore` for `.env`. Read tokens only via `os.environ.get("GITHUB_TOKEN")`. | Automated grep check before git commits verifying no tokens exist in tracked files. |
| **RSK-007** | **Biased Vector Baseline Accusation**<br>Judges question whether the Graph OFF baseline was artificially handicapped. | **MEDIUM** | Use a credible vector baseline with identical prompt templates and context budgets. Fairly benchmark multi-hop reasoning. | Document exact embedding model and top-k retrieval parameters in `eval/metrics_report.md` and `blog_post.md`. |
| **RSK-008** | **Time Crunch During Hackathon**<br>Scope creep prevents shipping a working demo by the October 18 deadline. | **HIGH** | Strict feature trimming protocol: Cut Track 02 stretch first, cut MCP server second, cut multi-repo third. NEVER CUT evidence paths, FalkorDB queries, or read-only safety. | Daily milestone audit at phase boundaries against `PROGRESS.md`. |
| **RSK-009** | **Prompt Injection via Repository Content**<br>Adversarial issues containing directives to override system prompt. | **MEDIUM** | Isolate repository content strictly in graph properties; the agent prompt treats graph results as passive data items, not instruction directives. | Test query containing adversarial issue text and assert agent treats it as data. |
| **RSK-010** | **Temporal Evaluation Target Leakage**<br>Evaluating reviewer recommendations against historical data already ingested. | **MEDIUM** | Partition repository data chronologically: populate graph with events prior to timestamp $T$, test predictions strictly against PRs merged after $T$. | Automated test verifying that test PR IDs are absent from the populated graph during backtest. |
| **RSK-011** | **Non-LLM Verifier False Rejection**<br>Valid answers rejected due to rigid string or URL matching. | **LOW** | Unit test verifier independently against synthetic valid and invalid graph records before wiring to UI. | Automated test suite in `tests/test_verifier.py`. |

---

## Active Blockers

* **Current Blockers:** **NONE.** Environment (Python 3.14, Docker Engine 29.6.1, Antigravity IDE, Extensions, Superpowers, Ponytail, Context7) is fully verified.
* **Operational Gate:** All application code generation is held until the hackathon start window opens on **October 15, 2026, 12:01 AM IST**.
