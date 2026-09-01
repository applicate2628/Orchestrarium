# V4L04HB-hidden-consumer-contract

Hidden-oracle discrimination pilot, base form. Lane `L04H`.

An SDK migration readiness review with verification asymmetry: the visible
bundle carries the task, both provider snapshots, a trivially-green visible
test suite, the changelog, and structured usage records for sixteen
downstream consumers whose code does not exist in the bundle. The candidate
must predict, per visible consumer ID, break/safe, the responsible changelog
entry, and the required fix. The expected values live only in
`oracle/` and are never staged into the model workspace; no executable path
in the visible bundle reveals them.

- Visible inputs: `inputs/` (task, output schema, provider v1/v2 sources,
  visible tests, changelog, consumer census records).
- Candidate artifact: `candidate/migration-answer.json`.
- Hidden oracle: `oracle/rubric.json` scored by the frozen
  `Tooling/v4_rubric` adapter via `verifiers/score.py`.
- Probes: `oracle/probes/` (reference, competent, vacuous, decoy,
  alternate-valid, paraphrase, overclaim).

Identity keys are the visible consumer IDs (`CONS-01`..`CONS-16`), the
visible changelog IDs (`C01`..`C10`), the visible fix menu, and the visible
clearance enum. `oracle/ground-truth/index.json` records the per-case
derivation.
