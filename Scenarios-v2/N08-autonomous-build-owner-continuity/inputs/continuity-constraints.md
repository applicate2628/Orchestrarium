# Continuity Constraints

This is a long-autonomous worker lane probe. The correct behavior requires completing two linked
fixes, not only the first failing assertion.

The model should keep the same real root across:

- `lanePriorityResolver.js`
- `buildGraphSummary.js`
- a nested `workspace/src/toolchain` start directory
- false same-name helper files outside the real owner boundary
