# S33 Task Contract

Role: `A02 $external-reviewer`

Assigned / replaced internal role: `$security-reviewer`
Review strategy: `adversarial`

Goal: write `candidate/transport-execution-report.md` as a transport-only execution report.

Read only:

- `inputs/accepted-review-phase.md`
- `inputs/agents-mode.yaml`
- `inputs/runtime-observations.md`
- `inputs/transport-wrapper-notes.md`
- `oracle/provenance-contract.json`

Write only:

- `candidate/transport-execution-report.md`

Required output properties:

- use the exact provenance labels shown in the candidate template
- record the requested review strategy and how the adapter handled it
- report the transport verdict for the selected provider only
- state that no internal reviewer, QA role, or consultant fallback was used
- avoid semantic reviewer findings, QA verdict language, or remediation advice

Out of scope:

- any semantic evaluation of the assigned `$security-reviewer` review packet
- producing a security finding list, QA verdict, or remediation plan
- rerouting to a different provider because another CLI is present
- provider ranking logic, score-table commentary, or taxonomy edits
