# Nearby Smoke Coverage

## Must-not-break neighbor

- surface: legacy `--text-summary` path
- reason: the new flags share summary-rendering and output-path selection logic with the existing
  text mode

## Smoke status

- `python tools/status_snapshot.py fixtures/500-items.json --text-summary`
  - status: `NOT RUN`
  - reason: the implementation phase stopped after targeted tests and the two JSON-mode smoke
    commands

## Consequence

There is no nearby smoke evidence proving that the legacy text path still works after the patch.
That gap should be called out explicitly instead of being folded into the dry-run regression.
