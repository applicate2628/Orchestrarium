# Migration Status

Updated after the freeze that moved active bundle loading to `Scenarios-v2`.

- Active collector reads bundle-local `scenario.yaml` files from the v2 root.
- The v1 archive index remains for historical export and audit work only.
- Score-profile lookup now uses the shared registry profile table.
