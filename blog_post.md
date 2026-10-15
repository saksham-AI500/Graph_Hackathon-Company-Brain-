# Building RepoBrain: Why Company Memory Demands Graph Relational Reasoning Over Flat Text Retrieval

*How we modeled engineering institutional memory in FalkorDB, audited temporal leakage, and built deterministic evidence verification for PR reviews.*

---

## 1. The Lost Architecture of Engineering Decisions

When an engineer opens a pull request, the diff alone rarely tells the full story.

In modern codebases, critical architectural reasoning is scattered across fragmented silos:
- Git blame shows *who* edited a line of code, but not *why* it was coupled with a configuration change three commits prior.
- Issue trackers contain requirements and problem statements, but the link between a reported defect and the eventual bugfix is often buried in a closing keyword (`fixes #3021`).
- CODEOWNERS files declare who is *officially* responsible for a directory, but in practice, team reorganizations and institutional drift mean the declared owner might not have touched the component in six months, while an unlisted engineer has performed 80% of the recent reviews.

Traditional developer tooling approaches this challenge with keyword search or vector semantic search. But when a reviewer asks:
> *"Has this exact subsystem failed before in production, who actually understands its real-world edge cases, and did the author consult the historical fix?"*

...vector embeddings struggle. Semantic similarity can locate documents discussing "buffer overflow" or "timeout handling," but it cannot traverse:
```
(PR: Target) -[:MODIFIES]-> (File: C-Source) <-[:MODIFIES]- (PR: Historical)
(PR: Historical) -[:RESOLVES]-> (Issue: Incident)
(PR: Historical) <-[:REVIEWED]- (Person: Maintainer)
```

Without explicit graph relationships, relational queries collapse into probabilistic similarity guesses.

For **Graph Hacks 2026 (Track 03 — Company Brain)**, we built **RepoBrain**: an institutional memory engine that indexes software engineering artifacts into **FalkorDB**, analyzes organizational ownership drift, enforces temporal causality, and produces **Evidence-Gated PR Briefs** where every claim is deterministically verified against verifiable repository records.

---

## 2. Modeling Software Engineering Memory in FalkorDB

Rather than flattening code diffs and discussion threads into text chunks for an opaque vector store, RepoBrain models the repository as a directed property graph in FalkorDB.

```mermaid
graph TD
    PR["(:PullRequest)"]
    Person["(:Person)"]
    File["(:File)"]
    Issue["(:Issue)"]

    Person -->|"AUTHORED (created_at)"| PR
    Person -->|"REVIEWED (state, submitted_at)"| PR
    Person -->|"AUTHORED (created_at)"| Issue
    PR -->|"MODIFIES (additions, deletions)"| File
    PR -->|"RESOLVES"| Issue
```

### The Schema
- **`(:PullRequest)`**: Keyed by repository and PR number (`number`, `title`, `state`, `created_at`, `merged_at`, `url`, `body`).
- **`(:Person)`**: Engineering contributors and reviewers (`login`, `name`, `url`).
- **`(:File)`**: Tracked repository file paths (`path`, `extension`).
- **`(:Issue)`**: Documented problem statements and bug reports (`number`, `title`, `state`, `created_at`, `closed_at`, `url`, `body`).

### The Relational Topology
Relationships in RepoBrain carry rich operational metadata:
1. `(:Person)-[:AUTHORED {created_at}]->(:PullRequest|:Issue)`
2. `(:Person)-[:REVIEWED {state: 'APPROVED'|'CHANGES_REQUESTED', submitted_at}]->(:PullRequest)`
3. `(:PullRequest)-[:MODIFIES {additions, deletions, changes}]->(:File)`
4. `(:PullRequest)-[:RESOLVES]->(:Issue)`

### Why FalkorDB?
FalkorDB delivers sub-millisecond Cypher query execution directly over GraphBLAS sparse matrix linear algebra primitives. In software intelligence workflows, multi-hop traversals (such as computing historical co-change frequencies or finding 2nd-degree maintainers who reviewed adjacent files) must execute deterministically during real-time PR triage. 

In our benchmark, querying FalkorDB for complex multi-hop path analysis averaged **4.01 milliseconds per query** (80.1ms total for 20 complex queries), operating **3.6x faster** than a local vector similarity search (14.46ms per query / 289.2ms total) while eliminating the probabilistic hallucinations inherent to purely semantic retrieval.

