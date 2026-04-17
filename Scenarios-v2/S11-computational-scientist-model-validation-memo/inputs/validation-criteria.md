# E4 Validation Criteria

The lab will treat the model as scientifically admissible for the admitted range only if all of the
following hold on the supplied validation packet.

## Quantitative criteria

1. profile-A mean absolute error must be `<= 1.5 C`
2. profile-B mean absolute error must be `<= 1.5 C`
3. the max absolute residual after the first `2 min` must be `<= 3.0 C` on each profile
4. if the trace crosses `48 C`, the predicted crossing time must be within `+/- 75 s` of the
   measured crossing time
5. on constant-power segments, the plateau or steady-state level must be within `+/- 1.5 C`

## Physical consistency checks

A passing memo must also state whether the draft model preserves these invariants:

- parameter signs remain physical: `C_eff > 0`, `K_loss > 0`
- units stay explicit and dimensionally consistent
- with constant positive power and fixed ambient, the one-state model should move monotonically
  toward `T_ss` without oscillation
- with `P_in = 0` and `T > T_amb`, the model should cool rather than self-heat

## Decision rule

If any criterion fails, the memo should not declare the current model fully validated for the full
admitted range. It may recommend a narrower admissible range or a revised model class.
