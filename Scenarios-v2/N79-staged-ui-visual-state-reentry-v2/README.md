# N79 Staged UI Visual State Reentry Packet

This diagnostic surface tests whether a worker can keep UI state, rendered accessibility
semantics, responsive layout geometry, and deterministic raster output coherent in one
bounded staged reentry patch.

The bundle is intentionally browserless. The oracle probes JavaScript state/view/layout modules
with Node and probes raster pixels through deterministic RGB arrays and PPM metadata.

N79 exists to replace the brittle N38 staged UI branch with a short, scoreable staged workflow.
The task keeps the same real UI-state failure classes as N60, but splits the work into source
ledger, state/render implementation, layout/raster implementation, and reentry closeout phases.
