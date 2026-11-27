# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added (milestone 1)
- Broker registry: one strict, schema-validated YAML file per broker, with
  parent/child ordering, an opt-out mode (`auto` / `assisted` / `manual`), query-hygiene
  limits on search templates, and freshness tracking (`last_verified`, `verified_live`).
- 10 seed brokers from the Big Ass Data Broker Opt-Out List: PeopleConnect (Intelius
  family), BeenVerified, Spokeo, Whitepages, MyLife, SmartBackgroundChecks, Nuwber,
  That's Them, FastPeopleSearch, Acxiom.
- Encrypted store: SQLite kept in memory and persisted as one AES-256-GCM file
  (`cryptography`), with a random key in the OS credential store. Writes are atomic,
  tampering is detected, an OS lock blocks concurrent runs, and migrations are versioned.
  SQLCipher was dropped after its bindings had no Windows wheel for Python 3.15.
- CI tests the latest stable Python (`3.x`) on Linux and Windows, and runs weekly
  so a new Python release that breaks installation is caught without a commit.
- Identity profile in the store, with name x state search fan-out.
- CLI: `key backup/restore`, `profile add/show/remove/variants`, `registry validate/list`.
  `doctor` now checks the store, the profile and the registry too.
- Adding a profile identifier also registers it with the PII commit guard, and the
  log redactor learns profile literals on every run.

### Fixed
- Windows: the default data dir moved from `%LOCALAPPDATA%\mrclean` to
  `%USERPROFILE%\.mrclean`. Packaged (MSIX) apps such as the Claude desktop app
  have AppData writes silently redirected into a private container, so a terminal
  and an app-launched process saw two different data dirs. Data dirs inside an
  MSIX `Packages\<app>\LocalCache` container are now refused.

### Added
- Project scaffold: packaging, CLI entry point (`mrclean init`, `doctor`, `pii`).
- Data dir guard: refuses data dirs inside a git work tree or cloud-sync folder.
- Deny-by-default `.gitignore`.
- PII pre-commit guard using salted HMAC-SHA256 digests of registered identifiers.
  It fails closed and never echoes matches.
- Logging filter that redacts emails, phone numbers and registered identity strings.
- gitleaks, ruff and pytest in pre-commit and CI.
