# Review Boundary

The review is limited to objective visual correctness defects in the provided target. A valid
finding needs source binding plus screenshot-probe or state-matrix evidence.

In scope:

- overlap, clipping, occlusion, invisible state, insufficient required-text contrast
- responsive regressions visible in the provided viewport probes
- visual states that contradict the state matrix

Out of scope:

- code refactors or implementation patches
- pure accessibility semantics when no visual defect is present
- subjective taste, brand style, copy edits, or feature requests
- harmless decorative elements and intentionally muted metadata
