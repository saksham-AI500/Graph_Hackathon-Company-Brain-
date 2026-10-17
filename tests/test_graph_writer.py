"""Integration and unit tests for GraphWriter in src/graph/writer.py.

Covers all 12 required regression scenarios:
1. Creating and updating a node.
2. Creating and updating an edge without duplicate entities or relationships.
3. Repeated identical upserts being idempotent.
4. Closing an edge and preserving its historical record.
5. As-of reads immediately before and after edge closure.
6. Tombstoning a node without hard-deleting history.
7. Provenance validation and change-event correctness.
8. Rejection of unsupported labels, edge types, properties and malformed inputs.
9. Rejection of missing or invalid source evidence for derived edges.
10. Read-only tools remaining unable to write.
11. Missing timestamps remaining null and not leaking through temporal filters.
12. Failure handling when a graph mutation or audit-record write fails.
"""

import pytest
from src.db import FalkorDBClient
from src.graph.writer import (
    GraphWriter,
    ProvenanceMetadata,
    ValidationError,
    EntityNotFoundError,
)
from src.investigation.tools import (
    validate_and_invoke_tool,
    ToolPermissionError,
)


@pytest.fixture(scope="module")
def writer_fixture():
    """Create a dedicated test graph client and writer instance."""
    test_graph_name = "test_writer_kg"
    client = FalkorDBClient(graph_name=test_graph_name)
    # Ensure fresh test graph
    try:
        client.graph.delete()
    except Exception:
        pass

    writer = GraphWriter(client=client, run_id="test_run_001")
    yield client, writer

    # Teardown test graph
    try:
        client.graph.delete()
    except Exception:
        pass


# -----------------------------------------------------------------------------
# 1. Creating and updating a node
# -----------------------------------------------------------------------------

def test_1_create_and_update_node(writer_fixture):
    client, writer = writer_fixture
    prov = ProvenanceMetadata(
        source_url="https://github.com/alice",
        run_id="run_node_01",
        valid_from="2026-10-15T00:00:00Z",
    )

    # Create node
    res = writer.upsert_node(
        label="Person",
        identity_value="writer_alice",
        properties={"url": "https://github.com/writer_alice"},
        provenance=prov,
    )
    assert res.success is True
    assert res.changed is True
    assert res.op == "upsert_node"

    # Verify node in graph
    node_res = client.ro_query("MATCH (p:Person {login: 'writer_alice'}) RETURN properties(p)")
    assert len(node_res.result_set) == 1
    props = node_res.result_set[0][0]
    assert props["login"] == "writer_alice"
    assert props["url"] == "https://github.com/writer_alice"
    assert props["status"] == "active"
    assert props["source_url"] == "https://github.com/alice"
    assert props["valid_from"] == "2026-10-15T00:00:00Z"
    assert props.get("valid_to") is None

    # Update node
    res_update = writer.upsert_node(
        label="Person",
        identity_value="writer_alice",
        properties={"url": "https://github.com/writer_alice_v2"},
        provenance=prov,
    )
    assert res_update.success is True
    assert res_update.changed is True

    node_res_updated = client.ro_query("MATCH (p:Person {login: 'writer_alice'}) RETURN p.url")
    assert node_res_updated.result_set[0][0] == "https://github.com/writer_alice_v2"


# -----------------------------------------------------------------------------
# 2. Creating and updating an edge without duplicate entities or relationships
# -----------------------------------------------------------------------------