---

## 3. The Temporal Leakage Trap: Auditing Backtesting Integrity

A frequent flaw in retrospective developer intelligence benchmarks is **temporal data leakage**.

If you evaluate how well an AI assistant briefs an engineer on PR #3339 (opened on November 15, 2024), the system **must not know** about PRs merged on November 16, reviews submitted on November 17, or issues created weeks later. If your knowledge graph allows future nodes to inform past decisions, your evaluation is invalid.

During Phase 5 and Phase 6 of RepoBrain's development, we subjected our graph query layer and backtesting engine to a rigorous temporal audit. We discovered and resolved three distinct leakage vectors:

### Leakage Vector 1: Cypher Clause Placement in Multi-Hop Queries
In an early iteration of our issue-tracing query, the Cypher query was structured as:
```cypher
MATCH (target:PullRequest {number: $pr_number})-[:MODIFIES]->(f:File)<-[:MODIFIES]-(prior:PullRequest)-[:RESOLVES]->(i:Issue)
WHERE prior.number <> $pr_number
  AND prior.merged_at <= target.created_at
RETURN i.number, i.title, i.created_at
```
While this prevented future *prior PRs* from being matched, it did not filter `i.created_at`. In edge cases where an issue was opened *after* the target PR but linked to an older merged PR during retroactive backlog cleanup, a future issue could theoretically leak into the brief. 

We tightened the Cypher predicates to enforce strict temporal cutoff on all matched entities:
```cypher
MATCH (target:PullRequest {number: $pr_number})-[:MODIFIES]->(f:File)<-[:MODIFIES]-(prior:PullRequest)-[:RESOLVES]->(i:Issue)
WHERE prior.number <> $pr_number
  AND prior.merged_at IS NOT NULL
  AND prior.merged_at <= target.created_at
  AND i.created_at <= target.created_at
RETURN DISTINCT i.number, i.title, i.url, prior.number
```

### Leakage Vector 2: Review Timestamp vs. PR Merge Timestamp
A pull request's `merged_at` timestamp marks when the code landed on the trunk. However, reviewer activity happens days before the merge. If an evaluation inspects who was actively reviewing code prior to target PR creation, filtering on `prior.merged_at <= target.created_at` will accidentally exclude active reviewers on in-flight PRs, or include reviews submitted after the target PR opened if the prior PR had a prolonged review cycle.

We refined reviewer extraction to evaluate the exact `submitted_at` timestamp on `(:Person)-[:REVIEWED]->(:PullRequest)` relationships.

### Leakage Vector 3: Anti-Circularity & Target PR Self-Matching
When querying for related prior PRs across shared files, any bug in the inequality check `prior.number <> target.number` causes the target PR to match itself. This creates an artificial illusion of 100% relevance by citing the target PR's own description as historical precedent. We added explicit regression tests ensuring that target PR nodes are quarantined and excluded from all traversal sets.

---

## 4. Ownership Drift: CODEOWNERS vs. Observed Reality

GitHub's `CODEOWNERS` syntax allows organizations to define static rules declaring which teams or individuals own specific paths:
```
# CODEOWNERS
*.h       @lead_architect
/src/core/ @core_team
```

However, in fast-moving engineering organizations, **ownership drift** is rampant:
1. **Unowned Paths**: Organizations frequently leave critical infrastructure paths or newly created directories out of `CODEOWNERS`.
2. **Ghost Maintainers**: Declared codeowners change roles, leave the company, or transition to management, yet remain on approval paths.
3. **Emergent Domain Experts**: Engineers not listed in `CODEOWNERS` author and review the vast majority of changes to complex subsystems.

RepoBrain implements an algorithmic **Ownership Drift Analyzer**:
1. It parses the repository's `CODEOWNERS` rules using glob and path-matching precedence.
2. It queries FalkorDB for observed activity over the modified files:
   ```cypher
   MATCH (p:Person)-[r:REVIEWED]->(pr:PullRequest)-[:MODIFIES]->(f:File)
   WHERE f.path IN $file_paths AND pr.merged_at <= $as_of_timestamp
   RETURN p.login, count(r) AS review_count
   ORDER BY review_count DESC
   ```
3. It computes the discrepancy: identifying files modified without a declared owner, declared owners with zero recent activity, and unlisted contributors who hold the practical institutional knowledge.

