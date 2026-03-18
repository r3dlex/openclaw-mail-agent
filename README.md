# Openclaw Mail Agent

Intelligent multi-account email management agent with AI-powered categorization
and digest reporting.

## Features

- **Multi-account support** — manage multiple IMAP accounts (Gmail, Exchange via DavMail)
- **4-step filtering pipeline** — address rules → keywords → AI scoring → review fallback
- **Per-account configuration** — custom rules and folder structures per mailbox
- **Digest reports** — daily summaries of inbox state across all accounts
- **Calendar sync** — CalDAV (Exchange) ↔ Google Calendar *(planned)*
- **Zero-install** — run everything via Docker, no local setup needed

## Quick Start

### Docker (recommended — zero install)

```bash
# 1. Configure
cp .env.example .env                                    # add your credentials
cp config/accounts.yaml.example config/accounts.yaml    # add your accounts

# 2. Optionally add per-account filter rules
cp config/filters/work_main.yaml.example config/filters/work_main.yaml

# 3. Run email tidy
docker compose up mail-tidy

# 4. Generate digest
docker compose up mail-digest

# 5. Run scheduled crons (tidy every 30min, digest at 8am/5pm)
docker compose up cron
```

### Local Development

```bash
# Install dependencies (requires Python 3.11+ and Poetry)
poetry install

# Run tidy (dry run — reads but doesn't move emails)
poetry run mail-tidy --dry-run

# Run tests
poetry run pytest -v

# Generate digest
poetry run mail-digest
```

## Email Filtering Pipeline

Each email passes through 4 steps. **First match wins** — the email stops at the
step that classifies it:

| Step | Method | Description |
|------|--------|-------------|
| 1 | **Address rules** | Emails from specific senders go to specific folders |
| 2 | **Keyword rules** | Regex patterns on subject+sender with confidence scoring |
| 3 | **AI scoring** | Agent scores email against folder descriptions (threshold: 0.8) |
| 4 | **Review fallback** | Unmatched emails go to `Review` for manual triage |

→ Full details: `spec/ARCHITECTURE.md`

## Configuration

```
.env.example                  # Environment template (credentials)
config/
├── accounts.yaml.example     # Account definitions template
├── accounts.yaml             # Your accounts (gitignored)
├── filters/
│   ├── _default.yaml         # Default pipeline (committed)
│   ├── *.yaml.example        # Per-account examples (committed)
│   └── <account_id>.yaml     # Your overrides (gitignored)
└── folder_mappings/
    ├── _example.md            # Folder structure template (committed)
    └── <account_id>.md        # Your folder docs (gitignored)
```

Credentials live in `.env` (never committed). See `.env.example` for the template.

## Project Structure

```
openclaw_mail/              # Python package (root-level)
├── cli.py                  # CLI entrypoints (mail-tidy, mail-digest)
├── config.py               # Config loader (.env + YAML)
├── tidy.py                 # Tidy engine + report generation
├── digest.py               # Digest generator
├── filters/pipeline.py     # 4-step filtering pipeline
└── utils/                  # Himalaya wrapper, logging

config/                     # All configuration (YAML, gitignored secrets)
spec/                      # Architecture & design docs
tests/                      # Unit & integration tests
cron/                       # Cron schedule templates
```

## Documentation

| File | Audience | Purpose |
|------|----------|---------|
| `README.md` | Everyone | Project overview & quick start |
| `CLAUDE.md` | Developer agents | How to work on this codebase |
| `AGENTS.md` | Openclaw agent | Operating procedures for the mail agent |
| `spec/ARCHITECTURE.md` | Deep dive | System design, pipeline, infrastructure |
| `spec/TESTING.md` | Contributors | Testing strategy & running tests |
| `spec/TROUBLESHOOTING.md` | Operations | Common issues & fixes |
| `spec/LEARNINGS.md` | Openclaw agent | Operational learnings & patterns |

## Requirements

- **Docker** (for zero-install) or **Python 3.11+** with Poetry
- **Himalaya CLI** — email client abstraction (bundled in Docker image)
- **DavMail** — Exchange/Office365 IMAP bridge (only for Exchange accounts)

## License

MIT
