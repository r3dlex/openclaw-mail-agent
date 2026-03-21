"""Himalaya CLI wrapper for email operations.

Timeout strategy:
    DavMail (Exchange/O365 bridge) is extremely slow — 5-90 seconds per query.
    All public functions accept an explicit ``timeout`` parameter. When callers
    know they're talking to a DavMail account, they should pass higher values.

    Helper: ``davmail_timeout(base)`` returns ``base * DAVMAIL_TIMEOUT_MULTIPLIER``
    so callers can simply write ``timeout=davmail_timeout(15)`` instead of
    guessing a safe number.

Retry strategy:
    ``himalaya_run_with_retry()`` wraps ``himalaya_run()`` with configurable
    retries and exponential back-off.  All high-level functions use it so that
    transient DavMail/IMAP hiccups don't cause silent data loss.
"""

from __future__ import annotations

import json
import os
import subprocess
import time

from openclaw_mail.utils.logging import get_logger

log = get_logger("himalaya")

# ---------------------------------------------------------------------------
# Timeout helpers
# ---------------------------------------------------------------------------

#: Multiplier applied to base timeouts when talking through DavMail.
DAVMAIL_TIMEOUT_MULTIPLIER: int = 4

#: Minimum timeout (seconds) we'll ever pass to subprocess.run.
MIN_TIMEOUT: int = 10


def davmail_timeout(base: int) -> int:
    """Return a DavMail-safe timeout: ``max(base * multiplier, MIN_TIMEOUT)``."""
    return max(base * DAVMAIL_TIMEOUT_MULTIPLIER, MIN_TIMEOUT)


def _effective_timeout(timeout: int) -> int:
    """Clamp a timeout to at least ``MIN_TIMEOUT``."""
    return max(timeout, MIN_TIMEOUT)


# ---------------------------------------------------------------------------
# Low-level runner
# ---------------------------------------------------------------------------

def himalaya_run(cmd: str, timeout: int = 30) -> tuple[str, str]:
    """Run a himalaya CLI command.  Returns ``(stdout, stderr)``.

    On timeout, logs a warning and returns ``("", "timeout")``.
    """
    timeout = _effective_timeout(timeout)
    env = os.environ.copy()
    env["RUST_LOG"] = "error"
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, env=env,
        )
        return result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        log.warning(f"Command timed out after {timeout}s: {cmd[:120]}…")
        return "", "timeout"


def himalaya_run_with_retry(
    cmd: str,
    timeout: int = 30,
    retries: int = 2,
    backoff: int = 5,
) -> tuple[str, str]:
    """Run a himalaya command with retry on timeout / transient errors.

    Args:
        cmd: Shell command string.
        timeout: Per-attempt timeout in seconds.
        retries: Number of *extra* attempts after the first failure (total = 1 + retries).
        backoff: Base seconds between retries (multiplied by attempt number).

    Returns:
        ``(stdout, stderr)`` from the first successful attempt, or from the
        last attempt if all fail.
    """
    for attempt in range(1 + retries):
        stdout, stderr = himalaya_run(cmd, timeout=timeout)

        # Success — got output and no error
        if stdout and "error" not in stderr.lower():
            return stdout, stderr

        # Non-timeout error on first attempt — return immediately (no point retrying auth errors etc.)
        is_timeout = stderr.strip().lower() == "timeout"
        if not is_timeout and attempt == 0 and stderr and "error" in stderr.lower():
            return stdout, stderr

        if attempt < retries:
            wait = backoff * (attempt + 1)
            log.warning(
                f"Retry {attempt + 1}/{retries} in {wait}s "
                f"(timeout={is_timeout}): {cmd[:100]}…"
            )
            time.sleep(wait)

    return stdout, stderr


# ---------------------------------------------------------------------------
# Envelope operations
# ---------------------------------------------------------------------------

def get_envelopes(
    account: str,
    folder: str = "INBOX",
    limit: int = 50,
    timeout: int = 30,
    retries: int = 0,
) -> list[dict]:
    """Fetch envelope list from an account via himalaya.

    Args:
        account: Himalaya account name.
        folder: Folder to list.
        limit: Max envelopes to return.
        timeout: Per-attempt timeout.
        retries: Extra retry attempts (0 = single attempt, for back-compat).
    """
    cmd = f'himalaya envelope list -a {account} -o json --folder "{folder}" -s {limit}'
    stdout, stderr = (
        himalaya_run_with_retry(cmd, timeout=timeout, retries=retries)
        if retries > 0
        else himalaya_run(cmd, timeout=timeout)
    )
    if not stdout or "error" in stderr.lower():
        return []
    try:
        return json.loads(stdout)[:limit]
    except (json.JSONDecodeError, TypeError):
        return []


