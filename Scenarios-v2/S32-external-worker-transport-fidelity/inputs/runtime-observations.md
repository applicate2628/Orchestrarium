# Runtime Observations

These observations are the source of truth for the transport report. Do not rerun probes.

- The host runtime supports direct external CLI launch when the selected provider binary exists.
- `Get-Command gemini -> found at C:\nvm4w\nodejs\gemini.ps1`
- `Get-Command codex -> found`
- `Get-Command claude -> found`
- `gemini --version -> 0.38.2`
- `gemini --help -> Use -p/--prompt for non-interactive (headless) mode.`
- The external route executed through `gemini` using the runtime default model/profile.
- No internal specialist, reviewer, or consultant fallback was invoked before or after the external launch.
- Codex and Claude availability is irrelevant because provider selection is explicit.
