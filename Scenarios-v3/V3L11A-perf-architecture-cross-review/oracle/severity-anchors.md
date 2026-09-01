# Severity Anchors

- blocking: scales super-linearly with batch size or reconstructs an expensive owner per request; will
  degrade the hot path under load. F1 (per-request rebuild) and F2 (quadratic re-resolve).
- major: steady-state cost that grows with process lifetime or pays avoidable work every batch. F3
  (unbounded retention) and F4 (unconditional serialization).
- minor: reserved for bounded, low-impact costs. None required here.

Severity is matched exactly by the verifier, so mislabeling F1/F2 as major or F3/F4 as blocking fails
the corresponding required-finding match.
