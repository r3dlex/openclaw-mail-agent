# CLAUDE.md — Developer Agent Guide

> This file is for **you** (Claude Code and other developer agents) working on
> this repository. For the **openclaw agent** operating the mail system, see
> `AGENTS.md`.

## Quick Start

```bash
# Install dependencies (poetry required)
poetry install

# Run tests
poetry run pytest -v

# Run tidy (dry run)
poetry run mail-tidy --dry-run

# Run via Docker (zero-install)
docker compose up mail-tidy
docker compose run test
```

## Repository Structure

```
├── CLAUDE.md              ← You are here (developer guide)
├── AGENTS.md              ← Openclaw agent operating guide
├── SOUL.md                ← Agent identity, principles & IAMQ swarm awareness
├── IDENTITY.md            ← Agent metadata & learnings (agent-maintained)
├── USER.md                ← User context (agent-maintained)
├── HEARTBEAT.md           ← Periodic task checklist
├── TOOLS.md               ← Environment-specific notes
│
├── openclaw_mail/         ← Python package (root-level)
│   ├── cli.py             ← CLI entrypoints (tidy, digest, validate)
│   ├── config.py          ← Centralized config loader
│   ├── tidy.py            ← Main tidy engine + reporting
│   ├── digest.py          ← Daily digest generator
│   ├── filters/           ← 4-step filtering pipeline
│   │   └── pipeline.py    ← FilterPipeline, FilterResult, Email
│   ├── pipelines/         ← Generic pipeline runner framework
│   │   ├── runner.py      ← Pipeline, PipelineStep, StepResult
│   │   └── validation.py  ← CI validation (ADR, secrets, gitignore)
│   ├── utils/             ← Shared utilities
│   │   ├── himalaya.py    ← Himalaya CLI wrapper
│   │   └── logging.py     ← Centralized logging (stdout + file)
│   ├── accounts/          ← Account management (stub)
│   └── calendar/          ← Calendar sync (stub)
│
├── config/                ← All configuration (YAML)
│   ├── accounts.yaml      ← Email accounts (gitignored)
│   ├── accounts.yaml.example ← Template with dummy data
│   ├── filters/           ← Per-account filter rules
│   │   ├── _default.yaml  ← Default 4-step pipeline (committed)
│   │   ├── *.yaml.example ← Per-account examples (committed)
│   │   └── *.yaml         ← Real overrides (gitignored)
│   └── folder_mappings/   ← Per-account folder docs (gitignored)
│       └── _example.md    ← Template (committed)
│
├── tests/                 ← Unit & integration tests (83 tests)
├── spec/                  ← Architecture & design docs
│   ├── ARCHITECTURE.md    ← System design & pipeline docs
│   ├── PIPELINES.md       ← Pipeline runner, ADRs, CI integration
│   ├── TESTING.md         ← Testing strategy
│   ├── TROUBLESHOOTING.md ← Common issues & fixes
│   ├── LEARNINGS.md       ← Agent operational learnings
│   └── adrs/              ← Architecture Decision Records
│       ├── ARCH-NNN-*.md      ← Decision documents
│       └── ARCH-NNN-*.check.py ← Machine-executable validation
│
├── .github/workflows/     ← GitHub Actions CI
│   └── ci.yml             ← Lint + test + validate
├── cron/                  ← Cron schedule templates
│   └── crontab.example    ← Example crontab
├── Dockerfile             ← Container build
├── docker-compose.yaml    ← Zero-install orchestration
└── pyproject.toml         ← Package & dependency config
```

## Key Design Decisions

→ See `spec/ARCHITECTURE.md` for the full picture.

1. **4-step filtering pipeline**: Address → Keywords → AI scoring → Review fallback.
   Each step only runs if the previous didn't match. Configured per-account in
   `config/filters/<account_id>.yaml`.

2. **No hardcoded credentials**: Everything from `.env`. Both email addresses
   (`user_env`) and passwords (`password_env`) are resolved at runtime.
   Even calendar credentials are env-referenced.

3. **Zero-install via Docker**: `docker compose up mail-tidy` works with just
   Docker installed. No Python, no himalaya, nothing else needed.

4. **Progressive disclosure**: This file links to `spec/` for details.
   `AGENTS.md` links to `spec/` for the openclaw agent's reference.

5. **Sensitive data separation**: Real account configs (`accounts.yaml`,
   per-account filters, folder mappings) are gitignored. Only `_default.yaml`,
   `.example` files, and templates are committed.

6. **Generic pipeline runner**: `openclaw_mail/pipelines/` provides reusable
   `Pipeline`/`PipelineStep`/`StepResult` abstractions. Used for both email
   filtering (`first_match`) and CI validation (`sequential`).
   → `spec/PIPELINES.md`

7. **ADR system**: Architecture Decision Records in `spec/adrs/` with
   `.md` decision docs and `.check.py` machine-executable validation.
   CI runs all checks automatically via `poetry run validate`.
   → `spec/adrs/`

8. **GitHub Actions CI**: Lint + test + validate on every push/PR.
   → `.github/workflows/ci.yml`

9. **Centralized logging**: All modules log to both stdout and
   `logs/openclaw.log` (shared) plus optional per-module files. The `logs/`
   directory is gitignored with a `.gitkeep` so it's always present.

## Working with the Code

### Adding a new email account

1. Add `USER_<X>` and `PASS_<X>` to `.env` (and `.env.example` for the template)
2. Add entry to `config/accounts.yaml` with `user_env`, `password_env`, `nickname`
   (see `accounts.yaml.example`)
3. Configure himalaya for the account
4. Optionally create `config/filters/<id>.yaml` (falls back to `_default.yaml`)
5. Optionally create `config/folder_mappings/<id>.md` for documentation

Each account has three identifiers: `id`, `nickname`, and `himalaya_name`.
The `find_account()` function resolves all three.

### Modifying filter rules

Edit the YAML in `config/filters/`. Each file supports:
- `address_rules` — sender-based routing (Step 1)
- `keyword_rules` — regex patterns with confidence (Step 2)
- `folder_definitions` — descriptions for AI scoring (Step 3)
- `ai_score_threshold` — minimum score for Step 3 (default: 0.8)
- `review_folder` — where unclassified emails go (default: "Review")

### Running tests

```bash
poetry run pytest -v              # all tests
poetry run pytest tests/test_pipeline.py  # pipeline only
docker compose run test           # via container
```

## Conventions

- **No local paths in code** — use `config.py` constants (`PROJECT_ROOT`, `LOG_DIR`, etc.)
- **No secrets in code** — always use `os.getenv()` or `config.get_env()`
- **Logs go to `logs/`** — never print to stdout in library code (use `get_logger`)
- **Reports go to `reports/`** — generated at runtime, gitignored
- **Example configs** — when adding new config files, always provide a `.example` version
- **Legacy code** lives in `artifacts/` — being migrated to `openclaw_mail/`

## Sensitive Data

**NEVER commit:**
- `.env` files (real credentials)
- `config/accounts.yaml` (real email addresses)
- `config/filters/*.yaml` (may contain real names — only `_default.yaml` and `.example` files)
- `config/folder_mappings/*.md` (account-specific — only `_example.md`)
- `*.json` files in `config/` (OAuth tokens, client secrets)
- `reports/` or `logs/` content
- Hardcoded email addresses, passwords, or PATs

The `.gitignore` is configured to prevent this. Run `git diff --cached` before
committing to verify.
