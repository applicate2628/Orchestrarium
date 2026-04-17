# E5 Anomaly Notes And Limitations

The lab notes include the following observed confounders.

1. the controller switches the cooling fan from low to high when the surface sensor first exceeds
   about `48 C`; an engineering note estimates the effective loss coefficient rises from roughly
   `0.78 W/K` to about `1.08 W/K` within `30 s`
2. the RTD is bonded to the outer surface, not embedded in the core; calibration logs suggest a
   transient sensor lag of about `15..25 s` when ramp rates exceed `2 C/min`
3. ambient temperature drifted upward by about `0.6 C` during Profile B because the enclosure lid
   stayed open between minute `6` and minute `10`
4. power telemetry is quantized to `2 W` and timestamps lag the controller by about `4 s`
5. no validation data exists outside `20..24 C` ambient, above `36 W`, or below `35 C` cooldown

These notes are not a request to repair the hardware or rewrite the controller. They exist so the
memo can judge whether the current model structure is valid, conditionally valid, or invalid for
the admitted use.
