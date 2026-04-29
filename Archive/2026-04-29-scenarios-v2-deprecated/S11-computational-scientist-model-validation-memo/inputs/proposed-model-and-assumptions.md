# E2 Proposed Model And Assumptions

The draft model is a single-state lumped-capacitance thermal model:

`C_eff * dT/dt = P_in(t) - K_loss * (T - T_amb)`

with the derived relations for constant `P_in`:

- `tau = C_eff / K_loss`
- `T_ss = T_amb + P_in / K_loss`

## Draft parameter set

- effective thermal capacitance `C_eff = 410 J/K`
- effective loss coefficient `K_loss = 0.78 W/K`
- implied time constant `tau = 526 s` or about `8.8 min`

## Draft modeling assumptions

1. internal temperature can be represented by one state variable `T(t)`
2. heater power is piecewise constant over each logged interval
3. ambient temperature is approximately constant within each short validation segment
4. radiative loss below `60 C` is small relative to the convective and conductive loss lumped into
   `K_loss`
5. the aluminum block is close enough to isothermal internally for a lumped-capacitance treatment
   to be dimensionally plausible

## Dimensional note

Using `h ~= 18 W/(m^2*K)`, `L_c = 0.006 m`, and `k = 167 W/(m*K)` gives an estimated Biot number
`Bi ~= 0.0006`. That supports the block-body lumped assumption, but it does not by itself prove
that the external sensor perfectly matches the core temperature during fast transients.

## Known omission in the draft

The draft model keeps `K_loss` constant across the full trace. It does not resolve any sensor-core
lag and does not model a controller-driven fan regime change.
