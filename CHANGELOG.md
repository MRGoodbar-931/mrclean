# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Project scaffold: packaging, CLI entry point (`mrclean init`, `doctor`, `pii`).
- Data dir guard: refuses data dirs inside a git work tree or cloud-sync folder.
- Deny-by-default `.gitignore`.
- PII pre-commit guard using salted HMAC-SHA256 digests of registered identifiers.
  It fails closed and never echoes matches.
- Logging filter that redacts emails, phone numbers and registered identity strings.
- gitleaks, ruff and pytest in pre-commit and CI.
