"""Main email tidy engine — runs the 4-step filtering pipeline across accounts.

Generates a full report of all mailboxes and emails filtered, including:
  - Content snippet and title for each email
  - Which step classified it (address/keyword/ai/review)
  - A list of emails requiring manual review

Output destinations:
  - Console (stdout) — human-readable summary
  - reports/last_tidy_report.md — full markdown report (latest)
  - reports/tidy_YYYYMMDD_HHMMSS.md — timestamped archive
  - reports/last_tidy_summary.txt — short notification-ready summary
  - logs/openclaw.log + logs/tidy.log — structured logs
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from openclaw_mail.config import REPORT_DIR, get_active_accounts, load_filter_config
from openclaw_mail.filters.pipeline import Email, FilterConfig, FilterPipeline, FilterResult
from openclaw_mail.utils.himalaya import create_folder, davmail_timeout, get_envelopes_with_retry, move_email
from openclaw_mail.utils.logging import get_logger

log = get_logger("tidy", "tidy.log")


def process_account(account: dict, dry_run: bool = False) -> dict:
    """Process a single account through the filtering pipeline.

    Fetches and processes emails in small batches to handle large inboxes.
    Returns a report dict with keys: account, moved, details, review_emails.
    """
    account_id = account["id"]
    himalaya_name = account.get("himalaya_name", account_id)
    provider = account.get("provider", "")
    is_davmail = provider == "davmail"

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
    log.info(f"  Provider: {provider}, is_davmail: {is_davmail}")

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

    # Process emails in small batches - fetch and process each batch immediately
    batch_size = 5
    total_fetched = 0
    
    while True:
        # Fetch a batch
        envelopes = get_envelopes_with_retry(
            himalaya_name, "INBOX", 
            limit=batch_size, 
            is_davmail=is_davmail,
            max_retries=2,
        )
        
        if not envelopes:
            # No more emails - inbox is empty
            break
            
        total_fetched += len(envelopes)
        log.info(f"  Batch: fetched {len(envelopes)} emails, processing...")
        
        # Process each email in this batch
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
                log.info(f"    [{result.step}] {subject[:50]}... -> {result.folder}")
        
        # If we got fewer than batch_size, we've reached the end of inbox
        if len(envelopes) < batch_size:
            break

    log.info(f"  Done: processed {report['total_processed']} emails, {report['auto_filed']} auto-filed, {report['review_count']} need review")
    
    if report["total_processed"] == 0:
        log.info(f"  {account['name']}: No emails to process")

    return report


def run_all(dry_run: bool = False, account_filter: str | None = None) -> list[dict]:
    """Run tidy across all active accounts.
    
    Args:
        dry_run: If True, don't actually move emails
        account_filter: Optional account ID (matches id, nickname, or himalaya_name)
    """
    accounts = get_active_accounts()
    
    # Filter to specific account if requested
    if account_filter:
        accounts = [a for a in accounts 
                    if a["id"] == account_filter 
                    or a.get("nickname") == account_filter
                    or a.get("himalaya_name") == account_filter]
    
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


def format_summary(reports: list[dict]) -> str:
    """Generate a short notification-ready summary.

    This is the text the Openclaw agent sends to Telegram/Instagram.
    Concise, emoji-marked, fits in a notification bubble.
    """
    now = datetime.now()
    total_processed = sum(r["total_processed"] for r in reports)
    total_auto = sum(r["auto_filed"] for r in reports)
    total_review = sum(r["review_count"] for r in reports)
    active_accounts = [r for r in reports if r["total_processed"] > 0]

    if total_processed == 0:
        return f"Tidy {now.strftime('%H:%M')} — All inboxes clean. Nothing to process."

    lines = [f"Tidy {now.strftime('%H:%M')} — {total_processed} emails processed"]

    # Per-account one-liner
    for r in active_accounts:
        nick = r.get("nickname", r.get("account_id", ""))
        lines.append(f"  {nick}: {r['auto_filed']} filed, {r['review_count']} review")

    # Bottom line
    if total_review > 0:
        lines.append(f"=> {total_auto} auto-filed, {total_review} need review")
        # List review emails
        for r in reports:
            for e in r["review_emails"]:
                subj = e["subject"][:40]
                sender = e["sender"].split("@")[0]
                lines.append(f"  ? {sender}: {subj}")
    else:
        lines.append(f"=> {total_auto} auto-filed, 0 review")

    return "\n".join(lines)


def save_report(reports: list[dict]) -> Path:
    """Save the tidy report, summary, and JSON to the reports directory.

    Files written:
      - last_tidy_report.md  — full markdown report (overwritten each run)
      - last_tidy_summary.txt — short notification summary (overwritten)
      - last_tidy_data.json — machine-readable report data (overwritten)
      - tidy_YYYYMMDD_HHMMSS.md — timestamped archive copy
    """
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()

    # Full markdown report
    report_text = format_report(reports)
    latest = REPORT_DIR / "last_tidy_report.md"
    latest.write_text(report_text)

    timestamped = REPORT_DIR / f"tidy_{now.strftime('%Y%m%d_%H%M%S')}.md"
    timestamped.write_text(report_text)

    # Short notification summary (for Telegram/Instagram/push)
    summary_text = format_summary(reports)
    summary_path = REPORT_DIR / "last_tidy_summary.txt"
    summary_path.write_text(summary_text)

    # Machine-readable JSON (for the Openclaw agent to parse)
    json_data = {
        "timestamp": now.isoformat(),
        "total_processed": sum(r["total_processed"] for r in reports),
        "total_auto_filed": sum(r["auto_filed"] for r in reports),
        "total_review": sum(r["review_count"] for r in reports),
        "accounts": [
            {
                "name": r["account"],
                "nickname": r.get("nickname", ""),
                "processed": r["total_processed"],
                "auto_filed": r["auto_filed"],
                "review_count": r["review_count"],
                "review_emails": r["review_emails"],
                "details": r["details"],
            }
            for r in reports
        ],
    }
    json_path = REPORT_DIR / "last_tidy_data.json"
    json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False))

    log.info(f"Report saved: {latest}")
    log.info(f"Summary saved: {summary_path}")
    log.info(f"JSON saved: {json_path}")

    return latest
