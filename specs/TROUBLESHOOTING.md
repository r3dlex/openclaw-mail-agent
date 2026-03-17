# Troubleshooting

## DavMail Issues

### Timeouts on Large Emails

**Symptom**: Himalaya commands hang or return "timeout" for the RIB account.

**Cause**: DavMail struggles with large emails (>5MB) containing attachments
like PowerPoint files, PDFs, or ZIP archives.

**Fix**:
1. The system automatically restarts DavMail on timeout (`restart_davmail()`)
2. RIB account uses a reduced batch size (5 emails vs 50)
3. If persistent, manually restart DavMail:
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
