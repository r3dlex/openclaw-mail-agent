"""Tests for the himalaya CLI wrapper — timeout, retry, and DavMail handling."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from openclaw_mail.utils.himalaya import (
    DAVMAIL_TIMEOUT_MULTIPLIER,
    MIN_TIMEOUT,
    bulk_move,
    create_folder,
    davmail_timeout,
    get_envelopes,
    himalaya_run,
    himalaya_run_with_retry,
    list_folders,
    move_email,
)


# ---------------------------------------------------------------------------
# davmail_timeout helper
# ---------------------------------------------------------------------------


class TestDavmailTimeout:
    def test_multiplier(self):
        assert davmail_timeout(30) == 30 * DAVMAIL_TIMEOUT_MULTIPLIER

    def test_respects_minimum(self):
        assert davmail_timeout(1) >= MIN_TIMEOUT

    def test_zero_base(self):
        assert davmail_timeout(0) == MIN_TIMEOUT


# ---------------------------------------------------------------------------
# himalaya_run
# ---------------------------------------------------------------------------


class TestHimalayaRun:
    @patch("openclaw_mail.utils.himalaya.subprocess.run")
    def test_returns_stdout_stderr(self, mock_run):
        mock_run.return_value = MagicMock(stdout="output", stderr="")
        stdout, stderr = himalaya_run("echo hello", timeout=10)
        assert stdout == "output"
        assert stderr == ""

    @patch("openclaw_mail.utils.himalaya.subprocess.run")
    def test_timeout_returns_empty_and_timeout_string(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 10)
        stdout, stderr = himalaya_run("slow cmd", timeout=10)
        assert stdout == ""
        assert stderr == "timeout"

    @patch("openclaw_mail.utils.himalaya.subprocess.run")
    def test_minimum_timeout_enforced(self, mock_run):
        mock_run.return_value = MagicMock(stdout="ok", stderr="")
        himalaya_run("cmd", timeout=1)  # Below MIN_TIMEOUT
        # Verify subprocess.run was called with at least MIN_TIMEOUT
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs.get("timeout", call_kwargs[1].get("timeout", 0)) >= MIN_TIMEOUT


# ---------------------------------------------------------------------------
# himalaya_run_with_retry
# ---------------------------------------------------------------------------


class TestHimalayaRunWithRetry:
    @patch("openclaw_mail.utils.himalaya.himalaya_run")
    def test_success_on_first_attempt(self, mock_run):
        mock_run.return_value = ('{"data": true}', "")
        stdout, stderr = himalaya_run_with_retry("cmd", retries=2)
        assert stdout == '{"data": true}'
        assert mock_run.call_count == 1

    @patch("openclaw_mail.utils.himalaya.time.sleep")
    @patch("openclaw_mail.utils.himalaya.himalaya_run")
    def test_retries_on_timeout(self, mock_run, mock_sleep):
        mock_run.side_effect = [
            ("", "timeout"),       # attempt 1: timeout
            ("", "timeout"),       # attempt 2: timeout
            ('{"ok": true}', ""),  # attempt 3: success
        ]
        stdout, stderr = himalaya_run_with_retry("cmd", retries=2, backoff=1)
        assert stdout == '{"ok": true}'
        assert mock_run.call_count == 3
        assert mock_sleep.call_count == 2  # slept between retries

    @patch("openclaw_mail.utils.himalaya.himalaya_run")
    def test_no_retry_on_auth_error(self, mock_run):
        """Non-timeout errors (like auth failure) should not retry."""
        mock_run.return_value = ("", "error: authentication failed")
        stdout, stderr = himalaya_run_with_retry("cmd", retries=2)
        assert "error" in stderr
        assert mock_run.call_count == 1

    @patch("openclaw_mail.utils.himalaya.time.sleep")
    @patch("openclaw_mail.utils.himalaya.himalaya_run")
    def test_all_retries_exhausted(self, mock_run, mock_sleep):
        mock_run.return_value = ("", "timeout")
        stdout, stderr = himalaya_run_with_retry("cmd", retries=2, backoff=1)
        assert stderr == "timeout"
        assert mock_run.call_count == 3  # 1 + 2 retries

    @patch("openclaw_mail.utils.himalaya.time.sleep")
    @patch("openclaw_mail.utils.himalaya.himalaya_run")
    def test_exponential_backoff(self, mock_run, mock_sleep):
        mock_run.return_value = ("", "timeout")
        himalaya_run_with_retry("cmd", retries=2, backoff=5)
        # Should sleep 5*1=5, then 5*2=10
        assert mock_sleep.call_args_list[0][0][0] == 5
        assert mock_sleep.call_args_list[1][0][0] == 10


# ---------------------------------------------------------------------------
# move_email
# ---------------------------------------------------------------------------


class TestMoveEmail:
    @patch("openclaw_mail.utils.himalaya.himalaya_run_with_retry")
    def test_single_message(self, mock_run):
        mock_run.return_value = ("", "")
        ok = move_email("RIB", "42", "Finance")
        assert ok is True
        cmd = mock_run.call_args[0][0]
        assert '-f "INBOX"' in cmd
        assert '"Finance"' in cmd
        assert "42" in cmd

    @patch("openclaw_mail.utils.himalaya.himalaya_run_with_retry")
    def test_batch_messages(self, mock_run):
        mock_run.return_value = ("", "")
        ok = move_email("RIB", ["1", "2", "3"], "Archive", source_folder="Review")
        assert ok is True
        cmd = mock_run.call_args[0][0]
        assert '-f "Review"' in cmd
        assert "1 2 3" in cmd

    @patch("openclaw_mail.utils.himalaya.himalaya_run_with_retry")
    def test_timeout_scales_with_batch_size(self, mock_run):
        mock_run.return_value = ("", "")
        ids = [str(i) for i in range(100)]
        move_email("RIB", ids, "Archive", timeout=30)
        call_kwargs = mock_run.call_args
        effective_timeout = call_kwargs.kwargs.get("timeout", call_kwargs[1].get("timeout", 0))
        # Should be at least 30 + 100 = 130
        assert effective_timeout >= 130

    @patch("openclaw_mail.utils.himalaya.himalaya_run_with_retry")
    def test_failure_returns_false(self, mock_run):
        mock_run.return_value = ("", "error: folder not found")
        ok = move_email("RIB", "42", "NonExistent")
        assert ok is False

    @patch("openclaw_mail.utils.himalaya.himalaya_run_with_retry")
    def test_timeout_returns_false(self, mock_run):
        mock_run.return_value = ("", "timeout")
        ok = move_email("RIB", "42", "Finance")
        assert ok is False


# ---------------------------------------------------------------------------
# get_envelopes
# ---------------------------------------------------------------------------


class TestGetEnvelopes:
    @patch("openclaw_mail.utils.himalaya.himalaya_run")
    def test_parses_json(self, mock_run):
        mock_run.return_value = ('[{"id": "1", "subject": "Test"}]', "")
        result = get_envelopes("RIB", "INBOX", limit=10)
        assert len(result) == 1
        assert result[0]["id"] == "1"

    @patch("openclaw_mail.utils.himalaya.himalaya_run")
    def test_empty_on_timeout(self, mock_run):
        mock_run.return_value = ("", "timeout")
        result = get_envelopes("RIB", "INBOX")
        assert result == []

    @patch("openclaw_mail.utils.himalaya.himalaya_run_with_retry")
    def test_uses_retry_when_requested(self, mock_retry):
        mock_retry.return_value = ('[{"id": "1"}]', "")
        result = get_envelopes("RIB", "INBOX", retries=2)
        assert len(result) == 1
        mock_retry.assert_called_once()

    @patch("openclaw_mail.utils.himalaya.himalaya_run")
    def test_respects_limit(self, mock_run):
        data = [{"id": str(i)} for i in range(10)]
        import json
        mock_run.return_value = (json.dumps(data), "")
        result = get_envelopes("RIB", "INBOX", limit=3)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# bulk_move
# ---------------------------------------------------------------------------


class TestBulkMove:
    @patch("openclaw_mail.utils.himalaya.move_email")
    def test_uses_prefetched_envelopes(self, mock_move):
        mock_move.return_value = True
        envelopes = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
        result = bulk_move("RIB", "Source", "Target", envelopes=envelopes)
        assert result["moved"] == 3
        assert result["errors"] == 0
        # Should NOT have called get_envelopes
        mock_move.assert_called_once()

    @patch("openclaw_mail.utils.himalaya.move_email")
    def test_empty_envelopes_reports_source_empty(self, mock_move):
        result = bulk_move("RIB", "Source", "Target", envelopes=[])
        assert result["source_empty"] is True
        assert result["moved"] == 0
        mock_move.assert_not_called()

    @patch("openclaw_mail.utils.himalaya.move_email")
    def test_move_failure_reports_errors(self, mock_move):
        mock_move.return_value = False
        envelopes = [{"id": "1"}, {"id": "2"}]
        result = bulk_move("RIB", "Source", "Target", envelopes=envelopes)
        assert result["moved"] == 0
        assert result["errors"] == 2

    @patch("openclaw_mail.utils.himalaya.move_email")
    def test_timeout_scales_with_count(self, mock_move):
        mock_move.return_value = True
        envelopes = [{"id": str(i)} for i in range(50)]
        bulk_move("RIB", "Source", "Target", timeout=30, envelopes=envelopes)
        call_kwargs = mock_move.call_args
        effective_timeout = call_kwargs.kwargs.get("timeout", call_kwargs[1].get("timeout", 0))
        # bulk_move passes max(timeout, 60) + len(ids), so at least 60 + 50 = 110
        assert effective_timeout >= 110


# ---------------------------------------------------------------------------
# create_folder / list_folders
# ---------------------------------------------------------------------------


class TestFolderOperations:
    @patch("openclaw_mail.utils.himalaya.himalaya_run_with_retry")
    def test_create_folder_success(self, mock_run):
        mock_run.return_value = ("", "")
        assert create_folder("RIB", "NewFolder") is True

    @patch("openclaw_mail.utils.himalaya.himalaya_run_with_retry")
    def test_create_folder_failure(self, mock_run):
        mock_run.return_value = ("", "error: permission denied")
        assert create_folder("RIB", "NewFolder") is False

    @patch("openclaw_mail.utils.himalaya.himalaya_run_with_retry")
    def test_list_folders(self, mock_run):
        import json
        folders = [{"name": "INBOX"}, {"name": "Sent"}, {"name": "Finance"}]
        mock_run.return_value = (json.dumps(folders), "")
        result = list_folders("RIB")
        assert result == ["INBOX", "Sent", "Finance"]

    @patch("openclaw_mail.utils.himalaya.himalaya_run_with_retry")
    def test_list_folders_empty_on_error(self, mock_run):
        mock_run.return_value = ("", "error: timeout")
        assert list_folders("RIB") == []
