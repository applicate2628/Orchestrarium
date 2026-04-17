# Runtime Observations

These observations are the source of truth for the transport report. Do not rerun probes.

- The host runtime supports direct external CLI launch when the selected provider binary exists.
- `Get-Command gemini -> not found`
- `Get-Command codex -> found`
- `Get-Command claude -> found`
- No Gemini-specific wrapper or alternate transport is installed for this lane.
- No external provider command was launched after the missing-CLI check.
- Codex and Claude availability is irrelevant because provider selection is explicit.
