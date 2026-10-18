"""RepoBrain Contract Verification Script.

Validates the backend API against the definitive API Contract (all 9 fixes):
1. /api/ask and /api/compare: return "status" on every answer.
2. Every claim: return "verified" (bool) and "verification_path" (str).
3. Every source: return "entity_type" (str).
4. Ranking items {rank, login, score, reasons, source_ids, tied} and excluded items {login, reason, end_date}. Use [] when empty.
5. /api/compare: set comparison.on_status and off_status from answers. Return difference_counts only if rubric exists, else null.
6. /api/stats: keep "active_model", remove "model_slug".
7. Error responses: {"error": {"code", "message", "retryable"}} with valid codes.
8. GET /api/eval/results: returns saved dev results without calling live model.
9. Verify sample JSON files in docs/api_samples/ and live TestClient responses.

Exits with code 0 on complete compliance, 1 on any failure.
"""

import json
import os
import sys
from pathlib import Path

# Ensure fixture-backed execution
os.environ["PYTEST_CURRENT_TEST"] = "check_contract"

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from fastapi.testclient import TestClient
from src.api.server import app

ALLOWED_STATUSES = {"VERIFIED", "PARTIALLY_VERIFIED", "ANSWERED_UNCERTAIN", "REFUSED"}
ALLOWED_ERROR_CODES = {
    "MISSING_KEY",
    "PROVIDER_CREDITS",
    "PROVIDER_RATE_LIMIT",
    "BACKEND_UNAVAILABLE",
    "INVALID_REQUEST",
}
REQUIRED_RANKING_KEYS = {"rank", "login", "score", "reasons", "source_ids", "tied"}
REQUIRED_EXCLUDED_KEYS = {"login", "reason", "end_date"}


def check(condition: bool, msg: str):
    if not condition:
        print(f"  [FAIL] {msg}")
        raise AssertionError(msg)
    print(f"  [PASS] {msg}")


def assert_answer_contract(ans: dict, context_label: str):
    check("status" in ans, f"{context_label}: contains 'status' field")
    check(ans.get("status") in ALLOWED_STATUSES, f"{context_label}: status '{ans.get('status')}' is valid")

    # Claims
    check("claims" in ans and isinstance(ans["claims"], list), f"{context_label}: 'claims' is a list")
    for i, c in enumerate(ans.get("claims", [])):
        check("verified" in c and isinstance(c["verified"], bool), f"{context_label}: claim[{i}] has boolean 'verified'")
        check("verification_path" in c and isinstance(c["verification_path"], str), f"{context_label}: claim[{i}] has string 'verification_path'")

    # Sources
    check("sources" in ans and isinstance(ans["sources"], list), f"{context_label}: 'sources' is a list")
    for i, s in enumerate(ans.get("sources", [])):
        check("entity_type" in s and isinstance(s["entity_type"], str), f"{context_label}: source[{i}] has string 'entity_type'")

    # Ranking
    check("ranking" in ans and isinstance(ans["ranking"], list), f"{context_label}: 'ranking' is a list")
    for i, r in enumerate(ans.get("ranking", [])):
        diff = REQUIRED_RANKING_KEYS - set(r.keys())
        check(len(diff) == 0, f"{context_label}: ranking[{i}] contains all required keys (missing: {diff})")

    # Excluded
    check("excluded" in ans and isinstance(ans["excluded"], list), f"{context_label}: 'excluded' is a list")
    for i, e in enumerate(ans.get("excluded", [])):
        diff = REQUIRED_EXCLUDED_KEYS - set(e.keys())
        check(len(diff) == 0, f"{context_label}: excluded[{i}] contains all required keys (missing: {diff})")


