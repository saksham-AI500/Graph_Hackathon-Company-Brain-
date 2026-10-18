"""Tests for multi-module reviewer ranking."""

import pytest
from unittest.mock import MagicMock
from src.agent.reviewer_ranking import is_bot_account, find_reviewers_for_modules


class TestBotDetection:
    """Test identification of bot accounts."""

    def test_bot_suffix(self):
        assert is_bot_account("copilot-pull-request-reviewer[bot]") is True
        assert is_bot_account("github-actions[bot]") is True
        assert is_bot_account("my-app[bot]") is True

    def test_known_bot_logins(self):
        assert is_bot_account("dependabot") is True
        assert is_bot_account("renovate") is True
        assert is_bot_account("codecov") is True
        assert is_bot_account("github-actions") is True
        assert is_bot_account("stale") is True

    def test_human_users(self):
        assert is_bot_account("alice") is False
        assert is_bot_account("bob-builder") is False
        assert is_bot_account("charlie_dev") is False


class TestReviewerRanking:
    """Test find_reviewers_for_modules with mock client."""

    def test_bot_exclusion_in_ranking(self):
        client = MagicMock()

        # Step 1: files query returns files
        client.ro_query.side_effect = [
            # files for auth/
            MagicMock(result_set=[["auth/login.py"], ["auth/token.py"]]),
            # files for payments/
            MagicMock(result_set=[["payments/checkout.py"]]),
            # reviews for auth/login.py: returns a bot and a human
            MagicMock(result_set=[
                ["copilot-pull-request-reviewer[bot]", "https://github.com/apps/copilot", 5, "2024-01-01"],
                ["alice", "https://github.com/alice", 3, "2024-01-02"],
            ]),
            # reviews for auth/token.py
            MagicMock(result_set=[
                ["bob", "https://github.com/bob", 2, "2024-01-03"],
            ]),
            # reviews for payments/checkout.py
            MagicMock(result_set=[
                ["alice", "https://github.com/alice", 4, "2024-01-04"],
            ]),
        ]

        ranked, metadata = find_reviewers_for_modules(client, ["auth/", "payments/"])

        # Ensure bot is excluded
        logins = [r["login"] for r in ranked]
        assert "copilot-pull-request-reviewer[bot]" not in logins
        assert "copilot-pull-request-reviewer[bot]" in metadata["bots_excluded"]
        assert "alice" in logins

        # Alice reviewed both auth/ and payments/ -> cross_module_prs bonus
        alice_data = next(r for r in ranked if r["login"] == "alice")
        assert alice_data["rank"] == 1
        assert alice_data["breakdown"]["recent_reviews"] == 7
        assert alice_data["breakdown"]["cross_module_prs"] == 2
        assert "auth/" in alice_data["breakdown"]["modules_active"]
        assert "payments/" in alice_data["breakdown"]["modules_active"]
        assert alice_data["total_score"] > 0

    def test_tie_breaking(self):
        client = MagicMock()
        client.ro_query.side_effect = [
            # files for mod1
            MagicMock(result_set=[["mod1/a.py"]]),
            # reviews for mod1/a.py: two users with identical score
            MagicMock(result_set=[
                ["zack", "https://github.com/zack", 2, "2024-01-01"],
                ["adam", "https://github.com/adam", 2, "2024-01-01"],
            ]),
        ]

        ranked, _ = find_reviewers_for_modules(client, ["mod1/"])
        assert len(ranked) == 2
        # Alphabetical tie-breaking: adam before zack
        assert ranked[0]["login"] == "adam"
        assert ranked[0]["rank"] == 1
        assert ranked[1]["login"] == "zack"
        assert ranked[1]["rank"] == 2
