"""Main email tidy engine — runs the 4-step filtering pipeline across accounts.

Generates a full report of all mailboxes and emails filtered, including:
  - Content snippet and title for each email
  - Which step classified it (address/keyword/ai/review)
  - A list of emails requiring manual review
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from openclaw_mail.config import REPORT_DIR, get_active_accounts, load_filter_config
from openclaw_mail.filters.pipeline import Email, FilterConfig, FilterPipeline, FilterResult
from openclaw_mail.utils.himalaya import create_folder, davmail_timeout, get_envelopes_with_retry, move_email
from openclaw_mail.utils.logging import get_logger

log = get_logger("tidy", "tidy.log")


def process_account(account: dict, dry_run: bool = False) -> dict:
    """Process a single account through the filtering pipeline.

    Returns a report dict with keys: account, moved, details, review_emails.
    """
    account_id = account["id"]
    himalaya_name = account.get("himalaya_name", account_id)
    is_davmail = account.get("provider") == "davmail"

    # Load per-account filter config (falls back to _default.yaml)
    filter_data = load_filter_config(account_id)
    if not filter_data:
        from openclaw_mail.config import CONFIG_DIR
        default_file = CONFIG_DIR / "filters" / "_default.yaml"
        if default_file.exists():
            import yaml
            with open(default_file) as f:
                filter_data = yaml.safe_load(f) or {}

    config = FilterConfig.from_yaml(filter_data)
    pipeline = FilterPipeline(config)

    nickname = account.get("nickname", account_id)
    log.info(f"Processing {account['name']} [{nickname}] ({himalaya_name})...")

    limit = 5 if is_davmail else 50
    envelopes = get_envelopes_with_retry(himalaya_name, "INBOX", limit=limit, is_davmail=is_davmail)

    report = {
        "account": account["name"],
        "account_id": account_id,
        "nickname": nickname,
        "total_processed": 0,
        "auto_filed": 0,
        "review_count": 0,
        "details": [],
        "review_emails": [],
    }

    if not envelopes:
        log.info(f"  {account['name']}: No emails to process")
        return report

    for env in envelopes:
        subject = env.get("subject", "")
        sender_data = env.get("from", {})
        sender = sender_data.get("addr", "") if isinstance(sender_data, dict) else str(sender_data)
        sender_name = sender_data.get("name", "") if isinstance(sender_data, dict) else ""
        msg_id = env.get("id", "")

        if not msg_id:
            continue

        email = Email(
            id=msg_id,
            subject=subject,
            sender=sender,
            sender_name=sender_name,
            snippet=subject[:200],
        )

        result: FilterResult = pipeline.classify(email)
        report["total_processed"] += 1

        detail = {
            "subject": subject[:80],
            "sender": sender[:50],
            "folder": result.folder,
            "step": result.step,
            "confidence": result.confidence,
            "reason": result.reason,
        }

        if result.step == "review":
            report["review_count"] += 1
            report["review_emails"].append(detail)
        else:
            report["auto_filed"] += 1

        report["details"].append(detail)

        if not dry_run:
            # DavMail accounts need higher timeouts (5-90s per operation)
            folder_timeout = davmail_timeout(20) if is_davmail else 20
            move_timeout = davmail_timeout(30) if is_davmail else 30
            create_folder(himalaya_name, result.folder, timeout=folder_timeout)
            move_email(himalaya_name, msg_id, result.folder, timeout=move_timeout)
            log.info(f"  [{result.step}] {subject[:50]}... -> {result.folder}")

    return report


def run_all(dry_run: bool = False) -> list[dict]:
    """Run tidy across all active accounts."""
    accounts = get_active_accounts()
    reports = []
    for acc in accounts:
        report = process_account(acc, dry_run=dry_run)
        reports.append(report)
    return reports


def format_report(reports: list[dict]) -> str:
    """Generate a full markdown report of the tidy run."""
    now = datetime.now()
    lines = [
        f"# Email Tidy Report — {now.strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Summary",
        "",
    ]

    total_auto = sum(r["auto_filed"] for r in reports)
    total_review = sum(r["review_count"] for r in reports)
    total_processed = sum(r["total_processed"] for r in reports)

    lines.append(f"- **Total processed:** {total_processed}")
    lines.append(f"- **Auto-filed:** {total_auto}")
    lines.append(f"- **Needs review:** {total_review}")
    lines.append("")

    # Per-account breakdown
    lines.append("## Per Account")
    lines.append("")

    for r in reports:
        if r["total_processed"] == 0:
            continue
        nick = r.get('nickname', r.get('account_id', ''))
        lines.append(f"### {r['account']} [{nick}]")
        lines.append(f"- Processed: {r['total_processed']} | Auto: {r['auto_filed']} | Review: {r['review_count']}")
        lines.append("")

        # Auto-filed details
        auto_details = [d for d in r["details"] if d["step"] != "review"]
        if auto_details:
            lines.append("**Auto-filed:**")
            lines.append("| Subject | Sender | Folder | Step | Confidence |")
            lines.append("|---------|--------|--------|------|------------|")
            for d in auto_details:
                lines.append(
                    f"| {d['subject'][:50]} | {d['sender'][:30]} | {d['folder']} | {d['step']} | {d['confidence']:.2f} |"
                )
            lines.append("")

    # Review section — always shown
    all_review = []
    for r in reports:
        for e in r["review_emails"]:
            all_review.append({**e, "account": r["account"]})

    lines.append("## Emails Requiring Review")
    lines.append("")
    if all_review:
        lines.append("| Account | Subject | Sender | Reason |")
        lines.append("|---------|---------|--------|--------|")
        for e in all_review:
            lines.append(f"| {e['account']} | {e['subject'][:50]} | {e['sender'][:30]} | {e['reason']} |")
    else:
        lines.append("*No emails require review.*")
    lines.append("")

    lines.append("---")
    lines.append("*Generated by openclaw-mail-agent*")
    return "\n".join(lines)


def save_report(reports: list[dict]) -> Path:
    """Save the tidy report to the reports directory."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_text = format_report(reports)

    # Save as latest + timestamped
    latest = REPORT_DIR / "last_tidy_report.md"
    latest.write_text(report_text)

    timestamped = REPORT_DIR / f"tidy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    timestamped.write_text(report_text)

    log.info(f"Report saved to {latest}")
    return latest
