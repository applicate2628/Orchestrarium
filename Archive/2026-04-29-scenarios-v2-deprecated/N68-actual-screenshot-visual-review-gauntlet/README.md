# N68 Actual Screenshot Visual Review Gauntlet

`N68` benchmarks visual review on an actual screenshot image rather than a text-only DOM/CSS packet.
The worker receives one dashboard screenshot and must return exact seeded visual defects with
component names, defect classes, and approximate pixel coordinates.

## Expected Candidate Work

Edit only `candidate/answer.json`.

The result must be JSON. The verifier reads the JSON and checks:

- exactly eight matched visual defects
- component and defect terms bound to the seeded oracle
- coordinates inside the accepted tolerance window
- no false-positive findings on decorative grid, disabled export, or muted timestamp content

## What This Bundle Tests

- actual screenshot grounding
- small UI defect localization
- visual review without relying only on DOM/source prose
- false-positive discipline on visually plausible but intentional UI states