def check_sample_files():
    print("\n--- Verifying Sample Files in docs/api_samples/ ---")
    samples_dir = WORKSPACE / "docs" / "api_samples"
    check(samples_dir.exists(), "docs/api_samples directory exists")

    # 1. Health
    for fn in ("get_api_health.json", "health.json"):
        fp = samples_dir / fn
        check(fp.exists(), f"Sample file {fn} exists")
        data = json.loads(fp.read_text(encoding="utf-8"))
        for k in ("status", "service", "timestamp", "database", "model"):
            check(k in data, f"{fn} contains key '{k}'")

    # 2. Stats
    for fn in ("get_api_stats.json", "stats.json"):
        fp = samples_dir / fn
        check(fp.exists(), f"Sample file {fn} exists")
        data = json.loads(fp.read_text(encoding="utf-8"))
        check("active_model" in data, f"{fn} contains 'active_model'")
        check("model_slug" not in data, f"{fn} DOES NOT contain 'model_slug'")

    # 3. Ask (graph_on & graph_off)
    for fn in ("post_api_ask_graph_on.json", "ask_graph_on.json", "post_api_ask_graph_off.json", "ask_graph_off.json"):
        fp = samples_dir / fn
        check(fp.exists(), f"Sample file {fn} exists")
        data = json.loads(fp.read_text(encoding="utf-8"))
        assert_answer_contract(data, fn)

    # 4. Compare
    for fn in ("post_api_compare.json", "compare.json"):
        fp = samples_dir / fn
        check(fp.exists(), f"Sample file {fn} exists")
        data = json.loads(fp.read_text(encoding="utf-8"))
        check("graph_on" in data and "graph_off" in data and "comparison" in data, f"{fn} has graph_on, graph_off, comparison")
        assert_answer_contract(data["graph_on"], f"{fn} -> graph_on")
        assert_answer_contract(data["graph_off"], f"{fn} -> graph_off")

        comp = data["comparison"]
        check("on_status" in comp and comp["on_status"] == data["graph_on"]["status"], f"{fn}: on_status matches graph_on.status ({comp.get('on_status')})")
        check("off_status" in comp and comp["off_status"] == data["graph_off"]["status"], f"{fn}: off_status matches graph_off.status ({comp.get('off_status')})")
        check("difference_counts" in comp, f"{fn}: comparison contains 'difference_counts'")

    # 5. Eval results
    for fn in ("get_api_eval_results.json", "eval_results.json"):
        fp = samples_dir / fn
        check(fp.exists(), f"Sample file {fn} exists")
        data = json.loads(fp.read_text(encoding="utf-8"))
        check("split_name" in data or "split" in data or "architectures" in data or "results" in data, f"{fn} contains saved dev evaluation results")


