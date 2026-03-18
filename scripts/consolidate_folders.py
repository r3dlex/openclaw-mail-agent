#!/usr/bin/env python3
"""Folder consolidation script for RIB work account.

Moves emails from legacy/duplicate folders to their standardized targets.
Run with --dry-run to preview without moving.

Usage:
    poetry run python scripts/consolidate_folders.py --dry-run
    poetry run python scripts/consolidate_folders.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openclaw_mail.utils.himalaya import bulk_move, create_folder, davmail_timeout, get_envelopes, list_folders
from openclaw_mail.utils.logging import get_logger

log = get_logger("consolidate")

ACCOUNT = "RIB"

# (source_folder, target_folder) — order matters for nested folders (children first)
MOVES = [
    # Newsletter duplicates → Newsletters
    ("INBOX/Newsletter/Benefits", "Newsletters"),
    ("INBOX/Newsletter/Corporate", "Newsletters"),
    ("INBOX/Newsletter/Yammer", "Communication/Viva"),
    ("INBOX/Newsletter", "Newsletters"),
    ("Newsletter", "Newsletters"),
    ("Promotions", "Newsletters"),
    ("Social Activity Notifications", "Newsletters"),

    # INBOX/Communication duplicates → standardized targets
    ("INBOX/Communication/Azure-DevOps", "Projects/RIB-4.0/DevOps"),
    ("INBOX/Communication/MSTeams", "Communication/Teams"),
    ("INBOX/Communication/VivaEngage", "Communication/Viva"),
    ("INBOX/Communication/One on One", "Communication"),
    ("INBOX/Communication/Ops Tickets", "Admin"),
    ("INBOX/Communication/PLM-Jira-GoldenRules-ReleasePhases", "Projects/RIB-4.0"),
    ("INBOX/Communication/Trivium", "Communication"),

    # INBOX subfolders → proper targets
    ("INBOX/AI", "Projects/RIB-4.0/AI"),
    ("INBOX/Automations", "Admin"),
    ("INBOX/CC", "Review"),  # CC has no sorting value; triage manually
    ("INBOX/Escalation", "Review"),  # Escalation → Review per design
    ("INBOX/Executive", "Executive"),
    ("INBOX/YPN", "Newsletters"),  # Young Professionals Network → newsletters

    # Customer subfolders → Sales or Projects
    ("Customer/Zeppelin", "Projects/Zeppelin"),
    ("Customer/Bosch", "Sales"),
    ("Customer/DB", "Sales"),
    ("Customer/Willemen", "Sales"),
    ("Customer", "Sales"),

    # Legacy project path → new standard
    ("Projects/Zeppelin Rental", "Projects/Zeppelin"),
]

# Folders to create before moving (targets that may not exist yet)
ENSURE_FOLDERS = [
    "Communication",
    "Communication/Teams",
    "Communication/Viva",
    "Newsletters",
    "Projects/RIB-4.0",
    "Projects/RIB-4.0/AI",
    "Projects/RIB-4.0/Atlassian",
    "Projects/RIB-4.0/DevOps",
    "Projects/Zeppelin",
]


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("=== DRY RUN — no emails will be moved ===\n")

    # Ensure target folders exist (DavMail needs higher timeouts)
    print("--- Ensuring target folders exist ---")
    for folder in ENSURE_FOLDERS:
        if dry_run:
            print(f"  [dry-run] Would create: {folder}")
        else:
            ok = create_folder(ACCOUNT, folder, timeout=davmail_timeout(20))
            print(f"  {'✓' if ok else '✗'} {folder}")

    print()

    # Check counts and move
    print("--- Folder consolidation ---")
    total_moved = 0
    total_errors = 0

    for source, target in MOVES:
        sys.stdout.write(f"  Checking {source}...")
        sys.stdout.flush()
        envelopes = get_envelopes(ACCOUNT, source, limit=500, timeout=davmail_timeout(30))
        count = len(envelopes)

        if count == 0:
            print(f"\r  [empty] {source} → {target} (0 messages)    ")
            continue

        if dry_run:
            print(f"\r  [dry-run] {source} → {target} ({count} messages)    ")
        else:
            print(f"\r  Moving {count} from {source} → {target}...    ")
            sys.stdout.flush()
            result = bulk_move(ACCOUNT, source, target, timeout=davmail_timeout(30), envelopes=envelopes)
            status = "✓" if result["errors"] == 0 else "⚠"
            print(f"  {status} {source} → {target} (moved {result['moved']}, errors {result['errors']})")
            total_moved += result["moved"]
            total_errors += result["errors"]

    print()
    if dry_run:
        print("=== DRY RUN complete. Re-run without --dry-run to execute. ===")
    else:
        print(f"=== Done. Moved {total_moved} emails, {total_errors} errors. ===")

    # Report orphan folders
    print("\n--- Orphan folder report ---")
    report_orphans()


def report_orphans() -> None:
    """List folders on the server that aren't in the filter rules or system folders."""
    import yaml
    from openclaw_mail.config import CONFIG_DIR

    # Load filter config
    config_file = CONFIG_DIR / "filters" / "rib_work.yaml"
    if config_file.exists():
        with open(config_file) as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}

    # Collect all folders referenced in filter rules
    known_folders: set[str] = set()

    # From address_rules
    for rule in config.get("address_rules", []) or []:
        known_folders.add(rule.get("folder", ""))

    # From keyword_rules
    for rule in config.get("keyword_rules", []) or []:
        known_folders.add(rule.get("folder", ""))

    # From folder_definitions
    for folder in config.get("folder_definitions", {}) or {}:
        known_folders.add(folder)

    # Add system/standard folders
    known_folders.update({
        "INBOX", "Sent", "Trash", "Drafts", "Junk", "Review",
        "Archive", "Unsent Messages", "Sync Issues",
        "Sync Issues/Conflicts", "Sync Issues/Local Failures",
        "Sync Issues/Server Failures", "Conversation History",
    })

    # Get server folders
    server_folders = list_folders(ACCOUNT, timeout=davmail_timeout(30))
    if not server_folders:
        print("  [error] Could not list server folders")
        return

    # Find orphans (not in known set, not a parent of a known folder, not Trash/*)
    orphans = []
    for folder in sorted(server_folders):
        # Skip Trash subfolders (flat trash per design)
        if folder.startswith("Trash/"):
            continue
        # Skip if exact match
        if folder in known_folders:
            continue
        # Skip if it's a parent path of a known folder (e.g. "HR" is parent of "HR/Training")
        is_parent = any(k.startswith(folder + "/") for k in known_folders)
        if is_parent:
            continue
        # Skip if it's a child of a known folder (e.g. "HR/Flextime" under "HR")
        is_child_of_known = any(folder.startswith(k + "/") for k in known_folders)
        if is_child_of_known:
            continue
        orphans.append(folder)

    if orphans:
        print(f"  Found {len(orphans)} orphan folders (not in filter rules):")
        for folder in orphans:
            envelopes = get_envelopes(ACCOUNT, folder, limit=1, timeout=davmail_timeout(15))
            has_mail = "has mail" if envelopes else "empty"
            print(f"    • {folder} ({has_mail})")
    else:
        print("  No orphan folders found.")


if __name__ == "__main__":
    main()
