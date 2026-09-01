# Verifier

`check_blind_audit.py` scores the blind SQL-injection audit by **recall at a fixed precision floor**
under an identical enforced budget. It never executes candidate code (the corpus is audit text), so it
needs no exec root.

## Usage

```
# bundle-shape check (structure only)
python verifiers/check_blind_audit.py --bundle-shape-only

# score the committed candidate/answer.json
python verifiers/check_blind_audit.py

# score an alternate candidate (reference / probe answers)
python verifiers/check_blind_audit.py --candidate-root oracle/reference-candidates/reference

# supply telemetry for the budget flag (else it auto-tries <bundle_root>.parent/meta/summary.json)
python verifiers/check_blind_audit.py --telemetry /path/to/summary.json
```

Under the v2.1 harness the runner auto-passes `--bundle-root <score>` and `--changed-path`, runs from
the `score/` root, and scores `candidate/answer.json` overlaid from the imported output.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | PASS (bundle shape, or scored: recall >= 0.70 AND precision >= 0.80) |
| 1 | SCORED-FAIL (quality: recall below threshold, or precision below floor) |
| 2 | NOT-SCOREABLE / NR (missing or invalid answer.json, missing corpus/truth, parse failure) |
| 3 | BUDGET-VIOLATION (telemetry present and outputTokens above the pinned cap — disqualified) |

Cost (tokens, wall clock, cost USD) is reported only as a DEFERRED, ASSUMPTION-labeled diagnostic
(I6); it is never part of the score.
