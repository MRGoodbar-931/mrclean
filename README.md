# MRclean

A re-runnable tool that finds your personal information on data brokers and
people-search sites, and drives its removal through each broker's opt-out
process. It tracks what it found and what it requested, so later runs catch
relistings and newly added brokers.

> **Status: pre-alpha scaffold.** The safety layer exists. Scanning and removal
> are being designed (see [BACKLOG.md](BACKLOG.md)) and aren't implemented yet.

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
| Data dir outside the repo | Data lives in `%LOCALAPPDATA%\mrclean` / `~/Library/Application Support/mrclean` / `~/.local/share/mrclean`. The tool **refuses to run** if the data dir is inside any git work tree or a cloud-sync folder. |
| Deny-by-default `.gitignore` | Everything is ignored unless explicitly allow-listed. Data-shaped files (`*.db`, `*.csv`, `*.eml`, screenshots, etc.) stay ignored even inside allowed dirs. |
| PII pre-commit guard | Checks staged files against salted HMAC digests of **your** identifiers. It fails closed when unarmed and never prints the matched value. |
| gitleaks | Generic secret scanning, in pre-commit and CI. |
| Redacted logging | Emails, phone numbers and registered identity strings are scrubbed from every log record, including tracebacks. |
| Encrypted storage | *Planned:* the identity profile and scan results are encrypted at rest. |

See [SECURITY.md](SECURITY.md) for the threat model and how to report issues.

## Quick start (development)

```bash
git clone https://github.com/MRGoodbar-931/mrclean
cd mrclean
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
mrclean init            # creates the local data dir
mrclean pii register    # arm the commit guard with your identifiers (hidden input)
mrclean doctor          # verify the guards
pytest
```

Full usage is in [docs/usage.md](docs/usage.md).

## License

MIT. See [LICENSE](LICENSE).
