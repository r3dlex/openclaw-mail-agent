"""Tests for the inter-agent message queue client."""

import json
from unittest.mock import patch

import pytest

from openclaw_mail.utils import mq


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_queue(tmp_path):
    """Create a temporary queue directory structure."""
    for agent in ["mail_agent", "broadcast", "main", "librarian_agent"]:
        (tmp_path / agent).mkdir()
    return tmp_path


@pytest.fixture
def mock_http_down():
    """Patch all HTTP helpers to simulate the MQ service being down."""
    with (
        patch.object(mq, "_post", return_value=None),
        patch.object(mq, "_get", return_value=None),
        patch.object(mq, "_patch", return_value=None),
    ):
        yield


@pytest.fixture
def mock_http_up():
    """Patch HTTP helpers to simulate a working MQ service."""
    with (
        patch.object(mq, "_post", return_value={"status": "ok"}),
        patch.object(mq, "_get", return_value={"messages": []}),
        patch.object(mq, "_patch", return_value={"status": "updated"}),
    ):
        yield


def _make_msg(
    from_agent="librarian_agent",
    to="mail_agent",
    msg_type="info",
    subject="Test message",
    body="Hello",
    status="unread",
    msg_id="test-uuid-1234",
    reply_to=None,
    priority="NORMAL",
):
    return {
        "id": msg_id,
        "from": from_agent,
        "to": to,
        "priority": priority,
        "type": msg_type,
        "subject": subject,
        "body": body,
        "replyTo": reply_to,
        "createdAt": "2026-03-21T08:00:00Z",
        "expiresAt": None,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Constants & metadata
# ---------------------------------------------------------------------------

class TestConstants:
    def test_agent_id(self):
        assert mq.AGENT_ID == "mail_agent"

    def test_metadata_has_required_fields(self):
        assert "name" in mq.AGENT_METADATA
        assert "emoji" in mq.AGENT_METADATA
        assert "description" in mq.AGENT_METADATA
        assert "capabilities" in mq.AGENT_METADATA
        assert "workspace" in mq.AGENT_METADATA

    def test_capabilities_are_list(self):
        assert isinstance(mq.AGENT_METADATA["capabilities"], list)
        assert len(mq.AGENT_METADATA["capabilities"]) > 0

    def test_emoji_is_crab(self):
        assert mq.AGENT_METADATA["emoji"] == "🦀"


# ---------------------------------------------------------------------------
# Message building
# ---------------------------------------------------------------------------

class TestBuildMessage:
    def test_build_message_structure(self):
        msg = mq._build_message("main", "info", "Test", "Hello world")
        assert msg["from"] == "mail_agent"
        assert msg["to"] == "main"
        assert msg["type"] == "info"
        assert msg["subject"] == "Test"
        assert msg["body"] == "Hello world"
        assert msg["priority"] == "NORMAL"
        assert msg["status"] == "unread"
        assert msg["replyTo"] is None
        assert msg["expiresAt"] is None
        assert "id" in msg
        assert "createdAt" in msg

    def test_build_message_with_reply_to(self):
        msg = mq._build_message("main", "response", "Re: Test", "Reply", reply_to="orig-uuid")
        assert msg["replyTo"] == "orig-uuid"

    def test_build_message_truncates_subject(self):
        long_subject = "x" * 200
        msg = mq._build_message("main", "info", long_subject, "body")
        assert len(msg["subject"]) == 80

    def test_build_message_priority(self):
        msg = mq._build_message("main", "request", "Urgent", "Now", priority="URGENT")
        assert msg["priority"] == "URGENT"

    def test_build_message_unique_ids(self):
        msg1 = mq._build_message("main", "info", "A", "a")
        msg2 = mq._build_message("main", "info", "B", "b")
        assert msg1["id"] != msg2["id"]


# ---------------------------------------------------------------------------
# File timestamp
# ---------------------------------------------------------------------------

class TestFileTimestamp:
    def test_no_colons_in_timestamp(self):
        ts = mq._file_timestamp()
        assert ":" not in ts

    def test_timestamp_format(self):
        ts = mq._file_timestamp()
        # Should look like 2026-03-21T08-30-00Z
        assert ts.endswith("Z")
        assert "T" in ts


# ---------------------------------------------------------------------------
# File-based message writing
# ---------------------------------------------------------------------------

class TestWriteMessageFile:
    def test_writes_to_recipient_inbox(self, tmp_queue):
        with patch.object(mq, "MQ_QUEUE_DIR", tmp_queue):
            msg = mq._build_message("main", "info", "Test", "Hello")
            filepath = mq._write_message_file(msg)

            assert filepath is not None
            assert filepath.exists()
            assert filepath.parent == tmp_queue / "main"

            written = json.loads(filepath.read_text())
            assert written["subject"] == "Test"
            assert written["from"] == "mail_agent"

    def test_returns_none_for_missing_inbox(self, tmp_queue):
        with patch.object(mq, "MQ_QUEUE_DIR", tmp_queue):
            msg = mq._build_message("nonexistent_agent", "info", "Test", "Hello")
            result = mq._write_message_file(msg)
            assert result is None

    def test_filename_format(self, tmp_queue):
        with patch.object(mq, "MQ_QUEUE_DIR", tmp_queue):
            msg = mq._build_message("main", "info", "Test", "Hello")
            filepath = mq._write_message_file(msg)
            assert filepath.name.endswith("-mail_agent.json")
            assert ":" not in filepath.name


# ---------------------------------------------------------------------------
# File-based inbox reading
# ---------------------------------------------------------------------------

class TestReadFileInbox:
    def test_reads_unread_messages(self, tmp_queue):
        inbox = tmp_queue / "mail_agent"
        msg = _make_msg(status="unread")
        (inbox / "2026-03-21T08-00-00Z-librarian_agent.json").write_text(json.dumps(msg))

        messages = mq._read_file_inbox(inbox)
        assert len(messages) == 1
        assert messages[0]["subject"] == "Test message"

    def test_skips_read_messages(self, tmp_queue):
        inbox = tmp_queue / "mail_agent"
        msg = _make_msg(status="read")
        (inbox / "2026-03-21T08-00-00Z-librarian_agent.json").write_text(json.dumps(msg))

        messages = mq._read_file_inbox(inbox)
        assert len(messages) == 0

    def test_skips_acted_messages(self, tmp_queue):
        inbox = tmp_queue / "mail_agent"
        msg = _make_msg(status="acted")
        (inbox / "2026-03-21T08-00-00Z-librarian_agent.json").write_text(json.dumps(msg))

        messages = mq._read_file_inbox(inbox)
        assert len(messages) == 0

    def test_empty_inbox(self, tmp_queue):
        messages = mq._read_file_inbox(tmp_queue / "mail_agent")
        assert messages == []

    def test_nonexistent_directory(self, tmp_path):
        messages = mq._read_file_inbox(tmp_path / "no_such_agent")
        assert messages == []

    def test_handles_corrupt_json(self, tmp_queue):
        inbox = tmp_queue / "mail_agent"
        (inbox / "2026-03-21T08-00-00Z-bad.json").write_text("not valid json{{{")

        messages = mq._read_file_inbox(inbox)
        assert messages == []

    def test_sorts_by_filename(self, tmp_queue):
        inbox = tmp_queue / "mail_agent"
        msg1 = _make_msg(subject="First", msg_id="1")
        msg2 = _make_msg(subject="Second", msg_id="2")
        (inbox / "2026-03-21T07-00-00Z-agent.json").write_text(json.dumps(msg1))
        (inbox / "2026-03-21T09-00-00Z-agent.json").write_text(json.dumps(msg2))

        messages = mq._read_file_inbox(inbox)
        assert len(messages) == 2
        assert messages[0]["subject"] == "First"
        assert messages[1]["subject"] == "Second"


# ---------------------------------------------------------------------------
# File-based status update
# ---------------------------------------------------------------------------

class TestUpdateFileStatus:
    def test_updates_status(self, tmp_queue):
        inbox = tmp_queue / "mail_agent"
        msg = _make_msg(status="unread", msg_id="update-me")
        filepath = inbox / "2026-03-21T08-00-00Z-test.json"
        filepath.write_text(json.dumps(msg))

        with patch.object(mq, "MQ_QUEUE_DIR", tmp_queue):
            result = mq._update_file_status("update-me", "acted")

        assert result is True
        updated = json.loads(filepath.read_text())
        assert updated["status"] == "acted"

    def test_returns_false_for_unknown_id(self, tmp_queue):
        with patch.object(mq, "MQ_QUEUE_DIR", tmp_queue):
            result = mq._update_file_status("nonexistent-id", "read")
        assert result is False

    def test_returns_false_for_missing_inbox(self, tmp_path):
        with patch.object(mq, "MQ_QUEUE_DIR", tmp_path / "no_queue"):
            result = mq._update_file_status("any-id", "read")
        assert result is False


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegister:
    def test_register_success(self):
        with patch.object(mq, "_post", return_value={"status": "registered"}) as mock_post:
            result = mq.register()
        assert result is True
        call_args = mock_post.call_args
        payload = call_args[0][1]
        assert payload["agent_id"] == "mail_agent"
        assert payload["name"] == "Openclaw 🦀"
        assert payload["emoji"] == "🦀"
        assert "capabilities" in payload
        assert "description" in payload
        assert "workspace" in payload

    def test_register_failure(self):
        with patch.object(mq, "_post", return_value=None):
            result = mq.register()
        assert result is False


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------

class TestHeartbeat:
    def test_heartbeat_success(self):
        with patch.object(mq, "_post", return_value={"status": "ok"}):
            assert mq.heartbeat() is True

    def test_heartbeat_failure(self):
        with patch.object(mq, "_post", return_value=None):
            assert mq.heartbeat() is False


# ---------------------------------------------------------------------------
# Send message
# ---------------------------------------------------------------------------

class TestSendMessage:
    def test_send_via_http(self):
        with patch.object(mq, "_post", return_value={"id": "new-uuid"}):
            result = mq.send_message("main", "info", "Test", "Hello")
        assert result is not None
        assert result["id"] == "new-uuid"

    def test_send_falls_back_to_file(self, tmp_queue):
        with (
            patch.object(mq, "_post", return_value=None),
            patch.object(mq, "MQ_QUEUE_DIR", tmp_queue),
        ):
            result = mq.send_message("main", "info", "Test", "Hello")
        assert result is not None
        assert result["to"] == "main"
        # Check file was written
        files = list((tmp_queue / "main").glob("*.json"))
        assert len(files) == 1

    def test_send_returns_none_when_both_fail(self, tmp_path):
        with (
            patch.object(mq, "_post", return_value=None),
            patch.object(mq, "MQ_QUEUE_DIR", tmp_path / "no_queue"),
        ):
            result = mq.send_message("nonexistent", "info", "Test", "Hello")
        assert result is None

    def test_send_with_reply_to(self):
        with patch.object(mq, "_post", return_value={"id": "new"}) as mock_post:
            mq.send_message("main", "response", "Re: Test", "Reply", reply_to="orig-id")
        payload = mock_post.call_args[0][1]
        assert payload["replyTo"] == "orig-id"


# ---------------------------------------------------------------------------
# Broadcast
# ---------------------------------------------------------------------------

class TestBroadcast:
    def test_broadcast_sends_to_broadcast(self):
        with patch.object(mq, "_post", return_value={"id": "bc-uuid"}) as mock_post:
            result = mq.broadcast("info", "System notice", "All agents read this")
        assert result is not None
        payload = mock_post.call_args[0][1]
        assert payload["to"] == "broadcast"


# ---------------------------------------------------------------------------
# Check inbox
# ---------------------------------------------------------------------------

class TestCheckInbox:
    def test_http_inbox(self):
        direct_msgs = [_make_msg(subject="Direct")]
        with patch.object(mq, "_get") as mock_get:
            mock_get.side_effect = [
                {"messages": direct_msgs},  # /inbox/mail_agent
                {"messages": []},  # /inbox/broadcast
            ]
            messages = mq.check_inbox()
        assert len(messages) == 1
        assert messages[0]["subject"] == "Direct"

    def test_includes_broadcast_not_from_self(self):
        broadcast_msg = _make_msg(from_agent="main", to="broadcast", subject="Broadcast")
        with patch.object(mq, "_get") as mock_get:
            mock_get.side_effect = [
                {"messages": []},
                {"messages": [broadcast_msg]},
            ]
            messages = mq.check_inbox()
        assert len(messages) == 1
        assert messages[0]["subject"] == "Broadcast"

    def test_excludes_own_broadcasts(self):
        own_msg = _make_msg(from_agent="mail_agent", to="broadcast", subject="My broadcast")
        with patch.object(mq, "_get") as mock_get:
            mock_get.side_effect = [
                {"messages": []},
                {"messages": [own_msg]},
            ]
            messages = mq.check_inbox()
        assert len(messages) == 0

    def test_fallback_to_file(self, tmp_queue):
        inbox = tmp_queue / "mail_agent"
        msg = _make_msg(subject="File msg")
        (inbox / "2026-03-21T08-00-00Z-test.json").write_text(json.dumps(msg))

        with (
            patch.object(mq, "_get", return_value=None),
            patch.object(mq, "MQ_QUEUE_DIR", tmp_queue),
        ):
            messages = mq.check_inbox()
        assert len(messages) == 1
        assert messages[0]["subject"] == "File msg"

    def test_sorts_chronologically(self):
        msg_old = _make_msg(subject="Old")
        msg_old["createdAt"] = "2026-03-21T07:00:00Z"
        msg_new = _make_msg(subject="New", msg_id="new-id")
        msg_new["createdAt"] = "2026-03-21T09:00:00Z"

        with patch.object(mq, "_get") as mock_get:
            mock_get.side_effect = [
                {"messages": [msg_new, msg_old]},
                {"messages": []},
            ]
            messages = mq.check_inbox()
        assert messages[0]["subject"] == "Old"
        assert messages[1]["subject"] == "New"


# ---------------------------------------------------------------------------
# Mark read / acted
# ---------------------------------------------------------------------------

class TestMarkStatus:
    def test_mark_read_via_http(self):
        with patch.object(mq, "_patch", return_value={"status": "read"}):
            assert mq.mark_read("msg-123") is True

    def test_mark_read_fallback_to_file(self, tmp_queue):
        inbox = tmp_queue / "mail_agent"
        msg = _make_msg(msg_id="file-msg-1")
        (inbox / "test.json").write_text(json.dumps(msg))

        with (
            patch.object(mq, "_patch", return_value=None),
            patch.object(mq, "MQ_QUEUE_DIR", tmp_queue),
        ):
            result = mq.mark_read("file-msg-1")
        assert result is True

    def test_mark_acted_via_http(self):
        with patch.object(mq, "_patch", return_value={"status": "acted"}):
            assert mq.mark_acted("msg-456") is True

    def test_mark_acted_returns_false_when_not_found(self):
        with (
            patch.object(mq, "_patch", return_value=None),
            patch.object(mq, "_update_file_status", return_value=False),
        ):
            assert mq.mark_acted("nonexistent") is False


# ---------------------------------------------------------------------------
# Reply helper
# ---------------------------------------------------------------------------

class TestReply:
    def test_reply_sets_reply_to(self):
        original = _make_msg(from_agent="librarian_agent", msg_id="orig-123", subject="Question")
        with patch.object(mq, "_post", return_value={"id": "reply-id"}) as mock_post:
            result = mq.reply(original, "Here's your answer")
        assert result is not None
        payload = mock_post.call_args[0][1]
        assert payload["to"] == "librarian_agent"
        assert payload["replyTo"] == "orig-123"
        assert payload["subject"] == "Re: Question"
        assert payload["type"] == "response"

    def test_reply_inherits_priority(self):
        original = _make_msg(priority="URGENT")
        with patch.object(mq, "_post", return_value={"id": "r"}) as mock_post:
            mq.reply(original, "On it")
        payload = mock_post.call_args[0][1]
        assert payload["priority"] == "URGENT"


# ---------------------------------------------------------------------------
# Request handling
# ---------------------------------------------------------------------------

class TestHandleRequest:
    def test_roll_call_reply(self):
        msg = _make_msg(
            msg_type="request",
            subject="Roll call: introduce yourself",
            body="Who are you?",
            from_agent="main",
        )
        with patch.object(mq, "_post", return_value={"id": "r"}) as mock_post:
            mq._handle_request(msg)
        payload = mock_post.call_args[0][1]
        assert "mail_agent" in payload["body"]
        assert "Capabilities" in payload["body"]
        assert payload["replyTo"] == "test-uuid-1234"

    def test_inbox_summary_with_report(self, tmp_path):
        msg = _make_msg(msg_type="request", subject="Inbox summary please")
        summary_file = tmp_path / "last_tidy_summary.txt"
        summary_file.write_text("Tidy 09:00 — 5 emails processed")

        with (
            patch.object(mq, "_post", return_value={"id": "r"}) as mock_post,
            patch("openclaw_mail.config.REPORT_DIR", tmp_path),
        ):
            mq._handle_request(msg)
        payload = mock_post.call_args[0][1]
        assert "5 emails processed" in payload["body"]

    def test_unknown_request_acknowledged(self):
        msg = _make_msg(msg_type="request", subject="Do something weird")
        with patch.object(mq, "_post", return_value={"id": "r"}) as mock_post:
            mq._handle_request(msg)
        payload = mock_post.call_args[0][1]
        assert "Received your request" in payload["body"]


# ---------------------------------------------------------------------------
# Process inbox (integration-level)
# ---------------------------------------------------------------------------

class TestProcessInbox:
    def test_processes_and_marks_acted(self):
        msg = _make_msg(msg_type="info", subject="FYI")
        with (
            patch.object(mq, "check_inbox", return_value=[msg]),
            patch.object(mq, "mark_read") as mock_read,
            patch.object(mq, "mark_acted") as mock_acted,
        ):
            processed = mq.process_inbox()
        assert len(processed) == 1
        mock_read.assert_called_once_with("test-uuid-1234")
        mock_acted.assert_called_once_with("test-uuid-1234")

    def test_handles_requests(self):
        msg = _make_msg(msg_type="request", subject="Roll call: introduce yourself")
        with (
            patch.object(mq, "check_inbox", return_value=[msg]),
            patch.object(mq, "mark_read"),
            patch.object(mq, "mark_acted"),
            patch.object(mq, "_handle_request") as mock_handle,
        ):
            mq.process_inbox()
        mock_handle.assert_called_once_with(msg)

    def test_does_not_handle_info_as_request(self):
        msg = _make_msg(msg_type="info", subject="Just FYI")
        with (
            patch.object(mq, "check_inbox", return_value=[msg]),
            patch.object(mq, "mark_read"),
            patch.object(mq, "mark_acted"),
            patch.object(mq, "_handle_request") as mock_handle,
        ):
            mq.process_inbox()
        mock_handle.assert_not_called()

    def test_empty_inbox(self):
        with patch.object(mq, "check_inbox", return_value=[]):
            processed = mq.process_inbox()
        assert processed == []


# ---------------------------------------------------------------------------
# Send tidy report
# ---------------------------------------------------------------------------

class TestSendTidyReport:
    def test_broadcasts_summary(self):
        with patch.object(mq, "_post", return_value={"id": "x"}) as mock_post:
            mq.send_tidy_report("Tidy 09:00 — 5 emails")
        # Should have called broadcast (to=broadcast)
        calls = mock_post.call_args_list
        assert any(c[0][1].get("to") == "broadcast" for c in calls)

    def test_sends_full_report_to_main(self):
        with patch.object(mq, "_post", return_value={"id": "x"}) as mock_post:
            mq.send_tidy_report("Summary", full_report="Full report here")
        calls = mock_post.call_args_list
        main_calls = [c for c in calls if c[0][1].get("to") == "main"]
        assert len(main_calls) == 1
        assert "Full report" in main_calls[0][0][1]["body"]

    def test_truncates_long_report(self):
        long_report = "x" * 10000
        with patch.object(mq, "_post", return_value={"id": "x"}) as mock_post:
            mq.send_tidy_report("Summary", full_report=long_report)
        calls = mock_post.call_args_list
        main_calls = [c for c in calls if c[0][1].get("to") == "main"]
        assert len(main_calls[0][0][1]["body"]) <= 5000

    def test_routes_pr_emails_when_reports_provided(self):
        reports = [{
            "account": "RIB",
            "details": [
                {"subject": "PR #41767: Fix auth timeout", "sender": "azuredevops@microsoft.com",
                 "folder": "Projects/RIB-4.0/DevOps", "step": "address", "confidence": 1.0, "reason": ""},
            ],
            "review_emails": [],
        }]
        with patch.object(mq, "_post", return_value={"id": "x"}) as mock_post:
            mq.send_tidy_report("Summary", reports=reports)
        calls = mock_post.call_args_list
        gitrepo_calls = [c for c in calls if c[0][1].get("to") == "gitrepo_agent"]
        assert len(gitrepo_calls) == 1
        assert "PR #41767" in gitrepo_calls[0][0][1]["body"]

    def test_no_pr_routing_when_no_pr_emails(self):
        reports = [{
            "account": "Personal",
            "details": [
                {"subject": "Newsletter from OReilly", "sender": "noreply@oreilly.com",
                 "folder": "Newsletters", "step": "keyword", "confidence": 0.95, "reason": ""},
            ],
            "review_emails": [],
        }]
        with patch.object(mq, "_post", return_value={"id": "x"}) as mock_post:
            mq.send_tidy_report("Summary", reports=reports)
        calls = mock_post.call_args_list
        gitrepo_calls = [c for c in calls if c[0][1].get("to") == "gitrepo_agent"]
        assert len(gitrepo_calls) == 0


# ---------------------------------------------------------------------------
# PR email detection and routing
# ---------------------------------------------------------------------------

class TestIsPrEmail:
    def test_azure_devops_sender(self):
        detail = {"subject": "Build completed", "sender": "azuredevops@microsoft.com", "folder": "DevOps"}
        assert mq._is_pr_email(detail) is True

    def test_github_sender(self):
        detail = {"subject": "Issue comment", "sender": "noreply@github.com", "folder": "DevOps"}
        assert mq._is_pr_email(detail) is True

    def test_pr_subject_in_devops_folder(self):
        detail = {"subject": "Pull request #41767: Fix auth", "sender": "someone@company.com",
                  "folder": "Projects/RIB-4.0/DevOps"}
        assert mq._is_pr_email(detail) is True

    def test_code_review_subject(self):
        detail = {"subject": "Code review requested for feature-branch", "sender": "someone@company.com",
                  "folder": "DevOps"}
        assert mq._is_pr_email(detail) is True

    def test_regular_email_not_pr(self):
        detail = {"subject": "Weekly newsletter", "sender": "news@company.com", "folder": "Newsletters"}
        assert mq._is_pr_email(detail) is False

    def test_hr_email_not_pr(self):
        detail = {"subject": "Training scheduled", "sender": "hr@company.com", "folder": "HR"}
        assert mq._is_pr_email(detail) is False

    def test_pr_subject_in_non_devops_folder(self):
        """PR subject but wrong folder — should not match unless strong pattern."""
        detail = {"subject": "Meeting notes", "sender": "someone@company.com", "folder": "Communication"}
        assert mq._is_pr_email(detail) is False

    def test_merge_code_subject(self):
        detail = {"subject": "Merge code to release/26.1", "sender": "dev@company.com",
                  "folder": "Projects/RIB-4.0/DevOps"}
        assert mq._is_pr_email(detail) is True

    def test_voted_on_pr(self):
        detail = {"subject": "Jeff.Ruan has voted on PR #123", "sender": "azuredevops@microsoft.com",
                  "folder": "Projects/RIB-4.0/DevOps"}
        assert mq._is_pr_email(detail) is True


class TestRoutePrEmails:
    def test_routes_pr_emails(self):
        reports = [{
            "account": "RIB Work",
            "details": [
                {"subject": "PR #41767: Fix auth", "sender": "azuredevops@microsoft.com",
                 "folder": "DevOps", "step": "address", "confidence": 1.0, "reason": ""},
                {"subject": "Newsletter", "sender": "news@company.com",
                 "folder": "Newsletters", "step": "keyword", "confidence": 0.95, "reason": ""},
            ],
            "review_emails": [],
        }]
        with patch.object(mq, "_post", return_value={"id": "x"}) as mock_post:
            count = mq.route_pr_emails(reports)
        assert count == 1
        calls = mock_post.call_args_list
        assert len(calls) == 1
        payload = calls[0][0][1]
        assert payload["to"] == "gitrepo_agent"
        assert payload["type"] == "request"
        assert payload["priority"] == "HIGH"
        assert "PR #41767" in payload["body"]

    def test_routes_multiple_prs(self):
        reports = [{
            "account": "RIB",
            "details": [
                {"subject": "PR #100: Feature A", "sender": "azuredevops@microsoft.com",
                 "folder": "DevOps", "step": "address", "confidence": 1.0, "reason": ""},
                {"subject": "PR #200: Feature B", "sender": "azuredevops@microsoft.com",
                 "folder": "DevOps", "step": "address", "confidence": 1.0, "reason": ""},
            ],
            "review_emails": [],
        }]
        with patch.object(mq, "_post", return_value={"id": "x"}):
            count = mq.route_pr_emails(reports)
        assert count == 2

    def test_no_prs_returns_zero(self):
        reports = [{
            "account": "Personal",
            "details": [
                {"subject": "Hello", "sender": "friend@gmail.com",
                 "folder": "Personal", "step": "keyword", "confidence": 0.9, "reason": ""},
            ],
            "review_emails": [],
        }]
        with patch.object(mq, "_post", return_value={"id": "x"}) as mock_post:
            count = mq.route_pr_emails(reports)
        assert count == 0
        mock_post.assert_not_called()

    def test_empty_reports(self):
        count = mq.route_pr_emails([])
        assert count == 0


# ---------------------------------------------------------------------------
# Get status / agents
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_returns_status(self):
        status = {"checkedAt": "2026-03-21T08:00:00Z", "queues": {}}
        with patch.object(mq, "_get", return_value=status):
            result = mq.get_status()
        assert result == status

    def test_returns_none_when_down(self):
        with patch.object(mq, "_get", return_value=None):
            assert mq.get_status() is None


class TestGetAgents:
    def test_returns_agent_list(self):
        agents_data = {"agents": [{"id": "mail_agent"}, {"id": "main"}]}
        with patch.object(mq, "_get", return_value=agents_data):
            agents = mq.get_agents()
        assert len(agents) == 2

    def test_returns_empty_when_down(self):
        with patch.object(mq, "_get", return_value=None):
            assert mq.get_agents() == []
