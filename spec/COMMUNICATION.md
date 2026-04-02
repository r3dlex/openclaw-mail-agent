# Communication — Openclaw Mail Agent

> IAMQ messaging patterns for cross-agent communication.

## Agent Identity

| Field | Value |
|-------|-------|
| **Agent ID** | `mail_agent` |
| **Display** | Openclaw |
| **Capabilities** | `email_tidy`, `email_digest`, `folder_management`, `rule_engine`, `email_filtering`, `inbox_summary` |

Registration happens on every startup via `mq.register()`. The MQ service
merges metadata on re-registration, so duplicate calls are safe.

## Transport — Dual Mode

All messaging tries HTTP first, falls back to file-based delivery:

| Mode | Endpoint | When |
|------|----------|------|
| HTTP | `http://127.0.0.1:18790` | MQ service is running |
| File | `~/Ws/Openclaw/openclaw-inter-agent-message-queue/queue/<recipient>/` | MQ service unavailable |

Messages are JSON dicts with `id`, `from`, `to`, `type`, `priority`,
`subject`, `body`, `status`, `createdAt`. Subject is capped at 80 chars.

> Implementation: `openclaw_mail/utils/mq.py`

## Outbound Messages

### 1. Broadcast — Tidy Summary

Sent after every tidy run to **all agents** via the `broadcast` channel.

| Field | Value |
|-------|-------|
| To | `broadcast` |
| Type | `info` |
| Subject | `Email tidy complete` |
| Priority | `NORMAL` |
| Body | Short notification summary (see `format_summary()` in `tidy.py`) |

### 2. Full Report — Main Agent

Detailed markdown report sent directly to the orchestrator.

| Field | Value |
|-------|-------|
| To | `main` |
| Type | `info` |
| Subject | `Email tidy report (full)` |
| Priority | `LOW` |
| Body | Full report, **truncated to 5000 chars** (PII boundary) |

### 3. PR Routing — gitrepo_agent

PR-related emails detected during tidy are forwarded for code-review tracking.

| Field | Value |
|-------|-------|
| To | `gitrepo_agent` |
| Type | `request` |
| Subject | `PR email notifications (<N> items)` |
| Priority | `HIGH` |
| Body | Itemised list with account, subject, sender, folder |

This is **pattern-match only** — the email itself is never modified or
forwarded. Only metadata (subject, sender, folder) is sent.

> See [PR Routing Patterns](#pr-routing-patterns) below.

## Inbound Message Handling

`process_inbox()` reads unread messages from both the agent inbox and the
broadcast channel (skipping own broadcasts). Each message is marked read,
handled, then marked acted.

### Request Types

| Trigger keywords (subject or body) | Action |
|------------------------------------|--------|
| `roll call`, `introduce yourself`, `who are you`, `capabilities` | Replies with agent ID, description, workspace, capabilities list |
| `inbox summary`, `email summary`, `mail summary`, `tidy status` | Replies with latest `last_tidy_summary.txt` or "no report yet" |
| *(anything else)* | Generic acknowledgement: "Received your request... I'll process this on my next cycle." |

### Other Message Types

| Type | Handling |
|------|----------|
| `info` / `response` | Logged and marked acted |
| `error` | Logged as warning and marked acted |

## Peer Agents

| Agent | Relationship |
|-------|-------------|
| `main` | Orchestrator. Receives full tidy reports. |
| `gitrepo_agent` | Receives PR email notifications (high priority). |
| `broadcast` | All agents. Receives tidy summaries. |

## PR Routing Patterns

PR emails are detected by `_is_pr_email()` in `mq.py` using three criteria
(any match triggers routing):

### `_PR_SENDERS`

Known PR notification senders — match triggers unconditionally:

```python
{"azuredevops@microsoft.com", "noreply@github.com"}
```

### `_DEVOPS_FOLDERS`

Folders that indicate DevOps content — combined with `_PR_PATTERNS` match:

```python
{"DevOps", "Projects/RIB-4.0/DevOps", "Projects/Deep-Amber"}
```

### `_PR_PATTERNS`

Regex applied to subject line:

```python
re.compile(
    r"(pull\s*request|"
    r"\bPR[\s#:]\d|"
    r"code\s*review|"
    r"merge\s*(code|request|complet)|"
    r"approved.*pull|"
    r"reviewer\s*(added|removed)|"
    r"completed.*pull\s*request|"
    r"abandon|"
    r"has\s*voted|"
    r"Azure\s*DevOps)",
    re.IGNORECASE,
)
```

### Matching Logic

```
sender in _PR_SENDERS                              → route
folder in _DEVOPS_FOLDERS AND _PR_PATTERNS match    → route
_PR_PATTERNS match AND "pull request" in subject    → route
```

Additionally, `tidy.py` has its own `_PR_PATTERNS` list for extracting
PR numbers from subjects and sending per-PR messages to `gitrepo_agent`
during the tidy pipeline itself (not just post-tidy).

## Further Reading

- `spec/ARCHITECTURE.md` — system overview, pipeline design
- `spec/SAFETY.md` — PII truncation, credential rules
- `spec/DATA_SCHEMA.md` — report structures sent via IAMQ
- `openclaw_mail/utils/mq.py` — full implementation

---

*Owner: openclaw-mail-agent team*

## References

- [IAMQ HTTP API](https://github.com/r3dlex/openclaw-inter-agent-message-queue/blob/main/spec/API.md)
- [IAMQ WebSocket Protocol](https://github.com/r3dlex/openclaw-inter-agent-message-queue/blob/main/spec/PROTOCOL.md)
- [IAMQ Cron Scheduling](https://github.com/r3dlex/openclaw-inter-agent-message-queue/blob/main/spec/CRON.md)
- [Sidecar Client](https://github.com/r3dlex/openclaw-inter-agent-message-queue/tree/main/sidecar)
- [openclaw-main-agent](https://github.com/r3dlex/openclaw-main-agent)
