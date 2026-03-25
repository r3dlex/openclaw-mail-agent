# Learnings

> This file is maintained by the openclaw agent. Add lessons learned,
> patterns discovered, and operational insights here over time.
> Keep entries concise and actionable.

## Format

```
### YYYY-MM-DD — Title
What happened, what was learned, and what to do differently next time.
```

## Entries

### 2026-03-25 — Cross-agent: librarian vault_path null orphans

- **Problem:** Librarian agent's `Staging.mark_filed/2` was called without
  setting `vault_path`, leaving 6 files in `processed/` as orphans — DB says
  "filed" but no vault entry exists. Discovered during a swarm status check.
- **Root cause:** The Elixir pipeline updated status before confirming the
  vault write succeeded. A null `vault_path` should be rejected by the schema.
- **Action for mail_agent:** When sending files to other agents (calendar
  exports, digest reports, PR summaries), always include a `vault_path` or
  `destination` field in the IAMQ message body so the receiving agent knows
  where to store it. Never assume the receiver will figure out the path.
- **Lesson:** Any pipeline that marks something as "done" before the write
  is confirmed has an orphan bug. Status transitions should be atomic with
  the operation they represent. This applies to our own tidy pipeline too —
  we move the email first, then record the action in the report.

### 2026-03-25 — Gmail rate limiting across multiple accounts

- **Problem:** All 7 Gmail accounts hit rate limits simultaneously during
  tidy runs. Status report showed all accounts timing out.
- **Root cause:** Tidy processed accounts sequentially but without inter-account
  delays. Gmail's rate limits are per-IP, not per-account, so 7 accounts
  from the same machine exhausts the quota fast.
- **Fix:** Added `HimalayaError` exception class to distinguish timeouts from
  empty inboxes, plus exponential backoff and inter-account breathing delays.
- **Lesson:** When operating multiple accounts on the same provider from one
  IP, add deliberate delays between accounts (not just between batches within
  an account).

### 2026-03-24 — DavMail digest timeout — fix

- **Problem:** `digest` command timed out on DavMail. `get_folder_count` used `limit=500` to fetch full folder contents for counting — DavMail Exchange backend times out on large envelope fetches.
- **Fix:** Changed `get_folder_count` in `digest.py` to use `limit=1` and `timeout=davmail_timeout(10)` with `retries=1`. Digest now completes in ~37s.
- **Tradeoff:** Counts are now "0 or 1+" (exact count unavailable without expensive full-folder scans on DavMail). This is acceptable for digest purposes.
- **Lesson:** Never fetch all envelopes from DavMail for counting. Use existence checks (`limit=1`) instead.
