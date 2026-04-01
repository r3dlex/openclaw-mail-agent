"""Tests for the tidy module — format_report, format_summary, save_report,
process_account helpers, and PR detection logic."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from openclaw_mail.tidy import (
    _detect_pr_from_subject,
    _send_pr_to_gitrepo_agent,
    format_report,
    format_summary,
    process_account,
    run_all,
    save_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def empty_report():
    return {
        "account": "Test Account",
        "account_id": "test",
        "nickname": "test",
        "total_processed": 0,
        "auto_filed": 0,
        "review_count": 0,
        "details": [],
        "review_emails": [],
    }


@pytest.fixture
def busy_report():
    return {
        "account": "Work Account",
        "account_id": "work",
        "nickname": "work",
        "total_processed": 5,
        "auto_filed": 3,
        "review_count": 2,
        "details": [
            {
                "subject": "Invoice #123",
                "sender": "billing@vendor.com",
                "folder": "Finance",
                "step": "keyword",
                "confidence": 0.90,
                "reason": "Keyword match",
            },
            {
                "subject": "Unclassified email",
                "sender": "unknown@random.org",
                "folder": "Review",
                "step": "review",
                "confidence": 0.0,
                "reason": "No filter matched",
            },
            {
                "subject": "Another review",
                "sender": "mystery@example.com",
                "folder": "Review",
                "step": "review",
                "confidence": 0.0,
                "reason": "No filter matched",
            },
        ],
        "review_emails": [
            {
                "subject": "Unclassified email",
                "sender": "unknown@random.org",
                "folder": "Review",
                "step": "review",
                "confidence": 0.0,
                "reason": "No filter matched",
            },
            {
                "subject": "Another review",
                "sender": "mystery@example.com",
                "folder": "Review",
                "step": "review",
                "confidence": 0.0,
                "reason": "No filter matched",
            },
        ],
    }


# ---------------------------------------------------------------------------
# _detect_pr_from_subject
# ---------------------------------------------------------------------------

class TestDetectPrFromSubject:
    def test_ado_pr_pattern(self):
        prs = _detect_pr_from_subject("PR #41803: Fix auth timeout", "azuredevops@microsoft.com")
        assert len(prs) >= 1
        assert prs[0]["pr_number"] == "41803"
        assert prs[0]["vcs"] == "ado"

    def test_github_sender_detected(self):
        prs = _detect_pr_from_subject("[org/repo] PR #99: Add tests", "notifications@github.com")
        assert len(prs) >= 1
        assert prs[0]["vcs"] == "github"

    def test_unknown_sender(self):
        prs = _detect_pr_from_subject("PR 200", "someone@company.com")
        assert len(prs) >= 1
        assert prs[0]["vcs"] == "unknown"

    def test_no_pr_in_subject(self):
        prs = _detect_pr_from_subject("Weekly newsletter", "news@company.com")
        assert prs == []

    def test_pr_subject_truncated(self):
        subject = "PR #1: " + "x" * 200
        prs = _detect_pr_from_subject(subject, "azuredevops@microsoft.com")
        assert len(prs) >= 1
        assert len(prs[0]["subject"]) <= 80

    def test_dev_azure_sender_detected_as_ado(self):
        prs = _detect_pr_from_subject("PR #55: Fix bug", "notify@dev.azure.com")
        assert len(prs) >= 1
        assert prs[0]["vcs"] == "ado"


# ---------------------------------------------------------------------------
# _send_pr_to_gitrepo_agent
# ---------------------------------------------------------------------------

class TestSendPrToGitrepoAgent:
    def test_empty_list_does_nothing(self):
        with patch("openclaw_mail.utils.mq.send_message") as mock_send:
            _send_pr_to_gitrepo_agent([])
        mock_send.assert_not_called()

    def test_sends_each_pr(self):
        prs = [
            {"pr_number": "100", "vcs": "ado", "org": "ribdev", "repo": "itwo40",
             "subject": "PR #100: Test", "sender": "azuredevops@microsoft.com"},
            {"pr_number": "200", "vcs": "github", "org": "org", "repo": "repo",
             "subject": "PR #200: Another", "sender": "noreply@github.com"},
        ]
        with patch("openclaw_mail.utils.mq.send_message") as mock_send:
            _send_pr_to_gitrepo_agent(prs)
        assert mock_send.call_count == 2
        # First call should target gitrepo_agent
        first_call = mock_send.call_args_list[0]
        assert first_call[1]["to"] == "gitrepo_agent"

    def test_mq_exception_is_silenced(self):
        prs = [{"pr_number": "1", "vcs": "ado", "org": "o", "repo": "r",
                "subject": "PR #1", "sender": "a@b.com"}]
        with patch("openclaw_mail.utils.mq.send_message", side_effect=RuntimeError("MQ down")):
            # Should not raise
            _send_pr_to_gitrepo_agent(prs)


# ---------------------------------------------------------------------------
# format_report
# ---------------------------------------------------------------------------

class TestFormatReport:
    def test_empty_reports(self, empty_report):
        report_text = format_report([empty_report])
        assert "Email Tidy Report" in report_text
        assert "Total processed:** 0" in report_text
        assert "No emails require review." in report_text

    def test_busy_report_contains_account(self, busy_report):
        report_text = format_report([busy_report])
        assert "Work Account" in report_text
        assert "Finance" in report_text

    def test_auto_filed_table(self, busy_report):
        report_text = format_report([busy_report])
        assert "Auto-filed" in report_text
        assert "Invoice #123" in report_text

    def test_review_section(self, busy_report):
        report_text = format_report([busy_report])
        assert "Emails Requiring Review" in report_text
        assert "Unclassified email" in report_text

    def test_multiple_accounts(self, empty_report, busy_report):
        report_text = format_report([empty_report, busy_report])
        assert "Work Account" in report_text
        # Empty account with 0 processed should NOT appear in per-account section
        assert "Test Account" not in report_text

    def test_totals_aggregated(self, busy_report):
        report_text = format_report([busy_report, busy_report])
        assert "Total processed:** 10" in report_text
        assert "Auto-filed:** 6" in report_text
        assert "Needs review:** 4" in report_text

    def test_generated_by_footer(self, empty_report):
        report_text = format_report([empty_report])
        assert "openclaw-mail-agent" in report_text


# ---------------------------------------------------------------------------
# format_summary
# ---------------------------------------------------------------------------

class TestFormatSummary:
    def test_all_clean_returns_clean_message(self, empty_report):
        summary = format_summary([empty_report])
        assert "All inboxes clean" in summary

    def test_summary_with_processed_emails(self, busy_report):
        summary = format_summary([busy_report])
        assert "5 emails processed" in summary
        assert "work:" in summary

    def test_summary_shows_review_action(self, busy_report):
        summary = format_summary([busy_report])
        assert "need review" in summary

    def test_summary_zero_review(self):
        report = {
            "account": "Personal",
            "account_id": "personal",
            "nickname": "personal",
            "total_processed": 3,
            "auto_filed": 3,
            "review_count": 0,
            "details": [],
            "review_emails": [],
        }
        summary = format_summary([report])
        assert "0 review" in summary

    def test_review_emails_listed(self, busy_report):
        summary = format_summary([busy_report])
        # The subject truncated + sender prefix should appear
        assert "?" in summary  # review marker

    def test_multiple_accounts_aggregated(self, busy_report, empty_report):
        summary = format_summary([busy_report, empty_report])
        assert "5 emails processed" in summary


# ---------------------------------------------------------------------------
# save_report
# ---------------------------------------------------------------------------

class TestSaveReport:
    def test_creates_report_files(self, tmp_path, busy_report):
        with patch("openclaw_mail.tidy.REPORT_DIR", tmp_path):
            result_path = save_report([busy_report])

        assert result_path == tmp_path / "last_tidy_report.md"
        assert (tmp_path / "last_tidy_report.md").exists()
        assert (tmp_path / "last_tidy_summary.txt").exists()
        assert (tmp_path / "last_tidy_data.json").exists()

    def test_creates_timestamped_archive(self, tmp_path, busy_report):
        with patch("openclaw_mail.tidy.REPORT_DIR", tmp_path):
            save_report([busy_report])

        tidy_files = list(tmp_path.glob("tidy_*.md"))
        assert len(tidy_files) == 1

    def test_json_data_is_valid(self, tmp_path, busy_report):
        with patch("openclaw_mail.tidy.REPORT_DIR", tmp_path):
            save_report([busy_report])

        json_data = json.loads((tmp_path / "last_tidy_data.json").read_text())
        assert "timestamp" in json_data
        assert "total_processed" in json_data
        assert json_data["total_processed"] == 5
        assert json_data["total_auto_filed"] == 3
        assert json_data["total_review"] == 2
        assert len(json_data["accounts"]) == 1

    def test_summary_text_written(self, tmp_path, busy_report):
        with patch("openclaw_mail.tidy.REPORT_DIR", tmp_path):
            save_report([busy_report])

        summary_text = (tmp_path / "last_tidy_summary.txt").read_text()
        assert "5 emails processed" in summary_text

    def test_mkdir_called_when_not_exist(self, tmp_path, empty_report):
        new_dir = tmp_path / "reports"
        with patch("openclaw_mail.tidy.REPORT_DIR", new_dir):
            save_report([empty_report])
        assert new_dir.exists()


# ---------------------------------------------------------------------------
# process_account
# ---------------------------------------------------------------------------

class TestProcessAccount:
    @pytest.fixture
    def account(self):
        return {
            "id": "personal",
            "name": "Personal Gmail",
            "nickname": "personal",
            "himalaya_name": "Personal",
            "provider": "gmail",
            "active": True,
        }

    def test_empty_inbox_returns_zero_processed(self, account):
        with (
            patch("openclaw_mail.tidy.load_filter_config", return_value={}),
            patch("openclaw_mail.tidy.get_envelopes_with_retry", return_value=[]),
        ):
            report = process_account(account, dry_run=True)

        assert report["total_processed"] == 0
        assert report["auto_filed"] == 0
        assert report["review_count"] == 0
        assert report["account"] == "Personal Gmail"

    def test_emails_classified_and_counted(self, account):
        envelopes = [
            {"id": "1", "subject": "Invoice #1", "from": {"addr": "billing@vendor.com", "name": "Billing"}},
            {"id": "2", "subject": "Random stuff", "from": {"addr": "unknown@random.org", "name": ""}},
        ]
        with (
            patch("openclaw_mail.tidy.load_filter_config", return_value={}),
            patch("openclaw_mail.tidy.get_envelopes_with_retry") as mock_fetch,
            patch("openclaw_mail.tidy.create_folder"),
            patch("openclaw_mail.tidy.move_email"),
            patch("openclaw_mail.tidy.time.sleep"),
        ):
            # First call returns 2 emails (less than batch_size=5, so loop ends)
            mock_fetch.return_value = envelopes
            report = process_account(account, dry_run=True)

        assert report["total_processed"] == 2

    def test_dry_run_does_not_move(self, account):
        envelopes = [
            {"id": "1", "subject": "Test email", "from": {"addr": "a@b.com", "name": "A"}},
        ]
        with (
            patch("openclaw_mail.tidy.load_filter_config", return_value={}),
            patch("openclaw_mail.tidy.get_envelopes_with_retry") as mock_fetch,
            patch("openclaw_mail.tidy.create_folder") as mock_create,
            patch("openclaw_mail.tidy.move_email") as mock_move,
            patch("openclaw_mail.tidy.time.sleep"),
        ):
            mock_fetch.return_value = envelopes
            process_account(account, dry_run=True)

        mock_create.assert_not_called()
        mock_move.assert_not_called()

    def test_live_run_moves_emails(self, account):
        envelopes = [
            {"id": "42", "subject": "Test email", "from": {"addr": "a@b.com", "name": "A"}},
        ]
        with (
            patch("openclaw_mail.tidy.load_filter_config", return_value={}),
            patch("openclaw_mail.tidy.get_envelopes_with_retry") as mock_fetch,
            patch("openclaw_mail.tidy.create_folder") as mock_create,
            patch("openclaw_mail.tidy.move_email") as mock_move,
            patch("openclaw_mail.tidy.time.sleep"),
            patch("openclaw_mail.tidy.davmail_timeout", return_value=20),
        ):
            mock_fetch.return_value = envelopes
            process_account(account, dry_run=False)

        mock_create.assert_called_once()
        mock_move.assert_called_once()

    def test_envelopes_with_string_from_field(self, account):
        """Handle emails where 'from' is a string rather than a dict."""
        envelopes = [
            {"id": "1", "subject": "Test", "from": "plain@example.com"},
        ]
        with (
            patch("openclaw_mail.tidy.load_filter_config", return_value={}),
            patch("openclaw_mail.tidy.get_envelopes_with_retry") as mock_fetch,
            patch("openclaw_mail.tidy.time.sleep"),
        ):
            mock_fetch.return_value = envelopes
            report = process_account(account, dry_run=True)

        assert report["total_processed"] == 1

    def test_missing_msg_id_skipped(self, account):
        envelopes = [
            {"subject": "No ID email", "from": {"addr": "a@b.com", "name": "A"}},
        ]
        with (
            patch("openclaw_mail.tidy.load_filter_config", return_value={}),
            patch("openclaw_mail.tidy.get_envelopes_with_retry") as mock_fetch,
            patch("openclaw_mail.tidy.time.sleep"),
        ):
            mock_fetch.return_value = envelopes
            report = process_account(account, dry_run=True)

        assert report["total_processed"] == 0

    def test_davmail_account_uses_higher_timeouts(self):
        account = {
            "id": "work",
            "name": "Work Exchange",
            "nickname": "work",
            "himalaya_name": "Work",
            "provider": "davmail",
            "active": True,
        }
        envelopes = [
            {"id": "1", "subject": "Meeting", "from": {"addr": "boss@corp.com", "name": "Boss"}},
        ]
        with (
            patch("openclaw_mail.tidy.load_filter_config", return_value={}),
            patch("openclaw_mail.tidy.get_envelopes_with_retry") as mock_fetch,
            patch("openclaw_mail.tidy.create_folder"),
            patch("openclaw_mail.tidy.move_email"),
            patch("openclaw_mail.tidy.davmail_timeout", return_value=80) as mock_davmail_to,
        ):
            mock_fetch.return_value = envelopes
            process_account(account, dry_run=False)

        mock_davmail_to.assert_called()

    def test_pr_detected_and_sent_in_live_mode(self, account):
        envelopes = [
            {"id": "1", "subject": "PR #41803: Fix bug", "from": {"addr": "azuredevops@microsoft.com", "name": "ADO"}},
        ]
        with (
            patch("openclaw_mail.tidy.load_filter_config", return_value={}),
            patch("openclaw_mail.tidy.get_envelopes_with_retry") as mock_fetch,
            patch("openclaw_mail.tidy.create_folder"),
            patch("openclaw_mail.tidy.move_email"),
            patch("openclaw_mail.tidy.time.sleep"),
            patch("openclaw_mail.tidy._send_pr_to_gitrepo_agent") as mock_pr_send,
        ):
            mock_fetch.return_value = envelopes
            process_account(account, dry_run=False)

        mock_pr_send.assert_called_once()

    def test_pr_not_sent_in_dry_run(self, account):
        envelopes = [
            {"id": "1", "subject": "PR #41803: Fix bug", "from": {"addr": "azuredevops@microsoft.com", "name": "ADO"}},
        ]
        with (
            patch("openclaw_mail.tidy.load_filter_config", return_value={}),
            patch("openclaw_mail.tidy.get_envelopes_with_retry") as mock_fetch,
            patch("openclaw_mail.tidy.time.sleep"),
            patch("openclaw_mail.tidy._send_pr_to_gitrepo_agent") as mock_pr_send,
        ):
            mock_fetch.return_value = envelopes
            process_account(account, dry_run=True)

        mock_pr_send.assert_not_called()

    def test_review_emails_collected(self, account):
        envelopes = [
            {"id": "1", "subject": "Mystery email", "from": {"addr": "unknown@random.org", "name": ""}},
        ]
        with (
            patch("openclaw_mail.tidy.load_filter_config", return_value={}),
            patch("openclaw_mail.tidy.get_envelopes_with_retry") as mock_fetch,
            patch("openclaw_mail.tidy.time.sleep"),
        ):
            mock_fetch.return_value = envelopes
            report = process_account(account, dry_run=True)

        assert report["review_count"] == 1
        assert len(report["review_emails"]) == 1

    def test_batching_loops_until_empty(self, account):
        """If batch returns exactly batch_size, fetch again until empty."""
        batch_of_5 = [
            {"id": str(i), "subject": f"Email {i}", "from": {"addr": "a@b.com", "name": ""}}
            for i in range(5)
        ]
        with (
            patch("openclaw_mail.tidy.load_filter_config", return_value={}),
            patch("openclaw_mail.tidy.get_envelopes_with_retry") as mock_fetch,
            patch("openclaw_mail.tidy.time.sleep"),
        ):
            # First call returns 5 (full batch), second call returns empty
            mock_fetch.side_effect = [batch_of_5, []]
            report = process_account(account, dry_run=True)

        assert report["total_processed"] == 5
        assert mock_fetch.call_count == 2


# ---------------------------------------------------------------------------
# run_all
# ---------------------------------------------------------------------------

class TestRunAll:
    def test_runs_across_all_accounts(self):
        accounts = [
            {"id": "acc1", "name": "Account 1", "nickname": "a1", "himalaya_name": "A1",
             "provider": "gmail", "active": True},
            {"id": "acc2", "name": "Account 2", "nickname": "a2", "himalaya_name": "A2",
             "provider": "gmail", "active": True},
        ]
        with (
            patch("openclaw_mail.tidy.get_active_accounts", return_value=accounts),
            patch("openclaw_mail.tidy.process_account") as mock_process,
            patch("openclaw_mail.tidy.time.sleep"),
        ):
            mock_process.return_value = {
                "account": "Test", "account_id": "test", "nickname": "test",
                "total_processed": 0, "auto_filed": 0, "review_count": 0,
                "details": [], "review_emails": [],
            }
            reports = run_all(dry_run=True)

        assert mock_process.call_count == 2
        assert len(reports) == 2

    def test_account_filter_by_id(self):
        accounts = [
            {"id": "personal", "name": "Personal", "nickname": "personal", "himalaya_name": "Personal",
             "provider": "gmail", "active": True},
            {"id": "work", "name": "Work", "nickname": "work", "himalaya_name": "Work",
             "provider": "davmail", "active": True},
        ]
        with (
            patch("openclaw_mail.tidy.get_active_accounts", return_value=accounts),
            patch("openclaw_mail.tidy.process_account") as mock_process,
            patch("openclaw_mail.tidy.time.sleep"),
        ):
            mock_process.return_value = {
                "account": "Personal", "account_id": "personal", "nickname": "personal",
                "total_processed": 0, "auto_filed": 0, "review_count": 0,
                "details": [], "review_emails": [],
            }
            run_all(account_filter="personal")

        assert mock_process.call_count == 1

    def test_account_filter_by_nickname(self):
        accounts = [
            {"id": "acc1", "name": "Account 1", "nickname": "work", "himalaya_name": "A1",
             "provider": "gmail", "active": True},
            {"id": "acc2", "name": "Account 2", "nickname": "personal", "himalaya_name": "A2",
             "provider": "gmail", "active": True},
        ]
        with (
            patch("openclaw_mail.tidy.get_active_accounts", return_value=accounts),
            patch("openclaw_mail.tidy.process_account") as mock_process,
            patch("openclaw_mail.tidy.time.sleep"),
        ):
            mock_process.return_value = {
                "account": "Account 1", "account_id": "acc1", "nickname": "work",
                "total_processed": 0, "auto_filed": 0, "review_count": 0,
                "details": [], "review_emails": [],
            }
            run_all(account_filter="work")

        assert mock_process.call_count == 1

    def test_davmail_accounts_no_sleep_between(self):
        """DavMail accounts don't trigger the inter-account sleep."""
        accounts = [
            {"id": "work", "name": "Work", "nickname": "work", "himalaya_name": "Work",
             "provider": "davmail", "active": True},
        ]
        with (
            patch("openclaw_mail.tidy.get_active_accounts", return_value=accounts),
            patch("openclaw_mail.tidy.process_account") as mock_process,
            patch("openclaw_mail.tidy.time.sleep") as mock_sleep,
        ):
            mock_process.return_value = {
                "account": "Work", "account_id": "work", "nickname": "work",
                "total_processed": 0, "auto_filed": 0, "review_count": 0,
                "details": [], "review_emails": [],
            }
            run_all()

        mock_sleep.assert_not_called()
