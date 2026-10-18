# RepoBrain Backend API Contract

This document provides the definitive REST API contract for the RepoBrain Backend service (Track 03 — Company Brain).
It is generated directly from the Pydantic models in `src/api/server.py` and `src/agent/models.py`, validated against real sample JSON responses produced by the live running API server and saved under `docs/api_samples/`.

Every field is cross-referenced with the sample JSON payloads. Fields declared in Pydantic models but omitted from serialized output are explicitly annotated as **declared, not returned**. Fields present in the serialized output that are computed dynamically are explicitly annotated as **returned, dynamically added**.

---

## 1. Global Enums & Constants

### Product Mode (`mode`)
- `"graph_on"`: Full graph-grounded agent with read-only Cypher graph tools, claim verifier, and structured source attribution.
- `"graph_off"`: Same base LLM route and prompt, zero tools, zero repository access.

### Verification Status (`status`)
- `"VERIFIED"`: All claims verified against active graph records with inline citations `[S#]`.
- `"PARTIALLY_VERIFIED"`: Some claims verified; others marked unresolved.
- `"ANSWERED_UNCERTAIN"`: Model provided an answer without full evidence support.
- `"REFUSED"`: Query unanswerable, out of scope, ambiguous, or asks for private data.

### Claim Type (`type` / `claim_type`)
- `"fact"` / `"OWNERSHIP"`, `"DECISION"`, `"KNOWLEDGE"`: Grounded factual assertion.
- `"inference"` / `"PR_INVESTIGATION"`, `"STALENESS"`: Supported deductive reasoning.
- `"unresolved"` / `"GENERAL"`: Claim that cannot be confirmed with repository data.

### Verification Path (`verification_path`)
- `"exact_lookup"`: Direct property or index match in graph/CODEOWNERS.
- `"structured"`: Subgraph relation traversal or Cypher constraint validation.
- `"nli_prose"`: Natural language inference entailment over document text.
- `"temporal_filter"`: Cutoff timestamp enforcement.

---

## 2. Endpoints Specification

### 2.1 `GET /api/health`
Checks backend service availability, database connectivity, and active model.

- **Request**: No parameters or body.
- **Response Fields**:
  - `status` (`string`): Service health status. *Enum: `["healthy"]`*.
  - `service` (`string`): Service identifier string (`"RepoBrain Backend API"`).
  - `timestamp` (`string`): ISO-8601 UTC timestamp.
  - `database` (`string`): Graph database connectivity state. *Enum: `["connected", "disconnected"]`*.
  - `model` (`string`): Active LLM model slug.
- **Sample File**: [`docs/api_samples/get_api_health.json`](docs/api_samples/get_api_health.json)

---

### 2.2 `GET /api/stats`
Returns graph database metrics, node and edge counts by category, and model identifier.

- **Request**: No parameters or body.
- **Response Fields**:
  - `node_count` (`integer`): Total active graph nodes in database.
  - `edge_count` (`integer`): Total active graph relationships in database.
  - `nodes_by_label` (`object`): Dictionary mapping label names to integer counts (`PullRequest`, `Issue`, `Person`, `Document`, `Decision`, `Comment`).
  - `edges_by_type` (`object`): Dictionary mapping relationship types to integer counts (`REVIEWED`, `MODIFIES`, `RESOLVES`, `AUTHORED`, `REPORTED`, `MEMBER_OF`, `DISCUSSES`).
  - `last_synced_at` (`string`): ISO-8601 UTC timestamp of last repository sync.
  - `active_model` (`string`): Currently configured live model route.
- **Sample File**: [`docs/api_samples/get_api_stats.json`](docs/api_samples/get_api_stats.json)

---

### 2.3 `POST /api/ask`
Answers an engineering query under `graph_on` or `graph_off` mode with grounded claims and evidence.

- **Request Body (`AskRequest`)**:
  - `question` (`string`, required): The engineering question to answer. Cannot be blank.
  - `mode` (`string`, optional, default: `"graph_on"`): Product mode. *Enum: `["graph_on", "graph_off"]`*.
  - `as_of` (`string | null`, optional, nullable): Optional ISO-8601 temporal cutoff.
  - `previous_answer_id` (`string | null`, optional, nullable): Cache key of previous answer for diff calculation.

