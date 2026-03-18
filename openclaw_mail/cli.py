"""CLI entrypoints for mail operations."""

from __future__ import annotations

import sys


def tidy():
    """Run the email tidy pipeline across all active accounts."""
    dry_run = "--dry-run" in sys.argv
    from openclaw_mail.tidy import format_report, run_all, save_report

    print("Starting email tidy...")
    reports = run_all(dry_run=dry_run)
    report_path = save_report(reports)
    print(format_report(reports))
    print(f"\nReport saved to {report_path}")


def digest():
    """Generate and save the daily email digest."""
    from openclaw_mail.digest import generate_digest, save_digest

    print("Generating digest...")
    path = save_digest()
    from openclaw_mail.digest import generate_digest

    print(generate_digest())
    print(f"\nDigest saved to {path}")



if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m openclaw_mail.cli <tidy|digest> [--dry-run]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "tidy":
        tidy()
    elif cmd == "digest":
        digest()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
