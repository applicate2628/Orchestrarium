# Expected Model Read

The expected memo should treat the task as scientific model validation, not as implementation or
policy work.

## Expected formulation

- write the one-state energy balance from `E2` explicitly and define `T(t)`, `P_in(t)`, `T_amb`,
  `C_eff`, `K_loss`, `tau`, and `T_ss`
- note that the admissible quantity is block core temperature over the `20..60 C` and `0..30 min`
  window from `E1`
- use the Biot estimate in `E2` to argue that the aluminum block itself can be modeled as a
  lumped body, while keeping sensor-core mismatch separate from that claim

## Expected validation read

- Profile A is a scientific pass for the current model on ordinary warmup: the listed residuals,
  mean absolute error, and max error all satisfy `E4`
- Profile B is not a pass for the same fixed-loss model: the profile-B mean absolute error and max
  residual breach `E4`, and the post-threshold segment is inconsistent with one constant `K_loss`
- the near-correct `48 C` crossing time does not rescue the full validation result because the
  plateau and cooldown behavior remain outside the accepted tolerances

## Expected disposition

The correct disposition is `REVISE`, not `PASS` and not `BLOCKED`.

Why `REVISE`:

- the model form is not physically absurd; it is useful as a starting point
- the evidence packet is sufficient to judge the current model
- the current fixed-loss single-state formulation is not validated across the full admitted range

The memo may recommend one of these bounded scientific follow-ups:

1. restrict the current model to the pre-threshold region where the fan regime does not switch
2. revise the model to include a piecewise loss coefficient or a second sensor/core state before
   claiming full-range validity

The memo should state those as model-validation recommendations, not as implementation tasks.
