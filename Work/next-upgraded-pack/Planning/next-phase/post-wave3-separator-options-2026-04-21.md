Date: 2026-04-21
Owner: `$lead`
Status: `DRAFT`

# Post-Wave-3 Separator Options — Strategic Planning for Next Session

## Context

Three hardening waves are complete and admitted on `2026-04-21`:

- **Wave 1 (pilot)**: `N06 authz-trust-boundary-review` rebuilt with tuple-exact verifier on
  `(file, line, category, severity, title, evidence)` findings. Binary tie remains.
- **Wave 2 (five cells)**: `S27`, `S28`, `S29`, `N05`, `N07` rebuilt with the same tuple-exact
  template plus `\|` escape / trailing-cells merge parser fix. Binary tie remains across all five.
- **Wave 3**: `S06 analyst-repository-fact-memo` rebuilt as three-table tuple-exact scenario
  (`Confirmed Facts`, `False Leads Rejected`, `Explicit Unknowns`) with abstract
  `noisy-intake-notes.md` that no longer names the false-lead files. Binary tie remains.

Seven cells are now tuple-exact hardened inside the `12+1` surface. Every one of them
legitimately ties `PASS / PASS` for `X1 / gpt-5.4` and `X3 / opus 4.7max`. The hardening
closed the compliance-retelling path on both review-class (`N06`, `S27`, `S28`, `S29`, `N05`,
`N07`) and factual-investigation (`S06`) surfaces.

Near-ceiling separation of X1 and X3 was not unlocked by leak removal on either surface
class. The two remaining under-explored surfaces are:

1. `(a)` Harder tests inside the already-functional implementation scenarios.
2. `(c)` A net-new multi-file code patch scenario.

This doc scopes and sequences both so the next session can pick up with full context.

## Option (a) — Harder Tests in Functional Implementation Cells

### Scope candidates

| Cell | Surface | Current verifier | Proposed tightening |
|---|---|---|---|
| `S15` | backend owner seam | `pytest` on candidate patch | add adversarial input cases that distinguish correct API shape from near-miss shapes |
| `S16` | frontend web ui | `node scripts/validate_...` + sha256 protected hashes | add input fixtures that cover edge interaction states near the gate boundary |
| `S17` | qt desktop ui | qt widget interaction tests | add focus-trap/key-chord edge cases that test near-correct implementations |
| `S18` | model/view correctness | proxy ordering tests | add tied-key and stable-sort edge cases |
| `S19` | data pipeline | `node scripts/validate_customer_day_rollup.py` | add late-arriving records and boundary-time cases |
| `S20` | platform observability | `validate_observability_patch.py` | `leak` warning in audit: task.md names the exact end-state values; rewrite task.md to describe the constraint abstractly and let the validator enforce |
| `S21` | toolchain ownership | publish-surface validator | same pattern as `S20` — abstract task.md |
| `S22` | geometry predicate | truth-table JSON exact match | add boundary-tolerance cases and degenerate-polygon cases |
| `S23` | graphics rendering | deterministic frame checks | add blend-mode and depth-test edge cases |
| `S24` | visualization encoding | JSON structural equality | add zero-centered diverging and sparsity-gap edge cases |
| `N08`–`N10` | autonomous long-form | `node --test` | add adversarial inputs that previous sessions of the model would mis-handle |

### Priority pick for wave 4 pilot

**Pick `S22 geometry-predicate-patch`** as the wave-4 pilot because:

- The existing verifier is already tuple-exact (truth-table JSON) — no framework change needed.
- Adversarial inputs are structural, not behavioral — can be added by extending the truth table
  with near-miss cases without reshaping the candidate surface.
- Geometry predicates have a clean near-ceiling vs real-correctness gap: a model that
  "understands the convention" passes the easy cases but fails boundary cases.
- Does not require contract redesign — just extending `oracle/truth-table.json`.

Secondary pick: `S20` / `S21` — the audit flagged them as having answer-leak in `task.md`
itself (the task names the exact config values to produce). Abstract-ing the task is a
smaller delta than rewriting tests.

Avoid `S23` / `S24` in the first pilot — GPU-adjacent and visualization oracles are harder
to calibrate without visual inspection.

### Wave-4 pilot plan (`S22` adversarial extension)

1. Read the current `oracle/truth-table.json` and `verifiers/run_geometry_checks.py`.
2. Identify the current case coverage (right-handed vs left-handed, signed area tolerance,
   degenerate polygons).
