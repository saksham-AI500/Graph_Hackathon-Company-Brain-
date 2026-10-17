"""End-to-End Acceptance Tests for RepoBrain Evidence-Path UI & Integration."""

from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from src.db import FalkorDBClient
from src.investigation.orchestrator import PROrchestrator
from src.investigation.models import PRBrief, PRBriefMetadata, LinkedIssueFinding

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture
def client():
    c = FalkorDBClient()
    c.ping()
    return c


@pytest.fixture
def orchestrator():
    return PROrchestrator()


def test_ui_initial_load():
    """Verify Streamlit app loads cleanly without unhandled exceptions."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert len(at.exception) == 0
    assert len(at.form_submit_button) == 1
    assert at.text_input[0].value == "3339"


def test_ui_investigate_pr_with_linked_issue():
    """Verify UI workflow for PR #3339 (resolves Issue #3338)."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    at.text_input[0].input("3339")
    at.form_submit_button[0].click().run()

    assert len(at.exception) == 0
    # Success card rendered
    assert any("[VERIFIED]" in s.value for s in at.success)
    # 4 tabs rendered (Executive Brief, Ownership Drift, Reviewers & Co-Changes, Auditable Evidence Paths)
    assert any(t.label == "Executive Brief" for t in at.tabs)
    assert any(t.label == "Ownership Drift" for t in at.tabs)
    assert any(t.label == "Reviewers & Co-Changes" for t in at.tabs)
    assert any(t.label == "Auditable Evidence Paths" for t in at.tabs)

    # Check that issue #3338 is referenced in markdown content
    markdown_texts = [m.value for m in at.markdown]
    combined_md = " ".join(markdown_texts)
    assert "3338" in combined_md
    assert "AviAvni" in combined_md
    assert "https://github.com/FalkorDB/FalkorDB/pull/3339" in combined_md


def test_ui_investigate_pr_without_linked_issue():
    """Verify UI workflow for PR #3342 (no linked issue)."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    at.text_input[0].input("https://github.com/FalkorDB/FalkorDB/pull/3342")
    at.form_submit_button[0].click().run()

    assert len(at.exception) == 0
    assert any("[VERIFIED]" in s.value for s in at.success)

    combined_md = " ".join([m.value for m in at.markdown])
    assert "No linked issues were closed" in combined_md or "No linked issue was closed" in combined_md
    assert "https://github.com/FalkorDB/FalkorDB/pull/3342" in combined_md


def test_ui_investigate_nonexistent_pr_refusal():
    """Verify UI handles nonexistent PR with explicit refusal card."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    at.text_input[0].input("9999")
    at.form_submit_button[0].click().run()

    assert len(at.exception) == 0
    # Refusal warning card rendered
    assert len(at.warning) >= 1
    assert any("[REFUSED]" in w.value for w in at.warning)
    assert any("not exist" in i.value or "not found" in i.value for i in at.info)


def test_ui_anti_circularity_target_pr_exclusion(orchestrator):
    """Verify historical reviewers rendered in UI never include target PR as precedent."""
    brief = orchestrator.investigate(3339)
    assert brief.status == "VERIFIED"
    for reviewer in brief.historical_reviewers:
        for pr_url in reviewer.evidence_pr_urls:
            assert not pr_url.endswith("/pull/3339"), (
                f"Circularity violation: Target PR 3339 cited as evidence for {reviewer.login}"
            )


def test_ui_renders_clickable_evidence_paths(orchestrator):
    """Verify all evidence sources have valid clickable URLs."""
    brief = orchestrator.investigate(3339)
    assert len(brief.evidence_sources) > 0
    for src in brief.evidence_sources:
        assert src.url.startswith("https://github.com/FalkorDB/FalkorDB/")
        assert src.entity_type in ["PullRequest", "Issue", "File", "Person"]


def test_ui_database_unavailability_handling(monkeypatch):
    """Verify UI shows clean error banner when FalkorDB is unavailable."""
    # Force get_db_client to return None
    import src.ui.app as ui_app
    monkeypatch.setattr(ui_app, "get_db_client", lambda: None)

    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert len(at.exception) == 0
    # Error message rendered indicating database offline
    assert len(at.error) >= 1
    combined_err = " ".join([e.value for e in at.error])
    assert "Database Connection Failed" in combined_err or "OFFLINE" in combined_err


def test_ui_get_orchestrator_reuses_client(client):
    """Verify get_orchestrator properly binds and reuses provided client."""
    import streamlit as st
    from src.ui.app import get_orchestrator
    st.cache_resource.clear()
    orch = get_orchestrator(_client=client)
    assert orch is not None
    assert orch.client is client


def test_ui_investigate_pr_with_hash_prefix():
    """Verify UI handles PR target entered with leading '#' (e.g. '#3339')."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()

    at.text_input[0].input("#3339")
    at.form_submit_button[0].click().run()

    assert len(at.exception) == 0
    assert len(at.success) >= 1
    assert any("[VERIFIED]" in s.value for s in at.success)


def test_ui_renders_visual_evidence_paths_and_pagerank():
    """Verify UI renders FalkorDB visual evidence paths and PageRank maintainers."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    at.text_input[0].input("3339")
    at.form_submit_button[0].click().run()

    assert len(at.exception) == 0
    subheaders = [s.value for s in at.subheader]
    assert "FalkorDB Visual Evidence Paths" in subheaders
    assert "FalkorDB Graph Algorithm: Maintainer Review Centrality" in subheaders
    md_text = " ".join([m.value for m in at.markdown])
    assert "PageRank Score" in md_text
    assert "&rarr;" in md_text



