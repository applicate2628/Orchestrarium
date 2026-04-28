# N80 Screenshot Grounding Review v2

`N80` is a calibrated visual-review separator for high-resolution screenshot grounding. The worker
receives one dashboard screenshot and must return exact seeded visual defects with component names,
defect classes, severity labels, and approximate pixel coordinates.

## Expected Candidate Work

Edit only `candidate/answer.json`.

The result must be JSON. The verifier reads the JSON and checks:

- exactly ten returned findings, with at least the configured pass-threshold matched to seeded defects
- component and defect terms bound to the seeded oracle
- coordinates inside a tighter accepted tolerance window than N68
- severity labels present for every finding
- no false-positive findings on intentional visual states and traps

## What This Bundle Tests

- actual screenshot grounding under dense UI context
- small UI defect localization with calibrated pixel tolerance
- visual review without relying on DOM/source prose
- false-positive discipline on visually plausible but intentional UI states
- output discipline under a strict JSON contract
