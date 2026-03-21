"""CLI entrypoints for mail operations."""

from __future__ import annotations

import sys

from openclaw_mail.utils.logging import get_logger

log = get_logger("cli")


def _mq_startup():
    """Register with the inter-agent MQ and check for incoming messages.

    Called at the start of every CLI command. Non-blocking — failures
    are logged but don't prevent the command from running.
    """
    try:
        from openclaw_mail.utils.mq import process_inbox, register

        registered = register()
        if registered:
            log.info("MQ: registered with inter-agent message queue")

        # Check for messages from other agents
        messages = process_inbox()
        if messages:
            print(f"[MQ] {len(messages)} message(s) from other agents:")
            for msg in messages:
                print(f"  [{msg.get('type', '?')}] {msg.get('from', '?')}: {msg.get('subject', '?')}")
            print()
    except Exception as e:
        log.debug(f"MQ startup skipped: {e}")


def tidy():
    """Run the email tidy pipeline across all active accounts.

    Outputs:
      - Full report to console (stdout)
      - Notification summary to console (for quick glance)
      - Full report saved to reports/last_tidy_report.md
      - Summary saved to reports/last_tidy_summary.txt
      - JSON data saved to reports/last_tidy_data.json
      - All actions logged to logs/openclaw.log + logs/tidy.log
      - Summary broadcast via inter-agent MQ
    """
    _mq_startup()

    dry_run = "--dry-run" in sys.argv

    # Parse --account filter if provided
    account_filter = None
    for i, arg in enumerate(sys.argv):
        if arg == "--account" and i + 1 < len(sys.argv):
            account_filter = sys.argv[i + 1]
            break

    from openclaw_mail.tidy import format_report, format_summary, run_all, save_report

    mode = "DRY RUN" if dry_run else "LIVE"
    log.info(f"Starting email tidy ({mode})...")
    print(f"Starting email tidy ({mode})...\n")

    reports = run_all(dry_run=dry_run, account_filter=account_filter)
    report_path = save_report(reports)

    # Print the notification summary first (quick glance)
    summary = format_summary(reports)
    print("=" * 60)
    print(summary)
    print("=" * 60)

    # Print full report
    full_report = format_report(reports)
    print()
    print(full_report)
    print(f"\nReport saved to {report_path}")

    # Log the summary for the Openclaw agent
    log.info(f"Tidy complete: {summary}")

    total_review = sum(r["review_count"] for r in reports)
    if total_review > 0:
        log.warning(f"{total_review} emails need manual review — check reports/last_tidy_summary.txt")

    # Distribute report via inter-agent MQ
    try:
        from openclaw_mail.utils.mq import send_tidy_report
        send_tidy_report(summary, full_report)
    except Exception as e:
        log.debug(f"MQ report distribution skipped: {e}")


def digest():
    """Generate and save the daily email digest."""
    _mq_startup()

    from openclaw_mail.digest import generate_digest, save_digest

    log.info("Generating digest...")
    print("Generating digest...")
    path = save_digest()

    digest_text = generate_digest()
    print(digest_text)
    print(f"\nDigest saved to {path}")
    log.info(f"Digest saved to {path}")


def validate():
    """Run the validation pipeline (ADR compliance, sensitive data scan).

    Used by CI (GitHub Actions) and local pre-push checks.
    Exit code 0 = all checks passed, 1 = failures found.
    """
    from openclaw_mail.pipelines.validation import build_validation_pipeline

    print("Running validation pipeline...\n")
    pipeline = build_validation_pipeline()
    result = pipeline.run()

    # Print per-step results
    for step in result.steps:
        icon = "✓" if step.matched else ("⊘" if step.skipped else "✗")
        print(f"  {icon} {step.step_name}: {step.reason}")
        if step.output and not step.matched:
            if isinstance(step.output, list):
                for item in step.output[:10]:
                    if isinstance(item, dict):
                        status = "✓" if item.get("passed") else "✗"
                        print(f"      {status} {item.get('adr', '?')}: {item.get('message', '')}")
                    else:
                        print(f"      • {item}")
                if len(step.output) > 10:
                    print(f"      ... and {len(step.output) - 10} more")

    print(f"\n{result.summary}")

    if not result.all_passed:
        print("\n❌ Validation FAILED")
        sys.exit(1)
    else:
        print("\n✅ All checks passed")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m openclaw_mail.cli <tidy|digest|validate> [--dry-run]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "tidy":
        tidy()
    elif cmd == "digest":
        digest()
    elif cmd == "validate":
        validate()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
