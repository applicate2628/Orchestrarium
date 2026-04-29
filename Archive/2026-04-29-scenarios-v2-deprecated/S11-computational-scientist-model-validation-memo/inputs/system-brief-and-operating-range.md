# E1 System Brief And Operating Range

The physical system is a benchtop aluminum calibration block used to temperature-condition a
reference puck before local optical-scanner checks. The benchmark team wants a simple predictive
model that estimates the block core temperature over one conditioning cycle so later planning work
can decide whether the current simplified model is scientifically admissible.

## Geometry and material summary

- aluminum block mass: `0.42 kg`
- aluminum specific heat: `900 J/(kg*K)`
- nominal exposed area: `0.031 m^2`
- characteristic length for lumped checks: `0.006 m`
- thermal conductivity of aluminum: `167 W/(m*K)`
- control heater range: `0..36 W`
- admitted ambient range for this memo: `20..24 C`
- admitted temperature range for this memo: `20..60 C`
- admitted time horizon: `0..30 min`

## Quantity of interest

The quantity to model is block core temperature `T(t)` in degrees Celsius. Temperature differences
may be treated in kelvin because only deltas appear in the loss term.

## Admitted use

This memo is only about whether the current simplified model is scientifically acceptable for the
admitted operating range and the supplied traces. It is not a control-tuning task and not a
hardware-change decision.
