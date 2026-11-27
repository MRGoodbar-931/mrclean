# Security

## Threat model

MRclean processes the personal identifiers it exists to remove. The main risks:

1. **Leaking personal data to the public repo.** Mitigated by the data dir guard,
   the deny-by-default `.gitignore`, the PII pre-commit guard, gitleaks, and CI.
2. **Leaking it through logs or crash output.** Mitigated by the redacting log filter.
3. **Local data theft.** Mitigated by planned encryption at rest. The PII guard
   digest file uses salted HMAC, but names and phone numbers are low-entropy, so
   someone who already holds the file could brute-force it. It never leaves the
   local data dir.
4. **Over-sharing with brokers.** Opt-out requests send only the fields a broker
   needs to find the listing, from a dedicated email alias.

## Reporting

Please report vulnerabilities privately through GitHub's
"Report a vulnerability" (Security → Advisories) rather than a public issue.