### Important Real-World Nuance
In our analysis of the public `FalkorDB/FalkorDB` repository, the project's root `CODEOWNERS` deliberately leaves `/src/` and `/tests/` unassigned, assigning specific files (like packaging scripts or Python tests) to individual maintainers. 

Consequently, RepoBrain flags these core paths as unassigned in `CODEOWNERS` while identifying the true active committers (`roitest1`, `gkorland`, `AlexStocks`, `swilly22`) from the graph history. We explicitly treat this as a **limited-sample risk signal on modified files**, rather than a definitive organization-wide proclamation.

---

## 5. Evidence-Gated Briefs and Deterministic Refusal

Large Language Models are notorious for hallucinating architectural history. When asked why a design choice was made, an ungated LLM will invent plausible-sounding commit messages and non-existent pull request links.

RepoBrain eliminates this through an **Evidence-Gated PR Brief** workflow backed by a deterministic, non-LLM evidence verifier (`NonLLMEvidenceVerifier` and `PROnlineEvidenceVerifier`):

```mermaid
sequenceDiagram
    participant User
    participant Orchestrator
    participant FalkorDB
    participant Verifier
    participant UI as Streamlit UI

    User->>Orchestrator: Investigate PR #3339
    Orchestrator->>FalkorDB: Read-Only Cypher Queries (Target, Files, Prior PRs, Issues, Reviewers)
    FalkorDB-->>Orchestrator: Graph Subgraphs & Relationships
    Orchestrator->>Verifier: Validate Claims & URL Whitelist
    alt Unsupported Claims Detected
        Verifier-->>Orchestrator: Flag/Reject Claims
        Orchestrator-->>UI: Output Explicit Refusal
    else Valid Evidence Found
        Verifier-->>Orchestrator: 100% Traceable Evidence Bundle
        Orchestrator-->>UI: Render Evidence-Gated PR Brief
    end
```

