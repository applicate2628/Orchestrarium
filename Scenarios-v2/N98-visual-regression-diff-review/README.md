# N98 Visual Regression Diff Review

`N98` targets `L12 review.ui-visual-correctness` with a baseline/current screenshot pair. The
worker must identify actual visual regressions in the current screenshot, avoid intentional
non-findings, and ground each finding with pixel coordinates.

This is diagnostic-only unless a later slot-replacement decision names the outgoing `/40` visual
review slot.