- **Response Fields (`to_api_response()`)**:
  - `status` (`string`): Overall answer verification status. *Enum: `["VERIFIED", "PARTIALLY_VERIFIED", "ANSWERED_UNCERTAIN", "REFUSED"]`*.
  - `answer` (`string`): Markdown response containing inline citations `[S1]`, `[S2]`.
  - `context` (`string`): Temporal context summary (e.g., `"As of latest synchronized data"`).
  - `ranking` (`array of objects`): Domain maintainer/reviewer rankings (`[]` when none):
    - `rank` (`integer`): 1-indexed reviewer ranking.
    - `login` (`string`): GitHub username.
    - `score` (`number`): Review affinity score.
    - `reasons` (`array of strings`): Grounded justifications.
    - `source_ids` (`array of strings`): Citing source IDs.
    - `tied` (`boolean`): Whether rank is tied.
  - `reasoning` (`string`): Chain-of-thought or resolution reasoning trace.
  - `claims` (`array of objects`): List of factual assertions:
    - `id` (`string`): Claim identifier (e.g. `"C1"`).
    - `text` (`string`): Proposition text.
    - `type` (`string`): Claim classification. *Enum: `["fact", "inference", "unresolved"]`*.
    - `source_ids` (`array of strings`): Citing source IDs (e.g. `["S1"]`).
    - `verified` (`boolean`): True if claim is verified by evidence.
    - `verification_path` (`string`): Verification path (`"exact_lookup"`, `"structured"`, `"nli_prose"`, `"temporal_filter"`).
  - `excluded` (`array of objects`): Excluded candidate reviewers (`[]` when none):
    - `login` (`string`): Excluded actor username.
    - `reason` (`string`): Reason for exclusion (e.g. `"PR author"`, `"Bot"`).
    - `end_date` (`string | null`): Expiration or cutoff date.
  - `unresolved` (`array of strings`): Questions or gaps that could not be resolved.
  - `sources` (`array of objects`): Supporting evidence sources:
    - `id` (`string`): Source citation tag (e.g. `"S1"`).
    - `entity` (`string`): Entity identifier or relative path (e.g. `"payments/refund.py"`).
    - `entity_type` (`string`): Entity category (e.g. `"file"`, `"pr"`, `"issue"`, `"doc"`, `"comment"`).
    - `url` (`string`): Canonical GitHub or documentation URL.
    - `date` (`string`): ISO-8601 date string or empty string.
    - `quote` (`string`): Raw text snippet or quotation from source.
  - `mode` (`string`): Mode executed. *Enum: `["graph_on", "graph_off"]`*.
  - `as_of` (`string | null`, nullable): Temporal cutoff used.
  - `synced_at` (`string`): ISO-8601 timestamp of graph data state.
  - `model` (`string`): Model slug used for generation or evaluation.
  - `tool_calls` (`array of objects`): Execution trace of tools called:
    - `tool` (`string`): Name of the tool called.
    - `args` (`object`): Dictionary of tool invocation arguments.
    - `result_count` (`integer`): Number of records returned.
    - `ms` (`number`): Execution time in milliseconds.
  - `verifier` (`object`): Evidence verification audit ledger:
    - `claims_total` (`integer`): Total claims evaluated.
    - `claims_passed` (`integer`): Claims backed by evidence.
    - `claims_fully_supported` (`integer`): Claims with zero unresolved points.
    - `sources_valid` (`integer`): Valid, resolvable source items.
    - `sources_total` (`integer`): Total source citations evaluated.
    - `sentences_total` (`integer`): Total factual sentences evaluated.
    - `sentences_passed` (`integer`): Sentences passing inline citation verification.
    - `post_hoc_citations` (`integer`): Count of ungrounded post-hoc citations.
    - `fabricated_citations` (`integer`, *returned in graph_off*): Citations fabricated without tools.
    - `sentence_logs` (`array of objects`): Sentence-level verification logs:
      - `sentence` (`string`): Evaluated sentence text.
      - `claim_ids` (`array of strings`): Linked claim IDs.
      - `cited_sources` (`array of strings`): Linked source citation tags.
      - `verification_path` (`string`): Verification strategy. *Enum: `["exact_lookup", "structured", "nli_prose", "temporal_filter"]`*.
      - `score` (`number`): NLI or lookup confidence score (0.0 to 1.0).
      - `passed` (`boolean`): Whether sentence passed verification gate.
      - `reason` (`string | null`, nullable): Rejection reason if failed.
  - `what_changed` (`object | null`, optional, nullable): Populated only when `previous_answer_id` is supplied.

