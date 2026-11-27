# Backlog

Ordered by priority. Items move to CHANGELOG.md when shipped.

## Now: design (needs sign-off before build)
- [ ] Architecture proposal: modules, run loop, state machine per broker listing.
- [ ] Broker registry schema (YAML, public metadata only): search URL patterns,
      opt-out method (form / email / account / mail), required fields, verification
      steps, relisting cadence, sources.
- [ ] Choose the encryption approach for local storage (e.g. `age`, or SQLCipher with
      the key in the OS keyring).

## Next: phase 1, third-party brokers
- [ ] Identity profile (encrypted): names (current and past), addresses, phones, emails, usernames.
- [ ] Seed the broker registry from public sources (Big Ass Data Broker Opt-Out List,
      the CA/VT/TX/OR broker registries, the Privacy Rights Clearinghouse database).
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
