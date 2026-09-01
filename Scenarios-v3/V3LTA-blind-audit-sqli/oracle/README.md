# Oracle (hidden — stripped from provider staging)

Nothing here is visible to the candidate. Contents:

- `blind-audit-contract.json` — scoring policy: metric (`recall_at_precision_floor`), precision floor
  (0.80), recall pass threshold (0.70), the pinned budget, the answer contract, exit codes, and bundle
  shape.
- `corpus-truth.json` — GENERATED ground truth: the 20 planted defects (file, build/execute lines,
  `acceptable_lines` window, shape, tainted source), the 15 decoys, the 45 clean files. The verifier
  scores against this file.
- `false-positive-traps.md` — human-readable decoy catalogue (reviewer provenance).
- `scoring-anchors.md` — construct, scored artifact, the A8-BLOCKER avoidance, budget enforcement, and
  the four-probe validation table.
- `generate_corpus.py` — deterministic corpus + ground-truth generator (seed 20260712). Re-running
  reproduces the corpus and `corpus-truth.json` byte-identically.
- `gen_reference_candidates.py` + `reference-candidates/` — the four-probe reference and adversarial
  candidate answers, derived from the ground truth.

Regenerate everything:

```
python oracle/generate_corpus.py
python oracle/gen_reference_candidates.py
```
