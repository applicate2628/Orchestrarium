# Scoring anchors -- V3L05 stamina (m)

## Graded measure
- `breadth_fraction = migrated_correct / 18` (0..1), reported per run.
- `points = round(breadth_fraction * 100)`.

## Binary cell verdict (pre-registered, task-intrinsic)
- PASS iff `breadth_fraction >= 0.9` AND `false_positives == 0`.
- Rationale for 0.9: the migration is ONE atomic contract shared by all
  consumers; leaving >10% of consumers on the legacy contract means a randomly drawn
  consumer has >10% chance of emitting a broken record -- a materially incomplete
  migration. The visible tests cover only 2 of 18 consumers
  (11.1%), far below the bar, so a "stop when tests pass" model fails by
  construction. The threshold is fixed BEFORE any target-model run and is immutable.

## Near-peer separation
- The binary bar alone risks reading all-PASS for strong large-context models on a
  mechanical task. The discriminating signal is therefore the GRADED fraction (median
  across repeats) and the completion-vs-length SLOPE across the matched triplet:
  `slope` of `breadth_fraction` vs `total_consumers` (see
  `verifiers/compute_stamina_slope.py`). A stamina-strong model holds ~1.0 across
  s/m/l (flat slope ~0). A stamina-weaker peer that both pass the short variant still
  separates by a steeper negative slope and a lower long-variant fraction.
- The short-but-deep sibling is `Scenarios-v2/N72-caller-spanning-api-refactor-scorecard`
  (4 caller surfaces, deep, binary). Passing long-breadth here while failing N72
  (or vice versa) isolates stamina from depth.

## False-positive (precision) floor
- Any change to a `report_*` or `audit_*` decoy is a false-positive and FAILS the cell
  regardless of `breadth_fraction`. This kills the "blanket-edit every return dict"
  adversarial shortcut, which would otherwise score high breadth with wrong substance.