- **Internal Model Fields Omitted from API Output**:
  - `AgentAnswer.step_count`: *Internal execution metric; omitted from external response*.
  - `AgentAnswer.tools_used`: *Internal summary; omitted from external response in favor of `tool_calls`*.
  - `AgentAnswer.execution_log`: *Internal execution trace; omitted from external response in favor of `reasoning`*.
  - `AgentAnswer.model_used`: *Mapped directly to `model`*.
  - `AgentAnswer.fresh_checked`: *Internal cache flag; omitted from external response*.
  - `AgentAnswer.refusal_reason`: *Integrated directly into `answer` / `status`*.
  - `Claim.unresolved_reason`: *Internal claim state; omitted from external response*.

- **Sample Files**:
  - [`docs/api_samples/post_api_ask_graph_on.json`](docs/api_samples/post_api_ask_graph_on.json)
  - [`docs/api_samples/post_api_ask_graph_off.json`](docs/api_samples/post_api_ask_graph_off.json)

---

### 2.4 `POST /api/compare`
Executes both `graph_on` and `graph_off` pipelines on the same query and returns side-by-side answers and comparison metrics.

- **Request Body (`CompareRequest`)**:
  - `question` (`string`, required): Question to evaluate comparatively.
  - `as_of` (`string | null`, optional, nullable): Optional ISO-8601 temporal cutoff.

- **Response Fields**:
  - `question` (`string`): The evaluated question text.
  - `as_of` (`string | null`, nullable): Temporal cutoff used.
  - `graph_on` (`object`): Full answer object matching `POST /api/ask` structure.
  - `graph_off` (`object`): Full answer object matching `POST /api/ask` structure.
  - `comparison` (`object`): Comparative analysis summary:
    - `on_status` (`string`): Verification status of `graph_on` answer (`"VERIFIED"`, `"PARTIALLY_VERIFIED"`, `"ANSWERED_UNCERTAIN"`, `"REFUSED"`).
    - `off_status` (`string`): Verification status of `graph_off` answer.
    - `on_claims_count` (`integer`): Number of claims generated under `graph_on`.
    - `off_claims_count` (`integer`): Number of claims generated under `graph_off`.
    - `on_sources_count` (`integer`): Number of sources cited under `graph_on`.
    - `off_sources_count` (`integer`): Number of sources cited under `graph_off`.
    - `fabricated_citations_in_off` (`integer`): Citations fabricated in `graph_off` mode.
    - `verified` (`boolean`): Whether `graph_on` achieved verified status.
    - `difference_counts` (`object | null`, nullable): Breakdown of difference metrics against ground-truth rubrics if a rubric exists for the question; `null` otherwise:
      - `claims_diff` (`integer`): Difference in claims generated (`on - off`).
      - `sources_diff` (`integer`): Difference in sources cited (`on - off`).
      - `facts_passed_diff` (`integer`): Difference in verified facts (`on - off`).
      - `violations_diff` (`integer`): Difference in rubric violations (`off - on`).
- **Sample File**: [`docs/api_samples/post_api_compare.json`](docs/api_samples/post_api_compare.json)

---

### 2.5 `GET /api/graph/neighborhood`
Retrieves the 1-hop and 2-hop neighborhood (nodes and edges) for a given entity identifier for graph visualization.

- **Request Query Parameters**:
  - `entity` (`string`, required): Identifier of entity (e.g. `marcus-vance`, `44`, `payments/checkout.py`, `ADR-0004`).
  - `as_of` (`string`, optional, nullable): Optional temporal cutoff.

