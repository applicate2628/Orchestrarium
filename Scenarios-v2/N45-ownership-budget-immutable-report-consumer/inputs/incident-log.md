# Incident Log

Incident: `INC-742`

Observed failure:

- A canary release for `acme/api/6.0/morning` committed to the ledger and notified once.
- The worker crashed after that committed canary step.
- Resume replayed the canary side effect and then deployed prod, creating duplicate notifications.

Operational source of truth:

- `activeProfile=balanced` is the authoritative runtime profile.
- `legacyProfile=emergency` is present only for old callers and is a fallback when `activeProfile`
  is absent.
- Reports used by incident commanders must be derived from ledger and audit, not notification lists.

Required visible recovery:

- Preserve the public `deploygrid` API.
- Keep source ids from requests visible in audit/report state.
- Roll back only the current failed deployment group; do not roll back earlier stable releases.
