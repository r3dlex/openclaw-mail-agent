"""Tests for the calendar module (ICS generation + API fallback logic)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from openclaw_mail.calendar.core import CalendarEvent, create_event, list_events
from openclaw_mail.calendar.ics import generate_ics


# ---------------------------------------------------------------------------
# CalendarEvent dataclass
# ---------------------------------------------------------------------------

class TestCalendarEvent:
    def test_default_end_is_one_hour(self):
        start = datetime(2026, 3, 25, 14, 0)
        event = CalendarEvent(summary="Test", start=start)
        assert event.end == start + timedelta(hours=1)

    def test_explicit_end(self):
        start = datetime(2026, 3, 25, 14, 0)
        end = datetime(2026, 3, 25, 16, 0)
        event = CalendarEvent(summary="Test", start=start, end=end)
        assert event.end == end

    def test_default_timezone(self):
        event = CalendarEvent(summary="Test", start=datetime(2026, 3, 25, 14, 0))
        assert event.timezone == "Europe/Berlin"

    def test_attendees_default_empty(self):
        event = CalendarEvent(summary="Test", start=datetime(2026, 3, 25, 14, 0))
        assert event.attendees == []


# ---------------------------------------------------------------------------
# ICS generation
# ---------------------------------------------------------------------------

class TestGenerateIcs:
    @pytest.fixture
    def event(self):
        return CalendarEvent(
            summary="Team Sync",
            start=datetime(2026, 3, 25, 14, 0),
            end=datetime(2026, 3, 25, 15, 0),
            description="Weekly sync meeting",
            location="Room 42",
            attendees=["alice@example.com", "bob@example.com"],
        )

    def test_produces_valid_vcalendar(self, event):
        ics = generate_ics(event)
        assert ics.startswith("BEGIN:VCALENDAR")
        assert "END:VCALENDAR" in ics

    def test_contains_vevent(self, event):
        ics = generate_ics(event)
        assert "BEGIN:VEVENT" in ics
        assert "END:VEVENT" in ics

    def test_contains_summary(self, event):
        ics = generate_ics(event)
        assert "SUMMARY:Team Sync" in ics

    def test_contains_description(self, event):
        ics = generate_ics(event)
        assert "DESCRIPTION:Weekly sync meeting" in ics

    def test_contains_location(self, event):
        ics = generate_ics(event)
        assert "LOCATION:Room 42" in ics

    def test_contains_attendees(self, event):
        ics = generate_ics(event)
        assert "ATTENDEE;RSVP=TRUE:mailto:alice@example.com" in ics
        assert "ATTENDEE;RSVP=TRUE:mailto:bob@example.com" in ics

    def test_contains_dtstart(self, event):
        ics = generate_ics(event)
        assert "DTSTART;TZID=Europe/Berlin:20260325T140000" in ics

    def test_contains_dtend(self, event):
        ics = generate_ics(event)
        assert "DTEND;TZID=Europe/Berlin:20260325T150000" in ics

    def test_contains_uid(self, event):
        ics = generate_ics(event)
        assert "UID:" in ics

    def test_contains_prodid(self, event):
        ics = generate_ics(event)
        assert "PRODID:-//OpenClaw Mail Agent//EN" in ics

    def test_no_description_when_empty(self):
        event = CalendarEvent(summary="Quick", start=datetime(2026, 3, 25, 14, 0))
        ics = generate_ics(event)
        assert "DESCRIPTION" not in ics

    def test_no_location_when_empty(self):
        event = CalendarEvent(summary="Quick", start=datetime(2026, 3, 25, 14, 0))
        ics = generate_ics(event)
        assert "LOCATION" not in ics

    def test_no_attendees_when_empty(self):
        event = CalendarEvent(summary="Quick", start=datetime(2026, 3, 25, 14, 0))
        ics = generate_ics(event)
        assert "ATTENDEE" not in ics

    def test_escapes_special_characters(self):
        event = CalendarEvent(
            summary="Meeting; with, special\\chars",
            start=datetime(2026, 3, 25, 14, 0),
            description="Line1\nLine2",
        )
        ics = generate_ics(event)
        assert "Meeting\\; with\\, special\\\\chars" in ics
        assert "Line1\\nLine2" in ics

    def test_crlf_line_endings(self, event):
        ics = generate_ics(event)
        assert "\r\n" in ics


# ---------------------------------------------------------------------------
# create_event — fallback to ICS
# ---------------------------------------------------------------------------

class TestCreateEvent:
    def test_falls_back_to_ics_when_no_account(self, tmp_path):
        event = CalendarEvent(summary="Fallback Test", start=datetime(2026, 3, 25, 14, 0))
        with patch("openclaw_mail.calendar.core.REPORT_DIR", tmp_path):
            result = create_event(event)
        assert result["method"] == "ics"
        ics_path = Path(result["result"])
        assert ics_path.exists()
        content = ics_path.read_text()
        assert "Fallback Test" in content

    def test_falls_back_to_ics_when_no_credentials(self, tmp_path):
        event = CalendarEvent(summary="No Creds", start=datetime(2026, 3, 25, 14, 0))
        fake_account = {
            "id": "test",
            "calendar": {"provider": "google", "_client_secrets": "/nonexistent/path.json"},
        }
        with (
            patch("openclaw_mail.calendar.core.find_account", return_value=fake_account),
            patch("openclaw_mail.calendar.core.REPORT_DIR", tmp_path),
        ):
            result = create_event(event, account_id="test")
        assert result["method"] == "ics"

    def test_uses_google_api_when_service_available(self):
        event = CalendarEvent(summary="API Test", start=datetime(2026, 3, 25, 14, 0))
        mock_service = MagicMock()
        mock_service.events().insert().execute.return_value = {
            "id": "abc123",
            "htmlLink": "https://calendar.google.com/event/abc123",
        }
        fake_account = {"id": "test", "calendar": {"provider": "google"}}
        with (
            patch("openclaw_mail.calendar.core.find_account", return_value=fake_account),
            patch("openclaw_mail.calendar.core._get_google_service", return_value=mock_service),
        ):
            result = create_event(event, account_id="test")
        assert result["method"] == "google_api"
        assert result["result"] == "abc123"

    def test_ics_filename_contains_summary(self, tmp_path):
        event = CalendarEvent(summary="Sprint Planning", start=datetime(2026, 3, 25, 10, 0))
        with patch("openclaw_mail.calendar.core.REPORT_DIR", tmp_path):
            result = create_event(event)
        assert "Sprint Planning" in result["result"]


# ---------------------------------------------------------------------------
# list_events
# ---------------------------------------------------------------------------

class TestListEvents:
    def test_returns_empty_when_no_account(self):
        events = list_events()
        assert events == []

    def test_returns_empty_when_no_google_service(self):
        fake_account = {"id": "test", "calendar": {"provider": "google"}}
        with (
            patch("openclaw_mail.calendar.core.find_account", return_value=fake_account),
            patch("openclaw_mail.calendar.core._get_google_service", return_value=None),
        ):
            events = list_events(account_id="test")
        assert events == []

    def test_returns_events_from_google(self):
        mock_service = MagicMock()
        mock_service.events().list().execute.return_value = {
            "items": [
                {
                    "summary": "Standup",
                    "start": {"dateTime": "2026-03-25T09:00:00+02:00"},
                    "end": {"dateTime": "2026-03-25T09:15:00+02:00"},
                    "id": "evt1",
                },
            ]
        }
        fake_account = {"id": "test", "calendar": {"provider": "google"}}
        with (
            patch("openclaw_mail.calendar.core.find_account", return_value=fake_account),
            patch("openclaw_mail.calendar.core._get_google_service", return_value=mock_service),
        ):
            events = list_events(account_id="test")
        assert len(events) == 1
        assert events[0]["summary"] == "Standup"
