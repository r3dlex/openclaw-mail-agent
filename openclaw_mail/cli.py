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

    print(generate_digest())
    print(f"\nDigest saved to {path}")


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
