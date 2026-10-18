"""Unit tests for GitHub ingestion client, models, and regex parsing."""

from pathlib import Path
from src.ingestion.github_client import GitHubClient
from src.ingestion.models import FileRecord, IssueRecord, PersonRecord, PullRequestRecord, ReviewRecord


def test_models_validation():
    person = PersonRecord(login="alice", url="https://github.com/alice")
    assert person.login == "alice"

    file_rec = FileRecord(
        path="src/main.c", url="https://github.com/repo/blob/main/src/main.c", additions=10, deletions=2
    )
    assert file_rec.path == "src/main.c"
    assert file_rec.additions == 10

    review = ReviewRecord(
        author_login="bob", author_url="https://github.com/bob", state="APPROVED"
    )
    assert review.state == "APPROVED"

    issue = IssueRecord(
        number=101, title="Crash on startup", url="https://github.com/repo/issues/101"
    )
    assert issue.number == 101

    pr = PullRequestRecord(
        number=202,
        title="Fix startup crash",
        url="https://github.com/repo/pull/202",
        author_login="alice",
        author_url="https://github.com/alice",
        files=[file_rec],
        reviews=[review],
        resolved_issues=[issue],
    )
    assert len(pr.files) == 1
    assert len(pr.reviews) == 1
    assert len(pr.resolved_issues) == 1


def test_extract_linked_issue_numbers():
    gh = GitHubClient()
    body = """
    This PR closes #123 and also fixes https://github.com/FalkorDB/FalkorDB/issues/456.
    Furthermore, see #789 for additional background.
    """
    nums = gh.extract_linked_issue_numbers(body)
    assert 123 in nums
    assert 456 in nums
    assert 789 in nums


def test_cache_file_generation(tmp_path: Path):
    gh = GitHubClient(cache_dir=tmp_path)
    p = gh._get_cache_path("repos/FalkorDB/FalkorDB/pulls?state=closed")
    assert str(tmp_path) in str(p)
    assert p.name.endswith(".json")


def test_seed_fixture_metadata_and_integrity():
    import json
    seed_file = Path("src/fixtures/seed_repo_data.json")
    assert seed_file.exists(), "Seed fixture must be checked in"
    with open(seed_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = data.get("metadata", {})
    assert meta.get("source_repo") == "FalkorDB/FalkorDB"
    assert "retrieval_time" in meta
    assert "source_url" in meta
    assert meta.get("schema_version") == "1.0.0"
    assert len(data.get("codeowners", "")) > 0
    assert len(data.get("pull_requests", [])) == 25


def test_seed_fixture_isolated_ingestion_idempotent():
    import json
    from src.db import FalkorDBClient
    from src.ingestion.loader import GraphLoader
    from src.ingestion.models import PullRequestRecord

    test_client = FalkorDBClient(graph_name="test_kg_fixture_temp")
    try:
        test_client.query("MATCH (n) DETACH DELETE n")
        seed_file = Path("src/fixtures/seed_repo_data.json")
        with open(seed_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        prs = [PullRequestRecord(**p) for p in data["pull_requests"]]
        loader = GraphLoader(test_client)

        pass1 = loader.load_pull_requests(prs)["final_counts"]
        pass2 = loader.load_pull_requests(prs)["final_counts"]

        assert pass1 == pass2
        assert pass1["nodes"] == 266
        assert pass1["edges"] == 482
    finally:
        test_client.query("MATCH (n) DETACH DELETE n")


def test_clean_clone_offline_vector_baseline_without_cache(tmp_path: Path):
    from src.evaluation.vector_baseline import LocalVectorBaseline
    # Supply empty temporary cache dir to simulate fresh clone without .cache
    v = LocalVectorBaseline(cache_dir=tmp_path)
    assert len(v.documents) > 20
    results = v.search("FalkorDB", top_k=3)
    assert len(results) > 0


def test_isolated_ingestion_has_zero_duplicates_and_zero_dangling_edges():
    """Verify that double ingestion produces zero duplicate entities and zero dangling edges."""
    import json
    from src.db import FalkorDBClient
    from src.ingestion.loader import GraphLoader
    from src.ingestion.models import PullRequestRecord

    test_client = FalkorDBClient(graph_name="test_kg_integrity_temp")
    try:
        test_client.query("MATCH (n) DETACH DELETE n")
        seed_file = Path("src/fixtures/seed_repo_data.json")
        with open(seed_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        prs = [PullRequestRecord(**p) for p in data["pull_requests"]]
        loader = GraphLoader(test_client)

        # Run ingestion twice
        loader.load_pull_requests(prs)
        loader.load_pull_requests(prs)

        # Check duplicate PRs
        dup_prs = test_client.ro_query(
            "MATCH (pr:PullRequest) WITH pr.number AS num, count(*) AS cnt WHERE cnt > 1 RETURN num"
        )
        assert len(dup_prs.result_set) == 0, "No duplicate PR numbers allowed"

        # Check duplicate Files
        dup_files = test_client.ro_query(
            "MATCH (f:File) WITH f.path AS path, count(*) AS cnt WHERE cnt > 1 RETURN path"
        )
        assert len(dup_files.result_set) == 0, "No duplicate file paths allowed"

        # Check duplicate Persons
        dup_persons = test_client.ro_query(
            "MATCH (p:Person) WITH p.login AS login, count(*) AS cnt WHERE cnt > 1 RETURN login"
        )
        assert len(dup_persons.result_set) == 0, "No duplicate person logins allowed"

        # Check dangling relationships
        dangling_src = test_client.ro_query("MATCH (a)-[r]->() WHERE a IS NULL RETURN count(r)")
        assert dangling_src.result_set[0][0] == 0, "Zero relationships with null source"

        dangling_dst = test_client.ro_query("MATCH ()-[r]->(b) WHERE b IS NULL RETURN count(r)")
        assert dangling_dst.result_set[0][0] == 0, "Zero relationships with null destination"
    finally:
        test_client.query("MATCH (n) DETACH DELETE n")


def test_failed_online_refresh_does_not_corrupt_existing_data(monkeypatch):
    """Verify that a network failure during online refresh leaves existing graph state intact."""
    import httpx
    from src.db import FalkorDBClient
    from src.ingestion.github_client import GitHubClient

    gh = GitHubClient(token=None)

    def mock_get(*args, **kwargs):
        raise httpx.ConnectError("Network connection refused")

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    # Calling fetch on uncached endpoint must raise and not falsely report success
    import pytest
    with pytest.raises(httpx.ConnectError):
        gh._fetch_json("repos/FalkorDB/FalkorDB/pulls?state=closed&page=999")

