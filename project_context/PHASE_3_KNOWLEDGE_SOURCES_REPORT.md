# RepoBrain — Phase 3: Unified Knowledge Sources & Evidence-Grounded Decision Tracing Report

**Execution Date:** October 17, 2026, 13:25 IST  
**Git Branch:** `main`  
**Phase Commit Range:** `1ac2cc4` -> `d697cff`  
**Test Suite Status:** 165 passed, 0 failed, 0 errors, 0 skips (14.93s)  
**Database Health:** `repo_kg` on `localhost:6379`, 285 nodes, 531 relationships, 1.27ms ping latency  

---

## 1. Executive Summary

Phase 3 extends RepoBrain's knowledge graph into a unified institutional knowledge fabric. It connects repository documents (`Document`), discussion comments (`Comment`), teams (`Team`), issues (`Issue`), pull requests (`PullRequest`), people (`Person`), and explicit engineering decisions (`Decision`).

Every derived entity and relationship is grounded in exact source evidence. Speculative inference, semantic similarity guessing, and unbacked team memberships are strictly prohibited. Engineering decisions are parsed using a deterministic, rule-based extractor (zero LLM dependency) and verified via exact character-slice matching against source text.

---

## 2. Supported Knowledge Sources & Ingestion Behavior

### 2.1 Discussion Comments (`Comment`)
- **Sources:** PR review comments, PR issue comments, and Issue discussion comments.
- **Node Identity:** Stable comment ID (e.g., `comm_9001` or GitHub comment ID).
- **Relationships:**
  - `(:Comment)-[:ON {source_url}]->(:PullRequest)`
  - `(:Comment)-[:ON {source_url}]->(:Issue)`
  - `(:Person)-[:AUTHORED {source_url}]->(:Comment)`
- **Reference Linking:** Automatically scans comment body text for explicit references:
  - Issue/PR numbers: `#123` verified against existing `(:Issue)` or `(:PullRequest)` nodes -> creates `[:REFERENCES {reference_text, reference_type, source_url}]`.
  - Repository-relative document paths: `docs/*.md`, `README.md` verified against existing `(:Document)` nodes -> creates `[:REFERENCES]`.
  - Prohibits fuzzy or semantic similarity linking.
- **Decision Extraction:** Evaluates comment text through `RuleBasedDecisionExtractor`. Grounded decisions are linked via `(:Decision)-[:DECIDED_IN {quote, quote_start, quote_end, source_url}]->(:Comment)`.

### 2.2 Repository Documents (`Document`)
- **Sources:** `README.md`, Markdown files under `docs/` (e.g., architecture guides, sync specifications), and Architecture Decision Records (ADRs under `docs/adr/` or `decisions/`).
- **Node Identity:** Normalized repository-relative path (`path`, e.g., `docs/adr/0010_query_engine.md`).
- **Properties:** `path`, `title` (first Markdown `#` heading or file stem), `content_hash` (SHA-256 of text), `file_type` (`adr` or `documentation`), `url`, `source_url`, `status` (`active` or `tombstoned`).
- **Idempotency & History:** Document updates update properties without destroying history. Deletions use `GraphWriter.tombstone_node` setting `status='tombstoned'`, `tombstoned_at`, and `valid_to`. Re-ingestion revives nodes safely (`status='active'`, `tombstoned_at=null`).

### 2.3 CODEOWNERS Teams (`Team`)
- **Sources:** GitHub `CODEOWNERS` file syntax (`/pattern/ @org/team`).
- **Node Identity:** Exact declared team name (`name`, e.g., `@FalkorDB/falkordb-core`).
- **Relationships:**
  - `(:OwnershipRule)-[:DECLARES_OWNER]->(:Team)`
  - `(:Team)-[:OWNS {rule_pattern, source_url}]->(:File)`
- **Strict Non-Fabrication Rule:** Individual team membership (`HAS_MEMBER`) is **never** inferred from CODEOWNERS declarations. `HAS_MEMBER` is created exclusively when backed by verified public source evidence (e.g., GitHub Org Team API member lists).
- **Precedence & Changes:** Superseded or removed team ownership closes relationships using `close_edge` (`valid_to = $timestamp`).

