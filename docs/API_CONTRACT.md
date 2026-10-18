# RepoBrain Backend API Contract

This document defines the complete HTTP REST API contract for the RepoBrain Backend (Track 03 — Company Brain).
It specifies all 8 endpoints, request/response models with exact types, validation constraints, and sample JSON payloads for frontend integration.

---

## Base Configuration

- **Default Base URL**: `http://localhost:8000`
- **Content-Type**: `application/json`
- **CORS**: Enabled for all origins (`*`)
- **Supported Modes**: Strictly `graph_on` and `graph_off`

---

## Summary of Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health, FalkorDB status, active LLM model |
| `POST` | `/api/ask` | Primary question answering (Graph ON / Graph OFF) |
| `POST` | `/api/compare` | Dual-mode comparison on a single question |
| `GET` | `/api/graph/neighborhood` | 1-hop and 2-hop graph neighborhood for entity view |
| `POST` | `/api/sync` | Incremental repository event sync trigger |
| `GET` | `/api/changes` | Repository mutation change feed |
| `GET` | `/api/stats` | Graph metrics (node/edge counts) and active model |
| `POST` | `/api/eval/run` | Evaluation harness runner for dev, failure, or holdout |

---

## 1. `GET /api/health`

Returns service health, database connection state, and active LLM model.

### Request
- **Headers**: None
- **Query Parameters**: None
- **Body**: None

### Response (`200 OK`)
```json
{
  "status": "healthy",
  "service": "RepoBrain Backend API",
  "timestamp": "2026-10-18T13:00:00.000000+00:00",
  "database": "connected",
  "model": "nvidia/nemotron-3.5-lightning:free"
}
```

### Response Fields
- `status` (`string`): Service health status (`"healthy"`).
- `service` (`string`): Service identifier.
- `timestamp` (`string`): ISO-8601 UTC timestamp.
- `database` (`string`): Connection status of graph database (`"connected"`).
- `model` (`string`): Active LLM model slug.

---

## 2. `POST /api/ask`

Answers an engineering question under `graph_on` or `graph_off` mode.

### Request Body (`AskRequest`)
```json
{
  "question": "Who owns payments/refund.py according to CODEOWNERS?",
  "mode": "graph_on",
  "as_of": "2026-09-30T23:59:59Z",
  "previous_answer_id": null
}
```

### Request Fields
- `question` (`string`, required): The engineering question to be answered.
- `mode` (`string`, optional, default: `"graph_on"`): Must be either `"graph_on"` or `"graph_off"`.
- `as_of` (`string | null`, optional): ISO-8601 timestamp cutoff for temporal point-in-time answers.
- `previous_answer_id` (`string | null`, optional): Cache key of previous answer to compute diffs.

### Response (`200 OK`)
```json
{
  "answer": "According to CODEOWNERS, payments/refund.py is owned by Marcus Vance [S1].",
  "status": "VERIFIED",
  "claims": [
    {
      "claim_id": "C1",
      "text": "payments/refund.py is owned by Marcus Vance",
      "source_ids": ["S1"],
      "verified": true
    }
  ],
  "sources": [
    {
      "source_id": "S1",
      "uri": "repo://CODEOWNERS#L14",
      "title": "CODEOWNERS rule: payments/refunds/ -> @marcus-vance",
      "entity_type": "OwnershipRule",
      "verified": true
    }
  ],
  "verifier": {
    "status": "VERIFIED",
    "claims_total": 1,
    "claims_passed": 1,
    "claims_fully_supported": 1,
    "sources_total": 1,
    "sources_valid": 1,
    "sentences_total": 1,
    "sentences_passed": 1,
    "post_hoc_citations": 0
  },
  "tools_used": ["who_owns"],
  "mode": "graph_on",
  "model": "nvidia/nemotron-3.5-lightning:free",
  "what_changed": null
}
```

---

## 3. `POST /api/compare`

Runs dual execution on the question: both `graph_on` and `graph_off`, returning side-by-side answers and comparison metrics.

### Request Body (`CompareRequest`)
```json
{
  "question": "Who owns payments/refund.py according to CODEOWNERS?",
  "as_of": null
}
```

### Response (`200 OK`)
```json
{
  "question": "Who owns payments/refund.py according to CODEOWNERS?",
  "as_of": null,
  "graph_on": {
    "answer": "According to CODEOWNERS, payments/refund.py is owned by Marcus Vance [S1].",
    "status": "VERIFIED",
    "claims": [...],
    "sources": [...]
  },
  "graph_off": {
    "answer": "I do not have access to the repository CODEOWNERS file and cannot verify ownership.",
    "status": "REFUSED",
    "claims": [],
    "sources": []
  },
  "comparison": {
    "on_status": "VERIFIED",
    "off_status": "REFUSED",
    "on_claims_count": 1,
    "off_claims_count": 0,
    "on_sources_count": 1,
    "off_sources_count": 0,
    "fabricated_citations_in_off": 0,
    "verified": true
  }
}
```

---

## 4. `GET /api/graph/neighborhood`

Fetches nodes and edges representing the 1-hop and 2-hop neighborhood of a given entity (person, issue, PR, file, or ADR) for interactive graph visualization.

