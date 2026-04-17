# Expected Routing Outcome

The correct result for this scenario is a disabled-route transport report.

Expected provenance values:

- `Execution role: external-worker`
- `Assigned / replaced internal role: $platform-engineer`
- `Requested provider: gemini`
- `Resolved provider: none`
- `Actual execution path: role disabled`
- `Model / profile used: unspecified by runtime`
- `Deviation reason: external unavailable: gemini CLI missing from PATH`

Expected verdict:

- `Outcome: BLOCKED:dependency`
- `Blocking reason: explicit provider gemini selected but gemini CLI is unavailable and no approved fallback path exists`

Required factual anchors:

- `inputs/agents-mode.yaml` selects `externalProvider: gemini`
- `inputs/runtime-observations.md` says `Get-Command gemini -> not found`
- Codex and Claude availability must not change the outcome because explicit provider selection
  forbids rerouting
- no internal `$platform-engineer`, reviewer, or consultant substitute is allowed
