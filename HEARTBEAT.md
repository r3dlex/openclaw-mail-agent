# HEARTBEAT.md — Periodic Tasks

> Check this file on each heartbeat. Execute due tasks. Reply HEARTBEAT_OK if nothing needs attention.

## Active Tasks

- [DONE] RIB inbox backlog cleared (2026-03-21): Inbox went from ~2000 emails to 2. Batch processing fixed (fetches 5, processes, repeats until empty).
- RIB Gmail Review (90+ stale): Pipeline only processes INBOX, not Review. No automated clear path yet.

## Recurring Checks (rotate 2-4x daily)

- [x] Check inbox counts across accounts
- [x] Review folder sizes
- [x] MQ inbox — poll for messages from other agents, reply to requests
- [x] MQ heartbeat — keep registration alive
- [ ] Calendar — not yet implemented
- [x] Generate digest — fixed (2026-03-24): get_folder_count uses limit=1 instead of limit=500. Digest completes in ~37s. Counts are 0 or 1+ (exact count unavailable on DavMail without full-folder scans).

## Report to User

Send a Telegram summary ONLY when there's something worth reporting:
- Tidy runs completed with notable results. Example: "Tidy: 6 auto-filed, 1 needs review."
- Gmail outages, DavMail timeouts, failed runs: report IMMEDIATELY.
- Do NOT send a message if nothing happened. Silent heartbeats are fine.

## Notes

- Tidy batch processing fixed: changed from fetching ALL emails first (timeout) to fetch+process in batches of 5
- Calendar module not yet implemented
- Gmail accounts may rate-limit or time out — DavMail (RIB) is the most reliable account
- When adding new address rules, update the per-account filter YAML in `config/filters/`
- PR emails are auto-routed to `gitrepo_agent` via IAMQ
