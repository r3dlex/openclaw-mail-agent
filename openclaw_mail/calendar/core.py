"""Calendar operations — create, list, and manage events.

Uses Google Calendar API when credentials are available, falls back to
ICS file generation when they're not.

Google Calendar setup:
  1. Create OAuth credentials at console.cloud.google.com
  2. Download client_secrets.json to config/
  3. Set GOOGLE_CLIENT_SECRETS_FILE and GOOGLE_TOKEN_FILE in .env
  4. First run will open a browser for OAuth consent
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from openclaw_mail.config import CONFIG_DIR, REPORT_DIR, find_account
from openclaw_mail.utils.logging import get_logger

log = get_logger("calendar", "calendar.log")


@dataclass
class CalendarEvent:
    """Represents a calendar event."""

    summary: str
    start: datetime
    end: datetime | None = None
    description: str = ""
    location: str = ""
    attendees: list[str] = field(default_factory=list)
    timezone: str = "Europe/Berlin"

    def __post_init__(self):
        if self.end is None:
            self.end = self.start + timedelta(hours=1)


def _get_google_service(account: dict):
    """Build a Google Calendar API service using stored credentials.

    Returns None if credentials are not configured or invalid.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        log.debug("Google Calendar dependencies not installed (poetry install --with calendar)")
        return None

    cal_config = account.get("calendar", {})
    secrets_path = cal_config.get("_client_secrets", "") or str(CONFIG_DIR / "client_secrets.json")
    token_path = cal_config.get("_token", "") or str(CONFIG_DIR / "token.json")

    secrets_file = Path(secrets_path)
    token_file = Path(token_path)

    if not secrets_file.exists():
        log.debug(f"Google client secrets not found: {secrets_file}")
        return None

    scopes = ["https://www.googleapis.com/auth/calendar"]
    creds = None

    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_file), scopes)
            creds = flow.run_local_server(port=0)
        token_file.write_text(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def create_event(
    event: CalendarEvent,
    account_id: str | None = None,
) -> dict:
    """Create a calendar event.

    Tries Google Calendar API first, falls back to ICS file generation.

    Returns:
        dict with keys: method ("google_api" | "ics"), result (event ID or file path)
    """
    account = find_account(account_id) if account_id else None
    cal_provider = (account or {}).get("calendar", {}).get("provider", "")

    # Try Google Calendar API
    if cal_provider == "google" and account:
        service = _get_google_service(account)
        if service:
            return _create_google_event(service, event)

    # Fallback to ICS
    from openclaw_mail.calendar.ics import generate_ics

    ics_content = generate_ics(event)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "" for c in event.summary)[:50].strip()
    ics_path = REPORT_DIR / f"event_{safe_name}_{event.start.strftime('%Y%m%d_%H%M')}.ics"
    ics_path.write_text(ics_content)
    log.info(f"ICS file saved: {ics_path}")
    return {"method": "ics", "result": str(ics_path)}


def _create_google_event(service, event: CalendarEvent) -> dict:
    """Create an event via Google Calendar API."""
    body = {
        "summary": event.summary,
        "description": event.description,
        "location": event.location,
        "start": {
            "dateTime": event.start.isoformat(),
            "timeZone": event.timezone,
        },
        "end": {
            "dateTime": event.end.isoformat(),
            "timeZone": event.timezone,
        },
    }
    if event.attendees:
        body["attendees"] = [{"email": a} for a in event.attendees]

    result = service.events().insert(calendarId="primary", body=body).execute()
    event_id = result.get("id", "")
    link = result.get("htmlLink", "")
    log.info(f"Google Calendar event created: {event_id} — {link}")
    return {"method": "google_api", "result": event_id, "link": link}


def list_events(
    account_id: str | None = None,
    max_results: int = 10,
    time_min: datetime | None = None,
) -> list[dict]:
    """List upcoming calendar events.

    Returns a list of event dicts with keys: summary, start, end, id.
    Falls back to empty list if API is not available.
    """
    account = find_account(account_id) if account_id else None
    cal_provider = (account or {}).get("calendar", {}).get("provider", "")

    if cal_provider == "google" and account:
        service = _get_google_service(account)
        if service:
            return _list_google_events(service, max_results, time_min)

    log.debug("No calendar API available — cannot list events")
    return []


def _list_google_events(
    service,
    max_results: int,
    time_min: datetime | None,
) -> list[dict]:
    """List events via Google Calendar API."""
    if time_min is None:
        time_min = datetime.now(UTC)

    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min.isoformat() + "Z",
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = []
    for item in result.get("items", []):
        events.append({
            "summary": item.get("summary", ""),
            "start": item.get("start", {}).get("dateTime", item.get("start", {}).get("date", "")),
            "end": item.get("end", {}).get("dateTime", item.get("end", {}).get("date", "")),
            "id": item.get("id", ""),
        })
    return events
