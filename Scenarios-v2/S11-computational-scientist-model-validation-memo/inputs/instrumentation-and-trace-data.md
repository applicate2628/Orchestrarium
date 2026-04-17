# E3 Instrumentation And Trace Data

The validation traces compare measured block temperature against the current one-state model using
the parameter set from `E2`.

## Instrumentation summary

- RTD sample cadence: `4 s`
- logged table cadence below: `2 min` aggregates
- RTD stated accuracy after calibration: `+/-0.4 C`
- heater power telemetry resolution: `2 W`

## Profile A - constant-power warmup

Conditions:

- ambient `T_amb = 22.1 C`
- power `P_in = 26 W` for the full interval
- intent: check ordinary warmup behavior below and slightly above `48 C`

| Time (min) | Measured `T` (C) | Draft-model `T` (C) | Residual measured-model (C) |
|---:|---:|---:|---:|
| 0 | 22.1 | 22.1 | 0.0 |
| 2 | 29.2 | 28.7 | 0.5 |
| 4 | 34.6 | 34.2 | 0.4 |
| 6 | 38.7 | 38.5 | 0.2 |
| 8 | 41.9 | 42.1 | -0.2 |
| 10 | 44.6 | 45.0 | -0.4 |
| 12 | 46.7 | 47.3 | -0.6 |
| 14 | 48.3 | 49.0 | -0.7 |
| 16 | 49.5 | 50.4 | -0.9 |
| 18 | 50.5 | 51.5 | -1.0 |
| 20 | 51.2 | 52.3 | -1.1 |

Summary supplied by the lab note:

- profile-A mean absolute error: `0.55 C`
- profile-A max absolute error after minute 2: `1.1 C`

## Profile B - burst then reduced power

Conditions:

- ambient `T_amb = 23.0 C` at start
- power `P_in = 36 W` for minutes `0..8`
- power `P_in = 18 W` for minutes `8..20`
- power `P_in = 0 W` for minutes `20..28`
- intent: check whether one fixed loss coefficient remains valid through a threshold-crossing and
  cooldown segment

| Time (min) | Measured `T` (C) | Draft-model `T` (C) | Residual measured-model (C) |
|---:|---:|---:|---:|
| 0 | 23.0 | 23.0 | 0.0 |
| 2 | 30.1 | 31.6 | -1.5 |
| 4 | 36.7 | 39.0 | -2.3 |
| 6 | 42.7 | 45.1 | -2.4 |
| 8 | 48.9 | 50.2 | -1.3 |
| 10 | 49.8 | 52.0 | -2.2 |
| 12 | 49.0 | 52.1 | -3.1 |
| 14 | 47.5 | 50.4 | -2.9 |
| 16 | 46.1 | 49.0 | -2.9 |
| 18 | 45.0 | 48.0 | -3.0 |
| 20 | 44.2 | 47.2 | -3.0 |
| 24 | 38.5 | 41.6 | -3.1 |
| 28 | 34.7 | 37.6 | -2.9 |

Summary supplied by the lab note:

- profile-B mean absolute error: `2.43 C`
- profile-B max absolute error after minute 2: `3.1 C`
- observed time to first cross `48 C`: about `7.6 min`
- draft-model time to first cross `48 C`: about `7.1 min`
