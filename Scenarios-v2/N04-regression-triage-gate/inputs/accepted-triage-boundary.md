# Accepted Triage Boundary

This packet covers one additive pre-PR change set for a bundle-local status-snapshot tool.

## Required behavior

1. `--dry-run` must not persist `.status-cache/last-run.json` or any equivalent run marker.
2. When `--only-failed` is active, the footer summary must describe the visible failed-job set, not
   the full underlying total.
3. Digest dedupe for repeated `ops-summary` notifications must remain stable across reruns of the
   same summary on the same channel.
4. Nearby must-not-break surfaces include the default text output and the `include_paused` filter.

## Triage posture

- prioritize likely regressions before merge
- keep the report triage-only; this packet does not admit implementation work or a specialist
  security/performance lane
- deprioritize pre-existing flake and lint noise unless new evidence ties them to the recent change
