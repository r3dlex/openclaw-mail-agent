# ARCH-001: No Hardcoded Credentials

**Status:** Accepted
**Date:** 2026-03-18

## Context

Email accounts require credentials (passwords, API keys, OAuth tokens).
Hardcoding these in source code creates security risks and makes the
repository unsafe to share publicly.

## Decision

All credentials are loaded from environment variables at runtime via
`config.py`. Account definitions in `config/accounts.yaml` reference
env var names (`user_env`, `password_env`), never actual values.

## Consequences

- `.env` files are gitignored and never committed
- `config.py` provides `get_env()` for safe env var access
- CI must verify no hardcoded passwords/keys/secrets in committed files
- Example files use placeholder values (`your-email@example.com`)

## Validation

Machine-checkable: `spec/adrs/ARCH-001-no-hardcoded-credentials.check.py`
