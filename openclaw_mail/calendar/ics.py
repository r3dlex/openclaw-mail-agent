"""ICS file generation for calendar events.

Produces RFC 5545 compliant .ics files that can be imported into any
calendar application (Google Calendar, Outlook, Apple Calendar, etc.).

No external dependencies — pure Python stdlib.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from openclaw_mail.calendar.core import CalendarEvent


def _ical_datetime(dt: datetime) -> str:
    """Format a datetime as iCalendar DTSTART/DTEND value."""
    return dt.strftime("%Y%m%dT%H%M%S")


def _escape(text: str) -> str:
    """Escape special characters for iCalendar text fields."""
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def generate_ics(event: CalendarEvent) -> str:
    """Generate an RFC 5545 .ics file content for a CalendarEvent.

    Returns the complete .ics file as a string.
    """
    uid = str(uuid.uuid4())
    now = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//OpenClaw Mail Agent//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now}",
        f"DTSTART;TZID={event.timezone}:{_ical_datetime(event.start)}",
        f"DTEND;TZID={event.timezone}:{_ical_datetime(event.end)}",
        f"SUMMARY:{_escape(event.summary)}",
    ]

    if event.description:
        lines.append(f"DESCRIPTION:{_escape(event.description)}")

    if event.location:
        lines.append(f"LOCATION:{_escape(event.location)}")

    for attendee in event.attendees:
        lines.append(f"ATTENDEE;RSVP=TRUE:mailto:{attendee}")

    lines.extend([
        "END:VEVENT",
        "END:VCALENDAR",
    ])

    return "\r\n".join(lines) + "\r\n"
