# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
