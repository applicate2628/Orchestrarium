# Validation And Invariant Anchors

The completed memo should include content close to the anchors below.

## Governing-equation anchors

- `EQ1`: the lumped-capacitance energy balance `C_eff * dT/dt = P_in - K_loss * (T - T_amb)`
- `EQ2`: the derived time constant `tau = C_eff / K_loss` and steady-state relation
  `T_ss = T_amb + P_in / K_loss` for constant input
- `EQ3`: an explicit statement that the current draft assumes one state and one fixed loss
  coefficient over the whole run

## Assumption anchors

- `AS1`: the block-body lumped assumption is dimensionally plausible from the small Biot number
- `AS2`: ambient and power are treated as piecewise-known inputs over each validation segment
- `AS3`: sensor temperature is only an approximate proxy for the core under fast transients
- `AS4`: the fan-regime change is outside the current fixed-`K_loss` formulation

## Units and invariant anchors

- `IV1`: units for `C_eff`, `K_loss`, `P_in`, `T`, `tau`, and `T_ss` are explicit
- `IV2`: `C_eff > 0` and `K_loss > 0` are required physical sign constraints
- `IV3`: under constant positive power and fixed ambient, the one-state model approaches
  `steady-state` monotonically without oscillation
- `IV4`: with `P_in = 0` and `T > T_amb`, the model cools rather than self-heats

## Validation anchors

- `V1`: Profile A passes the mean absolute error criterion from `E4`
- `V2`: Profile B fails the mean absolute error criterion from `E4`
- `V3`: Profile B reaches or exceeds the max-residual tolerance after minute `2`
- `V4`: the threshold-crossing timing is acceptable, but the plateau and cooldown behavior are not
- `V5`: the validation conclusion is based on the criteria plus the anomaly notes, not intuition

## Limitation anchors

- `L1`: sensor lag limits how strongly early transient mismatch can be interpreted
- `L2`: the fan-regime change means one constant `K_loss` is not valid over the full range
- `L3`: ambient drift and power quantization add measurement uncertainty
- `L4`: no data exists outside the admitted range, so the memo must not generalize beyond it
