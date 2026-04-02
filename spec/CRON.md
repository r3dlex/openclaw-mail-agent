# Cron Schedules — openclaw-mail-agent

## Overview

The Mail agent runs two morning jobs: inbox tidying at 06:30 and digest
generation at 07:00, so the user starts the day with a clean inbox and a
summary ready. All crons are registered with IAMQ on startup.

## Schedules

### tidy_inbox
- **Expression**: `30 6 * * *` (06:30 UTC daily)
- **Purpose**: Run the 4-step filter pipeline across all configured accounts:
  1. Mark newsletters and notifications as read / move to folders
  2. Apply per-account routing rules from `config/filters/*.yaml`
  3. Flag emails matching priority senders
  4. Soft-delete obvious spam (move to Trash; never permanent-delete)
  Uses Himalaya CLI for all IMAP operations. DavMail must be running for
  Exchange accounts.
- **Trigger**: Delivered via IAMQ message `cron::tidy_inbox`
- **Handler**: `openclaw_mail.tidy.run_tidy_pipeline()`
- **Expected duration**: 1–5 minutes depending on inbox volume
- **On failure**: Log to `logs/tidy.log`; send IAMQ warning to `agent_claude`;
  inbox remains untouched (tidy is idempotent — safe to rerun)

### daily_digest
- **Expression**: `0 7 * * *` (07:00 UTC daily, 30 min after tidy completes)
- **Purpose**: Read the now-tidied inbox across all accounts, compile a markdown
  digest: unread count, flagged messages, action items, calendar events for
  today. Deliver digest to user via Telegram.
- **Trigger**: Delivered via IAMQ message `cron::daily_digest`
- **Handler**: `openclaw_mail.digest.generate_digest()`
- **Expected duration**: 30–90 seconds
- **On failure**: Log error; skip delivery; user can request manually via
  `mail.digest` IAMQ message

## Cron Registration

Registered with IAMQ on startup via `POST /crons`:

```json
[
  {"subject": "cron::tidy_inbox",   "expression": "30 6 * * *"},
  {"subject": "cron::daily_digest", "expression": "0 7 * * *"}
]
```

## Ordering Guarantee

The 30-minute gap between `tidy_inbox` (06:30) and `daily_digest` (07:00)
ensures the digest reflects the tidied state. If tidy runs over 30 minutes
(unusual), the digest may show a slightly stale inbox — this is acceptable.

## Manual Trigger

```bash
# Manual tidy
docker compose run --rm mail tidy

# Manual digest
docker compose run --rm mail digest

# Via IAMQ
curl -X POST http://127.0.0.1:18790/send \
  -H "Content-Type: application/json" \
  -d '{"from":"developer","to":"mail_agent","type":"request","priority":"HIGH","subject":"mail.tidy","body":{}}'
```

---

**Related:** `spec/API.md`, `spec/COMMUNICATION.md`, `spec/ARCHITECTURE.md`
