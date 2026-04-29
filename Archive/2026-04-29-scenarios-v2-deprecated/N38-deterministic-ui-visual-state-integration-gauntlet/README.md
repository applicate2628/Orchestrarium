# N38 Deterministic UI Visual State Integration Gauntlet

This diagnostic surface tests whether a worker can keep UI state, rendered accessibility
semantics, responsive layout geometry, and deterministic raster output coherent across staged
fresh invocations.

The bundle is intentionally browserless. The oracle probes JavaScript state/view/layout modules
with Node and probes raster pixels through deterministic RGB arrays and PPM metadata.
