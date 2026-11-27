# Backlog

Ordered by priority. Items move to CHANGELOG.md when shipped.

## Done
- [x] Architecture and registry schema signed off (2026-11-26).
- [x] M1: registry, seed brokers, encrypted store, profile.

## Now: M2, scan and match
- [ ] Walk each seed broker live: confirm the opt-out fields, then set `verified_live`.
- [ ] Verify and add `search.url_template` per broker (all seed entries are `manual` until checked).
- [ ] Shared HTTP client: per-domain rate limits, retry with backoff, Retry-After, redaction.
- [ ] Per-broker canary search (a known public listing), so a broken parser is flagged
      instead of reporting "not found".
- [ ] Parsers with recorded fixtures, plus opt-in live smoke tests (never in CI).
- [ ] Match scoring and a review queue.

## Next: phase 1, third-party brokers
- [ ] Grow the registry beyond the seed 10 (CA/VT/TX/OR registries, PRC database).
- [ ] Scanner: polite, rate-limited, retrying HTTP plus a browser fallback for JS sites.
- [ ] Match scoring: does a listing actually refer to the subject?
- [ ] Removal drivers: email templates (sent from a dedicated alias), form-fill
      assistance, manual-task checklist for anything needing ID or CAPTCHA.
- [ ] State store and report: found / requested / confirmed / relisted.
- [ ] Scheduled re-scan.

## Later: phase 2, own accounts
- [ ] Account discovery (holehe-style email checks, username enumeration).
- [ ] Deletion guides (JustDeleteMe data) and tracking.

## Ideas
- Breach exposure check via HIBP (k-anonymity API).
- Export a redacted report for sharing.
