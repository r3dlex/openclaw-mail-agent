"""Himalaya CLI wrapper for email operations."""

from __future__ import annotations

import json
import os
import subprocess
import time

from openclaw_mail.utils.logging import get_logger

log = get_logger("himalaya")


def himalaya_run(cmd: str, timeout: int = 30) -> tuple[str, str]:
    """Run a himalaya CLI command. Returns (stdout, stderr)."""
    env = os.environ.copy()
    env["RUST_LOG"] = "error"
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, env=env)
        return result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return "", "timeout"


def get_envelopes(account: str, folder: str = "INBOX", limit: int = 50, timeout: int = 30) -> list[dict]:
    """Fetch envelope list from an account via himalaya."""
    cmd = f'himalaya envelope list -a {account} -o json --folder "{folder}" -s {limit}'
    stdout, stderr = himalaya_run(cmd, timeout=timeout)
    if not stdout or "error" in stderr.lower():
        return []
    try:
        return json.loads(stdout)[:limit]
    except (json.JSONDecodeError, TypeError):
        return []


def move_email(account: str, msg_id: str, folder: str, timeout: int = 15) -> bool:
    """Move an email to a target folder."""
    cmd = f'himalaya message move -a {account} "{folder}" {msg_id}'
    _, stderr = himalaya_run(cmd, timeout=timeout)
    return "error" not in stderr.lower()


def create_folder(account: str, folder: str, timeout: int = 10) -> bool:
    """Create a folder (idempotent)."""
    cmd = f'himalaya folder create -a {account} "{folder}"'
    _, stderr = himalaya_run(cmd, timeout=timeout)
    return "error" not in stderr.lower()


def restart_davmail() -> None:
    """Restart DavMail if it's not responding (macOS)."""
    log.info("Restarting DavMail...")
    subprocess.run("pkill -f davmail", shell=True, capture_output=True)
    time.sleep(2)
    subprocess.run("open -a DavMail", shell=True, capture_output=True)
    time.sleep(5)


def get_envelopes_with_retry(
    account: str,
    folder: str = "INBOX",
    limit: int = 50,
    max_retries: int = 3,
    is_davmail: bool = False,
) -> list[dict]:
    """Get envelopes with retry logic for slow/unresponsive servers."""
    timeout = 90 if is_davmail else 30
    batch = min(limit, 5) if is_davmail else limit
    davmail_restarted = False

    for attempt in range(max_retries):
        envelopes = get_envelopes(account, folder, batch, timeout)
        if envelopes:
            return envelopes

        if is_davmail and not davmail_restarted:
            restart_davmail()
            davmail_restarted = True
            continue

        wait = (attempt + 1) * 5
        log.warning(f"{account}: retry {attempt + 2}/{max_retries} in {wait}s...")
        time.sleep(wait)

    return []
