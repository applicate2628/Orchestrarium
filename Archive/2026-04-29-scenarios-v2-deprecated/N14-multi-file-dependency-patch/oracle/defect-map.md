# Defect Map

| id | owner file | category | Expected correction |
|---|---|---|---|
| D1 | `candidate/workspace/src/routing_eval/config.py` | source precedence | `activeProfile` plus plural `externalPriorityProfiles` owns routing order; singular `externalPriorityProfile` is fallback selector only |
| D2 | `candidate/workspace/src/routing_eval/status.py` | scoreability classification | route/runtime/quota/missing-output rows are non-scoreable; verifier failures remain scoreable |
| D3 | `candidate/workspace/src/routing_eval/scorecard.py` | denominator semantics | pass/fail denominator counts scoreable rows only |
| D4 | `candidate/workspace/src/routing_eval/render.py` | visible caveat reporting | report lines separate scoreable failures from non-scoreable caveats |

Forbidden decoys: `docs/legacy-profile-notes.md`, `legacy/legacy_score.py`, and `ui/chip_labels.py`
look relevant but do not own runtime behavior.
