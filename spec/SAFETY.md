# Safety — Openclaw Mail Agent

> Boundaries and constraints for safe email handling.

## Core Principle

**Never lose email.** Every operation must be reversible or non-destructive.

## Rules

### 1. No Permanent Deletion

- Emails are **moved to trash only**, never permanently deleted.
- `move_email()` targets folders; there is no delete API.
- Folder restructure proposals go through explicit approval (see rule 6).

### 2. Email Content Is PII

- Bodies are **truncated to 5000 chars** in all IAMQ messages
  (`full_report[:5000]` in `send_tidy_report()`).
- Only metadata (subject, sender, folder, action) appears in reports
  and inter-agent messages — never full message bodies.
- Tidy report details cap subject at 80 chars, sender at 50 chars.
- Log files may contain subjects and senders but **never** passwords,
  tokens, or full email bodies.

### 3. No Auto-Reply to External Emails

- The agent **never** sends email on behalf of the user.
- All communication is intra-swarm via IAMQ, not via SMTP.
- The SMTP port exists for DavMail infrastructure only.

### 4. Credential Handling

- DavMail and Gmail passwords come from `.env` **only**, resolved
  at runtime via `os.getenv()` or `config.get_env()`.
- Passwords are **never logged** — not in `logs/`, not in `reports/`,
  not in IAMQ messages.
- OAuth tokens and client secrets (`*.json` in `config/`) are gitignored.
- `.env` files are gitignored and never committed.

> ADR: `spec/adrs/ARCH-001-no-hardcoded-credentials.md`
> ADR: `spec/adrs/ARCH-004-sensitive-data-separation.md`

### 5. Rate Limits on IMAP Operations

- DavMail accounts use `DAVMAIL_TIMEOUT_MULTIPLIER` (default 4x) on all
  timeouts to avoid hammering the Exchange bridge.
- Batch processing uses scaled timeouts: +1s per message in bulk moves.
- `get_envelopes_with_retry()` uses exponential back-off with max 2 retries.
- Tidy processes emails in batches of 5 to avoid overloading IMAP connections.

> See: `spec/TROUBLESHOOTING.md` — DavMail timeout table

### 6. Folder Restructure Requires Approval

- Proposed folder changes go to `spec/FOLDER_RESTRUCTURE_PROPOSAL.md`.
- No automated folder creation beyond what the filter pipeline specifies.
- `create_folder()` only creates folders already defined in filter configs
  or the review fallback folder.

### 7. PR Email Routing — Read Only

- PR detection is **pattern-match only** on subject, sender, and folder metadata.
- The original email is **never modified** — only a metadata summary is
  forwarded to `gitrepo_agent` via IAMQ.
- Patterns: `_PR_PATTERNS`, `_PR_SENDERS`, `_DEVOPS_FOLDERS` in `mq.py`.

> See: `spec/COMMUNICATION.md` — PR Routing Patterns

## Sensitive File Protection

The `.gitignore` blocks all sensitive paths. CI validates this:

| Path | Content | Committed? |
|------|---------|------------|
| `.env` | Credentials | No |
| `config/accounts.yaml` | Email addresses | No |
| `config/filters/*.yaml` | May contain real names | No (except `_default.yaml`) |
| `config/folder_mappings/*.md` | Account-specific | No (except `_example.md`) |
| `config/*.json` | OAuth tokens | No |
| `reports/` | PII in email metadata | No |
| `logs/` | May contain subjects | No |

> ADR: `spec/adrs/ARCH-004-sensitive-data-separation.md`

## Validation

CI enforces safety rules automatically:

```bash
poetry run validate    # Runs sensitive data scan + gitignore check + ADR compliance
```

> See: `spec/PIPELINES.md` — Validation Pipeline

## Further Reading

- `spec/ARCHITECTURE.md` — system overview
- `spec/COMMUNICATION.md` — IAMQ message patterns, PII truncation in practice
- `spec/adrs/` — all architecture decision records

---

*Owner: openclaw-mail-agent team*
