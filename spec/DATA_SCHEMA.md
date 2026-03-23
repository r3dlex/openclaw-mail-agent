# Data Schema — Openclaw Mail Agent

> Structures used in tidy reports, IAMQ messages, and saved artifacts.

## Tidy Report — `process_account()` Return

Each account produces one report dict. `run_all()` returns `list[dict]`.

```python
{
    "account":         str,   # Human-readable name ("Work Account")
    "account_id":      str,   # Canonical ID ("work_main")
    "nickname":        str,   # Short alias ("work")
    "total_processed": int,   # Emails processed from INBOX
    "auto_filed":      int,   # Emails moved by steps 1-3
    "review_count":    int,   # Emails sent to Review (step 4)
    "details":         list,  # Per-email detail entries (see below)
    "review_emails":   list,  # Subset of details where step == "review"
}
```

## Detail Entry

One entry per email processed. Appears in `report["details"]` and
`report["review_emails"]`.

```python
{
    "subject":    str,    # Capped at 80 chars
    "sender":     str,    # Capped at 50 chars
    "folder":     str,    # Target folder (e.g. "Finance", "Review")
    "step":       str,    # Which pipeline step matched: "address", "keyword", "ai", "review"
    "confidence": float,  # 0.0–1.0 (always 1.0 for address rules, configurable for others)
    "reason":     str,    # Human-readable explanation of the match

    # Optional — present only when PR detected
    "pr_detected": bool,          # True if PR patterns matched
    "pr_numbers":  list[str],     # Extracted PR numbers (e.g. ["41803"])
}
```

## Saved Report Files

`save_report()` writes four files to `reports/`:

| File | Format | Content |
|------|--------|---------|
| `last_tidy_report.md` | Markdown | Full report with tables (overwritten) |
| `tidy_YYYYMMDD_HHMMSS.md` | Markdown | Timestamped archive copy |
| `last_tidy_summary.txt` | Plain text | Short notification summary (broadcast via IAMQ) |
| `last_tidy_data.json` | JSON | Machine-readable (schema below) |

## JSON Report — `last_tidy_data.json`

```python
{
    "timestamp":        str,   # ISO 8601
    "total_processed":  int,
    "total_auto_filed": int,
    "total_review":     int,
    "accounts": [
        {
            "name":          str,
            "nickname":      str,
            "processed":     int,
            "auto_filed":    int,
            "review_count":  int,
            "review_emails": list,   # Detail entries (see above)
            "details":       list,   # All detail entries
        }
    ]
}
```

## IAMQ Message Envelope

All inter-agent messages conform to this structure (built by `_build_message()`):

```python
{
    "id":        str,   # UUID
    "from":      str,   # "mail_agent"
    "to":        str,   # Recipient agent ID or "broadcast"
    "priority":  str,   # "LOW", "NORMAL", "HIGH"
    "type":      str,   # "info", "request", "response", "error"
    "subject":   str,   # Capped at 80 chars
    "body":      str,   # Content (truncated to 5000 chars for reports)
    "replyTo":   str | None,  # Original message ID when replying
    "createdAt": str,   # ISO 8601 UTC
    "expiresAt": str | None,
    "status":    str,   # "unread", "read", "acted"
}
```

## Pipeline Step Constants

| Step name | Source | Confidence |
|-----------|--------|------------|
| `address` | `config/filters/<account>.yaml` → `address_rules` | Always `1.0` |
| `keyword` | `config/filters/<account>.yaml` → `keyword_rules` | Per-rule, threshold `>= 0.8` |
| `ai` | `config/filters/<account>.yaml` → `folder_definitions` | Score `>= ai_score_threshold` (default `0.8`) |
| `review` | Fallback | `0.0` |

## Further Reading

- `spec/ARCHITECTURE.md` — pipeline design, per-account config
- `spec/COMMUNICATION.md` — how reports are sent via IAMQ
- `spec/SAFETY.md` — PII truncation rules applied to these structures
- `openclaw_mail/tidy.py` — report generation implementation

---

*Owner: openclaw-mail-agent team*
