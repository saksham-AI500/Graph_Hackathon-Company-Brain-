"""Automated tests for Declared Ownership (CODEOWNERS), Observed Activity, and Non-LLM Verifier."""

import pytest
from src.db import FalkorDBClient
from src.ownership.codeowners import CodeownersParser
from src.ownership.discrepancy import evaluate_ownership_discrepancy, OwnershipDiscrepancyReport
from src.ownership.metrics import get_file_authorship, get_file_review_activity, get_reviewer_concentration
from src.ownership.verifier import NonLLMEvidenceVerifier


@pytest.fixture(scope="module")
def client():
    c = FalkorDBClient()
    assert c.ping()["status"] == "healthy"
    return c


@pytest.fixture(scope="module")
def codeowners():
    return CodeownersParser.from_cache_or_default()


@pytest.fixture(scope="module")
def verifier(client):
    return NonLLMEvidenceVerifier(client)


# 1. CODEOWNERS Parser Tests
def test_codeowners_parser_rules(codeowners):
    """Verify CODEOWNERS parsed the official rules correctly."""
    assert len(codeowners.rules) >= 3
    patterns = [r.pattern for r in codeowners.rules]
    assert "/build/" in patterns
    assert "/.github/" in patterns
    assert "/CODEOWNERS" in patterns


def test_codeowners_matching_team_declaration(codeowners):
    """Verify path matching for team-level declared ownership."""
    # Test directory under /build/
    match_build = codeowners.match("build/CMakeLists.txt")
    assert match_build.matched is True
    assert "@FalkorDB/falkordb-core" in match_build.owners
    assert match_build.is_team is True
    assert match_build.rule_pattern == "/build/"

    # Test file under /.github/
    match_gh = codeowners.match(".github/workflows/ci.yml")
    assert match_gh.matched is True
    assert "@FalkorDB/falkordb-core" in match_gh.owners

    # Test CODEOWNERS self-file
    match_self = codeowners.match("CODEOWNERS")
    assert match_self.matched is True
    assert "@FalkorDB/falkordb-core" in match_self.owners


def test_codeowners_matching_unowned_file(codeowners):
    """Verify unowned files (e.g. src/ or tests/) return matched=False without fabrication."""
    match_src = codeowners.match("src/commands/bulk_insert.rs")
    assert match_src.matched is False
    assert len(match_src.owners) == 0
    assert "File does not match any declared pattern" in (match_src.ambiguity or "")


# 2. Observed Activity & Bot Handling
def test_bot_reviewer_handling(client):
    """Verify raw bot reviews are captured when requested, but excluded from human maintainer sets."""
    file_path = "graph/src/runtime/pending.rs"

    # With bots included
    with_bots = get_file_review_activity(client, file_path, include_bots=True)
    bot_names = [r["reviewer"] for r in with_bots["reviewers"] if r["is_bot"]]
    assert len(bot_names) >= 2
    assert any("cubic-dev-ai" in b for b in bot_names)

    # Without bots
    without_bots = get_file_review_activity(client, file_path, include_bots=False)
    human_names = [r["reviewer"] for r in without_bots["reviewers"]]
    assert not any("[bot]" in h for h in human_names)
    assert "DvirDukhan" in human_names
    assert "AviAvni" in human_names


def test_reviewer_concentration_metrics(client):
    """Verify HHI concentration calculation on human reviews."""
    file_path = "tests/flow/test_rdb_load.py"
    conc = get_reviewer_concentration(client, file_path)

    assert conc["file_path"] == file_path
    # DvirDukhan represents the dominant human reviewer for this file
    assert conc["top_reviewer_share"] > 0.5
    assert conc["concentration_hhi"] > 0.5


# 3. Ownership Discrepancy Scenarios
def test_discrepancy_unowned_with_active_maintainers(client, codeowners, verifier):
    """Scenario: File with no declared owner, but active human reviewers."""
    file_path = "graph/src/runtime/pending.rs"
    report = evaluate_ownership_discrepancy(client, file_path, codeowners)

    assert report.has_declared_owner is False
    assert report.discrepancy_category == "UNOWNED_WITH_ACTIVE_MAINTAINERS"
    assert "DvirDukhan" in report.observed_human_reviewers
    assert "AviAvni" in report.observed_human_reviewers
    assert report.total_modifying_prs == 2
    assert len(report.supporting_prs) == 2

    # Run verifier
    v_res = verifier.verify_ownership_report(report)
    assert v_res.is_valid is True
    assert v_res.status == "VERIFIED"
    assert v_res.verified_prs_count == 2