- **Response Fields**:
  - `entity` (`string`): Entity identifier queried.
  - `as_of` (`string | null`, nullable): Temporal cutoff applied.
  - `node_count` (`integer`): Number of neighborhood nodes returned.
  - `edge_count` (`integer`): Number of neighborhood edges returned.
  - `nodes` (`array of objects`): List of graph nodes:
    - `id` (`string`): Unique node identifier.
    - `label` / `labels` (`string` or `array of strings`): Graph label(s).
    - `properties` (`object`): Node attribute key-value pairs (`name`, `login`, `team`, `title`, `url`, `state`, etc.).
  - `edges` (`array of objects`): List of graph relationships:
    - `source` (`string`): Source node ID.
    - `target` (`string`): Destination node ID.
    - `type` (`string`): Relationship type (e.g. `"MEMBER_OF"`, `"KNOWS"`, `"AUTHORED"`, `"DECLARED_OWNER"`).
    - `properties` (`object`, optional): Edge properties (e.g. `score`).
- **Sample File**: [`docs/api_samples/get_api_graph_neighborhood.json`](docs/api_samples/get_api_graph_neighborhood.json)

---

### 2.6 `POST /api/sync`
Triggers an incremental graph synchronization run from the repository event feed.

- **Request Body**: Empty JSON object `{}`.
- **Response Fields**:
  - `run_id` (`string`): Unique sync execution ID (e.g. `"sync_1792329118"`).
  - `repo` (`string`): Target repository slug (`"saksham-AI500/company-brain-synthetic-testbed"`).
  - `status` (`string`): Sync completion status. *Enum: `["completed", "failed"]`*.
  - `events_processed` (`integer`): Number of synthetic event records scanned.
  - `mutations_applied` (`integer`): Number of graph mutations committed.
  - `failures` (`integer`): Count of unhandled event errors.
  - `dry_run` (`boolean`): Whether run was in simulation mode.
  - `synced_at` (`string`): ISO-8601 UTC timestamp of synchronization.
  - `changes` (`array of objects`): List of processed change records:
    - `id` (`string`): Change event identifier.
    - `entity` (`string`): Target entity name (e.g. `"PR #720"`).
    - `type` (`string`): Entity category. *Enum: `["PullRequest", "Issue", "Comment", "Document"]`*.
    - `action` (`string`): Mutation action. *Enum: `["MERGED", "CLOSED", "DECISION_RECORDED", "MODIFIED"]`*.
    - `timestamp` (`string`): ISO-8601 timestamp of mutation.
    - `summary` (`string`): Human-readable summary of change.
    - `author` (`string`): Actor login.
- **Sample File**: [`docs/api_samples/post_api_sync.json`](docs/api_samples/post_api_sync.json)

---

### 2.7 `GET /api/changes`
Fetches recent repository mutations, pull requests, issue resolutions, and decision updates.

- **Request Query Parameters**:
  - `since` (`string`, optional, nullable): Optional ISO-8601 timestamp cutoff.

- **Response Fields**:
  - `since` (`string | null`, nullable): Cutoff timestamp applied.
  - `count` (`integer`): Total changes returned.
  - `changes` (`array of objects`): Feed of mutation events:
    - `id` (`string`): Change event ID.
    - `entity` (`string`): Entity identifier.
    - `type` (`string`): Entity type.
    - `action` (`string`): Action type.
    - `timestamp` (`string`): ISO-8601 timestamp.
    - `summary` (`string`): Change description.
    - `author` (`string`): Actor username.
    - `url` (`string`): Canonical GitHub link.
- **Sample File**: [`docs/api_samples/get_api_changes.json`](docs/api_samples/get_api_changes.json)

---

### 2.8 `POST /api/eval/run`
Executes the evaluation harness on a specified split and product mode.

