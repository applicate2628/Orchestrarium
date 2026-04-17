# S32 Task Contract

Role: `A01 $external-worker`

Assigned / replaced internal role: `$platform-engineer`

Goal: write `candidate/transport-execution-report.md` as a transport-only execution report.

Read only:

- `inputs/accepted-worker-phase.md`
- `inputs/agents-mode.yaml`
- `inputs/runtime-observations.md`
- `inputs/transport-wrapper-notes.md`
- `oracle/provenance-contract.json`

Write only:

- `candidate/transport-execution-report.md`

Required output properties:

- use the exact provenance labels shown in the candidate template
- report the transport verdict for the selected provider only
- name the blocking dependency if the external route is disabled
- state that no internal specialist, reviewer, or consultant fallback was used

Out of scope:

- any semantic evaluation of the assigned `$platform-engineer` phase
- rerouting to a different provider because another CLI is present
- provider ranking logic, score-table commentary, or taxonomy edits
