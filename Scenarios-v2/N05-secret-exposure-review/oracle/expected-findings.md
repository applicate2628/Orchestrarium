# Expected Findings

- `[high]` export token exposure through the `export_token` query parameter on `export-download`
- `[high]` raw secret and customer-data leakage through `sendBeacon` telemetry
- `[medium]` visible customer-address exposure through `customerEmails.join(", ")`
