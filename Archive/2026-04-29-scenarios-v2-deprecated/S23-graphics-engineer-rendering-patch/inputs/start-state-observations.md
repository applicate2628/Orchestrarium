# Start-State Observations

The bundled candidate root is expected to fail exactly these deterministic oracle cases before any
repair is applied:

- `transparent-ordering`: transparent draws are processed near-to-far instead of back-to-front
- `transparent-depth-preserves-spark`: a transparent draw writes depth and blocks a later additive
  pass
- `additive-glow-accumulates`: additive emission is composited with alpha-over instead of
  accumulated

The bundle should still pass the non-failing anchor cases that verify the base opaque and depth-test
behavior.
