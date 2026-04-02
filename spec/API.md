# API — openclaw-mail-agent

## Overview

The Mail agent does not expose an HTTP server. Cross-agent communication uses
IAMQ. The agent also provides a CLI for operator use. Email is accessed
exclusively through the Himalaya CLI (which interfaces with DavMail for
Exchange accounts).

---

## IAMQ Message Interface

### Incoming messages accepted by `mail_agent`

| Subject | Purpose | Body fields |
|---------|---------|-------------|
| `mail.tidy` | Run the inbox tidy pipeline for one or all accounts | `account?: string` |
| `mail.digest` | Request the daily email digest | `account?: string`, `date?: "YYYY-MM-DD"` |
| `mail.summary` | Return a brief inbox summary (unread count, flagged) | `account?: string` |
| `mail.search` | Search emails by query | `query: string`, `account?: string`, `limit?: number` |
| `mail.calendar` | Fetch upcoming calendar events | `days?: number` |
| `status` | Return agent health and last tidy/digest timestamps | — |

#### Example: request a tidy run

```json
{
  "from": "agent_claude",
  "to": "mail_agent",
  "type": "request",
  "priority": "NORMAL",
  "subject": "mail.tidy",
  "body": {}
}
```

#### Example response

```json
{
  "from": "mail_agent",
  "to": "agent_claude",
  "type": "response",
  "priority": "NORMAL",
  "subject": "mail.tidy.result",
  "body": {
    "accounts_processed": 2,
    "emails_moved": 14,
    "emails_deleted": 3,
    "emails_flagged": 1,
    "duration_seconds": 28
  }
}
```

#### Example: request today's digest

```json
{
  "from": "agent_claude",
  "to": "mail_agent",
  "type": "request",
  "subject": "mail.digest",
  "body": {"date": "2026-04-02"}
}
```

---

## CLI Interface

```bash
# Run inbox tidy
poetry run python -m openclaw_mail.cli tidy

# Generate digest
poetry run python -m openclaw_mail.cli digest

# Validate configuration
poetry run python -m openclaw_mail.cli validate

# Or via Docker
docker compose run --rm mail tidy
docker compose run --rm mail digest
```

---

## Email Access (Himalaya / DavMail)

All email I/O goes through the Himalaya CLI wrapper in
`openclaw_mail/utils/himalaya.py`. The agent never touches IMAP/SMTP directly.

- Himalaya manages multiple accounts defined in `config/accounts.yaml`
- DavMail provides an Exchange-to-IMAP bridge for corporate accounts
- Filter rules per account live in `config/filters/*.yaml`

---

**Related:** `spec/COMMUNICATION.md`, `spec/ARCHITECTURE.md`, `spec/DATA_SCHEMA.md`