- **Request Body (`EvalRunRequest`)**:
  - `split` (`string`, required, default: `"dev"`): Dataset split. *Enum: `["dev", "failure", "holdout"]`*.
  - `mode` (`string`, optional, default: `"graph_on"`): Product mode. *Enum: `["graph_on", "graph_off"]`*.
  - `limit` (`integer | null`, optional, nullable): Maximum questions to evaluate.
  - `repetitions` (`integer`, optional, default: `1`): Number of repetitions per question.

- **Response Fields**:
  - `split` (`string`): Split evaluated. *Enum: `["dev", "failure", "holdout"]`*.
  - `mode` (`string`): Mode evaluated. *Enum: `["graph_on", "graph_off"]`*.
  - `total_questions` (`integer`): Number of questions executed.
  - `correct_count` (`integer`): Questions matching rubric expectations.
  - `accuracy` (`number`): Ratio of correct questions (0.0 to 1.0).
  - `supported_count` (`integer`): Questions with verified factual grounding.
  - `refusal_correct_count` (`integer`): Questions where refusal matched rubric expectation.
  - `mean_latency_ms` (`number`): Average execution latency per question.
  - `results` (`array of objects`): Question-level evaluation breakdown:
    - `id` (`string`): Question identifier (e.g. `"Q1"`, `"FAIL-01"`).
    - `question` (`string`): Question prompt.
    - `mode` (`string`): Mode evaluated.
    - `status` (`string`): Result status. *Enum: `["VERIFIED", "PARTIALLY_VERIFIED", "ANSWERED_UNCERTAIN", "REFUSED"]`*.
    - `is_refusal` (`boolean`): Whether response was a refusal.
    - `refusal_correct` (`boolean`): Whether refusal behavior was expected.
    - `correct` (`boolean`): Whether answer met rubric correctness.
    - `supported` (`boolean`): Whether all claims were verified.
    - `latency_ms` (`number`): Turn execution time in milliseconds.
    - `claims_count` (`integer`): Count of claims generated.
    - `sources_count` (`integer`): Count of sources cited.
    - `answer_preview` (`string`): First 120 characters of answer.
- **Sample File**: [`docs/api_samples/post_api_eval_run.json`](docs/api_samples/post_api_eval_run.json)

---

### 2.9 `GET /api/eval/results`
Returns saved development evaluation results directly from disk (`project_context/eval_v2/summary_development.json`) without calling the live model.

- **Request**: No parameters or body.
- **Response Fields**:
  - `run_id` (`string`): Unique evaluation run ID (e.g. `"dev_v2_20261017_112444"`).
  - `timestamp` (`string`): ISO-8601 UTC timestamp of evaluation completion.
  - `split_name` (`string`): Evaluated dataset split (`"development"`).
  - `architectures` (`object`): Aggregated statistics per architecture (`graph_on`, `plain_retrieval`):
    - `total_evaluations` (`integer`): Total number of question evaluations executed.
    - `overall_accuracy_pct` (`number`): Accuracy percentage against benchmark rubrics.
    - `citation_support_rate_pct` (`number`): Percentage of claims supported by evidence citations.
    - `unsupported_claim_rate_pct` (`number`): Percentage of unsupported claims (0.0% in graph_on).
    - `mean_latency_ms` (`number`): Average latency per turn in milliseconds.
  - `results` (`array of objects`): Question-level breakdown records across all repetitions.
- **Sample File**: [`docs/api_samples/get_api_eval_results.json`](docs/api_samples/get_api_eval_results.json)

---

## 3. Standardized Error Contract

All error responses across all endpoints adhere strictly to the format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description of error",
    "retryable": false
  }
}
```

### Error Codes
- `"MISSING_KEY"`: Missing or invalid authentication credentials (HTTP 401). `retryable: false`.
- `"PROVIDER_CREDITS"`: Upstream provider balance exhausted or credit limit reached (HTTP 402). `retryable: false`.
- `"PROVIDER_RATE_LIMIT"`: Upstream model provider rate limit throttled (HTTP 429). `retryable: true`.
- `"BACKEND_UNAVAILABLE"`: Internal server error or unhandled backend dependency failure (HTTP 500/503). `retryable: true`.
- `"INVALID_REQUEST"`: Malformed request payload, missing required parameters, or validation failure (HTTP 400). `retryable: false`.

