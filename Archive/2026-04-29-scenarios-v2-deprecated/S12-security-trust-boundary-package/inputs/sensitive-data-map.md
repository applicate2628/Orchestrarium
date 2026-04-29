# Evidence E4 - Sensitive Data Map

## Data classes

| Data class | Example | Sensitivity | May cross to provider transport? | May appear in analyst export? |
|---|---|---|---|---|
| broker-issued provider token | `[REDACTED_PROVIDER_TOKEN]` | secret | no | no |
| vault write token | `[REDACTED_VAULT_TOKEN]` | secret | no | no |
| scenario attachments | synthetic repo files selected by the manifest | internal and candidate-controlled | only explicit allowlisted files | no raw paths or uncontrolled files |
| provider stdout and stderr | model output, diagnostics, warnings | untrusted and potentially sensitive | already returned from the provider | only sanitized excerpts |
| structured result packet | JSON result plus provenance | internal and partially untrusted | not applicable | sanitized, schema-checked fields only |
| analyst export package | summary memo, selected evidence, provenance hash | internal | no | yes |
| raw evidence vault contents | full stdout, full stderr, raw packet | restricted | no | no |

## Security implications

- raw provider output is both untrusted and potentially sensitive
- scenario-selected files must not be allowed to widen outside the admitted bundle root
- provenance hashes may appear in the analyst export, but raw secrets and raw tokens may not
