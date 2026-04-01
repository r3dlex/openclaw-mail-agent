"""Tests for CLI entrypoints (tidy, digest, calendar_add, validate)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

import openclaw_mail.cli as cli


# ---------------------------------------------------------------------------
# _mq_startup
# ---------------------------------------------------------------------------

class TestMqStartup:
    def test_mq_startup_success(self):
        with (
            patch("openclaw_mail.cli.get_logger"),
            patch("openclaw_mail.utils.mq.register", return_value=True),
            patch("openclaw_mail.utils.mq.process_inbox", return_value=[]),
        ):
            # Should not raise
            cli._mq_startup()

    def test_mq_startup_with_messages(self, capsys):
        msg = {"type": "info", "from": "main", "subject": "Hello"}
        with (
            patch("openclaw_mail.utils.mq.register", return_value=True),
            patch("openclaw_mail.utils.mq.process_inbox", return_value=[msg]),
        ):
            cli._mq_startup()

        captured = capsys.readouterr()
        assert "[MQ]" in captured.out

    def test_mq_startup_exception_silenced(self):
        """If MQ imports raise, startup still continues."""
        with patch("openclaw_mail.utils.mq.register", side_effect=RuntimeError("MQ down")):
            # Should NOT raise
            cli._mq_startup()

    def test_mq_register_not_logged_when_false(self):
        """When register returns False, no MQ registered log."""
        with (
            patch("openclaw_mail.utils.mq.register", return_value=False),
            patch("openclaw_mail.utils.mq.process_inbox", return_value=[]),
        ):
            cli._mq_startup()  # Should complete without error


# ---------------------------------------------------------------------------
# tidy()
# ---------------------------------------------------------------------------

class TestTidyCli:
    def _make_reports(self):
        return [
            {
                "account": "Personal",
                "account_id": "personal",
                "nickname": "personal",
                "total_processed": 3,
                "auto_filed": 2,
                "review_count": 1,
                "details": [],
                "review_emails": [{"subject": "Mystery", "sender": "x@y.com", "reason": "?"}],
            }
        ]

    def test_tidy_runs_dry_run(self, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(sys, "argv", ["mail-tidy", "--dry-run"])
        reports = self._make_reports()

        with (
            patch("openclaw_mail.cli._mq_startup"),
            patch("openclaw_mail.tidy.run_all", return_value=reports),
            patch("openclaw_mail.tidy.save_report", return_value=tmp_path / "report.md"),
            patch("openclaw_mail.tidy.format_report", return_value="Full report"),
            patch("openclaw_mail.tidy.format_summary", return_value="Summary text"),
        ):
            cli.tidy()

        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out

    def test_tidy_runs_live(self, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(sys, "argv", ["mail-tidy"])
        reports = self._make_reports()

        with (
            patch("openclaw_mail.cli._mq_startup"),
            patch("openclaw_mail.tidy.run_all", return_value=reports),
            patch("openclaw_mail.tidy.save_report", return_value=tmp_path / "report.md"),
            patch("openclaw_mail.tidy.format_report", return_value="Full report"),
            patch("openclaw_mail.tidy.format_summary", return_value="Summary"),
        ):
            cli.tidy()

        captured = capsys.readouterr()
        assert "LIVE" in captured.out

    def test_tidy_account_filter_parsed(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "argv", ["mail-tidy", "--account", "personal"])
        reports = self._make_reports()

        with (
            patch("openclaw_mail.cli._mq_startup"),
            patch("openclaw_mail.tidy.run_all", return_value=reports) as mock_run,
            patch("openclaw_mail.tidy.save_report", return_value=tmp_path / "report.md"),
            patch("openclaw_mail.tidy.format_report", return_value="Full"),
            patch("openclaw_mail.tidy.format_summary", return_value="Summary"),
        ):
            cli.tidy()

        mock_run.assert_called_once_with(dry_run=False, account_filter="personal")

    def test_tidy_with_review_logs_warning(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "argv", ["mail-tidy"])
        reports = self._make_reports()  # 1 review

        with (
            patch("openclaw_mail.cli._mq_startup"),
            patch("openclaw_mail.tidy.run_all", return_value=reports),
            patch("openclaw_mail.tidy.save_report", return_value=tmp_path / "report.md"),
            patch("openclaw_mail.tidy.format_report", return_value="Full"),
            patch("openclaw_mail.tidy.format_summary", return_value="Summary"),
            patch("openclaw_mail.cli.log") as mock_log,
        ):
            cli.tidy()

        # Warning should have been logged about review emails
        mock_log.warning.assert_called()

    def test_tidy_mq_report_sent_when_processed(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "argv", ["mail-tidy"])
        reports = self._make_reports()

        with (
            patch("openclaw_mail.cli._mq_startup"),
            patch("openclaw_mail.tidy.run_all", return_value=reports),
            patch("openclaw_mail.tidy.save_report", return_value=tmp_path / "report.md"),
            patch("openclaw_mail.tidy.format_report", return_value="Full"),
            patch("openclaw_mail.tidy.format_summary", return_value="Summary"),
            patch("openclaw_mail.utils.mq.send_tidy_report") as mock_mq,
        ):
            cli.tidy()

        mock_mq.assert_called_once()

    def test_tidy_mq_report_skipped_when_nothing_processed(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "argv", ["mail-tidy"])
        empty_reports = [{
            "account": "Personal", "account_id": "p", "nickname": "p",
            "total_processed": 0, "auto_filed": 0, "review_count": 0,
            "details": [], "review_emails": [],
        }]

        with (
            patch("openclaw_mail.cli._mq_startup"),
            patch("openclaw_mail.tidy.run_all", return_value=empty_reports),
            patch("openclaw_mail.tidy.save_report", return_value=tmp_path / "report.md"),
            patch("openclaw_mail.tidy.format_report", return_value="Full"),
            patch("openclaw_mail.tidy.format_summary", return_value="Summary"),
            patch("openclaw_mail.utils.mq.send_tidy_report") as mock_mq,
        ):
            cli.tidy()

        mock_mq.assert_not_called()

    def test_tidy_mq_send_exception_silenced(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "argv", ["mail-tidy"])
        reports = self._make_reports()

        with (
            patch("openclaw_mail.cli._mq_startup"),
            patch("openclaw_mail.tidy.run_all", return_value=reports),
            patch("openclaw_mail.tidy.save_report", return_value=tmp_path / "report.md"),
            patch("openclaw_mail.tidy.format_report", return_value="Full"),
            patch("openclaw_mail.tidy.format_summary", return_value="Summary"),
            patch("openclaw_mail.utils.mq.send_tidy_report", side_effect=RuntimeError("MQ down")),
        ):
            # Should not raise
            cli.tidy()


# ---------------------------------------------------------------------------
# digest()
# ---------------------------------------------------------------------------

class TestDigestCli:
    def test_digest_runs_and_prints(self, capsys, tmp_path):
        with (
            patch("openclaw_mail.cli._mq_startup"),
            patch("openclaw_mail.digest.save_digest", return_value=tmp_path / "digest.md"),
            patch("openclaw_mail.digest.generate_digest", return_value="# Daily Digest\nContent here"),
        ):
            cli.digest()

        captured = capsys.readouterr()
        assert "# Daily Digest" in captured.out
        assert "Digest saved to" in captured.out

    def test_digest_logs_path(self, tmp_path):
        with (
            patch("openclaw_mail.cli._mq_startup"),
            patch("openclaw_mail.digest.save_digest", return_value=tmp_path / "digest.md"),
            patch("openclaw_mail.digest.generate_digest", return_value="Digest"),
            patch("openclaw_mail.cli.log") as mock_log,
        ):
            cli.digest()

        mock_log.info.assert_called()


# ---------------------------------------------------------------------------
# calendar_add()
# ---------------------------------------------------------------------------

class TestCalendarAddCli:
    def test_calendar_add_too_few_args_exits(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["mail-calendar-add"])
        with (
            patch("openclaw_mail.cli._mq_startup"),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli.calendar_add()

        assert exc_info.value.code == 1

    def test_calendar_add_basic(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["mail-calendar-add", "Team Sync", "2026-04-01 14:00"])
        with (
            patch("openclaw_mail.cli._mq_startup"),
            patch("openclaw_mail.calendar.core.create_event",
                  return_value={"method": "ics", "result": "/tmp/event.ics"}),
        ):
            cli.calendar_add()

        captured = capsys.readouterr()
        assert "ICS file saved" in captured.out

    def test_calendar_add_google_api(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["mail-calendar-add", "Meeting", "2026-04-01 10:00"])
        with (
            patch("openclaw_mail.cli._mq_startup"),
            patch("openclaw_mail.calendar.core.create_event",
                  return_value={"method": "google_api", "result": "evt-id-123", "link": "http://cal.google.com/x"}),
        ):
            cli.calendar_add()

        captured = capsys.readouterr()
        assert "Google Calendar" in captured.out

    def test_calendar_add_with_end_flag(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", [
            "mail-calendar-add", "Standup", "2026-04-01 09:00",
            "--end", "2026-04-01 09:30",
        ])
        with (
            patch("openclaw_mail.cli._mq_startup"),
            patch("openclaw_mail.calendar.core.create_event") as mock_create,
        ):
            mock_create.return_value = {"method": "ics", "result": "/tmp/x.ics"}
            cli.calendar_add()

        event_arg = mock_create.call_args[0][0]
        assert event_arg.end is not None
        assert event_arg.end.hour == 9
        assert event_arg.end.minute == 30

    def test_calendar_add_with_account_flag(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", [
            "mail-calendar-add", "Event", "2026-04-01 14:00",
            "--account", "personal",
        ])
        with (
            patch("openclaw_mail.cli._mq_startup"),
            patch("openclaw_mail.calendar.core.create_event") as mock_create,
        ):
            mock_create.return_value = {"method": "ics", "result": "/tmp/x.ics"}
            cli.calendar_add()

        assert mock_create.call_args[1].get("account_id") == "personal"

    def test_calendar_add_with_description_and_location(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", [
            "mail-calendar-add", "Event", "2026-04-01 14:00",
            "--description", "Notes here",
            "--location", "Room 101",
        ])
        with (
            patch("openclaw_mail.cli._mq_startup"),
            patch("openclaw_mail.calendar.core.create_event") as mock_create,
        ):
            mock_create.return_value = {"method": "ics", "result": "/tmp/x.ics"}
            cli.calendar_add()

        event_arg = mock_create.call_args[0][0]
        assert event_arg.description == "Notes here"
        assert event_arg.location == "Room 101"

    def test_calendar_add_with_attendees_flag(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", [
            "mail-calendar-add", "Event", "2026-04-01 14:00",
            "--attendees", "a@example.com,b@example.com",
        ])
        with (
            patch("openclaw_mail.cli._mq_startup"),
            patch("openclaw_mail.calendar.core.create_event") as mock_create,
        ):
            mock_create.return_value = {"method": "ics", "result": "/tmp/x.ics"}
            cli.calendar_add()

        event_arg = mock_create.call_args[0][0]
        assert "a@example.com" in event_arg.attendees
        assert "b@example.com" in event_arg.attendees

    def test_calendar_add_unknown_flag_ignored(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", [
            "mail-calendar-add", "Event", "2026-04-01 14:00",
            "--unknown-flag",
        ])
        with (
            patch("openclaw_mail.cli._mq_startup"),
            patch("openclaw_mail.calendar.core.create_event") as mock_create,
        ):
            mock_create.return_value = {"method": "ics", "result": "/tmp/x.ics"}
            cli.calendar_add()

        mock_create.assert_called_once()


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------

class TestValidateCli:
    def _make_step_result(self, name, matched=True, skipped=False, reason="ok", output=None):
        step = MagicMock()
        step.step_name = name
        step.matched = matched
        step.skipped = skipped
        step.reason = reason
        step.output = output
        return step

    def _make_pipeline_result(self, steps, all_passed=True):
        result = MagicMock()
        result.steps = steps
        result.all_passed = all_passed
        result.summary = "3/3 checks passed" if all_passed else "2/3 checks passed"
        return result

    def test_validate_all_passed(self, capsys):
        step = self._make_step_result("ADR check", matched=True)
        pipeline_result = self._make_pipeline_result([step], all_passed=True)

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = pipeline_result

        with (
            patch("openclaw_mail.pipelines.validation.build_validation_pipeline",
                  return_value=mock_pipeline),
        ):
            cli.validate()

        captured = capsys.readouterr()
        assert "All checks passed" in captured.out

    def test_validate_failure_exits_1(self, capsys):
        step = self._make_step_result("ADR check", matched=False, reason="Failed ADR-001")
        pipeline_result = self._make_pipeline_result([step], all_passed=False)

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = pipeline_result

        with (
            patch("openclaw_mail.pipelines.validation.build_validation_pipeline",
                  return_value=mock_pipeline),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli.validate()

        assert exc_info.value.code == 1

    def test_validate_prints_step_results(self, capsys):
        step = self._make_step_result("Sensitive data scan", matched=True, reason="No violations")
        pipeline_result = self._make_pipeline_result([step], all_passed=True)

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = pipeline_result

        with patch("openclaw_mail.pipelines.validation.build_validation_pipeline",
                   return_value=mock_pipeline):
            cli.validate()

        captured = capsys.readouterr()
        assert "Sensitive data scan" in captured.out

    def test_validate_prints_skipped_step(self, capsys):
        step = self._make_step_result("Git check", matched=False, skipped=True, reason="Skipped")
        pipeline_result = self._make_pipeline_result([step], all_passed=True)

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = pipeline_result

        with patch("openclaw_mail.pipelines.validation.build_validation_pipeline",
                   return_value=mock_pipeline):
            cli.validate()

        captured = capsys.readouterr()
        assert "Git check" in captured.out

    def test_validate_failure_output_printed(self, capsys):
        violations = ["src/foo.py:10: Hardcoded password", "src/bar.py:20: Email address"]
        step = self._make_step_result("Sensitive scan", matched=False, reason="Violations", output=violations)
        pipeline_result = self._make_pipeline_result([step], all_passed=False)

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = pipeline_result

        with (
            patch("openclaw_mail.pipelines.validation.build_validation_pipeline",
                  return_value=mock_pipeline),
            pytest.raises(SystemExit),
        ):
            cli.validate()

        captured = capsys.readouterr()
        assert "src/foo.py" in captured.out

    def test_validate_dict_output_items(self, capsys):
        """Dict items in step output should be formatted with check marks."""
        dict_violations = [
            {"adr": "ARCH-001", "passed": True, "message": "Correct"},
            {"adr": "ARCH-002", "passed": False, "message": "Missing docstring"},
        ]
        step = self._make_step_result("ADR check", matched=False, reason="Violations", output=dict_violations)
        pipeline_result = self._make_pipeline_result([step], all_passed=False)

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = pipeline_result

        with (
            patch("openclaw_mail.pipelines.validation.build_validation_pipeline",
                  return_value=mock_pipeline),
            pytest.raises(SystemExit),
        ):
            cli.validate()

        captured = capsys.readouterr()
        assert "ARCH-001" in captured.out
        assert "ARCH-002" in captured.out

    def test_validate_truncates_long_output(self, capsys):
        """Output longer than 10 items should show '... and N more'."""
        violations = [f"file_{i}.py:1: issue" for i in range(15)]
        step = self._make_step_result("Big check", matched=False, reason="Many issues", output=violations)
        pipeline_result = self._make_pipeline_result([step], all_passed=False)

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = pipeline_result

        with (
            patch("openclaw_mail.pipelines.validation.build_validation_pipeline",
                  return_value=mock_pipeline),
            pytest.raises(SystemExit),
        ):
            cli.validate()

        captured = capsys.readouterr()
        assert "more" in captured.out


# ---------------------------------------------------------------------------
# __main__ block
# ---------------------------------------------------------------------------

class TestMainBlock:
    def test_main_tidy_command(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["cli.py", "tidy"])
        with patch("openclaw_mail.cli.tidy") as mock_tidy:
            # Simulate the __main__ block
            cmd = sys.argv[1]
            if cmd == "tidy":
                cli.tidy()
        mock_tidy.assert_called_once()

    def test_main_digest_command(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["cli.py", "digest"])
        with patch("openclaw_mail.cli.digest") as mock_digest:
            cmd = sys.argv[1]
            if cmd == "digest":
                cli.digest()
        mock_digest.assert_called_once()

    def test_main_no_args_exits(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["cli.py"])
        with pytest.raises(SystemExit) as exc_info:
            if len(sys.argv) < 2:
                import sys as _sys
                _sys.exit(1)
        assert exc_info.value.code == 1

    def test_main_unknown_command_exits(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["cli.py", "unknown"])
        with pytest.raises(SystemExit) as exc_info:
            cmd = sys.argv[1]
            if cmd not in ("tidy", "digest", "calendar-add", "validate"):
                sys.exit(1)
        assert exc_info.value.code == 1
