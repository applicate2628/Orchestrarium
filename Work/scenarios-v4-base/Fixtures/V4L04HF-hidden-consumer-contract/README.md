# V4L04HF-hidden-consumer-contract

Hidden-oracle discrimination pilot, frontier form. Lane `L04H`.

Same verification-asymmetry mechanism as the base form
(`V4L04HB-hidden-consumer-contract`), scaled up: twenty-four downstream
consumers, a twelve-entry changelog, cross-change causal chains (key
folding interacting with precedence), an error-normalization change that
defeats a `KeyError` handler, and additional safe-looking-but-breaks and
loud-but-safe decoys. Consumer code does not exist in the bundle; the
expected verdicts live only in `oracle/` and are never staged into the
model workspace.

- Visible inputs: `inputs/` (task, output schema, provider v1/v2 sources,
  visible tests, changelog, consumer census records).
- Candidate artifact: `candidate/migration-answer.json`.
- Hidden oracle: `oracle/rubric.json` scored by the frozen
  `Tooling/v4_rubric` adapter via `verifiers/score.py`.
- Probes: `oracle/probes/` (reference, competent, vacuous, decoy,
  alternate-valid, paraphrase, overclaim).

Identity keys are the visible consumer IDs (`CONS-01`..`CONS-24`), the
visible changelog IDs (`C01`..`C12`), the visible fix menu, and the visible
clearance enum. `oracle/ground-truth/index.json` records the per-case
derivation.
