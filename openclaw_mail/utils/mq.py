"""Inter-agent message queue client.

Connects to the OpenClaw inter-agent MQ service (Elixir/OTP) for
cross-agent communication. Supports both HTTP API and file-based fallback.

The MQ service runs at:
  - HTTP: http://127.0.0.1:18790
  - WebSocket: ws://127.0.0.1:18791/ws
  - File fallback: ~/Ws/Openclaw/openclaw-inter-agent-message-queue/queue/

See: openclaw-inter-agent-message-queue/spec/API.md
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from openclaw_mail.utils.logging import get_logger

log = get_logger("mq", "mq.log")

AGENT_ID = "mail_agent"
MQ_HTTP_BASE = "http://127.0.0.1:18790"
MQ_QUEUE_DIR = Path.home() / "Ws" / "Openclaw" / "openclaw-inter-agent-message-queue" / "queue"

# Timeout for HTTP requests to the MQ service (seconds)
HTTP_TIMEOUT = 5


# ---------------------------------------------------------------------------
# Low-level HTTP helpers
# ---------------------------------------------------------------------------

def _post(path: str, body: dict) -> dict | None:
    """POST JSON to the MQ HTTP API. Returns parsed response or None on failure."""
    url = f"{MQ_HTTP_BASE}{path}"
    data = json.dumps(body).encode()
    req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except (URLError, OSError, json.JSONDecodeError) as e:
        log.debug(f"MQ HTTP POST {path} failed: {e}")
        return None


def _get(path: str) -> dict | None:
    """GET from the MQ HTTP API. Returns parsed response or None on failure."""
    url = f"{MQ_HTTP_BASE}{path}"
    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except (URLError, OSError, json.JSONDecodeError) as e:
        log.debug(f"MQ HTTP GET {path} failed: {e}")
        return None


def _patch(path: str, body: dict) -> dict | None:
    """PATCH to the MQ HTTP API."""
    url = f"{MQ_HTTP_BASE}{path}"
    data = json.dumps(body).encode()
    req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="PATCH")
    try:
        with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except (URLError, OSError, json.JSONDecodeError) as e:
        log.debug(f"MQ HTTP PATCH {path} failed: {e}")
        return None


# ---------------------------------------------------------------------------
# File-based fallback helpers
# ---------------------------------------------------------------------------

def _file_timestamp() -> str:
    """Generate an ISO timestamp safe for filenames (colons replaced with dashes)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _build_message(
    to: str,
    msg_type: str,
    subject: str,
    body: str,
    priority: str = "NORMAL",
    reply_to: str | None = None,
    expires_at: str | None = None,
) -> dict:
    """Build a message dict conforming to the MQ protocol."""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "id": str(uuid.uuid4()),
        "from": AGENT_ID,
        "to": to,
        "priority": priority,
        "type": msg_type,
        "subject": subject[:80],
        "body": body,
        "replyTo": reply_to,
        "createdAt": now,
        "expiresAt": expires_at,
        "status": "unread",
    }


def _write_message_file(msg: dict) -> Path | None:
    """Write a message as a JSON file to the recipient's queue directory."""
    recipient = msg["to"]
    inbox_dir = MQ_QUEUE_DIR / recipient
    if not inbox_dir.exists():
        log.warning(f"MQ queue directory not found: {inbox_dir}")
        return None
    filename = f"{_file_timestamp()}-{AGENT_ID}.json"
    filepath = inbox_dir / filename
    filepath.write_text(json.dumps(msg, indent=2, ensure_ascii=False))
    log.debug(f"MQ file written: {filepath}")
    return filepath


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def register() -> bool:
    """Register mail_agent with the MQ service.

    Tries HTTP first, falls back to logging a notice if the service is down.
    The file-based queue works regardless of registration.
    """
    result = _post("/register", {"agent_id": AGENT_ID})
    if result:
        log.info(f"MQ registered via HTTP: {result}")
        return True
    log.info("MQ HTTP unavailable — file-based queue still active")
    return False


def heartbeat() -> bool:
    """Send a heartbeat to the MQ service."""
    result = _post("/heartbeat", {"agent_id": AGENT_ID})
    if result:
        log.debug("MQ heartbeat sent")
        return True
    return False


def send_message(
    to: str,
    msg_type: str,
    subject: str,
    body: str,
    priority: str = "NORMAL",
    reply_to: str | None = None,
    expires_at: str | None = None,
) -> dict | None:
    """Send a message to another agent.

    Tries HTTP API first, falls back to file-based delivery.
    Returns the message dict on success, None on failure.
    """
    # Try HTTP first
    http_body = {
        "from": AGENT_ID,
        "to": to,
        "type": msg_type,
        "priority": priority,
        "subject": subject[:80],
        "body": body,
        "replyTo": reply_to,
        "expiresAt": expires_at,
    }
    result = _post("/send", http_body)
    if result:
        log.info(f"MQ sent via HTTP → {to}: {subject[:50]}")
        return result

    # Fallback: file-based
    msg = _build_message(to, msg_type, subject, body, priority, reply_to, expires_at)
    filepath = _write_message_file(msg)
    if filepath:
        log.info(f"MQ sent via file → {to}: {subject[:50]}")
        return msg

    log.warning(f"MQ send failed (both HTTP and file) → {to}: {subject[:50]}")
    return None