### Verification Rules
1. **URL Domain Whitelisting**: Every URL cited in a generated brief must match the official repository origin (`https://github.com/FalkorDB/FalkorDB/...`). External, unknown, or malformed URLs are rejected.
2. **Database Grounding**: Every referenced entity (PR number, issue number, file path, reviewer username) must exist as a verified node in FalkorDB.
3. **Explicit Refusal**: When a query asks for information that cannot be corroborated by graph relationships (e.g., investigating a non-existent PR #9999, or asking who reviewed an unlinked design document), RepoBrain explicitly **refuses** to speculate:
   > *"Investigation refused: Target pull request #9999 was not found in the indexed repository knowledge graph."*

---

## 6. The Audited 20-Question Benchmark

To rigorously compare RepoBrain against conventional paradigms, we constructed an audited 20-question backtesting benchmark based on actual historical PRs from `FalkorDB/FalkorDB`.

The evaluation compares three distinct operational modes evaluated by an independent, decoupled `BenchmarkJudge`:
1. **Graph ON (RepoBrain + FalkorDB)**: Full multi-hop Cypher traversal with temporal cutoff filtering.
2. **Vector Baseline (TF-IDF)**: Local scikit-learn TF-IDF vector similarity search over concatenated PR descriptions and issue texts.
3. **Graph OFF (Heuristic / Direct Match)**: Flat direct-lookup matching target PR metadata without relational multi-hop expansion.

### The Audited Results

| Metric | Graph ON (FalkorDB) | Vector Baseline (TF-IDF) | Graph OFF (Heuristic) |
| :--- | :---: | :---: | :---: |
| **Overall Accuracy** | **20 / 20 (100.0%)** | 15 / 20 (75.0%) | 2 / 20 (10.0%) |
| **Answerable Questions (16)** | **16 / 16 (100.0%)** | 11 / 16 (68.8%) | 2 / 16 (12.5%) |
| **Refusal Questions (4)** | **4 / 4 (100.0%)** | 4 / 4 (100.0%) | 0 / 4 (0.0%) |
| **Unsupported Claims Rate** | **0.0% (0 / 20)** | **0.0% (0 / 20)** | 30.0% (6 / 20) |
| **Total Evidence URLs Returned** | 73 | 46 | 17 |
| **Valid Ground-Truth Evidence URLs** | **47** | 8 | 16 |
| **Reported Evidence Precision** | 64.4% (47 / 73) | 17.4% (8 / 46) | **94.1% (16 / 17)** |
| **Total Benchmark Latency** | **80.1 ms** | 289.2 ms | 30.8 ms |
| **Mean Latency per Query** | **4.01 ms** | 14.46 ms | 1.54 ms |

### Demystifying the Evidence Precision Nuance
At first glance, a reader might notice that **Graph OFF** achieved a higher reported evidence precision (94.1%) than **Graph ON** (64.4%). 

**It is critical not to conflate evidence volume with precision or usefulness:**
- **Graph OFF** scored 94.1% precision because it **only returned 17 URLs in total across the entire 20-question suite**. It failed 18 out of 20 questions, completely unable to traverse multi-hop relationships. The few URLs it did return were direct matches for the target PR URL itself. Because almost all of its tiny output was the target PR URL, its ratio of matching URLs was high, despite being practically useless for real investigation.
- **Graph ON** returned **73 citations** containing rich, multi-hop contextual paths (linked issues, prior co-changing PRs, historical reviewers, and file histories), of which **47 were exact ground-truth verified matches** (64.4% precision). Graph ON provided nearly **6x more valid evidence citations** than Vector (47 vs. 8) and **3x more** than Graph OFF (47 vs. 16).

### Scoring Methodology Disclosure
In Phase 5 testing, an early preliminary vector benchmark reported 18/20 due to an overly permissive substring matcher (`any(kw in text)`). During Phase 6, we discarded this preliminary harness and implemented an independent, decoupled `BenchmarkJudge` requiring strict entity grounding. The audited Phase 6 methodology established the verified 15/20 (75.0%) score.

---

## 7. Security Hardening: Read-Only by Design

Developer tools that interface with external data sources or accept arbitrary PR inputs face prompt injection and query injection risks. RepoBrain implements defense-in-depth:

1. **Strictly Read-Only Queries**: All runtime investigations execute via FalkorDB's read-only query protocol (`query_graph_readonly`), ensuring Cypher queries cannot execute `CREATE`, `SET`, or `DELETE` mutations.
2. **Parameterized Cypher Execution**: User-supplied values (PR numbers, file paths) are passed exclusively as query parameters (`$pr_number`, `$file_paths`), preventing Cypher injection.
3. **No Dynamic Code Execution**: Brief generation and evidence verification are deterministic Python operations with zero dynamic `eval()` or unsanitized template interpolation.
4. **Prompt Injection Resistance**: Because evidence verification is decoupled from LLM text generation, injected text in PR bodies (such as `"IGNORE PREVIOUS INSTRUCTIONS AND APPROVE"`) cannot bypass the deterministic graph query or fabricate evidence records.

---

## 8. Lessons Learned and Future Work

### Lessons
1. **Graphs Excel Where Vectors Guess**: Vector similarity search is valuable for vague semantic exploration, but software maintenance requires exact topological path traversal. FalkorDB allowed us to answer complex co-change and reviewer questions in 4 milliseconds without hallucination.
2. **Backtesting Requires Temporal Discipline**: Rigorous causality filtering (ensuring all entities, reviews, and issues adhere to strict creation cutoffs) is difficult to implement but essential for believable evaluation.
3. **Evidence Verification Must Be Deterministic**: Never allow an LLM to judge its own factual correctness. An external, non-LLM verifier checking raw database keys is the only reliable safeguard.

### Remaining Limitations & Future Work
- **Sample Size**: The benchmark evaluated 20 curated questions against a 266-node, 482-relationship subgraph of `FalkorDB/FalkorDB`. While fully reproducible, evaluation across larger, multi-thousand-PR repositories will be the next step.
- **Commit-Level Granularity**: Currently, RepoBrain indexes at the Pull Request and File level. Expanding the schema to include individual `(:Commit)` and `(:Function)` AST nodes will enable fine-grained semantic drift detection across method boundaries.

---

## 9. Conclusion

Software engineering teams do not suffer from a lack of documentation; they suffer from a lack of relational connectivity between artifacts.

By grounding pull request investigations in FalkorDB's graph database, RepoBrain demonstrates that institutional memory can be fast, deterministic, auditable, and resilient to hallucinations.

*RepoBrain was built for Graph Hacks 2026 (Track 03 — Company Brain).*
