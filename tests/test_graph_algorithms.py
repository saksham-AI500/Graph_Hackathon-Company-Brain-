"""Unit and integration tests for FalkorDB native graph algorithms and explanation paths."""

import pytest
from src.db import FalkorDBClient
from src.graph.algorithms import find_explanation_path, run_maintainer_pagerank


@pytest.fixture
def client():
    c = FalkorDBClient()
    c.ping()
    return c


def test_maintainer_pagerank_on_repo_kg(client):
    """Verify PageRank algorithm returns ranked maintainers on real repo_kg."""
    ranks = run_maintainer_pagerank(client, limit=5)
    assert len(ranks) > 0
    top = ranks[0]
    assert "login" in top
    assert "score" in top
    assert top["score"] > 0
    assert "url" in top


def test_find_explanation_path_pr_to_issue(client):
    """Verify shortest-path explanation between PR #3307 and Issue #3306 on repo_kg."""
    path = find_explanation_path(client, pr_number=3307, target_identifier=3306)
    assert path is not None
    assert path["hop_count"] == 1
    assert len(path["hops"]) == 1
    hop = path["hops"][0]
    assert "PullRequest" in hop["source"]
    assert hop["relationship"] == "RESOLVES"
    assert "Issue" in hop["target"]
    assert len(path["evidence_urls"]) >= 2


def test_graph_algorithm_on_synthetic_graph():
    """Verify PageRank and ShortestPath algorithms on an isolated synthetic graph."""
    test_client = FalkorDBClient(graph_name="test_kg_algo_synth")
    try:
        test_client.query("MATCH (n) DETACH DELETE n")
        test_client.query(
            """
            CREATE (pr1:PullRequest {number: 101, title: 'Add feature'})
            CREATE (pr2:PullRequest {number: 102, title: 'Fix bug'})
            CREATE (f:File {path: 'src/lib.rs'})
            CREATE (p1:Person {login: 'lead_dev', url: 'https://github.com/lead_dev'})
            CREATE (p2:Person {login: 'reviewer_bob', url: 'https://github.com/reviewer_bob'})
            CREATE (pr1)-[:MODIFIES]->(f)
            CREATE (pr2)-[:MODIFIES]->(f)
            CREATE (p1)-[:AUTHORED]->(pr1)
            CREATE (p2)-[:REVIEWED {state: 'APPROVED', submitted_at: '2026-10-01T00:00:00Z'}]->(pr1)
            CREATE (p2)-[:REVIEWED {state: 'APPROVED', submitted_at: '2026-10-02T00:00:00Z'}]->(pr2)
            """
        )

        # 1. Test PageRank on synthetic graph
        ranks = run_maintainer_pagerank(test_client, limit=5)
        # reviewer_bob reviewed 2 PRs, lead_dev reviewed 0 PRs
        logins = [r["login"] for r in ranks]
        assert "reviewer_bob" in logins
        bob_entry = next(r for r in ranks if r["login"] == "reviewer_bob")
        assert bob_entry["review_count"] == 2
        assert bob_entry["score"] > 0

        # 2. Test Shortest Path on synthetic graph
        # Path from PR 101 to PR 102 via File: (pr1)-[:MODIFIES]->(f)<-[:MODIFIES]-(pr2)
        path = find_explanation_path(test_client, pr_number=101, target_identifier=102, max_depth=3)
        assert path is not None
        assert path["hop_count"] == 2
        assert len(path["hops"]) == 2
        assert path["hops"][0]["relationship"] == "MODIFIES"
        assert path["hops"][1]["relationship"] == "MODIFIES"
    finally:
        test_client.query("MATCH (n) DETACH DELETE n")


def test_pagerank_distinguishes_human_maintainers_and_bots(client):
    """Verify PageRank distinguishes humans from bots and provides distinct scores."""
    all_ranks = run_maintainer_pagerank(client, limit=10, include_bots=True)
    assert any(r["is_bot"] for r in all_ranks)

    human_ranks = run_maintainer_pagerank(client, limit=5, include_bots=False)
    assert len(human_ranks) > 0
    assert not any(r["is_bot"] for r in human_ranks)

    # Verify scores are varied rather than flat uniform
    scores = [r["score"] for r in human_ranks]
    assert len(set(scores)) > 1, "PageRank scores should not be uniform across maintainers"


def test_find_explanation_path_edge_cases(client):
    """Verify find_explanation_path handles missing nodes, self targets, and invalid IDs safely."""
    # 1. Nonexistent target
    assert find_explanation_path(client, pr_number=3339, target_identifier=99999) is None
    # 2. Nonexistent source
    assert find_explanation_path(client, pr_number=99999, target_identifier=3338) is None
    # 3. Source equals Target
    assert find_explanation_path(client, pr_number=3339, target_identifier=3339) is None
    # 4. Invalid negative IDs
    assert find_explanation_path(client, pr_number=-1, target_identifier="invalid") is None
    # 5. Nonexistent user
    assert find_explanation_path(client, pr_number=3339, target_identifier="nonexistent_dev_xyz") is None


def test_find_explanation_path_directionality_and_depth_limits(client):
    """Verify bidirectional traversal, depth limits, and unreachable nodes."""
    # 1. Reverse direction: Person REVIEWED PullRequest (dst -> src in graph)
    path_rev = find_explanation_path(client, pr_number=3339, target_identifier="cubic-dev-ai[bot]", max_depth=2)
    assert path_rev is not None
    assert path_rev["hop_count"] == 1
    assert any(h["relationship"] == "REVIEWED" for h in path_rev["hops"])

    # 2. Forward direction: PullRequest RESOLVES Issue (src -> dst in graph)
    path_fwd = find_explanation_path(client, pr_number=3339, target_identifier=3338, max_depth=2)
    assert path_fwd is not None
    assert path_fwd["hop_count"] == 1
    assert path_fwd["hops"][0]["relationship"] == "RESOLVES"

    # 3. Unreachable disconnected node returns None
    test_client = FalkorDBClient(graph_name="test_kg_algo_synth")
    try:
        test_client.query("MATCH (n) DETACH DELETE n")
        test_client.query("CREATE (:PullRequest {number: 201}) CREATE (:File {path: 'isolated.py'})")
        unreachable = find_explanation_path(test_client, pr_number=201, target_identifier="isolated.py", max_depth=3)
        assert unreachable is None
    finally:
        test_client.query("MATCH (n) DETACH DELETE n")


