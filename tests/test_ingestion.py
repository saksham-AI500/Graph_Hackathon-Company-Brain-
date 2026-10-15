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
