# ARCH-003: Per-Account Config with Default Fallback

**Status:** Accepted
**Date:** 2026-03-18

## Context

Different email accounts (work, personal, system) need different filter
rules — a work account has HR/DevOps keywords, while a personal account
has shopping/travel keywords. But every account should have *some* config
even if uncustomized.

## Decision

Filter configuration uses a fallback chain:
1. `config/filters/<account_id>.yaml` — account-specific (gitignored)
2. `config/filters/_default.yaml` — default fallback (committed)

Per-account configs are gitignored to prevent leaking real names/addresses.
Only `_default.yaml` and `.yaml.example` templates are committed.

## Consequences

- New accounts work immediately with default rules
- Account-specific customization is optional
- Example files (`.yaml.example`) serve as documentation
- Real account configs never reach the public repo

## Validation

Machine-checkable: `spec/adrs/ARCH-003-per-account-config-fallback.check.py`
