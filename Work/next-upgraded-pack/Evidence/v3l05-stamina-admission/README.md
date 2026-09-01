Date: 2026-07-12
Owner: `$knowledge-archivist`
Item: F1 (Phase-3, A6) — stamina family admission evidence

# V3L05 stamina-migration — admission evidence

Durable, hashed provenance for the `V3L05-stamina-migration-{s,m,l}` family (BUILD-PLAN
v2.1 item F1). Moved out of gitignored `.scratch/` per the review-loop synthesis rule
("move admitted material OUT of `.scratch/` into `Work/` and hash it").

## Contents

| Path | What |
|---|---|
| `generate/gen_stamina.py`, `generate/gen_main.py` | deterministic generator that materialises the three roots (rewrites them idempotently) |
| `generate/check_stamina_migration.py` | canonical verifier template projected byte-identically into all three generated roots |
| `generate/make_probes.py` | builds each probe candidate (reference / partial / decoy-blanket / visible-only / keyword-stuffed) from the committed starter + hidden oracle |
| `four-probe-metrics/*.json` | the metrics emitted by `check_stamina_migration.py --metrics-out` for every probe below |
| `admission.json` | machine-readable four-probe summary + variant params |
| `sha256-manifest.json` | sha256 of every committed bundle file + this evidence dir |

## Four-probe validation (all on the long variant unless noted)

| Probe | Candidate | breadth_fraction | verdict | why |
|---|---|---|---|---|
| 1 reference PASS | complete migration | 1.0 | PASS | a correct full migration scores 1.0 (also PASS on s & m) |
| 2a vacuous | untouched starter | 0.0 | FAIL | no migration |
| 2b keyword-stuffed | ledger claims all migrated, code untouched | 0.0 | FAIL | verifier scores behaviour, not keywords |
| 3a adversarial decoy-blanket | all consumers migrated + decoys corrupted | 1.0 | FAIL | 18 false-positives trip the precision floor (right shape, wrong substance) |
| 3b stop-when-tests-green | only the 2 visible-covered anchors migrated | 0.056 | FAIL | visible tests go green early; the rest are hidden |
| 3c truncated-60% | 22/36 consumers migrated | 0.611 | FAIL | below the 0.90 task-intrinsic bar |
| 4 near-peer split | A=1.0/1.0/1.0, B=1.0/0.94/0.92, C=1.0/0.83/0.61 | — | A,B all-PASS; C PASS/FAIL/FAIL | A and B both clear every binary bar yet separate on graded fraction + completion-vs-length slope (A drop 0.0 vs B drop 0.083, slope -0.028/10); C separates on binary + slope -0.137/10 |

## Confound avoided ("measuring the wrapper, not the model")

- Each per-consumer edit adds three short fields, so the whole migrated diff is a few
  hundred tokens (well under any default output-token cap — see
  `discrimination.yaml:harness_properties.expected_output_tokens_upper_bound`). The
  output cap is NOT the binding constraint, so a fraction difference is stamina, not
  budget.
- Resource limits (max output tokens, context config) are pinned identically for both
  providers and recorded in telemetry (harness properties, declared in
  `discrimination.yaml`).
- The fraction→P/F threshold (0.90) is pre-registered from TASK-INTRINSIC grounds
  (atomic shared contract; visible tests cover only 2/N, far below the bar) and is fixed
  before any target-model run.
- The "reads all-P for frontier models" risk is met by the GRADED fraction + SLOPE across
  the matched triplet, which separate near-peers (Model A vs B) even when both pass every
  binary gate.

## Reproduce

```
python generate/gen_main.py <benchmarks-root>
# then, from <benchmarks-root>:
python generate/make_probes.py --root Scenarios-v3/V3L05-stamina-migration-l --out <tmp>/ref/candidate --mode reference
python Scenarios-v3/V3L05-stamina-migration-l/verifiers/check_stamina_migration.py --candidate-root <tmp>/ref/candidate
```
