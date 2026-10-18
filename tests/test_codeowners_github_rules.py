"""Test GitHub CODEOWNERS exact level prefix matching rules against real fixtures.

Required cases:
- payments/refund.py -> owner from the payments/ rule (not payments/refunds/)
- payments/refunds/batch.py -> owner from payments/refunds/
- billing/anything -> billing/ rule
- a path matching no rule -> unowned
"""

import pytest
from src.agent.fixture_loader import (
    get_codeowners_rule_for_path,
    match_codeowners_pattern,
)
from src.agent.fixture_tools import execute_fixture_tool


def test_payments_refund_matches_payments_rule_not_refunds():
    """payments/refund.py -> owner from payments/ rule (@acme/payments), NOT payments/refunds/."""
    # 1. Test via fixture loader
    rule_pat, owners = get_codeowners_rule_for_path("payments/refund.py")
    assert rule_pat == "payments/"
    assert owners == ["@acme/payments"]
    assert "@acme/legacy-settlements" not in owners

    # 2. Test via who_owns fixture tool
    res, urls = execute_fixture_tool("who_owns", {"file_path": "payments/refund.py"})
    assert res["file_path"] == "payments/refund.py"
    assert res["has_declared_owner"] is True
    assert res["declared_rule_pattern"] == "payments/"
    assert res["declared_owners"] == ["@acme/payments"]
    assert res["team_status"] == "ACTIVE"


def test_payments_refunds_batch_matches_refunds_rule():
    """payments/refunds/batch.py -> owner from payments/refunds/ (@acme/legacy-settlements)."""
    # 1. Test via fixture loader
    rule_pat, owners = get_codeowners_rule_for_path("payments/refunds/batch.py")
    assert rule_pat == "payments/refunds/"
    assert owners == ["@acme/legacy-settlements"]

    # 2. Test via who_owns fixture tool
    res, urls = execute_fixture_tool("who_owns", {"file_path": "payments/refunds/batch.py"})
    assert res["file_path"] == "payments/refunds/batch.py"
    assert res["has_declared_owner"] is True
    assert res["declared_rule_pattern"] == "payments/refunds/"
    assert res["declared_owners"] == ["@acme/legacy-settlements"]
    assert res["is_stale_team"] is True


def test_billing_anything_matches_billing_rule():
    """billing/anything -> owner from billing/ rule (@acme/payments)."""
    # 1. Test via fixture loader
    rule_pat, owners = get_codeowners_rule_for_path("billing/anything")
    assert rule_pat == "billing/"
    assert owners == ["@acme/payments"]

    # 2. Test via who_owns fixture tool
    res, urls = execute_fixture_tool("who_owns", {"file_path": "billing/anything"})
    assert res["file_path"] == "billing/anything"
    assert res["has_declared_owner"] is True
    assert res["declared_rule_pattern"] == "billing/"
    assert res["declared_owners"] == ["@acme/payments"]


def test_path_matching_no_rule_is_unowned():
    """A path matching no rule -> unowned."""
    # When evaluated against custom rules without a fallback '*'
    rules = [
        ("payments/", ["@acme/payments"]),
        ("payments/refunds/", ["@acme/legacy-settlements"]),
        ("billing/", ["@acme/payments"]),
    ]
    unmatched_path = "unowned/random/component.py"

    best_match = None
    for pat, owners in rules:
        if match_codeowners_pattern(pat, unmatched_path):
            best_match = (pat, owners)

    assert best_match is None

    # In who_owns tool when no rule matches
    # Test match_codeowners_pattern directly
    assert not match_codeowners_pattern("payments/", "random/script.py")
    assert not match_codeowners_pattern("billing/", "random/script.py")
    assert not match_codeowners_pattern("payments/refunds/", "payments/refund.py")