# ---------------------------------------------------------------------------
# Move operations
# ---------------------------------------------------------------------------

def move_email(
    account: str,
    msg_id: str | list[str],
    folder: str,
    source_folder: str = "INBOX",
    timeout: int = 30,
    retries: int = 1,
) -> bool:
    """Move email(s) to a target folder.

    Args:
        account: Himalaya account name.
        msg_id: Single message ID or list of IDs.
        folder: Target folder name.
        source_folder: Source folder (default INBOX).
        timeout: Per-attempt timeout in seconds (default 30 — was 15, too low for DavMail).
        retries: Extra retry attempts on timeout (default 1).
    """
    ids = msg_id if isinstance(msg_id, str) else " ".join(msg_id)
    # Scale timeout with batch size — each extra message adds ~0.5s over DavMail
    id_count = len(msg_id) if isinstance(msg_id, list) else 1
    scaled_timeout = max(timeout, timeout + id_count)

    cmd = f'himalaya message move -a {account} -f "{source_folder}" "{folder}" {ids}'
    _, stderr = himalaya_run_with_retry(cmd, timeout=scaled_timeout, retries=retries)
    ok = "error" not in stderr.lower() and stderr.strip().lower() != "timeout"
    if not ok:
        log.error(f"move_email failed: {source_folder} → {folder} ({id_count} msgs): {stderr[:200]}")
    return ok


def bulk_move(
    account: str,
    source_folder: str,
    target_folder: str,
    timeout: int = 30,
    envelopes: list[dict] | None = None,
    retries: int = 1,
) -> dict:
    """Move all emails from source_folder to target_folder.

    Uses batch move (all IDs in one command) for efficiency.
    Pass pre-fetched envelopes to avoid a redundant server query.
    Returns dict with keys: moved (int), errors (int), source_empty (bool).
    """
    if envelopes is None:
        envelopes = get_envelopes(
            account, source_folder, limit=500,
            timeout=max(timeout, 60), retries=retries,
        )
    if not envelopes:
        return {"moved": 0, "errors": 0, "source_empty": True}

    ids = [str(env.get("id", "")) for env in envelopes if env.get("id")]
    if not ids:
        return {"moved": 0, "errors": len(envelopes), "source_empty": False}

    # Batch move — scale timeout with message count
    move_timeout = max(timeout, 60) + len(ids)  # +1s per message
    ok = move_email(
        account, ids, target_folder,
        source_folder=source_folder,
        timeout=move_timeout,
        retries=retries,
    )
    moved = len(ids) if ok else 0
    errors = 0 if ok else len(ids)

    log.info(f"{account}: moved {moved}/{len(envelopes)} from '{source_folder}' → '{target_folder}' ({errors} errors)")
    return {"moved": moved, "errors": errors, "source_empty": False}


# ---------------------------------------------------------------------------
# Folder operations
# ---------------------------------------------------------------------------

def create_folder(account: str, folder: str, timeout: int = 20) -> bool:
    """Create a folder (idempotent).

    Default timeout raised from 10 → 20s (DavMail commonly needs 8-15s).
    """
    cmd = f'himalaya folder create -a {account} "{folder}"'
    _, stderr = himalaya_run_with_retry(cmd, timeout=timeout, retries=1)
    return "error" not in stderr.lower()


def list_folders(account: str, timeout: int = 30) -> list[str]:
    """List all folder names for an account.

    Default timeout raised from 15 → 30s (DavMail can be slow listing many folders).
    """
    cmd = f'himalaya folder list -a {account} -o json'
    stdout, stderr = himalaya_run_with_retry(cmd, timeout=timeout, retries=1)
    if not stdout or "error" in stderr.lower():
        return []
    try:
        folders = json.loads(stdout)
        return [f["name"] for f in folders]
    except (json.JSONDecodeError, TypeError, KeyError):
        return []


# ---------------------------------------------------------------------------
# DavMail management
# ---------------------------------------------------------------------------

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
    """Get envelopes with retry logic for slow/unresponsive servers.

    For DavMail accounts, uses higher timeouts and smaller batch sizes.
    Falls back to restarting DavMail if the first attempt fails.
    """
    timeout = davmail_timeout(60) if is_davmail else 30  # 240s vs 30s for large batches
    batch = limit  # No artificial cap — fetch all requested
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
