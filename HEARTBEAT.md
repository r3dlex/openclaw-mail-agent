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
- [ ] Generate digest — last digest timed out on DavMail. Retry when DavMail is responsive.

## Report to User

After completing recurring checks, **send a summary to the user via your messaging channel** (through OpenClaw gateway). The user cannot see IAMQ messages.

- After tidy runs: report counts and any emails needing review. Example: "Tidy: 6 auto-filed, 1 review (sender: subject). Gmail recovering."
- If nothing happened: "All inboxes clean. Nothing to report."
- Gmail outages, DavMail timeouts, failed runs: report IMMEDIATELY, don't wait for the next heartbeat.

## Notes

- Tidy batch processing fixed: changed from fetching ALL emails first (timeout) to fetch+process in batches of 5
- Calendar module not yet implemented
- Gmail accounts may rate-limit or time out — DavMail (RIB) is the most reliable account
- When adding new address rules, update the per-account filter YAML in `config/filters/`
- PR emails are auto-routed to `gitrepo_agent` via IAMQ