3. Design 8–12 new adversarial cases: degenerate triangles, collinear-points, near-zero
   signed area, winding-number edge cases, numerical instability at small scales.
4. Extend `oracle/truth-table.json` with the new cases.
5. Dry-run the existing candidate against the extended oracle — it should PASS if the
   current implementation is correct on the edge cases; if it fails, either the hardening
   uncovered a real defect or the oracle case is ambiguous (investigate and resolve).
6. Launch `X1`/`X3` on the hardened `S22` and read the binary result.

### Expected outcome

`S22` has the best shape for a true binary separator because geometric predicates have an
unambiguous right answer and near-miss implementations are easy to construct. If near-ceiling
models genuinely both understand the convention, they both pass the edge cases; if not, the
adversarial cases separate them cleanly. Either outcome is useful: a separator advances the
search; a tie confirms the ceiling is real even on structural edge cases.

## Option (c) — New Multi-file Code Patch Scenario

### Rationale

The existing patch-style scenarios (`S15`–`S24`, `N08`–`N10`) target known coupling patterns
inside a single module or a well-framed test surface. They do not exercise multi-hop
reasoning across a multi-file dependency graph with decoy defects that *look* like bugs but
are actually correct under the constraints.

### Scenario sketch (`N14-multi-file-dependency-patch` — working name)

- `candidate/review-target/` — a 5–8 file codebase with deliberate dependency coupling:
  - a public API (`api.py`) that calls an internal helper (`helper.py`)
  - a config loader (`config.py`) that validates inputs
  - a serializer (`serialize.py`) that renders output
  - a test harness (`test_api.py`)
- 4–6 real defects spread across 3+ files (some defects require tracing through the call
  graph to identify — cannot be found by reading any one file in isolation)
- 4–6 adversarial decoys: code patterns that look suspicious but are correct under the
  constraints in `config.py` (e.g., a seemingly-unchecked attribute that is actually
  validated at construction time in a separate file)
- `oracle/patch-contract.json` with `(file, line, category, severity)` tuples for real
  defects + `forbidden_findings` for adversarial decoys
- Verifier reuses the wave-2 tuple-exact parser

### Expected signal

Near-ceiling models that reason well across files pass; models that reason one file at a
time either miss real defects (they span files) or flag decoys (they look suspicious
locally). The multi-file reasoning surface is the most likely to separate near-ceiling
models structurally, because it is the first task type where "reading more carefully" on
one file is not enough.

### Cost

Authoring this scenario is substantial: 5–8 files of real code, real tests, real defects,
real decoys, plus oracle and verifier. Realistically a full session of its own.

## Recommended sequence for next session

1. **Start with wave 4 pilot on `S22`** — smallest delta, existing verifier shape works, can
   likely land inside one session including X1/X3 runs.
2. **If `S22` separates**, extend adversarial-input approach to one or two more patch cells
   (`S15` backend seam is the next candidate).
3. **If `S22` still ties**, shift to `(c)` new multi-file scenario — the remaining
   under-explored surface.
4. **Do not harden more review-class cells** — seven are already hardened and all tie; adding
   more of the same shape does not add signal.
5. **Always preserve `candidate/repo-snapshot/`** and similar real-code directories unchanged;
   hardening should happen through contract and verifier changes, not code changes, so the
   task itself remains authentic.

## Not in scope for next session

- Hardening the remaining `~35` cells that were not flagged by the audit. Those are either
  structurally hopeless for near-ceiling separation (`S03`, `S32`, `S33`) or already strong
  (`S15`–`S24` in their current form). Do not touch them.
- Rerunning `X4` — the secret-backed Claude route still returns `502 unknown provider for
  model claude-opus-4-7` as of `2026-04-21`; wait for route recovery.
- Rerunning `X5` — Gemini Pro runtime timeouts persist on the diagnostic slice; out of scope
  until runtime recovers.
- Adding a new external-opinion layer. The E3 rubric is already admitted and does not
  separate the pair beyond the one-point `N13 denominator reporting` delta. Adding more
  rubrics of the same shape is low-yield.

## Caveat: final 12+1 shape

Seven tuple-exact cells (`N06`, `S27`, `S28`, `S29`, `N05`, `N07`, `S06`) are now the
`compliance-retelling-resistant anchor set` inside the `12+1` surface. They do not separate
the top pair but are honest about why they do not. In any final publication they should be
retained as ceiling-legitimacy indicators, and the separator — if one exists — should come
from the remaining surface classes (`S15`–`S24`, `N08`–`N10`, or a new `(c)` cell).
