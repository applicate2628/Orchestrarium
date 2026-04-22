# Expected Findings

The ground-truth report for `N07` must return `REVISE` with exactly these three findings,
presented as a structured table under `## Findings`.

## Ground-truth finding tuples

| # | File | Line (any of) | Category | Severity | Title anchor | Required evidence terms |
|---|---|---|---|---|---|---|
| F1 | `candidate/review-target/routing-matrix/assemble_lane_matrix.py` | `21`–`24`, `33`–`36` | `scalability` | `blocking` | every lane rescans the full scenarios tree | `collect_lane_members`, `iterdir` |
| F2 | `candidate/review-target/routing-matrix/lane_basis.py` | `1`–`4` | `maintainability` | `blocking` | lane-basis membership duplicated across `lane_basis.py` and `lane_catalog.py` | `lane_basis.py`, `lane_catalog.py` |
| F3 | `candidate/review-target/routing-matrix/assemble_lane_matrix.py` | `7`, `48`–`50` | `memory` | `major` | snapshot history grows without bound | `HISTORY.append`, `json.dumps` |

Line tolerance: the candidate must cite one of the listed lines per finding.

Finding count: exactly three.

## Forbidden findings (false-positive traps)

| Title keyword group | Reason |
|---|---|
| `lane label`, `labels presentation`, `presentation data` | lane labels are harmless presentation data |
| `unassigned`, `resolve_lane return` | returning `unassigned` from `resolve_lane` is not the defect |
| `small tuple`, `local literal`, `small list` | small local literals are acceptable when not competing maintained owners |

## Required false-positive mentions

The `## False Positives Avoided` section must mention both `lane_catalog` and `unassigned`.

## Expected gate

`REVISE`
