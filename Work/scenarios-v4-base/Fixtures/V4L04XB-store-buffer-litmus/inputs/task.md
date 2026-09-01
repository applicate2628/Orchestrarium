# Task

You are the verification lead for a soft-core CPU project. Two candidate
store-buffer designs — machine `SB-A` and machine `SB-B` — are specified in
`inputs/sources/machine-spec.md`. The release decision needs to know, for
every observation listed in `inputs/sources/programs.md`, on which of the
two machines it can occur.

## Goal

Write `candidate/litmus-answer.json` (valid JSON matching
`inputs/output-schema.json`) with:

1. `verdicts` — for EVERY observation ID (`P01-O1` .. `P16-O2`), exactly
   one class, as `{"value": "<class>", "unit": "class"}`:
   - `both` — reachable on SB-A and reachable on SB-B
   - `a-only` — reachable on SB-A, NOT reachable on SB-B
   - `b-only` — reachable on SB-B, NOT reachable on SB-A
   - `neither` — not reachable on either machine
2. `divergent_program_ids` — every program ID (`P01` .. `P16`) with
   at least one `a-only` or `b-only` observation among its listed
   observations (the programs on which the two machines observably differ).
3. `equivalence_gate.machines_verdict` — `agree` if the two machines are
   observationally equivalent across ALL listed observations, `diverge`
   otherwise.
4. Optional `narrative` — free text, not scored.

## Rules of the game

- Reachability means: at least one COMPLETE run (as defined in
  `machine-spec.md`, including trailing write-backs) satisfies every claim
  of the observation simultaneously. The grader has exhaustively enumerated
  every reachable final state of every program on both machines; your
  classes are checked against that enumeration, one observation at a time.
- Scoring is symmetric and unforgiving: a reachable outcome classified as
  unreachable and an unreachable outcome classified as reachable are equally
  wrong. Guessing a direction loses the point either way, so only a
  precisely justified class is worth writing.
- The machines are fully defined by `machine-spec.md` ALONE. They are not
  any published hardware or language memory model, and they differ from each
  other in exactly two pinned respects. Pattern-matching to a model you
  already know will misclassify some observations.
- `unit` is always the literal string `class`.
- Every observation ID must appear in `verdicts`; missing IDs score zero.
- Do not write anything outside `candidate/`.