def check_live_endpoints():
    print("\n--- Verifying Live / TestClient API Responses ---")
    client = TestClient(app)

    # 1. GET /api/health
    resp = client.get("/api/health")
    check(resp.status_code == 200, "GET /api/health returns 200")
    h = resp.json()
    check(h.get("status") == "healthy", "/api/health status is 'healthy'")
    check("database" in h and "model" in h, "/api/health includes database and model")

    # 2. GET /api/stats
    resp = client.get("/api/stats")
    check(resp.status_code == 200, "GET /api/stats returns 200")
    s = resp.json()
    check("active_model" in s, "GET /api/stats contains 'active_model'")
    check("model_slug" not in s, "GET /api/stats DOES NOT contain 'model_slug'")

    # 3. POST /api/ask (graph_on)
    resp = client.post("/api/ask", json={
        "question": "Who owns payments/refund.py according to CODEOWNERS?",
        "mode": "graph_on"
    })
    check(resp.status_code == 200, "POST /api/ask (graph_on) returns 200")
    assert_answer_contract(resp.json(), "Live /api/ask (graph_on)")

    # 4. POST /api/ask (graph_off)
    resp = client.post("/api/ask", json={
        "question": "Who owns payments/refund.py according to CODEOWNERS?",
        "mode": "graph_off"
    })
    check(resp.status_code == 200, "POST /api/ask (graph_off) returns 200")
    assert_answer_contract(resp.json(), "Live /api/ask (graph_off)")

    # 5. POST /api/compare (rubric question -> difference_counts not null)
    resp = client.post("/api/compare", json={
        "question": "Who owns payments/refund.py according to CODEOWNERS?"
    })
    check(resp.status_code == 200, "POST /api/compare (rubric Q1) returns 200")
    c_rubric = resp.json()
    assert_answer_contract(c_rubric["graph_on"], "Live /api/compare -> graph_on")
    assert_answer_contract(c_rubric["graph_off"], "Live /api/compare -> graph_off")
    comp = c_rubric["comparison"]
    check(comp.get("on_status") == c_rubric["graph_on"]["status"], "compare.on_status matches graph_on.status")
    check(comp.get("off_status") == c_rubric["graph_off"]["status"], "compare.off_status matches graph_off.status")
    check(comp.get("difference_counts") is not None, "compare: difference_counts is populated for rubric question")
    diff_keys = {"claims_diff", "sources_diff", "facts_passed_diff", "violations_diff"}
    check(diff_keys.issubset(set(comp.get("difference_counts", {}).keys())), "compare.difference_counts has required diff keys")

    # 6. POST /api/compare (non-rubric question -> difference_counts is null)
    resp = client.post("/api/compare", json={
        "question": "Arbitrary question without any rubric in the dev benchmark"
    })
    check(resp.status_code == 200, "POST /api/compare (non-rubric) returns 200")
    c_non_rubric = resp.json()
    check(c_non_rubric["comparison"].get("difference_counts") is None, "compare: difference_counts is null for non-rubric question")
    check(c_non_rubric["comparison"].get("on_status") == c_non_rubric["graph_on"]["status"], "compare: on_status set correctly")
    check(c_non_rubric["comparison"].get("off_status") == c_non_rubric["graph_off"]["status"], "compare: off_status set correctly")

    # 7. GET /api/eval/results
    resp = client.get("/api/eval/results")
    check(resp.status_code == 200, "GET /api/eval/results returns 200")
    res_data = resp.json()
    check("split_name" in res_data or "split" in res_data or "architectures" in res_data or "results" in res_data, "GET /api/eval/results returns saved dev results")

    # 8. Error responses contract: {"error": {"code", "message", "retryable"}}
    resp_err = client.post("/api/ask", json={})
    check(resp_err.status_code == 400, "Invalid POST /api/ask returns 400")
    err_body = resp_err.json()
    check("error" in err_body, "Error response root contains 'error'")
    err_obj = err_body["error"]
    check("code" in err_obj and "message" in err_obj and "retryable" in err_obj, "Error object contains {code, message, retryable}")
    check(err_obj["code"] in ALLOWED_ERROR_CODES, f"Error code '{err_obj['code']}' is in allowed codes list")
    check(isinstance(err_obj["retryable"], bool), "Error 'retryable' is a boolean")

    # 404 test
    resp_404 = client.get("/api/nonexistent_endpoint")
    check(resp_404.status_code == 404, "404 endpoint returns 404")
    err_404 = resp_404.json()
    check("error" in err_404 and err_404["error"]["code"] in ALLOWED_ERROR_CODES, "404 handler returns standardized error contract")


def main():
    print("=" * 60)
    print("      REPOBRAIN API CONTRACT VERIFICATION (9 FIXES)       ")
    print("=" * 60)
    try:
        check_sample_files()
        check_live_endpoints()
        print("\n" + "=" * 60)
        print("  ALL CONTRACT CHECKS PASSED SUCCESSFULLY (EXIT CODE 0)  ")
        print("=" * 60 + "\n")
        sys.exit(0)
    except AssertionError as e:
        print("\n" + "!" * 60)
        print(f"  CONTRACT VERIFICATION FAILED: {e}")
        print("!" * 60 + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
