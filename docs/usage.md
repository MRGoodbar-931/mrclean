# Usage

## Commands

| Command | Purpose |
| --- | --- |
| `mrclean init` | Create the data dir and the encrypted store. The key is generated and saved to your OS credential store. |
| `mrclean doctor` | Check the data dir, PII guard, store, profile and registry. |
| `mrclean key backup` | Print the store's recovery key so you can keep it in a password manager. |
| `mrclean key restore` | Put a backed-up key into the credential store (new machine, wiped keychain). It checks that the key opens the store first. |
| `mrclean profile add {name,address,phone,email,username}` | Add an identifier interactively. It's also registered with the PII commit guard. |
| `mrclean profile show` / `remove KIND N` | View or remove profile entries. |
| `mrclean profile variants [--with-city]` | Show the exact narrow queries a scan will send (name variant x state). |
| `mrclean registry validate` / `list` | Validate the broker YAML, or list brokers in execution order with their opt-out mode (`auto`, `assisted` or `manual`). |
| `mrclean pii register` | Add identifiers to the commit guard. Input is hidden and never passed on the command line, so it stays out of shell history. |
| `mrclean pii scan FILE...` | Scan files for registered identifiers. Pre-commit runs this for you. |
| `mrclean -v ...` | Debug logging. Logs are still redacted. |

## Data directory

The default is per-user and not synced: `%USERPROFILE%\.mrclean` on Windows,
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

## Query hygiene

Scans get coverage from many narrow queries, not a few rich ones. Each search
sends only first name, last name (plus a middle initial variant) and state, once
for every name you've used in every state you've lived in. Ages, phones, emails
and street addresses never leave your machine. They're used locally to decide
which results are you. Run `mrclean profile variants` to see exactly what will be
sent.

## The encryption key

Lose the key and the store can't be read. That costs your request history, not
your safety, and a re-scan rebuilds it. Run `mrclean key backup` once and keep the
output in a password manager. Anyone holding both the key and your data folder can
read the store.
