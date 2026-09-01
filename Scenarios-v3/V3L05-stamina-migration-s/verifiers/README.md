# Verifiers — V3L05 stamina migration

## `check_stamina_migration.py`
Graded breadth-completeness scorer.

| Mode | Command |
|---|---|
| bundle shape | `python check_stamina_migration.py --bundle-shape-only` |
| score a candidate | `python check_stamina_migration.py --candidate-root <dir>/candidate --metrics-out <path>` |
| production | runner sets `BENCH_EXEC_ROOT` (oracle-free exec root); oracle is read from the private scorer bundle root |

Scoring:
- `breadth_fraction = migrated_correct / total_consumers` (graded 0..1), where a
  consumer is "correct" iff calling its `quote_*` function returns the exact expected
  v2 record from `oracle/stamina-contract.json`.
- PASS iff `breadth_fraction >= pass_fraction` (pre-registered) AND no `report_*` /
  `audit_*` decoy was changed (`false_positives == 0`) AND the workspace imports and
  the visible tests pass (floor).
- Emits `--metrics-out` JSON: `breadth_fraction`, `completed_count`, `missed[]`,
  `false_positives[]`, `points`, `verdict`, `failure_ids`.

Candidate code is executed from `BENCH_EXEC_ROOT` when set (H9 exec-root topology), so
the scorer never runs candidate code inside a tree that contains `oracle/`.

## `compute_stamina_slope.py`
Reads the three per-variant metrics files and reports the completion-vs-length slope
(the near-peer separation signal). See `oracle/scoring-anchors.md`.

```
python compute_stamina_slope.py --short s.json --medium m.json --long l.json --out slope.json
```
