# Architecture — Openclaw Mail Agent

## System Overview

```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐
│  Email       │     │  Himalaya    │     │  Filter        │
│  Accounts    │────▶│  CLI         │────▶│  Pipeline      │
│  (IMAP)      │     │  (envelope)  │     │  (4-step)      │
└─────────────┘     └──────────────┘     └────────┬───────┘
                                                   │
                    ┌──────────────┐     ┌─────────▼───────┐
                    │  Reports     │◀────│  Tidy Engine     │
                    │  (Markdown)  │     │  (orchestrator)  │
                    └──────────────┘     └─────────────────┘
```

## Email Processing Pipeline

### 4-Step Filtering

Every email from INBOX is processed through these steps in order.
**First match wins** — the email stops at the step that classifies it.

#### Step 1: Address Rules
- **What**: Exact sender address matching
- **Config**: `config/filters/<account>.yaml` → `address_rules`
- **Use case**: VIP senders, known automated systems
- **Confidence**: Always 1.0

```yaml
address_rules:
  - sender: "ceo@company.com"
    folder: "Executive"
```

#### Step 2: Keyword Rules
- **What**: Regex patterns matched against `subject + sender`
- **Config**: `config/filters/<account>.yaml` → `keyword_rules`
- **Use case**: Common categories (newsletters, finance, HR)
- **Confidence**: Configurable per rule (only matches ≥ 0.8 accepted)

```yaml
keyword_rules:
  - pattern: "(newsletter|marketing|digest)"
    folder: "Newsletters"
    confidence: 0.95
```

#### Step 3: AI Scoring (Openclaw Agent)
- **What**: Agent scores email against folder descriptions
- **Config**: `config/filters/<account>.yaml` → `folder_definitions`
- **Use case**: Nuanced categorization that rules can't capture
- **Threshold**: Only scores ≥ `ai_score_threshold` (default 0.8) trigger a move

```yaml
folder_definitions:
  Finance: "Banking, invoices, payments, receipts"
  HR: "Human resources, vacation, personnel matters"
```

The agent receives the email subject, sender, and content snippet, then returns
a score (0.0–1.0) for each folder. The highest-scoring folder above threshold wins.

#### Step 4: Review Fallback
- **What**: Unmatched emails go to the `Review` folder
- **Config**: `config/filters/<account>.yaml` → `review_folder`
- **Use case**: Safety net — human reviews what the system couldn't classify

### Per-Account Configuration

Each account can have its own filter configuration in
`config/filters/<account_id>.yaml`. If no account-specific file exists,
the system falls back to `config/filters/_default.yaml`.

Account IDs are defined in `config/accounts.yaml` under the `id` field.

## Account Management

### Account Definition

All accounts are defined in `config/accounts.yaml`. Email addresses and
passwords are stored in `.env` and referenced via `user_env` and `password_env`:

```yaml
accounts:
  - id: "work_main"              # Unique ID (filter/folder_mapping file names)
    nickname: "work"              # Short alias (agent can use this)
    himalaya_name: "Work"         # Name in himalaya CLI config
    name: "Work Account"          # Human-readable display name
    provider: "davmail"           # "davmail" or "gmail"
    user_env: "USER_WORK"         # .env var for email address
    password_env: "PASS_WORK"     # .env var for password/app token
    role: "work"                  # "work", "personal", "system", "gaming"
    active: true                  # Whether to process this account
    calendar:                     # Optional calendar sync
      provider: "caldav"          # "caldav" or "google"
      url_env: "CALDAV_WORK_URL"
      user_env: "USER_WORK"       # Can reuse same env vars
      password_env: "PASS_WORK"
```

### Account Identifiers

Each account can be referenced by any of three names:
- **id** — canonical (`work_main`, `personal_main`)
- **nickname** — short alias (`work`, `personal`, `family-fb`)
- **himalaya_name** — CLI identifier (`Work`, `Personal`)

The `find_account()` function in `config.py` resolves all three.

### Adding a New Account

1. Add `USER_<X>` and `PASS_<X>` to `.env` (and `.env.example`)
2. Add entry to `config/accounts.yaml` (see `accounts.yaml.example`)
3. Configure himalaya for the account
4. Optionally create `config/filters/<id>.yaml` (see `.yaml.example` files)
5. Optionally create `config/folder_mappings/<id>.md` (see `_example.md`)

## Reporting

Every tidy run generates a markdown report with:

1. **Summary**: Total processed, auto-filed, needs review
2. **Per-account breakdown**: Table with subject, sender, folder, step, confidence
3. **Review list**: All emails that couldn't be classified — always shown

Reports are saved to:
- `reports/last_tidy_report.md` (latest, overwritten each run)
- `reports/tidy_YYYYMMDD_HHMMSS.md` (timestamped archive)

## Heartbeat System

The agent can receive periodic heartbeat polls. When a heartbeat arrives:

1. Read `HEARTBEAT.md` for pending tasks
2. Execute any due tasks
3. Reply `HEARTBEAT_OK` if nothing needs attention

Heartbeats are for batched checks (inbox status, calendar upcoming events).
For exact-timing tasks, use cron (see `cron/crontab.example`).

## Infrastructure

### DavMail (Exchange/Office365)
- Bridges Exchange to standard IMAP/SMTP/CalDAV
- Runs locally, configured via environment variables
- Ports: IMAP `$DAVMAIL_IMAP_PORT`, SMTP `$DAVMAIL_SMTP_PORT`, CalDAV `$DAVMAIL_CALDAV_PORT`
- Known for timeouts with large emails — see `specs/TROUBLESHOOTING.md`

### Himalaya CLI
- Rust-based email client abstraction
- Used for all envelope listing, message reading, folder operations
- Account configuration lives in `~/.config/himalaya/config.toml`

### Docker (Zero-Install)
- `docker compose up mail-tidy` — run tidy
- `docker compose up cron` — run scheduled cron jobs
- `docker compose run test` — run tests
- All dependencies bundled in the container

## Directory Layout

```
openclaw_mail/              # Python package (root-level)
├── cli.py                  # CLI entrypoints
├── config.py               # Config loader (.env + YAML)
├── tidy.py                 # Tidy engine + reporting
├── digest.py               # Digest generation
├── filters/
│   └── pipeline.py         # 4-step pipeline implementation
├── utils/
│   ├── himalaya.py         # Himalaya CLI wrapper
│   └── logging.py          # Centralized logging
├── accounts/               # Account management (stub)
└── calendar/               # Calendar sync (stub)

config/                     # Configuration (secrets gitignored)
├── accounts.yaml.example   # Template (committed)
├── accounts.yaml           # Real accounts (gitignored)
├── filters/
│   ├── _default.yaml       # Fallback config (committed)
│   ├── *.yaml.example      # Per-account examples (committed)
│   └── *.yaml              # Real per-account rules (gitignored)
└── folder_mappings/
    ├── _example.md          # Template (committed)
    └── *.md                 # Real folder docs (gitignored)

specs/                      # Design & operations docs
├── ARCHITECTURE.md         # This file
├── TESTING.md              # Testing strategy
├── TROUBLESHOOTING.md      # Common issues
└── LEARNINGS.md            # Agent operational insights

cron/                       # Cron schedule templates
└── crontab.example         # Example crontab
```