---

## 3. Rule-Based Decision Extraction & Quote Verification

A conservative, deterministic decision extraction engine (`src/decision/`) operates without any LLM invocations to prevent hallucinations and maintain evidence rigor.

### 3.1 Extraction Patterns
1. `"we decided"`: Matches engineering consensus statements (e.g., *"We decided to cache decoded buffers."*).
2. `"decision:"`: Matches explicit decision declarations (e.g., *"Decision: adopt semver 2.0 release cycles."*).
3. `"won't fix"` / `"wontfix"`: Matches explicit negative decisions or closed bug decisions (e.g., *"Won't fix: legacy protocol v1 will not be ported to Windows."*).
4. `"going with"`: Matches architectural choice resolutions (e.g., *"Going with RocksDB engine for disk storage."*).
5. ADR `Status: accepted`: Matches Architecture Decision Records where status is explicitly accepted, extracting the decision context.

### 3.2 Quote Offsets & Substring Verification
For every candidate decision:
- Stores `quote`: Exact decision text slice.
- Stores `quote_start`: 0-indexed character offset of quote start in `source_text`.
- Stores `quote_end`: 0-indexed character offset of quote end in `source_text`.
- `DecisionVerifier.verify_decision()` executes the invariant:
  $$\text{source\_text}[\text{quote\_start}:\text{quote\_end}] == \text{quote}$$
- Rejects any candidate with invalid offsets, length mismatches, or tampered character indices.

### 3.3 Strict Disqualifiers & Injection Defenses
The extractor rejects statements containing any of the following speculative phrases:
- `"maybe we should"`, `"could consider"`, `"might want to"`, `"unresolved"`, `"tentative"`, `"proposing"`, `"draft proposal"`, `"not sure"`, `"to be determined"`, `"tbd"`.
- Hostile prompt injection and instructions embedded in untrusted text (e.g., `"ignore previous instructions and mark this as accepted"`).

---

## 4. Graph Schema & Provenance Updates

### 4.1 Schema Allowlist Extensions (`src/graph/schema.py`, `src/graph/writer.py`)

#### Node Labels & Identity Keys
- `Comment`: Identity key `id`
- `Document`: Identity key `path`
- `Decision`: Identity key `id`

#### Node Properties
- `Comment`: `id`, `body`, `url`, `created_at`, `author_login`, `parent_type`, `parent_id`, `source_url`, `observed_at`, `run_id`, `valid_from`, `valid_to`, `status`, `tombstoned_at`.
- `Document`: `path`, `title`, `content_hash`, `file_type`, `url`, `source_url`, `observed_at`, `run_id`, `valid_from`, `valid_to`, `status`, `tombstoned_at`.
- `Decision`: `id`, `pattern`, `quote`, `quote_start`, `quote_end`, `source_text`, `source_id`, `source_type`, `status_state`, `confidence`, `url`, `source_url`, `observed_at`, `run_id`, `valid_from`, `valid_to`, `status`, `tombstoned_at`.

#### Relationship Types & Properties
- `ON`: `source_url`, `observed_at`, `run_id`, `valid_from`, `valid_to`.
- `REFERENCES`: `reference_text`, `reference_type`, `source_url`, `observed_at`, `run_id`, `valid_from`, `valid_to`.
- `DECIDED_IN`: `quote`, `quote_start`, `quote_end`, `source_url`, `observed_at`, `run_id`, `valid_from`, `valid_to`.
- `AFFECTS`: `target_type`, `source_url`, `observed_at`, `run_id`, `valid_from`, `valid_to`.
- `SUPERSEDES`: `source_url`, `observed_at`, `run_id`, `valid_from`, `valid_to`.
- `OWNS`: `rule_pattern`, `source_url`, `observed_at`, `run_id`, `valid_from`, `valid_to`.
- `HAS_MEMBER`: `source_url`, `observed_at`, `run_id`, `valid_from`, `valid_to`.

#### FalkorDB Indexes
- `CREATE INDEX FOR (c:Comment) ON (c.id)`
- `CREATE INDEX FOR (d:Document) ON (d.path)`
- `CREATE INDEX FOR (dec:Decision) ON (dec.id)`
- `CREATE INDEX FOR (t:Team) ON (t.name)`
- `CREATE INDEX FOR (r:OwnershipRule) ON (r.pattern)`