def broadcast(
    msg_type: str,
    subject: str,
    body: str,
    priority: str = "NORMAL",
) -> dict | None:
    """Broadcast a message to all agents."""
    return send_message("broadcast", msg_type, subject, body, priority)


def check_inbox() -> list[dict]:
    """Check for unread messages (HTTP inbox + file-based fallback).

    Returns a list of message dicts, sorted chronologically.
    """
    messages = []

    # Try HTTP first
    result = _get(f"/inbox/{AGENT_ID}?status=unread")
    if result and "messages" in result:
        messages.extend(result["messages"])
        log.info(f"MQ inbox (HTTP): {len(result['messages'])} unread messages")
    else:
        # Fallback: read from file-based queue
        messages.extend(_read_file_inbox(MQ_QUEUE_DIR / AGENT_ID))

    # Also check broadcast
    broadcast_result = _get("/inbox/broadcast?status=unread")
    if broadcast_result and "messages" in broadcast_result:
        # Filter broadcasts we haven't seen
        for msg in broadcast_result["messages"]:
            if msg.get("from") != AGENT_ID:  # Don't read our own broadcasts
                messages.append(msg)
    else:
        # Fallback: read broadcast files
        for msg in _read_file_inbox(MQ_QUEUE_DIR / "broadcast"):
            if msg.get("from") != AGENT_ID:
                messages.append(msg)

    # Sort chronologically
    messages.sort(key=lambda m: m.get("createdAt", ""))
    return messages


def _read_file_inbox(inbox_dir: Path) -> list[dict]:
    """Read unread messages from a file-based inbox directory."""
    messages = []
    if not inbox_dir.exists():
        return messages
    for f in sorted(inbox_dir.glob("*.json")):
        try:
            msg = json.loads(f.read_text())
            if msg.get("status") == "unread":
                messages.append(msg)
        except (json.JSONDecodeError, OSError) as e:
            log.warning(f"MQ: failed to read {f}: {e}")
    return messages


def mark_read(message_id: str) -> bool:
    """Mark a message as read."""
    result = _patch(f"/messages/{message_id}", {"status": "read"})
    if result:
        return True
    # File-based: update status in the file (search all inbox dirs)
    return _update_file_status(message_id, "read")


def mark_acted(message_id: str) -> bool:
    """Mark a message as acted upon."""
    result = _patch(f"/messages/{message_id}", {"status": "acted"})
    if result:
        return True
    return _update_file_status(message_id, "acted")


def _update_file_status(message_id: str, status: str) -> bool:
    """Update a message's status in the file-based queue."""
    inbox_dir = MQ_QUEUE_DIR / AGENT_ID
    if not inbox_dir.exists():
        return False
    for f in inbox_dir.glob("*.json"):
        try:
            msg = json.loads(f.read_text())
            if msg.get("id") == message_id:
                msg["status"] = status
                f.write_text(json.dumps(msg, indent=2, ensure_ascii=False))
                return True
        except (json.JSONDecodeError, OSError):
            continue
    return False


def get_status() -> dict | None:
    """Get the MQ service status (queue health, online agents)."""
    return _get("/status")


def get_agents() -> list[dict]:
    """List all registered agents."""
    result = _get("/agents")
    if result and "agents" in result:
        return result["agents"]
    return []


def send_tidy_report(summary: str, full_report: str | None = None) -> None:
    """Send a tidy report summary to relevant agents via MQ.

    Broadcasts the summary to all agents so they're aware of mail activity.
    Also sends directly to main for dashboard purposes.
    """
    # Broadcast summary to all agents
    broadcast(
        msg_type="info",
        subject="Email tidy complete",
        body=summary,
        priority="NORMAL",
    )

    # Send detailed report to main (the orchestrator)
    if full_report:
        send_message(
            to="main",
            msg_type="info",
            subject="Email tidy report (full)",
            body=full_report[:5000],  # Truncate to keep messages reasonable
            priority="LOW",
        )

    log.info("MQ: tidy report distributed")


def process_inbox() -> list[dict]:
    """Check inbox for messages and process them.

    Returns list of messages that were processed.
    Marks each as read after processing.
    """
    messages = check_inbox()
    processed = []

    for msg in messages:
        msg_from = msg.get("from", "unknown")
        msg_type = msg.get("type", "info")
        subject = msg.get("subject", "(no subject)")
        body = msg.get("body", "")
        msg_id = msg.get("id")

        log.info(f"MQ inbox: [{msg_type}] from {msg_from}: {subject}")

        # Log the message content for the agent to see
        if body:
            log.info(f"  Body: {body[:200]}")

        # Mark as read
        if msg_id:
            mark_read(msg_id)

        processed.append(msg)

    if not messages:
        log.debug("MQ inbox: no unread messages")

    return processed
