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
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from openclaw_mail.utils.logging import get_logger

log = get_logger("mq", "mq.log")

AGENT_ID = os.environ.get("IAMQ_AGENT_ID", "mail_agent")
MQ_HTTP_BASE = os.environ.get("IAMQ_HTTP_URL", "http://127.0.0.1:18790")
MQ_QUEUE_DIR = Path.home() / "Ws" / "Openclaw" / "openclaw-inter-agent-message-queue" / "queue"
WORKSPACE = str(Path(__file__).resolve().parent.parent.parent)

# Timeout for HTTP requests to the MQ service (seconds)
HTTP_TIMEOUT = 5

# Agent metadata — sent with every registration so other agents can discover us
AGENT_METADATA = {
    "name": "Openclaw 🦀",
    "emoji": "🦀",
    "description": "Multi-account email management and auto-filing. "
                   "Runs a 4-step filtering pipeline (address/keyword/AI/review) "
                   "across DavMail and Gmail accounts. Generates tidy reports and digests.",
    "capabilities": [
        "email_tidy",
        "email_digest",
        "folder_management",
        "rule_engine",
        "email_filtering",
        "inbox_summary",
    ],
    "workspace": WORKSPACE,
}


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
    """Register mail_agent with full metadata so other agents can discover us.

    Sends agent_id + name, emoji, description, capabilities, workspace.
    The MQ service merges metadata on re-registration, so this is safe
    to call on every startup.
    """
    payload = {"agent_id": AGENT_ID, **AGENT_METADATA}
    result = _post("/register", payload)
    if result:
        log.info(f"MQ registered with metadata: {AGENT_ID}")
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


