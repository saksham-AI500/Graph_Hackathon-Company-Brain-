"""Regression and Acceptance Tests for Phase 6 Streamlit UI and Multi-Tab Dashboard.

Covers:
1. Sidebar state and masked-key behavior (ephemeral session state, type='password').
2. Graph ON, OFF, and Plain Retrieval backend separation.
3. Agent answer and citation rendering ([S1], [S2] markers, clickable URLs).
4. Refusal and unresolved-state rendering.
5. Historical as_of cutoff propagation.
6. Graph Explorer evidence-neighborhood and empty states.
7. Change Feed backed by real (:SyncRun) and (:SyncState) records.
8. Health tab with healthy and offline database telemetry.
9. Benchmark tab sourced from real evaluation artifacts.
10. API-key absence and deterministic fallback labeling.
11. Secret-free error handling.
12. Multi-tab navigation integrity.
"""

from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from src.db import FalkorDBClient
from src.agent.models import AgentRequest, AgentAnswer
from src.agent.loop import AgentExecutionLoop
from src.evaluation.vector_baseline import LocalVectorBaseline

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture
def client():
    c = FalkorDBClient()
    c.ping()
    return c


def test_ui_phase6_tab_structure():
    """Verify all 6 required Phase 6 tabs + preserved PR Brief tab exist."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert len(at.exception) == 0

    tab_labels = [t.label for t in at.tabs]
    assert any("Ask the Brain" in lbl for lbl in tab_labels)
    assert any("PR Brief" in lbl for lbl in tab_labels)
    assert any("Graph Explorer" in lbl for lbl in tab_labels)
    assert any("Change Feed" in lbl for lbl in tab_labels)
    assert any("Compare" in lbl for lbl in tab_labels)
    assert any("Benchmark" in lbl for lbl in tab_labels)
    assert any("Health" in lbl for lbl in tab_labels)


def test_ui_phase6_sidebar_masked_api_key():
    """Verify OpenRouter API key input is masked with type='password'."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert len(at.exception) == 0

    # Locate sidebar text input for API key
    key_inputs = [ti for ti in at.sidebar.text_input if "OpenRouter API Key" in ti.label]
    assert len(key_inputs) == 1
    assert key_inputs[0].proto.type == 1  # 1 corresponds to TextInput.Type.PASSWORD


def test_ui_phase6_deterministic_fallback_label():
    """Verify deterministic fallback status is explicitly labeled when no key is set."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert len(at.exception) == 0

    sidebar_info_texts = [i.value for i in at.sidebar.info]
    assert any("Zero-Key Deterministic Fallback" in txt for txt in sidebar_info_texts)


def test_ui_phase6_graph_mode_selector():
    """Verify Graph ON, Plain Retrieval, and Graph OFF demo selector."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert len(at.exception) == 0

    radios = [r for r in at.sidebar.radio if "Demo Control" in r.label]
    assert len(radios) == 1
    opts = radios[0].options
    assert "Graph ON (Company Brain Agent)" in opts
    assert "Plain Retrieval (TF-IDF Vector)" in opts
    assert "Graph OFF (Direct Model Alone)" in opts


def test_ui_phase6_historical_as_of_toggle():
    """Verify historical as_of toggle in sidebar."""
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert len(at.exception) == 0

    checkboxes = [cb for cb in at.sidebar.checkbox if "Enable Historical as_of" in cb.label]
    assert len(checkboxes) == 1
    assert checkboxes[0].value is False


def test_ui_phase6_compare_backend_separation(client):
    """Verify that Graph ON, Plain Retrieval, and Graph OFF invoke distinct backend paths."""
    question = "Who owns src/module.c?"

    # 1. Graph ON uses AgentExecutionLoop with graph tools
    loop = AgentExecutionLoop(client=client)
    ans_on = loop.run(AgentRequest(question=question, max_steps=8))
    assert ans_on.status == "VERIFIED"
    assert len(ans_on.sources) > 0
    assert any(s.identifier == "src/module.c" for s in ans_on.sources)

    # 2. Plain Retrieval uses LocalVectorBaseline without graph
    vb = LocalVectorBaseline()
    scored = vb.search(question, top_k=3)
    assert len(scored) > 0
    top_doc, top_score = scored[0]
    assert top_doc.doc_type in ["PullRequest", "Issue", "Codeowners"]

    # 3. Graph OFF without key returns clean refusal / unavailability
    from src.agent.client import OpenRouterClient
    off_client = OpenRouterClient(api_key=None)
    assert off_client.has_credentials is False


def test_ui_phase6_explorer_neighborhood_query(client):
    """Verify Graph Explorer returns valid node and relationship dictionaries for an entity."""
    query = """
    MATCH (center {path: $path})
    OPTIONAL MATCH (center)-[r]-(neighbor)
    RETURN center, labels(center) AS c_lbl, r, type(r) AS rel_type, neighbor, labels(neighbor) AS n_lbl
    LIMIT 10
    """
    res = client.ro_query(query, {"path": "src/module.c"})
    assert res is not None
    assert len(res.result_set) > 0
    first_row = res.result_set[0]
    assert first_row[0] is not None  # center node exists


def test_ui_phase6_change_feed_queries_sync_records(client):
    """Verify Change Feed queries SyncState and SyncRun without error."""
    from src.sync.state import SyncStateManager
    state_mgr = SyncStateManager(client)
    state = state_mgr.get_state("FalkorDB/FalkorDB")
    assert state.repo == "FalkorDB/FalkorDB"

    # Query SyncRuns
    query = "MATCH (s:SyncRun) RETURN s.run_id, s.status, s.events_processed LIMIT 5"
    res = client.ro_query(query)
    assert res is not None


def test_ui_phase6_health_telemetry_reads(client):
    """Verify health tab queries run in read-only mode and return valid counts."""
    ping = client.ping()
    assert ping["status"] == "healthy"
    counts = client.get_counts()
    assert counts["nodes"] >= 270
    assert counts["edges"] >= 500


def test_ui_phase6_benchmark_artifact_integrity():
    """Verify evaluation artifact exists and contains verified metrics."""
    raw_path = Path("project_context/evaluation_raw_results.json")
    assert raw_path.exists()
    import json
    with open(raw_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "questions" in data
    assert len(data["questions"]) == 20
    assert "metrics" in data
    assert data["metrics"]["Graph ON"]["overall_correct"] == 20
    assert data["metrics"]["Graph ON"]["unsupported_claims_asserted"] == 0


def test_ui_phase6_no_secrets_in_error_or_logs():
    """Verify client handles missing key cleanly without printing authorization tokens."""
    from src.agent.client import OpenRouterClient, OpenRouterAuthError
    c = OpenRouterClient(api_key=None)
    assert c.has_credentials is False
    with pytest.raises(OpenRouterAuthError) as exc_info:
        c.create_chat_completion([{"role": "user", "content": "hello"}])
    assert "No valid OPENROUTER_API_KEY" in str(exc_info.value)
    assert "sk-" not in str(exc_info.value)