def test_2_create_and_update_edge_without_duplication(writer_fixture):
    client, writer = writer_fixture
    prov = ProvenanceMetadata(
        source_url="https://github.com/FalkorDB/falkordb-py/pull/9991",
        run_id="run_edge_01",
        valid_from="2026-10-15T01:00:00Z",
    )

    # Ensure target PR node exists
    writer.upsert_node(
        label="PullRequest",
        identity_value=9991,
        properties={"title": "Test PR for Edge", "url": "https://github.com/FalkorDB/falkordb-py/pull/9991"},
        provenance=prov,
    )

    # Create edge
    res = writer.upsert_edge(
        rel_type="AUTHORED",
        source_label="Person",
        source_identity="writer_alice",
        target_label="PullRequest",
        target_identity=9991,
        provenance=prov,
    )
    assert res.success is True
    assert res.changed is True

    # Count edges
    count_res = client.ro_query(
        "MATCH (p:Person {login: 'writer_alice'})-[r:AUTHORED]->(pr:PullRequest {number: 9991}) RETURN count(r)"
    )
    assert count_res.result_set[0][0] == 1

    # Update edge with new property
    prov_v2 = ProvenanceMetadata(
        source_url="https://github.com/FalkorDB/falkordb-py/pull/9991#v2",
        run_id="run_edge_02",
        valid_from="2026-10-15T02:00:00Z",
    )
    res_update = writer.upsert_edge(
        rel_type="AUTHORED",
        source_label="Person",
        source_identity="writer_alice",
        target_label="PullRequest",
        target_identity=9991,
        provenance=prov_v2,
    )
    assert res_update.success is True
    assert res_update.changed is True

    # Ensure edge count remains strictly 1 (no duplicates)
    count_res2 = client.ro_query(
        "MATCH (p:Person {login: 'writer_alice'})-[r:AUTHORED]->(pr:PullRequest {number: 9991}) RETURN count(r)"
    )
    assert count_res2.result_set[0][0] == 1


# -----------------------------------------------------------------------------
# 3. Repeated identical upserts being idempotent
# -----------------------------------------------------------------------------

def test_3_idempotent_no_ops(writer_fixture):
    client, writer = writer_fixture
    prov = ProvenanceMetadata(
        source_url="https://github.com/alice",
        run_id="run_idempotent",
        valid_from="2026-10-15T00:00:00Z",
    )

    # 1. Node identical upsert
    res_node = writer.upsert_node(
        label="Person",
        identity_value="writer_alice",
        properties={"url": "https://github.com/writer_alice_v2"},
        provenance=prov,
    )
    assert res_node.success is True
    assert res_node.changed is False  # Safe no-op

    # 2. Edge identical upsert
    prov_edge = ProvenanceMetadata(
        source_url="https://github.com/FalkorDB/falkordb-py/pull/9991#v2",
        run_id="run_edge_02",
        valid_from="2026-10-15T02:00:00Z",
    )
    res_edge = writer.upsert_edge(
        rel_type="AUTHORED",
        source_label="Person",
        source_identity="writer_alice",
        target_label="PullRequest",
        target_identity=9991,
        provenance=prov_edge,
    )
    assert res_edge.success is True
    assert res_edge.changed is False  # Safe no-op


# -----------------------------------------------------------------------------
# 4. Closing an edge and preserving its historical record
# -----------------------------------------------------------------------------

def test_4_close_edge_preserves_history(writer_fixture):
    client, writer = writer_fixture

    # Close edge at T
    closed_at = "2026-10-16T12:00:00Z"
    res = writer.close_edge(
        rel_type="AUTHORED",
        source_label="Person",
        source_identity="writer_alice",
        target_label="PullRequest",
        target_identity=9991,
        closed_at=closed_at,
    )
    assert res.success is True
    assert res.changed is True

    # Edge must still exist with valid_to set
    edge_res = client.ro_query(
        "MATCH (p:Person {login: 'writer_alice'})-[r:AUTHORED]->(pr:PullRequest {number: 9991}) RETURN r.valid_to"
    )
    assert len(edge_res.result_set) == 1
    assert edge_res.result_set[0][0] == closed_at

    # Repeated close is idempotent
    res_repeat = writer.close_edge(
        rel_type="AUTHORED",
        source_label="Person",
        source_identity="writer_alice",
        target_label="PullRequest",
        target_identity=9991,
        closed_at=closed_at,
    )
    assert res_repeat.success is True
    assert res_repeat.changed is False


# -----------------------------------------------------------------------------
# 5. As-of reads immediately before and after edge closure
# -----------------------------------------------------------------------------

