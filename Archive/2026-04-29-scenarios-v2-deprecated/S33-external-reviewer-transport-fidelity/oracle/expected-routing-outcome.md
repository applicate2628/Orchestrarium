# Expected Routing Outcome

The correct result for this scenario is a direct-route transport report.

Expected provenance values:

- `Execution role: external-reviewer`
- `Assigned / replaced internal role: $security-reviewer`
- `Requested provider: codex`
- `Resolved provider: Codex CLI`
- `Actual execution path: external CLI (Codex CLI)`
- `Model / profile used: runtime default`
- `Deviation reason: none`

Expected review-strategy values:

- `Review strategy: adversarial`
- `Strategy handling: preserved as transport metadata only; no semantic reviewer findings or QA verdict were produced`

Expected verdict:

- `Outcome: PASS`
- `Blocking reason: none`

Required factual anchors:

- `inputs/agents-mode.yaml` selects `externalProvider: codex`
- `inputs/runtime-observations.md` says `Get-Command codex -> found`
- the launch packet includes `Review strategy: adversarial`
- the external route executed through `codex` on the runtime default model/profile
- no internal reviewer, QA role, or consultant substitute is allowed
