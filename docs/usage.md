# Usage

## Commands

| Command | Purpose |
| --- | --- |
| `mrclean init` | Create the local data dir (owner-only permissions on POSIX). |
| `mrclean doctor` | Check that the data dir is safe and the PII guard is armed. |
| `mrclean pii register` | Add identifiers to the commit guard. Input is hidden and never passed on the command line, so it stays out of shell history. |
| `mrclean pii scan FILE...` | Scan files for registered identifiers. Pre-commit runs this for you. |
| `mrclean -v ...` | Debug logging. Logs are still redacted. |

## Data directory

The default is per-user and not synced: `%LOCALAPPDATA%\mrclean` on Windows,
`~/Library/Application Support/mrclean` on macOS and `$XDG_DATA_HOME/mrclean`
on Linux. Override it with `MRCLEAN_DATA_DIR`. The override goes through the
same checks: a path inside a git repo or a OneDrive/Dropbox/Google Drive/iCloud
folder is refused.

## What to register with the PII guard

Register every identifier you'd never want in the repo: full names (current and
past), email addresses, phone numbers, and street addresses (the street line,
e.g. "1234 Elm Street"). Matching ignores case, punctuation and phone formatting.
Single words shorter than three characters are skipped to avoid false positives.

Avoid registering a single common word (e.g. just a first name). It will block
any commit that contains that word. Register the full name instead.