def test_discrepancy_team_declaration_with_individual_activity(client, verifier):
    """Scenario: Team-level declaration where individual reviewers execute the work."""
    # Synthetic parser representing team declaration on build/
    custom_parser = CodeownersParser(content="/graph/src/  @FalkorDB/falkordb-core\n")
    file_path = "graph/src/runtime/pending.rs"
    report = evaluate_ownership_discrepancy(client, file_path, custom_parser)

    assert report.has_declared_owner is True
    assert report.is_team_declaration is True
    assert report.discrepancy_category == "TEAM_DECLARED_INDIVIDUAL_ACTIVE"
    assert "DvirDukhan" in report.observed_human_reviewers
    assert any("GitHub team" in limit for limit in report.limitations)

    v_res = verifier.verify_ownership_report(report)
    assert v_res.is_valid is True


def test_discrepancy_sparse_or_unrecorded_history(client, codeowners, verifier):
    """Scenario: File with 0 PRs in the ingested sample."""
    file_path = "src/nonexistent/missing_file.rs"
    report = evaluate_ownership_discrepancy(client, file_path, codeowners)

    assert report.discrepancy_category == "INSUFFICIENT_EVIDENCE"
    assert report.confidence_level == "INSUFFICIENT"
    assert report.total_modifying_prs == 0

    v_res = verifier.verify_ownership_report(report)
    assert v_res.is_valid is True


# 4. Non-LLM Verifier Rejection of Fabricated Evidence
def test_verifier_rejects_fabricated_pr(client, codeowners, verifier):
    """Verify that the NonLLMEvidenceVerifier detects and rejects synthetic/fabricated claims."""
    file_path = "graph/src/runtime/pending.rs"
    report = evaluate_ownership_discrepancy(client, file_path, codeowners)

    # Inject a fabricated PR record into the report
    fake_pr = {
        "number": 99999,
        "title": "Fabricated PR",
        "url": "https://github.com/FalkorDB/FalkorDB/pull/99999",
        "merged_at": "2026-10-15T00:00:00Z",
    }
    report.supporting_prs.append(fake_pr)
    report.total_modifying_prs += 1

    v_res = verifier.verify_ownership_report(report)
    assert v_res.is_valid is False
    assert v_res.status == "REJECTED"
    assert any("Fabrication detected: PR #99999" in r for r in v_res.rejection_reasons)


def test_verifier_rejects_unsupported_reviewer(client, codeowners, verifier):
    """Verify that the NonLLMEvidenceVerifier rejects reviewers not present in actual graph records."""
    file_path = "graph/src/runtime/pending.rs"
    report = evaluate_ownership_discrepancy(client, file_path, codeowners)

    # Inject a nonexistent reviewer
    report.observed_human_reviewers.append("ghost_maintainer_404")

    v_res = verifier.verify_ownership_report(report)
    assert v_res.is_valid is False
    assert v_res.status == "REJECTED"
    assert any("Unsupported claim: Reviewer 'ghost_maintainer_404'" in r for r in v_res.rejection_reasons)


def test_evaluate_ownership_discrepancy_respects_temporal_cutoff(client, codeowners):
    """Verify that evaluate_ownership_discrepancy strictly excludes reviews after the cutoff."""
    file_path = "build/runtime/Dockerfile"

    # Cutoff well before any 2026 PRs
    early_cutoff = "2024-01-01T00:00:00Z"
    early_report = evaluate_ownership_discrepancy(
        client, file_path, codeowners, cutoff_timestamp=early_cutoff
    )
    assert early_report.total_modifying_prs == 0
    assert len(early_report.observed_human_reviewers) == 0

    # Cutoff after all PRs
    late_cutoff = "2026-10-15T00:00:00Z"
    late_report = evaluate_ownership_discrepancy(
        client, file_path, codeowners, cutoff_timestamp=late_cutoff
    )
    assert late_report.declared_owners == ["@FalkorDB/falkordb-core"]

