# Runtime Observations

These observations are the source of truth for the transport report. Do not rerun probes.

- The host runtime supports direct external CLI launch when the selected provider binary exists.
- `Get-Command codex -> found`
- `Get-Command claude -> found`
- `Get-Command gemini -> not found`
- The launch packet includes `Assigned / replaced internal role: $security-reviewer`.
- The launch packet includes `Review strategy: adversarial`.
- The external route executed through `codex` using the runtime default model/profile.
- No internal reviewer, QA role, or consultant fallback was invoked before or after the external launch.
- No semantic reviewer findings or QA verdict were emitted into the transport packet.
