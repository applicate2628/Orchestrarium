# Scoring anchors — V3LTA blind-audit (working-audit family, F2 / A8-revised)

## Construct

Wide-shallow single-aspect blind audit: recall of ONE planted defect class (SQL injection) across 80
small files under a **fixed, identically-enforced output budget**. The budget is the forcing function —
it makes coverage-vs-depth a real tradeoff. Without it, every strong model deep-dives everything and
recall saturates (no separation); with it, the profile that triages breadth efficiently wins on recall.

## Scored artifact (the sufficiency gate)

`score = recall = TP / total_defects`, GATED by a pre-registered **precision floor**:

- `precision_floor = 0.80`  — if `precision = TP / (TP + FP) < 0.80`, the run FAILS regardless of recall.
- `recall_pass_threshold = 0.70` — PASS requires `recall >= 0.70` AND `precision >= 0.80`.
- `total_defects = 20`, `decoys = 15`, `clean = 45`.

Matching is location-only and deterministic: a finding is a TP iff its file basename matches a planted
defect and its cited line is inside that defect's `acceptable_lines` window (build-line..execute-line,
padded +/-1). Every finding that matches no defect window is an FP. This is why flagging a decoy, a
clean file, or a wrong line drops precision.

## What this family deliberately does NOT do (A8 BLOCKER avoided)

- **No cost denominator.** Cost/latency/tokens are NEVER divided into the score. There is no
  coverage-per-cost metric. `summary.json` carries no validated cost measure; file-mtime and
  output-bytes are verbosity/infra proxies, not cost. Cost-superiority for the working-audit profile
  stays an `ASSUMPTION (UNVERIFIED)` diagnostic (I6), deferred until telemetry variance is known (P3).
- **Brevity is not the skill.** A disciplined strong model that is wide AND terse under the cap can win
  — and if it does, that is a legitimate measurement, not a confound. `expected_winner: working-audit`
  is a pre-registered HYPOTHESIS, not a construction that forces Terra to win; `validated_discrimination`
  starts `none`.

## Budget enforcement

The output-token cap (`6000`) and turnaround timeout (`900000 ms`) are HARNESS properties pinned
identically for all four profiles by the v2.1 runner (same mechanism as F1). The verifier does not
generate under the cap; when a telemetry `summary.json` is available it flags an over-cap run as a
non-scoring `BUDGET-VIOLATION` (exit 3) — a defense-in-depth demonstration of enforcement. Absent
telemetry, the budget is assumed harness-enforced.

## Four-probe validation (all runnable via `verifiers/check_blind_audit.py --candidate-root ...`)

| Probe | Candidate (`oracle/reference-candidates/<name>`) | Expected |
|---|---|---|
| reference PASSES | `reference` | PASS — recall 1.0, precision 1.0 |
| realistic PASS | `breadth-triager` | PASS — recall 0.8, precision ~0.94 |
| vacuous FAILS | `vacuous-keyword` | SCORED-FAIL — recall 0, precision below floor |
| over-flag FAILS | `shotgun` | SCORED-FAIL — precision 0.25 |
| decoy-following FAILS | `decoy-follower` | SCORED-FAIL — precision below floor (right shape, wrong substance) |
| near-peer separation | `over-analyzer` vs `breadth-triager` | over-analyzer FAILS (recall 0.25, precision 1.0); breadth-triager PASSES |

The last row is the discriminator's teeth: a high-precision **depth-first** strong model (over-analyzer:
covered only the defects in the first 12 files under the budget) FAILS on breadth, while a
**breadth-first** strong model PASSES — separating two near-peer strong models that both have perfect
precision, purely on budget-bounded coverage.

## Exit-code separation (route/runtime vs quality)

- `0` PASS / `1` SCORED-FAIL (quality) / `2` NOT-SCOREABLE (NR: missing/invalid answer, parse failure)
  / `3` BUDGET-VIOLATION. A parse/route/runtime failure is NR (2), never a model-quality FAIL.
