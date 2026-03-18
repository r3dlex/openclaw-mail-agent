# ARCH-004: Sensitive Data Separation

**Status:** Accepted
**Date:** 2026-03-18

## Context

The repository is public on GitHub. Real email addresses, passwords, account
names, and personal filter rules must never be committed.

## Decision

Sensitive data is separated via `.gitignore`:

**Never committed:**
- `.env` files (credentials)
- `config/accounts.yaml` (real email addresses)
- `config/filters/*.yaml` (may contain real names — only `_default.yaml` and `.example`)
- `config/folder_mappings/*.md` (account-specific — only `_example.md`)
- `reports/`, `logs/`, `memory/` (runtime output)
- OAuth/credential JSON files

**Always committed:**
- `.env.example`, `accounts.yaml.example` (templates with placeholders)
- `_default.yaml` (generic defaults, no PII)
- `*.yaml.example` (documented templates)

## Consequences

- CI must scan for accidental credential commits
- Every config file needs a committed `.example` counterpart
- The `SensitiveDataStep` validation pipeline enforces this

## Validation

Machine-checkable: `spec/adrs/ARCH-004-sensitive-data-separation.check.py`
