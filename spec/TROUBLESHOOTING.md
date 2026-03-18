# Troubleshooting

## DavMail Issues

### Timeouts on DavMail Operations

**Symptom**: Himalaya commands hang or return "timeout" for DavMail accounts
(e.g. RIB). Moves silently fail, envelope lists return empty.

**Cause**: DavMail (Exchange/O365 IMAP bridge) is inherently slow — typical
response times are 5–90 seconds per query. Large emails (>5MB with attachments)
and batch moves (many IDs in one command) are especially slow.

**How the system handles it** (see `openclaw_mail/utils/himalaya.py`):

1. **`davmail_timeout(base)`** — multiplies base timeout by `DAVMAIL_TIMEOUT_MULTIPLIER`
   (default 4×). Use this when passing timeouts for DavMail accounts:
   ```python
   from openclaw_mail.utils.himalaya import davmail_timeout
   create_folder(account, folder, timeout=davmail_timeout(20))  # → 80s
   ```

2. **`himalaya_run_with_retry()`** — retries on timeout with exponential back-off.
   All high-level functions (`move_email`, `create_folder`, `list_folders`) now
   use this internally.

3. **Scaled batch timeouts** — `move_email()` adds +1s per message ID to the
   timeout. `bulk_move()` does the same. A batch of 170 messages gets ~230s.

4. **DavMail restart** — `get_envelopes_with_retry()` auto-restarts DavMail on
   first failure for DavMail accounts.

5. **Timeout logging** — all timeouts are now logged as warnings with the
   command that timed out.

**Default timeout comparison**:

| Function | Old default | New default | DavMail (4×) |
|----------|-------------|-------------|--------------|
| `move_email` | 15s | 30s | 120s + 1s/msg |
| `create_folder` | 10s | 20s | 80s |
| `list_folders` | 15s | 30s | 120s |
| `get_envelopes` | 30s | 30s | 120s |

**Manual fix** (if automated retry fails):
```bash
pkill -f davmail && open -a DavMail  # macOS
```

### DavMail Not Starting

**Symptom**: Connection refused on port 1143.

**Fix**:
1. Check DavMail is running: `lsof -i :1143`
2. Start it: `open -a DavMail` (macOS) or `davmail &` (Linux)
3. Verify `.env` has correct `DAVMAIL_IMAP_PORT`

## Gmail App Passwords

### Authentication Failed

**Symptom**: "Login failed" for Gmail accounts.

**Fix**:
1. Ensure 2FA is enabled on the Google account
2. Generate an App Password at https://myaccount.google.com/apppasswords
3. Update the password in `.env`
4. App passwords are 16 characters, no spaces

## Himalaya

### "Account not found"

**Symptom**: `himalaya envelope list -a RIB` fails.

**Fix**: The account name must match exactly what's in `~/.config/himalaya/config.toml`.
Check `config/accounts.yaml` → `himalaya_name` matches the himalaya config.

### Empty Envelope List

**Symptom**: Himalaya returns `[]` even though inbox has emails.

**Cause**: Usually a timeout or auth issue that silently fails.

**Fix**: Run with verbose logging:
```bash
RUST_LOG=debug himalaya envelope list -a RIB -o json --folder INBOX -s 1
```

## Docker

### Container Can't Reach DavMail

**Symptom**: Timeouts when running in Docker.

**Cause**: DavMail runs on the host, not in the container.

**Fix**: Use `host.docker.internal` instead of `localhost` in `.env`:
```
DAVMAIL_HOST="host.docker.internal"
```

## Filter Pipeline

### Email Not Being Categorized

**Symptom**: Email goes to Review even though a rule should match.

**Debug**:
1. Run with `--dry-run` to see what the pipeline decides
2. Check `config/filters/<account_id>.yaml` exists
3. Verify regex pattern matches (test with `python -c "import re; print(re.search(...))"`)
4. For Step 3 (AI), check that `ai_score_threshold` isn't too high

### Wrong Folder Assignment

**Symptom**: Email goes to the wrong folder.

**Cause**: A higher-priority step (address or keyword) matches before the
intended rule.

**Fix**: Remember the pipeline order: Address → Keywords → AI → Review.
Check if an address rule or keyword pattern is catching the email first.