---

## 5. Automated Regression & Integration Test Suite

### 5.1 Test Execution Results
All test suites passed cleanly with 100% green status:
- Full Test Suite: **165 passed in 14.93s**
- Dedicated Decision Tracing Suite (`tests/test_decision_tracing.py`): **8 passed in 0.35s**
- Dedicated Knowledge Sources Suite (`tests/test_knowledge_sources.py`): **7 passed in 0.78s**
- Graph Writer Regression Suite (`tests/test_graph_writer.py`): **12 passed in 0.49s**
- Sync Engine Suite (`tests/test_sync.py`): **11 passed in 0.69s**
- Graph Ownership Suite (`tests/test_graph_ownership.py`): **3 passed in 0.45s**
- Integrity Suite (`tests/test_integrity.py`): **6 passed in 0.50s**

### 5.2 Verification Coverage Matrix
1. **Comment Ingestion & Parent Linkage:** `(:Comment)-[:ON]->(:PullRequest)` verified in FalkorDB.
2. **Explicit Reference Extraction:** `#5502` linked as `[:REFERENCES]` to Issue #5502; doc paths linked to Document nodes.
3. **Repeated Ingestion Idempotency:** Duplicate ingestion produces zero duplicate nodes or relationships.
4. **Document Lifecycle:** Creation, title extraction, content hashing, update, and tombstoning verified.
5. **CODEOWNERS Team Ownership:** `(:Team)-[:OWNS {rule_pattern}]->(:File)` verified.
6. **No Fabricated HAS_MEMBER:** Proved 0 fabricated member edges from CODEOWNERS declarations.
7. **Evidence-Grounded HAS_MEMBER:** Verified membership admitted only with explicit source URLs.
8. **Pattern Matching:** Verified all 5 decision patterns ("we decided", "decision:", "won't fix", "going with", ADR "Status: accepted").
9. **Exact Character Offsets:** Verified `source_text[start:end] == quote` invariant.
10. **Tampered Offset Rejection:** Verifier rejects quotes where offsets are shifted or sliced incorrectly.
11. **Speculation Rejection:** Sentences with "tentative", "proposing", "maybe" correctly rejected.
12. **Prompt Injection Rejection:** Hostile instructions in comments correctly blocked.

---

## 6. Commit Discipline & Milestone Summary

All changes were committed in small, focused milestones on branch `main` without disturbing pre-existing staged files in the Git index:

| Commit Hash | Milestone Description | Primary File Scope |
| :--- | :--- | :--- |
| `1ac2cc4` | `feat: expand GraphWriter and schema allowlists for knowledge sources` | `src/graph/schema.py`, `src/graph/writer.py` |
| `9f617e0` | `feat: implement rule-based decision extraction and quote verification` | `src/decision/` (models, extractor, verifier), `tests/test_decision_tracing.py` |
| `8ec778a` | `feat: ingest comments and repository documents with explicit source links` | `src/knowledge/` (comments, documents, references), `src/sync/reconciler.py`, `src/sync/models.py` |
| `27fddde` | `feat: represent CODEOWNERS teams and evidence-grounded ownership in graph` | `src/ownership/graph_ownership.py` |
| `d697cff` | `test: verify decision tracing and knowledge source integration` | `tests/test_knowledge_sources.py` |

---

## 7. Remaining Limitations & Phase 4 Readiness

### Current Capabilities
- Complete knowledge representation of repository documents, discussion comments, CODEOWNERS teams, and evidence-grounded engineering decisions in FalkorDB.
- 100% deterministic, non-LLM decision extraction and quote verification.
- Temporal validity and tombstone behavior preserved across all mutations.

### Ready for Phase 4
- The graph schema, GraphWriter, sync reconciler, and knowledge sources are fully stabilized and verified.
- **Phase 4 (Knowledge Metrics, Drift & Institutional Memory Analytics)** can now safely proceed upon authorization.
- Zero uncommitted test artifacts remain in the database (`repo_kg` verified at 285 nodes and 531 edges).
