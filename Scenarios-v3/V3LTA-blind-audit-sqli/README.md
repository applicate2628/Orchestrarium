# V3LTA — blind single-aspect audit (working-audit family)

Wide-shallow blind audit of an 80-file handler corpus for ONE planted defect class (SQL injection)
under a fixed, identically-enforced output budget. The scored artifact is **recall at a fixed
precision floor** (precision floor 0.80, recall pass threshold 0.70) — NOT coverage-per-cost. Cost is a
deferred, ASSUMPTION-labeled diagnostic (I6); there is no cost denominator (the A8 BLOCKER is avoided).

- `expected_winner`: `working-audit` (pre-registered hypothesis; `validated_discrimination: none`).
- rf12 line: `LTA` (new working-audit lane; 4-way table only — mapped into review lanes for the 2-way
  read per I5). Aggregator lane-map registration is an integration step owned by the main loop.
- Build lineage: Phase-3 F2 of BUILD-PLAN v2.1 (A8-revised), review-loop-synthesis A8 constraint.

## Layout

| Path | Role |
|---|---|
| `inputs/task.md` | audit task + output contract (candidate-visible) |
| `inputs/corpus/h001..h080.py` | the 80 audit-target files (candidate-visible) |
| `candidate/answer.json` | the candidate's findings (the only editable file) |
| `oracle/blind-audit-contract.json` | scoring policy (hidden) |
| `oracle/corpus-truth.json` | generated ground truth (hidden) |
| `oracle/generate_corpus.py` | deterministic corpus + truth generator |
| `oracle/gen_reference_candidates.py`, `oracle/reference-candidates/` | four-probe candidates |
| `oracle/false-positive-traps.md`, `oracle/scoring-anchors.md` | decoy catalogue + scoring anchors |
| `verifiers/check_blind_audit.py` | recall@precision-floor scorer (no candidate-code exec) |
| `discrimination.yaml` | S2 profile metadata (never staged to the provider root) |

## Four-probe validation

See `oracle/scoring-anchors.md`. Reference PASSES; vacuous/shotgun/decoy-follower FAIL; over-analyzer
(depth-first, high precision, low recall) FAILS while breadth-triager PASSES — the near-peer
separation on budget-bounded coverage.
