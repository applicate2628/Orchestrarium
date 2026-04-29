# Expected Routing Outcome

The correct result for this scenario is a direct-route transport report.

Expected provenance values:

- `Execution role: external-worker`
- `Assigned / replaced internal role: $platform-engineer`
- `Requested provider: gemini`
- `Resolved provider: Gemini CLI`
- `Actual execution path: external CLI (Gemini CLI)`
- `Model / profile used: runtime default`
- `Deviation reason: none`

Expected verdict:

- `Outcome: PASS`
- `Blocking reason: none`

Required factual anchors:

- `inputs/agents-mode.yaml` selects `externalProvider: gemini`
- `inputs/runtime-observations.md` says `Get-Command gemini -> found`
- `inputs/runtime-observations.md` says `gemini --version -> 0.38.2`
- `inputs/runtime-observations.md` says Gemini exposes `non-interactive (headless) mode`
- Codex and Claude availability must not change the outcome because explicit provider selection
  forbids rerouting
- the external route executed through `gemini` on the runtime default model/profile
- no internal `$platform-engineer`, reviewer, or consultant substitute is allowed
