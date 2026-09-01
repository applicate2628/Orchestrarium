Status: `STARTER`

## Candidate Workspace

Edit only:

- `candidate/answer.json`

`answer.json` is the single scored artifact. It must be valid JSON with exactly the keys
`authority`, `action`, `escalate_to`, `reason_code`, `reason_evidence` (see `inputs/task.md` for the
enum domains and field semantics).

The starter `answer.json` is intentionally unfilled and fails the verifier; the completed-candidate
check is expected to pass only after a model run edits it into a correct answer.
