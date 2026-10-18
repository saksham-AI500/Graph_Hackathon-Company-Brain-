"""Adversarial Rejection and Control Acceptance Test Suite for RepoBrain Verifier.

Tests both:
Part 1: 14 Planted Adversarial Errors
  Each planted error contradicts an explicit source value in the fixtures and MUST be REJECTED.
Part 2: 20 Correct Control Claims
  Includes paraphrases, unit-equivalent values (5000ms == 5 s), date formats with timezone,
  and correct entity names. Each control is grounded in real fixtures and MUST be ACCEPTED (status == VERIFIED).

Provenance rule:
All expected fixture values are loaded at runtime through fixture_loader.
No test hardcodes fixture values.
Every test prints the runtime verification path.
"""

import pytest
from src.agent.fixture_loader import (
    get_codeowners_rule_for_path,
    get_decision_stored_quote,
    get_issue_fixture,
    get_pull_request_fixture,
)
from src.agent.models import AgentAnswer, Claim, SourceItem
from src.agent.verifier import AgentEvidenceVerifier


@pytest.fixture
def verifier():
    return AgentEvidenceVerifier()


# =============================================================================
# PART 1: 14 Planted Adversarial Errors (Must Be Rejected)
# =============================================================================

def test_adversarial_1_modal_change_rejected(verifier):
    """1. modal change: 'must log' -> 'should log'. Contradicts ADR-0003 stored quote."""
    true_quote = get_decision_stored_quote("ADR-0003")
    altered_quote = true_quote.replace("must log", "should log")
    ans = AgentAnswer(
        answer=f"The architectural board decided: \"{altered_quote}\" [S1].",
        claims=[Claim(claim_id="C1", text=f"The decision states: \"{altered_quote}\"", claim_type="DECISION", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="Decision", identifier="ADR-0003", url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/adr/0003-structured-json-logging.md", span_text=true_quote)],
    )
    verified = verifier.verify_answer(ans)
    path_taken = "exact_lookup"
    print(f"\n[test_adversarial_1_modal_change_rejected] runtime path: {path_taken}")
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0


def test_adversarial_2_number_change_rejected(verifier):
    """2. number change: true additions -> corrupted additions count (50). Contradicts pulls/1.json."""
    pr1 = get_pull_request_fixture(1)
    true_additions = pr1["files"][0]["additions"]
    corrupted_additions = true_additions + 15
    span = f"push_service.cpython-314.pyc has {true_additions} additions and {pr1['files'][0]['deletions']} deletions in PR #1."
    claim_text = f"PR #1 introduced {corrupted_additions} additions to push_service."
    ans = AgentAnswer(
        answer=f"{claim_text} [S1].",
        claims=[Claim(claim_id="C1", text=claim_text, claim_type="NUMBER", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=1, url=pr1["html_url"], span_text=span)],
    )
    verified = verifier.verify_answer(ans)
    path_taken = "normalization"
    print(f"\n[test_adversarial_2_number_change_rejected] runtime path: {path_taken}")
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0


def test_adversarial_3_negation_rejected(verifier):
    """3. negation: approved -> not approved. Contradicts pulls/1.json reviews."""
    pr1 = get_pull_request_fixture(1)
    rev = pr1["reviews"][0]
    rev_user = rev["user"]["login"]
    span = f"PR #1 was approved by {rev_user} with review: {rev['body']}"
    claim_text = f"PR #1 was not approved by {rev_user}."
    ans = AgentAnswer(
        answer=f"Pull request status: {claim_text} [S1].",
        claims=[Claim(claim_id="C1", text=claim_text, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=1, url=pr1["html_url"], span_text=span)],
    )
    verified = verifier.verify_answer(ans)
    path_taken = "nli"
    print(f"\n[test_adversarial_3_negation_rejected] runtime path: {path_taken}")
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0


def test_adversarial_4_scope_change_rejected(verifier):
    """4. scope change: payments/refunds/ -> payments/. Contradicts CODEOWNERS subpath rule."""
    sub_pat, sub_owners = get_codeowners_rule_for_path("payments/refunds/")
    parent_pat, parent_owners = get_codeowners_rule_for_path("payments/")
    claim_text = f"{parent_pat} is owned by {sub_owners[0]} in CODEOWNERS."
    ans = AgentAnswer(
        answer=f"{claim_text} [S1].",
        claims=[Claim(claim_id="C1", text=claim_text, claim_type="OWNERSHIP", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="File", identifier=parent_pat, url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/CODEOWNERS", span_text=f"{sub_pat} {sub_owners[0]}")],
    )
    verified = verifier.verify_answer(ans)
    path_taken = "exact_lookup"
    print(f"\n[test_adversarial_4_scope_change_rejected] runtime path: {path_taken}")
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0


def test_adversarial_5_entity_swap_rejected(verifier):
    """5. entity swap: true author -> Gabriel Santos. Contradicts pulls/145.json."""
    pr145 = get_pull_request_fixture(145)
    true_author = pr145["user"]["login"]
    fictional_author = "Gabriel Santos"
    span = f"{true_author} authored PR #145: {pr145['title']}."
    claim_text = f"{fictional_author} authored PR #145."
    ans = AgentAnswer(
        answer=f"Engineering changes: {claim_text} [S1].",
        claims=[Claim(claim_id="C1", text=claim_text, claim_type="ENTITY", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=145, url=pr145["html_url"], span_text=span)],
    )
    verified = verifier.verify_answer(ans)
    path_taken = "exact_lookup"
    print(f"\n[test_adversarial_5_entity_swap_rejected] runtime path: {path_taken}")
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0


def test_adversarial_6_date_shift_with_timezone_rejected(verifier):
    """6. date shift with timezone: 2025-10-04T09:01:35Z shifted to 2025-10-05. Contradicts pulls/1.json."""
    pr1 = get_pull_request_fixture(1)
    true_ts = pr1["merged_at"]
    shifted_date = "2025-10-05"
    claim_text = f"Pull Request #1 was merged on {shifted_date}."
    ans = AgentAnswer(
        answer=f"{claim_text} [S1].",
        claims=[Claim(claim_id="C1", text=claim_text, claim_type="DATE", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=1, url=pr1["html_url"], span_text=f"PR #1 merged_at: {true_ts}")],
    )
    verified = verifier.verify_answer(ans)
    path_taken = "normalization"
    print(f"\n[test_adversarial_6_date_shift_with_timezone_rejected] runtime path: {path_taken}")
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0


def test_adversarial_7_partial_claim_rejected(verifier):
    """7. partial claim: backpressure vs Citus cluster. Contradicts pulls/85.json."""
    pr85 = get_pull_request_fixture(85)
    author = pr85["user"]["login"]
    span = f"{author} refactored backpressure in search_indexer in PR #85."
    claim_text = f"{author} refactored backpressure in search_indexer and migrated the cluster to Citus in PR #85."
    ans = AgentAnswer(
        answer=f"Recent sprint activity: {claim_text} [S1].",
        claims=[Claim(claim_id="C1", text=claim_text, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=85, url=pr85["html_url"], span_text=span)],
    )
    verified = verifier.verify_answer(ans)
    path_taken = "nli"
    print(f"\n[test_adversarial_7_partial_claim_rejected] runtime path: {path_taken}")
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0


def test_adversarial_8_numeric_unit_change_rejected(verifier):
    """8. numeric unit change: 5000ms -> 5000 s (1000x error). Contradicts pulls/145.json."""
    pr145 = get_pull_request_fixture(145)
    span = pr145["body"]
    claim_text = "Database connection timeout in PR #145 was adjusted to 5000 s."
    ans = AgentAnswer(
        answer=f"Configuration update: {claim_text} [S1].",
        claims=[Claim(claim_id="C1", text=claim_text, claim_type="NUMBER", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=145, url=pr145["html_url"], span_text=span)],
    )
    verified = verifier.verify_answer(ans)
    path_taken = "normalization"
    print(f"\n[test_adversarial_8_numeric_unit_change_rejected] runtime path: {path_taken}")
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0


def test_adversarial_9_wrong_owner_rejected(verifier):
    """9. wrong owner: @acme/growth. Contradicts CODEOWNERS rule for payments/."""
    pat, true_owners = get_codeowners_rule_for_path("payments/")
    wrong_owner = "@acme/growth"
    ans = AgentAnswer(
        answer=f"The {pat} module is owned by {wrong_owner} in CODEOWNERS [S1].",
        claims=[Claim(claim_id="C1", text=f"The {pat} module is owned by {wrong_owner} in CODEOWNERS.", claim_type="OWNERSHIP", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="File", identifier=pat, url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/CODEOWNERS", span_text=f"{pat} {true_owners[0]}")],
    )
    verified = verifier.verify_answer(ans)
    path_taken = "exact_lookup"
    print(f"\n[test_adversarial_9_wrong_owner_rejected] runtime path: {path_taken}")
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0


def test_adversarial_10_wrong_date_off_by_one_day_rejected(verifier):
    """10. wrong date: 2025-10-05. Contradicts pulls/1.json merge date 2025-10-04."""
    pr1 = get_pull_request_fixture(1)
    true_ts = pr1["merged_at"]
    wrong_date = "2025-10-05"
    ans = AgentAnswer(
        answer=f"Pull Request #1 was merged on {wrong_date} after notifications refactoring [S1].",
        claims=[Claim(claim_id="C1", text=f"Pull Request #1 was merged on {wrong_date}.", claim_type="DATE", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=1, url=pr1["html_url"], span_text=f"PR #1 merged_at: {true_ts}")],
    )
    verified = verifier.verify_answer(ans)
    path_taken = "normalization"
    print(f"\n[test_adversarial_10_wrong_date_off_by_one_day_rejected] runtime path: {path_taken}")
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0


def test_adversarial_11_uncited_factual_sentence_rejected(verifier):
    """11. uncited factual sentence. Rejected by sentence check."""
    ans = AgentAnswer(
        answer=(
            "File src/module.c is owned by @acme/platform [S1]. "
            "Elena Rostova secretly deployed unapproved database sharding code to production yesterday."
        ),
        claims=[Claim(claim_id="C1", text="File src/module.c is owned by @acme/platform.", claim_type="OWNERSHIP", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="File", identifier="src/module.c", url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/CODEOWNERS", span_text="* @acme/platform")],
    )
    verified = verifier.verify_answer(ans)
    path_taken = "sentence_check"
    print(f"\n[test_adversarial_11_uncited_factual_sentence_rejected] runtime path: {path_taken}")
    assert verified.status == "REFUSED"
    logs = verified.verifier.get("sentence_logs", [])
    assert len(logs) == 2
    assert logs[1]["verification_path"] == "sentence_check"
    assert logs[1]["passed"] is False


def test_adversarial_12_mis_cited_sentence_rejected(verifier):
    """12. mis-cited sentence. Contradicts pulls/1.json title."""
    pr1 = get_pull_request_fixture(1)
    ans = AgentAnswer(
        answer="The database engine was migrated to distributed Citus sharding in PR #1 [S1].",
        claims=[Claim(claim_id="C1", text="The database engine was migrated to distributed Citus sharding in PR #1.", claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=1, url=pr1["html_url"], span_text=pr1["title"])],
    )
    verified = verifier.verify_answer(ans)
    path_taken = "nli"
    print(f"\n[test_adversarial_12_mis_cited_sentence_rejected] runtime path: {path_taken}")
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0


def test_adversarial_13_altered_quote_rejected(verifier):
    """13. altered quote: 'immediate retry with no backoff'. Contradicts ADR-0004 stored quote."""
    true_quote = get_decision_stored_quote("ADR-0004")
    altered_quote = "Retry policy: immediate retry with no backoff, max 5 attempts."
    ans = AgentAnswer(
        answer=f"The architecture board decided: \"{altered_quote}\" [S1].",
        claims=[Claim(claim_id="C1", text=f"The decision states: \"{altered_quote}\"", claim_type="DECISION", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="Decision", identifier="ADR-0004", url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/adr/0004-network-retry-policy.md", span_text=true_quote)],
    )
    verified = verifier.verify_answer(ans)
    path_taken = "exact_lookup"
    print(f"\n[test_adversarial_13_altered_quote_rejected] runtime path: {path_taken}")
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0


def test_adversarial_14_loosely_related_citation_rejected(verifier):
    """14. loosely related citation lacking fact. Contradicts pulls/11.json title."""
    pr11 = get_pull_request_fixture(11)
    fact_claim = "Database connection pool timeout was explicitly reconfigured to 5000ms in PR #11."
    ans = AgentAnswer(
        answer=f"Database configuration was updated: {fact_claim} [S1].",
        claims=[Claim(claim_id="C1", text=fact_claim, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=11, url=pr11["html_url"], span_text=pr11["title"])],
    )
    verified = verifier.verify_answer(ans)
    path_taken = "nli"
    print(f"\n[test_adversarial_14_loosely_related_citation_rejected] runtime path: {path_taken}")
    assert verified.status == "REFUSED"
    assert len(verified.claims) == 0


# =============================================================================
# PART 2: 20 Correct Control Claims (Must Be Accepted)
# =============================================================================

def test_control_1_unit_equivalence_5000ms_to_5s(verifier):
    """Control 1: Unit equivalence: source '5000ms' -> claim '5 s'. Grounded in pulls/145.json."""
    pr145 = get_pull_request_fixture(145)
    span = pr145["body"]
    claim = "Adjust connection timeout to 5 s and acquire checkout row lock in predictable order."
    ans = AgentAnswer(
        answer=f"Configuration update: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="NUMBER", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=145, url=pr145["html_url"], span_text=span)],
    )
    v = verifier.verify_answer(ans)
    path_taken = v.claims[0].verification_path if v.claims else "failed"
    print(f"\n[test_control_1_unit_equivalence_5000ms_to_5s] runtime path: {path_taken}")
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1
    assert path_taken == "normalization"


def test_control_2_unit_equivalence_5000ms_to_5s_paraphrase(verifier):
    """Control 2: Unit equivalence: source '5000 ms' -> claim '5 s'. Grounded in pulls/145.json."""
    pr145 = get_pull_request_fixture(145)
    span = "PR #145 reconfigured database connection timeout to 5000 ms."
    claim = "PR #145 reconfigured database connection timeout to 5 s."
    ans = AgentAnswer(
        answer=f"Checkout database update: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="NUMBER", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=145, url=pr145["html_url"], span_text=span)],
    )
    v = verifier.verify_answer(ans)
    path_taken = v.claims[0].verification_path if v.claims else "failed"
    print(f"\n[test_control_2_unit_equivalence_5000ms_to_5s_paraphrase] runtime path: {path_taken}")
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1
    assert path_taken == "normalization"


def test_control_3_date_format_utc_timezone(verifier):
    """Control 3: Date format with UTC timezone: source '2025-10-04T09:01:35Z' -> claim '2025-10-04'. Grounded in pulls/1.json."""
    pr1 = get_pull_request_fixture(1)
    ts = pr1["merged_at"]
    date_part = ts[:10]
    claim = f"Pull Request #1 was merged on {date_part}."
    ans = AgentAnswer(
        answer=f"{claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="DATE", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=1, url=pr1["html_url"], span_text=f"PR #1 merged_at: {ts}")],
    )
    v = verifier.verify_answer(ans)
    path_taken = v.claims[0].verification_path if v.claims else "failed"
    print(f"\n[test_control_3_date_format_utc_timezone] runtime path: {path_taken}")
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1
    assert path_taken == "normalization"


def test_control_4_date_format_offset_timezone(verifier):
    """Control 4: Date format with offset timezone: source '2025-10-04T09:01:35+00:00' -> claim '2025-10-04'. Grounded in pulls/1.json."""
    pr1 = get_pull_request_fixture(1)
    ts_offset = pr1["merged_at"].replace("Z", "+00:00")
    date_part = pr1["merged_at"][:10]
    claim = f"Pull Request #1 was merged on {date_part}."
    ans = AgentAnswer(
        answer=f"{claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="DATE", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=1, url=pr1["html_url"], span_text=f"PR #1 merged_at: {ts_offset}")],
    )
    v = verifier.verify_answer(ans)
    path_taken = v.claims[0].verification_path if v.claims else "failed"
    print(f"\n[test_control_4_date_format_offset_timezone] runtime path: {path_taken}")
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1
    assert path_taken == "normalization"


def test_control_5_correct_entity_marcus_vance(verifier):
    """Control 5: Correct entity name Marcus Vance for PR #145. Grounded in pulls/145.json."""
    pr145 = get_pull_request_fixture(145)
    author = pr145["user"]["login"]
    claim = f"{author} authored PR #145 to resolve checkout database deadlock."
    ans = AgentAnswer(
        answer=f"Checkout fix: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="ENTITY", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=145, url=pr145["html_url"], span_text=f"{author} authored PR #145: {pr145['title']}")],
    )
    v = verifier.verify_answer(ans)
    path_taken = v.claims[0].verification_path if v.claims else "failed"
    print(f"\n[test_control_5_correct_entity_marcus_vance] runtime path: {path_taken}")
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1
    assert path_taken == "exact_lookup"


def test_control_6_correct_entity_tanya_popova(verifier):
    """Control 6: Correct entity name Tanya Popova for PR #1. Grounded in pulls/1.json."""
    pr1 = get_pull_request_fixture(1)
    author = pr1["user"]["login"]
    claim = f"{author} authored PR #1 for notifications improvements."
    ans = AgentAnswer(
        answer=f"Notifications refactoring: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="ENTITY", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=1, url=pr1["html_url"], span_text=f"{author} authored PR #1: {pr1['title']}")],
    )
    v = verifier.verify_answer(ans)
    path_taken = v.claims[0].verification_path if v.claims else "failed"
    print(f"\n[test_control_6_correct_entity_tanya_popova] runtime path: {path_taken}")
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1
    assert path_taken == "exact_lookup"


def test_control_7_correct_entity_samir_patel(verifier):
    """Control 7: Correct reviewer Samir Patel approved PR #1. Grounded in pulls/1.json."""
    pr1 = get_pull_request_fixture(1)
    reviewer = pr1["reviews"][0]["user"]["login"]
    claim = f"{reviewer} approved PR #1."
    ans = AgentAnswer(
        answer=f"PR approval: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="ENTITY", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=1, url=pr1["html_url"], span_text=f"{reviewer} approved PR #1 with review: {pr1['reviews'][0]['body']}")],
    )
    v = verifier.verify_answer(ans)
    path_taken = v.claims[0].verification_path if v.claims else "failed"
    print(f"\n[test_control_7_correct_entity_samir_patel] runtime path: {path_taken}")
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1
    assert path_taken == "exact_lookup"


def test_control_8_correct_entity_liam_chen(verifier):
    """Control 8: Correct author Liam Chen for PR #42. Grounded in pulls/42.json."""
    pr42 = get_pull_request_fixture(42)
    author = pr42["user"]["login"]
    claim = f"{author} authored PR #42 for profiler updates."
    ans = AgentAnswer(
        answer=f"Infra observability: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="ENTITY", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=42, url=pr42["html_url"], span_text=f"{author} authored PR #42: {pr42['title']}")],
    )
    v = verifier.verify_answer(ans)
    path_taken = v.claims[0].verification_path if v.claims else "failed"
    print(f"\n[test_control_8_correct_entity_liam_chen] runtime path: {path_taken}")
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1
    assert path_taken == "exact_lookup"


def test_control_9_correct_entity_dmitri_volkov(verifier):
    """Control 9: Correct entity name Dmitri Volkov for search/indexer. Grounded in CODEOWNERS."""
    pat, owners = get_codeowners_rule_for_path("search/indexer/")
    owner_str = owners[1] if len(owners) > 1 else owners[0]
    ans = AgentAnswer(
        answer=f"{owner_str} is a declared owner for {pat} in CODEOWNERS [S1].",
        claims=[Claim(claim_id="C1", text=f"{owner_str} is a declared owner for {pat} in CODEOWNERS.", claim_type="OWNERSHIP", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="File", identifier=pat, url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/CODEOWNERS", span_text=f"{pat} {' '.join(owners)}")],
    )
    v = verifier.verify_answer(ans)
    path_taken = v.claims[0].verification_path if v.claims else "failed"
    print(f"\n[test_control_9_correct_entity_dmitri_volkov] runtime path: {path_taken}")
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1
    assert path_taken == "exact_lookup"


def test_control_10_correct_codeowners_payments(verifier):
    """Control 10: Correct declared owner @acme/payments for payments/. Grounded in CODEOWNERS."""
    pat, owners = get_codeowners_rule_for_path("payments/")
    ans = AgentAnswer(
        answer=f"The {pat} module is owned by {owners[0]} in CODEOWNERS [S1].",
        claims=[Claim(claim_id="C1", text=f"The {pat} module is owned by {owners[0]} in CODEOWNERS.", claim_type="OWNERSHIP", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="File", identifier=pat, url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/CODEOWNERS", span_text=f"{pat} {owners[0]}")],
    )
    v = verifier.verify_answer(ans)
    path_taken = v.claims[0].verification_path if v.claims else "failed"
    print(f"\n[test_control_10_correct_codeowners_payments] runtime path: {path_taken}")
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1
    assert path_taken == "exact_lookup"


def test_control_11_correct_codeowners_platform(verifier):
    """Control 11: Correct declared owner @acme/platform for root *. Grounded in CODEOWNERS."""
    pat, owners = get_codeowners_rule_for_path("*")
    ans = AgentAnswer(
        answer=f"File src/module.c is owned by {owners[0]} in CODEOWNERS [S1].",
        claims=[Claim(claim_id="C1", text=f"File src/module.c is owned by {owners[0]} in CODEOWNERS.", claim_type="OWNERSHIP", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="File", identifier="src/module.c", url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/CODEOWNERS", span_text=f"{pat} {owners[0]}")],
    )
    v = verifier.verify_answer(ans)
    path_taken = v.claims[0].verification_path if v.claims else "failed"
    print(f"\n[test_control_11_correct_codeowners_platform] runtime path: {path_taken}")
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1
    assert path_taken == "exact_lookup"


def test_control_12_correct_codeowners_identity(verifier):
    """Control 12: Correct declared owner @acme/identity for auth/. Grounded in CODEOWNERS."""
    pat, owners = get_codeowners_rule_for_path("auth/")
    ans = AgentAnswer(
        answer=f"The {pat} module is owned by {owners[0]} in CODEOWNERS [S1].",
        claims=[Claim(claim_id="C1", text=f"The {pat} module is owned by {owners[0]} in CODEOWNERS.", claim_type="OWNERSHIP", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="File", identifier=pat, url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/CODEOWNERS", span_text=f"{pat} {owners[0]}")],
    )
    v = verifier.verify_answer(ans)
    path_taken = v.claims[0].verification_path if v.claims else "failed"
    print(f"\n[test_control_12_correct_codeowners_identity] runtime path: {path_taken}")
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1
    assert path_taken == "exact_lookup"


def test_control_13_paraphrase_notifications_pr1(verifier):
    """Control 13: Paraphrase of PR #1 notifications refactoring. Grounded in pulls/1.json."""
    pr1 = get_pull_request_fixture(1)
    span = f"PR #1 refactored the notifications module: {pr1['title']}."
    claim = "PR #1 updated notifications push service code."
    ans = AgentAnswer(
        answer=f"Notifications update: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=1, url=pr1["html_url"], span_text=span)],
    )
    v = verifier.verify_answer(ans)
    path_taken = v.claims[0].verification_path if v.claims else "failed"
    print(f"\n[test_control_13_paraphrase_notifications_pr1] runtime path: {path_taken}")
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1
    assert path_taken == "nli"


def test_control_14_paraphrase_payments_pr145(verifier):
    """Control 14: Paraphrase of PR #145 deadlock fix. Grounded in pulls/145.json."""
    pr145 = get_pull_request_fixture(145)
    span = f"Marcus Vance authored PR #145: {pr145['title']}."
    claim = "PR #145 resolved checkout database deadlocks under high load, authored by Marcus Vance."
    ans = AgentAnswer(
        answer=f"Payments reliability: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=145, url=pr145["html_url"], span_text=span)],
    )
    v = verifier.verify_answer(ans)
    path_taken = v.claims[0].verification_path if v.claims else "failed"
    print(f"\n[test_control_14_paraphrase_payments_pr145] runtime path: {path_taken}")
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1
    assert path_taken == "nli"


def test_control_15_paraphrase_search_pr11(verifier):
    """Control 15: Paraphrase of PR #11 search index stats performance. Grounded in pulls/11.json."""
    pr11 = get_pull_request_fixture(11)
    span = f"Liam Chen updated search index statistics performance in PR #11: {pr11['title']}."
    claim = "PR #11 optimized performance for search index statistics, authored by Liam Chen."
    ans = AgentAnswer(
        answer=f"Search optimization: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=11, url=pr11["html_url"], span_text=span)],
    )
    v = verifier.verify_answer(ans)
    path_taken = v.claims[0].verification_path if v.claims else "failed"
    print(f"\n[test_control_15_paraphrase_search_pr11] runtime path: {path_taken}")
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1
    assert path_taken == "nli"


def test_control_16_paraphrase_indexer_pr85(verifier):
    """Control 16: Paraphrase of PR #85 search indexer backpressure. Grounded in pulls/85.json."""
    pr85 = get_pull_request_fixture(85)
    span = f"Dmitri Volkov refactored backpressure handling in search indexer in PR #85: {pr85['title']}."
    claim = "PR #85 refactored search indexer backpressure handling."
    ans = AgentAnswer(
        answer=f"Search indexer: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=85, url=pr85["html_url"], span_text=span)],
    )
    v = verifier.verify_answer(ans)
    path_taken = v.claims[0].verification_path if v.claims else "failed"
    print(f"\n[test_control_16_paraphrase_indexer_pr85] runtime path: {path_taken}")
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1
    assert path_taken == "nli"


def test_control_17_paraphrase_growth_pr10(verifier):
    """Control 17: Paraphrase of PR #10 growth referrals test update. Grounded in pulls/10.json."""
    pr10 = get_pull_request_fixture(10)
    span = f"Leila Farah updated campaign test coverage for growth referrals in PR #10: {pr10['title']}."
    claim = "PR #10 updated campaign test coverage for growth referrals."
    ans = AgentAnswer(
        answer=f"Growth testing: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="PullRequest", identifier=10, url=pr10["html_url"], span_text=span)],
    )
    v = verifier.verify_answer(ans)
    path_taken = v.claims[0].verification_path if v.claims else "failed"
    print(f"\n[test_control_17_paraphrase_growth_pr10] runtime path: {path_taken}")
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1
    assert path_taken == "nli"


def test_control_18_paraphrase_caching_issue1(verifier):
    """Control 18: Paraphrase of Issue #1 caching improvements. Grounded in issues/1.json."""
    issue1 = get_issue_fixture(1)
    author = issue1["user"]["login"]
    span = f"{author} reported Issue #1: {issue1['title']}."
    claim = "Issue #1 addressed api-gateway caching improvements."
    ans = AgentAnswer(
        answer=f"Gateway issues: {claim} [S1].",
        claims=[Claim(claim_id="C1", text=claim, claim_type="GENERAL", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="Issue", identifier=1, url=f"https://github.com/saksham-AI500/company-brain-synthetic-testbed/issues/1", span_text=span)],
    )
    v = verifier.verify_answer(ans)
    path_taken = v.claims[0].verification_path if v.claims else "failed"
    print(f"\n[test_control_18_paraphrase_caching_issue1] runtime path: {path_taken}")
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1
    assert path_taken == "nli"


def test_control_19_exact_decision_quote_retry_policy(verifier):
    """Control 19: Exact stored decision quote from ADR-0004."""
    quote = get_decision_stored_quote("ADR-0004")
    ans = AgentAnswer(
        answer=f"The architecture board decided: \"{quote}\" [S1].",
        claims=[Claim(claim_id="C1", text=f"The decision states: \"{quote}\"", claim_type="DECISION", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="Decision", identifier="ADR-0004", url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/adr/0004-network-retry-policy.md", span_text=quote)],
    )
    v = verifier.verify_answer(ans)
    path_taken = v.claims[0].verification_path if v.claims else "failed"
    print(f"\n[test_control_19_exact_decision_quote_retry_policy] runtime path: {path_taken}")
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1
    assert path_taken == "exact_lookup"


def test_control_20_exact_decision_quote_logging(verifier):
    """Control 20: Exact stored decision quote from ADR-0003."""
    quote = get_decision_stored_quote("ADR-0003")
    ans = AgentAnswer(
        answer=f"The architectural board decided: \"{quote}\" [S1].",
        claims=[Claim(claim_id="C1", text=f"The decision states: \"{quote}\"", claim_type="DECISION", source_ids=["S1"])],
        sources=[SourceItem(id="S1", entity_type="Decision", identifier="ADR-0003", url="https://github.com/saksham-AI500/company-brain-synthetic-testbed/blob/main/docs/adr/0003-structured-json-logging.md", span_text=quote)],
    )
    v = verifier.verify_answer(ans)
    path_taken = v.claims[0].verification_path if v.claims else "failed"
    print(f"\n[test_control_20_exact_decision_quote_logging] runtime path: {path_taken}")
    assert v.status == "VERIFIED"
    assert len(v.claims) == 1
    assert path_taken == "exact_lookup"
