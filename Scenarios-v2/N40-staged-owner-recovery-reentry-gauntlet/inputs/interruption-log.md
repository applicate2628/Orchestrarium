# Interruption Log

| Interruption id | Event | Required continuity decision |
|---|---|---|
| I1 | X3 quota unavailable until user-reported 17:10 | prepare bundles, do not score X3 before quota clears |
| I2 | N38 prepared while quota unavailable | queue with top-pair batch |
| I3 | N39 prepared while quota unavailable | queue with top-pair batch |
| I4 | X5 route health has been mixed after N27..N37 | smoke or route-check before semantic promotion |
| I5 | X4 secret-backed route still fails | keep NOT-RUN |
| I6 | sidecar proposal may lag mainline preparation | use sidecar as advisory only |
