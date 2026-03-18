# Testing Strategy

## Running Tests

```bash
# Local (poetry)
poetry run pytest -v

# Docker (zero-install)
docker compose run test

# With coverage
poetry run pytest --cov=openclaw_mail --cov-report=term-missing
```

## Test Structure

```
tests/
├── conftest.py            # Shared fixtures (sample emails, configs)
└── test_pipeline.py       # Filter pipeline unit tests
```

## What's Tested

### Filter Pipeline (`test_pipeline.py`)

- **Step 1 (Address)**: Sender matching, partial vs exact, case insensitivity
- **Step 2 (Keywords)**: Regex matching, confidence thresholds, best-match selection
- **Step 3 (AI)**: Score threshold enforcement, scorer callback integration
- **Step 4 (Review)**: Fallback behavior when nothing matches
- **Pipeline order**: Verify first-match-wins semantics
- **Config loading**: YAML parsing, default fallback

## Writing New Tests

1. Unit tests go in `tests/test_<module>.py`
2. Use `conftest.py` fixtures for common setup (sample emails, configs)
3. Mock external dependencies (himalaya, IMAP) — don't hit real servers
4. Test the pipeline logic, not the I/O

## Integration Testing

For full end-to-end testing with real accounts:

```bash
# Dry-run against real mailboxes (reads but doesn't move)
poetry run mail-tidy --dry-run
```

This connects to real IMAP servers but doesn't modify any emails.
Check the report output in `reports/last_tidy_report.md`.
