# Testing Strategy

## Running Tests

```bash
# Local (poetry)
poetry run pytest -v

# Docker (zero-install)
docker compose run test

# With coverage
poetry run pytest --cov=openclaw_mail --cov-report=term-missing --cov-fail-under=70

# Run validation pipeline (ADR compliance + sensitive data scan)
poetry run validate

# Run linter
poetry run ruff check openclaw_mail/ tests/
```

## Test Structure

```
tests/
├── conftest.py            # Shared fixtures (sample emails, configs)
├── test_pipeline.py       # Filter pipeline unit tests (20 tests)
├── test_himalaya.py       # Himalaya wrapper tests (28 tests)
├── test_runner.py         # Pipeline runner framework tests (22 tests)
└── test_validation.py     # Validation pipeline tests (13 tests)
```

## What's Tested

### Filter Pipeline (`test_pipeline.py`)

- **Step 1 (Address)**: Sender matching, partial vs exact, case insensitivity
- **Step 2 (Keywords)**: Regex matching, confidence thresholds, best-match selection
- **Step 3 (AI)**: Score threshold enforcement, scorer callback integration
- **Step 4 (Review)**: Fallback behavior when nothing matches
- **Pipeline order**: Verify first-match-wins semantics
- **Config loading**: YAML parsing, default fallback

### Himalaya Wrapper (`test_himalaya.py`)

- **Timeout handling**: DavMail multiplier, minimum timeout floor
- **Retry logic**: Exponential backoff, auth error bypass, exhaustion
- **Move operations**: Single/batch, timeout scaling, failure detection
- **Envelope fetching**: JSON parsing, retry mode, limit enforcement
- **Bulk operations**: Pre-fetched envelopes, error reporting, timeout scaling
- **Folder operations**: Create/list with retry

→ DavMail timeout architecture: `spec/TROUBLESHOOTING.md`

### Pipeline Runner (`test_runner.py`)

- **First-match mode**: Stop at first match, no-match fallthrough, empty pipeline
- **Sequential mode**: Run all steps, continue after failure, all-pass tracking
- **Context sharing**: Mutable dict passed between steps
- **Protocol compliance**: PipelineStep duck typing
- **Duration tracking**: Per-step and pipeline-level timing
- **Skipped steps**: Don't count as match or failure

→ Pipeline framework details: `spec/PIPELINES.md`

### Validation Pipeline (`test_validation.py`)

- **Sensitive data scan**: Clean project passes, hardcoded passwords detected, env refs allowed
- **Gitignore check**: Complete patterns pass, missing patterns fail
- **ADR compliance**: Passing/failing/crashing checks, multiple checks, no-ADR skip
- **Integration**: Full pipeline against real codebase

→ ADR system: `spec/adrs/`

## Writing New Tests

1. Unit tests go in `tests/test_<module>.py`
2. Use `conftest.py` fixtures for common setup (sample emails, configs)
3. Mock external dependencies (himalaya, IMAP) — don't hit real servers
4. Test the pipeline logic, not the I/O
5. For new pipeline steps, verify both `matched=True` and `matched=False` paths

## CI Pipeline

Tests run automatically via GitHub Actions on every push to `main` and PR:

```
.github/workflows/ci.yml
├── lint       — ruff check
├── test       — pytest + coverage (≥70% required)
└── validate   — ADR compliance + sensitive data scan
```

Run the same checks locally before pushing:

```bash
poetry run ruff check openclaw_mail/ tests/
poetry run pytest -v --cov=openclaw_mail --cov-fail-under=70
poetry run validate
```

→ CI workflow details: `spec/PIPELINES.md`

## Integration Testing

For full end-to-end testing with real accounts:

```bash
# Dry-run against real mailboxes (reads but doesn't move)
poetry run mail-tidy --dry-run
```

This connects to real IMAP servers but doesn't modify any emails.
Check the report output in `reports/last_tidy_report.md`.
