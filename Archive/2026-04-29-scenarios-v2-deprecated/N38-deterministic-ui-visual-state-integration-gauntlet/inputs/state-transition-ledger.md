# State Transition Ledger

Source ids used for implementation trace:

| Source id | Requirement |
|---|---|
| S1 | command keys combine group and id |
| S2 | disabled commands are never focusable or selectable |
| S3 | command filtering preserves only an enabled visible exact active command |
| S4 | dirty state is per record baseline |
| S5 | dirty navigation is blocked with target route preserved |
| S6 | validation failure keeps dirty state and focuses first invalid field |
| S7 | failed save keeps dirty state and prior baseline |
| S8 | successful save commits only active record |
| S9 | discard restores active record baseline |
| S10 | rendered cues must expose owner and visible return cue |
| S11 | layout boxes must fit small and desktop viewports without interactive overlap |
| S12 | raster gaps, overlays, legend, and PPM metadata are part of the contract |