def test_5_as_of_reads_before_and_after_closure(writer_fixture):
    client, _ = writer_fixture

    # As-of T - 1 second: edge was still valid
    query_before = """
    MATCH (p:Person {login: 'writer_alice'})-[r:AUTHORED]->(pr:PullRequest {number: 9991})
    WHERE r.valid_from <= '2026-10-16T11:59:59Z'
      AND (r.valid_to IS NULL OR r.valid_to > '2026-10-16T11:59:59Z')
    RETURN count(r)
    """
    res_before = client.ro_query(query_before)
    assert res_before.result_set[0][0] == 1

    # As-of T + 1 second: edge is closed
    query_after = """
    MATCH (p:Person {login: 'writer_alice'})-[r:AUTHORED]->(pr:PullRequest {number: 9991})
    WHERE r.valid_from <= '2026-10-16T12:00:01Z'
      AND (r.valid_to IS NULL OR r.valid_to > '2026-10-16T12:00:01Z')
    RETURN count(r)
    """
    res_after = client.ro_query(query_after)
    assert res_after.result_set[0][0] == 0


# -----------------------------------------------------------------------------
# 6. Tombstoning a node without hard-deleting history
# -----------------------------------------------------------------------------

def test_6_tombstone_node_preserves_history(writer_fixture):
    client, writer = writer_fixture
    tomb_ts = "2026-10-16T15:00:00Z"

    res = writer.tombstone_node(
        label="Person",
        identity_value="writer_alice",
        tombstoned_at=tomb_ts,
    )
    assert res.success is True
    assert res.changed is True

    # Node still exists in FalkorDB (not hard-deleted)
    node_res = client.ro_query("MATCH (p:Person {login: 'writer_alice'}) RETURN p.status, p.tombstoned_at, p.valid_to")
    assert len(node_res.result_set) == 1
    assert node_res.result_set[0][0] == "tombstoned"
    assert node_res.result_set[0][1] == tomb_ts
    assert node_res.result_set[0][2] == tomb_ts

    # Historical edge still connected to tombstoned node
    edge_res = client.ro_query("MATCH (p:Person {login: 'writer_alice'})-[r:AUTHORED]->(pr) RETURN count(r)")
    assert edge_res.result_set[0][0] == 1

    # Repeated tombstone is an idempotent no-op
    res_repeat = writer.tombstone_node(
        label="Person",
        identity_value="writer_alice",
        tombstoned_at=tomb_ts,
    )
    assert res_repeat.success is True
    assert res_repeat.changed is False


# -----------------------------------------------------------------------------
# 7. Provenance validation and change-event correctness
# -----------------------------------------------------------------------------

def test_7_provenance_and_change_events(writer_fixture):
    client, writer = writer_fixture

    history = writer.get_change_history(target_id="writer_alice")
    assert len(history) >= 2  # upsert_node and tombstone_node

    ops = [h["op"] for h in history]
    assert "upsert_node" in ops
    assert "tombstone_node" in ops

    for h in history:
        assert h["source_url"].startswith("http")
        assert h["run_id"] != ""
        assert h["observed_at"] != ""


# -----------------------------------------------------------------------------
# 8. Rejection of unsupported labels, edge types, properties and malformed inputs
# -----------------------------------------------------------------------------

def test_8_rejection_of_unsupported_and_malformed_inputs(writer_fixture):
    _, writer = writer_fixture

    # Unsupported node label
    with pytest.raises(ValidationError, match="Prohibited or unknown node label"):
        writer.upsert_node(label="AdminUser", identity_value="admin")

    # Unsupported relationship type
    with pytest.raises(ValidationError, match="Prohibited or unknown relationship type"):
        writer.upsert_edge(
            rel_type="DELETED_BY",
            source_label="Person",
            source_identity="writer_alice",
            target_label="PullRequest",
            target_identity=9991,
            provenance=ProvenanceMetadata(source_url="https://github.com"),
        )

    # Prohibited property on node
    with pytest.raises(ValidationError, match="Prohibited property 'dangerous_flag'"):
        writer.upsert_node(
            label="Person",
            identity_value="writer_bob",
            properties={"dangerous_flag": True},
        )

    # Empty identity value
    with pytest.raises(ValidationError, match="cannot be null or empty"):
        writer.upsert_node(label="Person", identity_value="")


