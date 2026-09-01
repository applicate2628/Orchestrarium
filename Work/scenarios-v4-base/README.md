# Scenarios v4 Base Work Pack

This mutable work area contains the deterministic v4 scorer and calibration-only roots. The four
`V4C*` fixtures validate the mechanism and are not ranking-denominator entries. No provider runner,
model output, freeze manifest, or archived result belongs to this phase.

## Identity Principle

Scored candidate identity must use only visible or directly derivable vocabulary. For L09 review
roots, `anchor_source_id` is the sole candidate identity field, and every expected rubric identity
key is a source-card ID that appears in the visible source cards. Hidden oracle IDs, legacy internal
finding names, model-invented witness IDs, and diff/output heading suffixes are not match targets.

The source-card ID is an evidence pointer, not a dictated conclusion. Cards provide raw diffs,
outputs, and measurements; the candidate still has to derive which cards are defects, which are safe,
how evidence binds across cards, what severity and action are appropriate, and whether merge clearance
is safe.

Run the local checks from the benchmark root:

```powershell
python -m unittest discover -s Work/scenarios-v4-base/Tooling/tests -v
python Work/scenarios-v4-base/Tooling/validate_calibration.py
```

## Terms and Abbreviations

- `F1`: harmonic mean of precision and recall.
- `L09`: pre-pull-request review lane.
- `v4`: the deterministic partial-credit benchmark generation under construction.
