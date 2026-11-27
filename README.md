# MRclean

A re-runnable tool that finds your personal information on data brokers and
people-search sites, and drives its removal through each broker's opt-out
process. It tracks what it found and what it requested, so later runs catch
relistings and newly added brokers.

> **Status: pre-alpha (milestone 1).** The safety layer, the encrypted store,
> the identity profile and a 10-broker registry exist. Scanning and removal come
> in milestones 2 and 3 (see [BACKLOG.md](BACKLOG.md)).

## Why another one?

Commercial services such as Optery, DeleteMe and Incogni do this for a
subscription fee, with your data on their servers. Open-source projects either
cover OSINT discovery (Sherlock, Maigret, holehe) or publish opt-out
instructions (the Big Ass Data Broker Opt-Out List, the state broker
registries), but nothing standardises the loop: **scan → request removal →
verify → re-scan on a schedule**, with your data never leaving your machine.

## Safety model

MRclean handles exactly the data it exists to remove, so leaking that data is
the worst failure it can have. Defense in depth:

| Layer | What it does |
| --- | --- |
| Data dir outside the repo | Data lives in `%USERPROFILE%\.mrclean` / `~/Library/Application Support/mrclean` / `~/.local/share/mrclean`. The tool **refuses to run** if the data dir is inside any git work tree or a cloud-sync folder. |
| Deny-by-default `.gitignore` | Everything is ignored unless explicitly allow-listed. Data-shaped files (`*.db`, `*.csv`, `*.eml`, screenshots, etc.) stay ignored even inside allowed dirs. |
| PII pre-commit guard | Checks staged files against salted HMAC digests of **your** identifiers. It fails closed when unarmed and never prints the matched value. |
| gitleaks | Generic secret scanning, in pre-commit and CI. |
| Redacted logging | Emails, phone numbers and registered identity strings are scrubbed from every log record, including tracebacks. |
| Encrypted storage | The profile and all state live in a SQLCipher database. Its key is held in the OS credential store (Windows Credential Manager, Keychain, Secret Service), never on disk in plaintext. |

See [SECURITY.md](SECURITY.md) for the threat model and how to report issues.

## Quick start (development)

```bash
git clone https://github.com/MRGoodbar-931/mrclean
cd mrclean
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
mrclean init               # data dir + encrypted store (key goes to your OS credential store)
mrclean key backup         # save the recovery key in a password manager
mrclean profile add name   # who to look for; also arms the PII commit guard
mrclean profile add address
mrclean doctor             # verify every guard
mrclean registry list      # brokers, in the order they'll be worked
pytest
```

Full usage is in [docs/usage.md](docs/usage.md).

## License

MIT. See [LICENSE](LICENSE).