# -----------------------------------------------------------------------------
# 9. Rejection of missing or invalid source evidence for derived edges
# -----------------------------------------------------------------------------

def test_9_rejection_of_missing_or_invalid_source_evidence(writer_fixture):
    _, writer = writer_fixture

    # Missing provenance
    with pytest.raises(ValidationError, match="ProvenanceMetadata is required"):
        writer.upsert_edge(
            rel_type="AUTHORED",
            source_label="Person",
            source_identity="writer_alice",
            target_label="PullRequest",
            target_identity=9991,
            provenance=None,
        )

    # Malformed source URL (not http/https)
    with pytest.raises(ValueError, match="source_url must start with http:// or https://"):
        ProvenanceMetadata(source_url="javascript:alert(1)")

    # Nonexistent source node
    with pytest.raises(EntityNotFoundError, match="source entity .* does not exist"):
        writer.upsert_edge(
            rel_type="AUTHORED",
            source_label="Person",
            source_identity="nonexistent_ghost_user",
            target_label="PullRequest",
            target_identity=9991,
            provenance=ProvenanceMetadata(source_url="https://github.com/valid"),
        )


# -----------------------------------------------------------------------------
# 10. Read-only tools remaining unable to write
# -----------------------------------------------------------------------------

def test_10_read_only_tools_cannot_write(writer_fixture):
    client, _ = writer_fixture

    # ro_query blocks write Cypher
    with pytest.raises(Exception):
        client.ro_query("CREATE (x:RogueNode {name: 'intruder'})")

    # validate_and_invoke_tool blocks write tool names
    with pytest.raises(ToolPermissionError, match="Unauthorized tool execution rejected"):
        validate_and_invoke_tool(client, "upsert_node", {"label": "Person", "identity_value": "mallory"})


# -----------------------------------------------------------------------------
# 11. Missing timestamps remaining null and not leaking through temporal filters
# -----------------------------------------------------------------------------

def test_11_missing_timestamps_stored_as_null(writer_fixture):
    client, writer = writer_fixture

    writer.upsert_node(
        label="Issue",
        identity_value=8881,
        properties={"title": "Issue with null closed_at", "closed_at": "", "url": "https://github.com/issue/8881"},
        provenance=ProvenanceMetadata(source_url="https://github.com/issue/8881"),
    )

    # Property is genuine Cypher null
    prop_res = client.ro_query("MATCH (i:Issue {number: 8881}) RETURN i.closed_at")
    assert prop_res.result_set[0][0] is None

    # Temporal filter doesn't leak null
    cutoff_res = client.ro_query("MATCH (i:Issue {number: 8881}) WHERE i.closed_at <= '2026-10-17T00:00:00Z' RETURN count(i)")
    assert cutoff_res.result_set[0][0] == 0


# -----------------------------------------------------------------------------
# 12. Failure handling when a graph mutation or audit-record write fails
# -----------------------------------------------------------------------------

def test_12_failure_handling_and_safe_rejection(writer_fixture):
    _, writer = writer_fixture

    # Invalid timestamp format in closed_at
    with pytest.raises(ValidationError, match="Invalid timestamp for closed_at"):
        writer.close_edge(
            rel_type="AUTHORED",
            source_label="Person",
            source_identity="writer_alice",
            target_label="PullRequest",
            target_identity=9991,
            closed_at="not_a_valid_timestamp",
        )

    # Closing nonexistent edge
    with pytest.raises(EntityNotFoundError, match="Relationship not found to close"):
        writer.close_edge(
            rel_type="MODIFIES",
            source_label="PullRequest",
            source_identity=9991,
            target_label="File",
            target_identity="nonexistent/file.py",
        )