### Request
- **Query Parameters**:
  - `entity` (`string`, required): Entity identifier (e.g. `marcus-vance`, `44`, `payments/checkout.py`, `ADR-0004`).
  - `as_of` (`string`, optional): ISO-8601 temporal cutoff.

### Example Request
`GET /api/graph/neighborhood?entity=marcus-vance`

### Response (`200 OK`)
```json
{
  "entity": "marcus-vance",
  "as_of": null,
  "node_count": 5,
  "edge_count": 4,
  "nodes": [
    {
      "id": "marcus-vance",
      "labels": ["Person"],
      "properties": {
        "name": "Marcus Vance",
        "login": "marcus-vance",
        "team": "team-payments"
      }
    },
    {
      "id": "team-payments",
      "labels": ["Team"],
      "properties": {
        "name": "Payments Core"
      }
    }
  ],
  "edges": [
    {
      "source": "marcus-vance",
      "target": "team-payments",
      "type": "MEMBER_OF",
      "properties": {}
    }
  ]
}
```

---

## 5. `POST /api/sync`

Triggers an incremental graph synchronization run from the repository event feed.

### Request
- **Headers**: None
- **Body**: `{}` (empty JSON object or null)

### Response (`200 OK`)
```json
{
  "run_id": "sync_1760792400",
  "repo": "saksham-AI500/company-brain-synthetic-testbed",
  "status": "completed",
  "events_processed": 3,
  "mutations_applied": 3,
  "failures": 0,
  "dry_run": true,
  "synced_at": "2026-10-18T13:00:00.000000+00:00",
  "changes": [
    {
      "id": "chg_720",
      "entity": "PR #720",
      "type": "PullRequest",
      "action": "MERGED",
      "timestamp": "2026-09-30T18:00:00Z",
      "summary": "Optimize pool checkout timeout and add retry jitter",
      "author": "marcus-vance"
    }
  ]
}
```

---

## 6. `GET /api/changes`

Retrieves the recent change feed of repository mutations (merged PRs, closed issues, decisions, and documentation updates).

### Request
- **Query Parameters**:
  - `since` (`string`, optional): ISO-8601 timestamp cutoff to return changes after this time.

### Example Request
`GET /api/changes?since=2026-09-29T00:00:00Z`

### Response (`200 OK`)
```json
{
  "since": "2026-09-29T00:00:00Z",
  "count": 3,
  "changes": [
    {
      "id": "chg_720",
      "entity": "PR #720",
      "type": "PullRequest",
      "action": "MERGED",
      "timestamp": "2026-09-30T18:00:00Z",
      "summary": "Optimize pool checkout timeout and add retry jitter",
      "author": "marcus-vance",
      "url": "https://github.com/saksham-AI500/company-brain-synthetic-testbed/pull/720"
    }
  ]
}
```

---

## 7. `GET /api/stats`

Returns graph topology metrics (total nodes, total edges, distribution by label and type), last sync timestamp, and active model.

### Request
- **Headers**: None
- **Body**: None

### Response (`200 OK`)
```json
{
  "node_count": 5262,
  "edge_count": 11340,
  "nodes_by_label": {
    "PullRequest": 720,
    "Issue": 350,
    "Person": 56,
    "Document": 47,
    "Decision": 25,
    "Comment": 4064
  },
  "edges_by_type": {
    "REVIEWED": 4929,
    "MODIFIES": 2840,
    "RESOLVES": 350,
    "AUTHORED": 720,
    "REPORTED": 350,
    "MEMBER_OF": 56,
    "DISCUSSES": 2095
  },
  "last_synced_at": "2026-09-30T23:59:59Z",
  "model_slug": "deepseek/deepseek-chat",
  "active_model": "nvidia/nemotron-3.5-lightning:free"
}
```

---

## 8. `POST /api/eval/run`

Triggers an evaluation run for a specified split (`dev`, `failure`, `holdout`) and mode (`graph_on`, `graph_off`).

### Request Body (`EvalRunRequest`)
```json
{
  "split": "dev",
  "mode": "graph_on",
  "limit": 5,
  "repetitions": 1
}
```

### Request Fields
- `split` (`string`, required): `"dev"`, `"failure"`, or `"holdout"`.
- `mode` (`string`, optional, default: `"graph_on"`): `"graph_on"` or `"graph_off"`.
- `limit` (`integer | null`, optional): Max questions to run.
- `repetitions` (`integer`, optional, default: `1`): Number of repetitions per question.

### Response (`200 OK`)
```json
{
  "split": "dev",
  "mode": "graph_on",
  "total_questions": 5,
  "correct_count": 5,
  "accuracy": 1.0,
  "supported_count": 5,
  "refusal_correct_count": 0,
  "mean_latency_ms": 312.45,
  "results": [
    {
      "id": "Q1",
      "question": "Summarize everything known about the checkout timeout bug...",
      "mode": "graph_on",
      "status": "VERIFIED",
      "is_refusal": false,
      "refusal_correct": true,
      "correct": true,
      "supported": true,
      "latency_ms": 420.5,
      "claims_count": 4,
      "sources_count": 4,
      "answer_preview": "Issue #44 describes checkout timeouts during peak traffic..."
    }
  ]
}
```