def send_tidy_report(
    summary: str,
    full_report: str | None = None,
    reports: list[dict] | None = None,
) -> None:
    """Send a tidy report summary to relevant agents via MQ.

    Broadcasts the summary to all agents so they're aware of mail activity.
    Also sends directly to main for dashboard purposes.
    If reports are provided, routes PR-related emails to gitrepo_agent.
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

    # Route PR-related emails to gitrepo_agent
    if reports:
        route_pr_emails(reports)

    log.info("MQ: tidy report distributed")


# ---------------------------------------------------------------------------
# PR email routing — mail_agent → gitrepo_agent
# ---------------------------------------------------------------------------

# Patterns that indicate a PR/code-review email
_PR_PATTERNS = re.compile(
    r"(pull\s*request|"
    r"\bPR[\s#:]\d|"
    r"code\s*review|"
    r"merge\s*(code|request|complet)|"
    r"approved.*pull|"
    r"reviewer\s*(added|removed)|"
    r"completed.*pull\s*request|"
    r"abandon|"
    r"has\s*voted|"
    r"Azure\s*DevOps)",
    re.IGNORECASE,
)

# Folders that indicate DevOps/code content
_DEVOPS_FOLDERS = {"DevOps", "Projects/RIB-4.0/DevOps", "Projects/Deep-Amber"}

# Senders that are known PR notification sources
_PR_SENDERS = {"azuredevops@microsoft.com", "noreply@github.com"}


def _is_pr_email(detail: dict) -> bool:
    """Check if a tidy detail entry looks like a PR notification."""
    subject = detail.get("subject", "")
    sender = detail.get("sender", "").lower()
    folder = detail.get("folder", "")

    # Known PR notification sender
    if any(s in sender for s in _PR_SENDERS):
        return True

    # Filed to a DevOps folder AND subject matches PR pattern
    if folder in _DEVOPS_FOLDERS and _PR_PATTERNS.search(subject):
        return True

    # Strong PR pattern match regardless of folder
    if _PR_PATTERNS.search(subject) and "pull request" in subject.lower():
        return True

    return False


def route_pr_emails(reports: list[dict]) -> int:
    """Scan tidy results for PR-related emails and forward to gitrepo_agent.

    Returns the number of PR emails routed.
    """
    pr_details = []
    for report in reports:
        account = report.get("account", "unknown")
        for detail in report.get("details", []):
            if _is_pr_email(detail):
                pr_details.append({**detail, "account": account})

    if not pr_details:
        return 0

    # Build a summary for gitrepo_agent
    lines = [f"PR notifications detected in email tidy ({len(pr_details)} items):"]
    lines.append("")
    for pr in pr_details:
        lines.append(
            f"- [{pr.get('account', '?')}] {pr.get('subject', '?')} "
            f"(from: {pr.get('sender', '?')}, folder: {pr.get('folder', '?')})"
        )

    body = "\n".join(lines)

    send_message(
        to="gitrepo_agent",
        msg_type="request",
        subject=f"PR email notifications ({len(pr_details)} items)",
        body=body,
        priority="HIGH",
    )

    log.info(f"MQ: routed {len(pr_details)} PR emails to gitrepo_agent")
    return len(pr_details)


def reply(original_msg: dict, body: str, msg_type: str = "response") -> dict | None:
    """Reply to a message via the MQ, setting replyTo correctly."""
    return send_message(
        to=original_msg["from"],
        msg_type=msg_type,
        subject=f"Re: {original_msg.get('subject', '')}",
        body=body,
        priority=original_msg.get("priority", "NORMAL"),
        reply_to=original_msg.get("id"),
    )


def _handle_request(msg: dict) -> None:
    """Handle an incoming request message and reply via MQ.

    Recognises roll-call / introduction requests and capability queries.
    For unknown requests, sends a polite acknowledgement.
    """
    subject = msg.get("subject", "").lower()
    body_lower = msg.get("body", "").lower()

    # Roll-call / introduction requests
    if any(kw in subject or kw in body_lower for kw in [
        "roll call", "introduce yourself", "who are you", "capabilities",
    ]):
        intro = (
            f"I am {AGENT_ID} — {AGENT_METADATA['description']}\n\n"
            f"Workspace: {WORKSPACE}\n"
            f"Capabilities: {', '.join(AGENT_METADATA['capabilities'])}\n\n"
            "Send me requests of type 'request' and I'll process them. "
            "I broadcast tidy reports after each run so all agents stay informed."
        )
        reply(msg, intro, msg_type="response")
        log.info(f"MQ: replied to roll-call from {msg['from']}")
        return

    # Inbox summary request
    if any(kw in subject or kw in body_lower for kw in [
        "inbox summary", "email summary", "mail summary", "tidy status",
    ]):
        # Try to read the latest summary
        from openclaw_mail.config import REPORT_DIR
        summary_file = REPORT_DIR / "last_tidy_summary.txt"
        if summary_file.exists():
            summary = summary_file.read_text()
        else:
            summary = "No tidy report available yet. Run `mail-tidy` first."
        reply(msg, summary, msg_type="response")
        log.info(f"MQ: sent inbox summary to {msg['from']}")
        return

    # Generic acknowledgement for other requests
    reply(
        msg,
        f"Received your request: {msg.get('subject', '?')}. "
        "I'll process this on my next cycle.",
        msg_type="response",
    )
    log.info(f"MQ: acknowledged request from {msg['from']}: {msg.get('subject')}")


def process_inbox() -> list[dict]:
    """Check inbox for messages and process them.

    - info/response messages: log and mark as acted
    - request messages: handle (auto-reply where possible) and mark as acted
    - error messages: log warning and mark as acted

    Returns list of messages that were processed.
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
        if body:
            log.info(f"  Body: {body[:300]}")

        # Mark as read first
        if msg_id:
            mark_read(msg_id)

        # Handle requests — reply via MQ
        if msg_type == "request":
            _handle_request(msg)

        # Log errors from other agents
        if msg_type == "error":
            log.warning(f"MQ error from {msg_from}: {subject} — {body[:200]}")

        # Mark as acted (we've processed it)
        if msg_id:
            mark_acted(msg_id)

        processed.append(msg)

    if not messages:
        log.debug("MQ inbox: no unread messages")

    return processed
