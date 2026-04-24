# N60 UI Visual State Reentry Packet

This diagnostic surface tests whether a worker can keep UI state, rendered accessibility
semantics, responsive layout geometry, and deterministic raster output coherent in one
single-session reentry patch.

The bundle is intentionally browserless. The oracle probes JavaScript state/view/layout modules
with Node and probes raster pixels through deterministic RGB arrays and PPM metadata.
