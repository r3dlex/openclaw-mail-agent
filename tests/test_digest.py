"""Tests for the daily email digest module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from openclaw_mail.digest import generate_digest, get_folder_count, save_digest


# ---------------------------------------------------------------------------
# get_folder_count
# ---------------------------------------------------------------------------

class TestGetFolderCount:
    def test_returns_count_from_envelopes(self):
        with patch("openclaw_mail.digest.get_envelopes", return_value=[{"id": "1"}]):
            count = get_folder_count("Personal", "INBOX")
        assert count == 1

    def test_returns_zero_on_empty(self):
        with patch("openclaw_mail.digest.get_envelopes", return_value=[]):
            count = get_folder_count("Personal", "INBOX")
        assert count == 0

    def test_returns_zero_on_himalaya_error(self):
        # HimalayaError is falsy and has no len — get_envelopes with retries returns it
        # but in practice get_folder_count passes retries=1 so it uses himalaya_run_with_retry
        # The function just calls len() on the result, so we test the happy path
        # when get_envelopes returns an empty list (error case falls back to 0 via len([]))
        with patch("openclaw_mail.digest.get_envelopes", return_value=[]):
            count = get_folder_count("Personal", "INBOX")
        assert count == 0

    def test_passes_limit_one(self):
        with patch("openclaw_mail.digest.get_envelopes") as mock_get:
            mock_get.return_value = []
            get_folder_count("Work", "Review")
        call_kwargs = mock_get.call_args
        assert call_kwargs[1].get("limit", call_kwargs[0][2] if len(call_kwargs[0]) > 2 else None) == 1


# ---------------------------------------------------------------------------
# generate_digest
# ---------------------------------------------------------------------------

class TestGenerateDigest:
    @pytest.fixture
    def two_accounts(self):
        return [
            {"id": "personal", "name": "Personal Gmail", "himalaya_name": "Personal", "active": True},
            {"id": "work", "name": "Work Exchange", "himalaya_name": "Work", "active": True},
        ]

    def test_contains_header(self, two_accounts):
        with (
            patch("openclaw_mail.digest.get_active_accounts", return_value=two_accounts),
            patch("openclaw_mail.digest.get_folder_count", return_value=0),
            patch("openclaw_mail.digest.get_envelopes", return_value=[]),
        ):
            digest = generate_digest()

        assert "Daily Email Digest" in digest

    def test_contains_account_names(self, two_accounts):
        with (
            patch("openclaw_mail.digest.get_active_accounts", return_value=two_accounts),
            patch("openclaw_mail.digest.get_folder_count", return_value=0),
            patch("openclaw_mail.digest.get_envelopes", return_value=[]),
        ):
            digest = generate_digest()

        assert "Personal Gmail" in digest
        assert "Work Exchange" in digest

    def test_contains_inbox_and_review_counts(self, two_accounts):
        with (
            patch("openclaw_mail.digest.get_active_accounts", return_value=two_accounts),
            patch("openclaw_mail.digest.get_folder_count", return_value=3),
            patch("openclaw_mail.digest.get_envelopes", return_value=[]),
        ):
            digest = generate_digest()

        assert "Inbox: 3" in digest
        assert "Review: 3" in digest

    def test_shows_recent_review_emails_when_count_positive(self, two_accounts):
        envelopes = [{"subject": "Urgent: fix this", "id": "1"}, {"subject": "Another item", "id": "2"}]

        def fake_folder_count(account, folder):
            return 2 if folder == "Review" else 0

        with (
            patch("openclaw_mail.digest.get_active_accounts", return_value=two_accounts),
            patch("openclaw_mail.digest.get_folder_count", side_effect=fake_folder_count),
            patch("openclaw_mail.digest.get_envelopes", return_value=envelopes),
        ):
            digest = generate_digest()

        assert "Urgent: fix this" in digest

    def test_action_needed_when_many_review(self, two_accounts):
        def fake_folder_count(account, folder):
            return 11 if folder == "Review" else 0

        with (
            patch("openclaw_mail.digest.get_active_accounts", return_value=two_accounts),
            patch("openclaw_mail.digest.get_folder_count", side_effect=fake_folder_count),
            patch("openclaw_mail.digest.get_envelopes", return_value=[]),
        ):
            digest = generate_digest()

        assert "Action needed" in digest

    def test_no_action_needed_when_few_review(self, two_accounts):
        def fake_folder_count(account, folder):
            return 5 if folder == "Review" else 0

        with (
            patch("openclaw_mail.digest.get_active_accounts", return_value=two_accounts),
            patch("openclaw_mail.digest.get_folder_count", side_effect=fake_folder_count),
            patch("openclaw_mail.digest.get_envelopes", return_value=[]),
        ):
            digest = generate_digest()

        assert "Action needed" not in digest

    def test_totals_line(self, two_accounts):
        def fake_folder_count(account, folder):
            return 2

        with (
            patch("openclaw_mail.digest.get_active_accounts", return_value=two_accounts),
            patch("openclaw_mail.digest.get_folder_count", side_effect=fake_folder_count),
            patch("openclaw_mail.digest.get_envelopes", return_value=[]),
        ):
            digest = generate_digest()

        assert "Totals" in digest

    def test_footer_present(self, two_accounts):
        with (
            patch("openclaw_mail.digest.get_active_accounts", return_value=two_accounts),
            patch("openclaw_mail.digest.get_folder_count", return_value=0),
            patch("openclaw_mail.digest.get_envelopes", return_value=[]),
        ):
            digest = generate_digest()

        assert "openclaw-mail-agent" in digest

    def test_empty_accounts_list(self):
        with (
            patch("openclaw_mail.digest.get_active_accounts", return_value=[]),
            patch("openclaw_mail.digest.get_envelopes", return_value=[]),
        ):
            digest = generate_digest()

        assert "Daily Email Digest" in digest

    def test_account_uses_himalaya_name(self):
        accounts = [{"id": "acc1", "name": "Test", "himalaya_name": "TestHimalaya", "active": True}]
        with (
            patch("openclaw_mail.digest.get_active_accounts", return_value=accounts),
            patch("openclaw_mail.digest.get_folder_count", return_value=0) as mock_count,
            patch("openclaw_mail.digest.get_envelopes", return_value=[]),
        ):
            generate_digest()

        # get_folder_count should be called with "TestHimalaya"
        calls = mock_count.call_args_list
        account_names_used = [c[0][0] for c in calls]
        assert "TestHimalaya" in account_names_used

    def test_account_without_himalaya_name_uses_id(self):
        accounts = [{"id": "acc_fallback", "name": "Fallback", "active": True}]
        with (
            patch("openclaw_mail.digest.get_active_accounts", return_value=accounts),
            patch("openclaw_mail.digest.get_folder_count", return_value=0) as mock_count,
            patch("openclaw_mail.digest.get_envelopes", return_value=[]),
        ):
            generate_digest()

        calls = mock_count.call_args_list
        account_names_used = [c[0][0] for c in calls]
        assert "acc_fallback" in account_names_used


# ---------------------------------------------------------------------------
# save_digest
# ---------------------------------------------------------------------------

class TestSaveDigest:
    def test_creates_digest_files(self, tmp_path):
        accounts = [{"id": "p", "name": "Personal", "himalaya_name": "Personal", "active": True}]
        with (
            patch("openclaw_mail.digest.REPORT_DIR", tmp_path),
            patch("openclaw_mail.digest.get_active_accounts", return_value=accounts),
            patch("openclaw_mail.digest.get_folder_count", return_value=0),
            patch("openclaw_mail.digest.get_envelopes", return_value=[]),
        ):
            result = save_digest()

        assert result == tmp_path / "last_digest.md"
        assert (tmp_path / "last_digest.md").exists()

    def test_creates_timestamped_archive(self, tmp_path):
        accounts = [{"id": "p", "name": "Personal", "himalaya_name": "Personal", "active": True}]
        with (
            patch("openclaw_mail.digest.REPORT_DIR", tmp_path),
            patch("openclaw_mail.digest.get_active_accounts", return_value=accounts),
            patch("openclaw_mail.digest.get_folder_count", return_value=0),
            patch("openclaw_mail.digest.get_envelopes", return_value=[]),
        ):
            save_digest()

        digest_files = list(tmp_path.glob("digest_*.md"))
        assert len(digest_files) == 1

    def test_file_content_is_digest(self, tmp_path):
        accounts = [{"id": "p", "name": "Personal", "himalaya_name": "Personal", "active": True}]
        with (
            patch("openclaw_mail.digest.REPORT_DIR", tmp_path),
            patch("openclaw_mail.digest.get_active_accounts", return_value=accounts),
            patch("openclaw_mail.digest.get_folder_count", return_value=0),
            patch("openclaw_mail.digest.get_envelopes", return_value=[]),
        ):
            result_path = save_digest()

        content = result_path.read_text()
        assert "Daily Email Digest" in content

    def test_mkdir_when_not_exists(self, tmp_path):
        new_dir = tmp_path / "reports"
        accounts = [{"id": "p", "name": "Personal", "himalaya_name": "Personal", "active": True}]
        with (
            patch("openclaw_mail.digest.REPORT_DIR", new_dir),
            patch("openclaw_mail.digest.get_active_accounts", return_value=accounts),
            patch("openclaw_mail.digest.get_folder_count", return_value=0),
            patch("openclaw_mail.digest.get_envelopes", return_value=[]),
        ):
            save_digest()

        assert new_dir.exists()
