# Accepted Brief

The policy surface is moving from a single default external priority profile to lane-specific
`externalPriorityProfiles`.

The old singular key `externalPriorityProfile` still appears in older runbook notes and may remain as
an input compatibility alias, but it is not the new source of truth.

The decision must preserve:

- adapters remain transport-only
- provider route facts stay separate from policy identity
- `X4` must continue to use the secret-backed Claude route when it is enabled
- missing lane-specific profiles must fail visibly or use an explicitly documented default
