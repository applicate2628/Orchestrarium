# Oracle

- `localization-oracle.json`: target centers and pass thresholds.
- `answer-schema.json`: strict JSON shape used by the visual runner for Codex rows.
- `reference-answer.json`: exact target centers for local verifier calibration.

The pass threshold is intentionally not zero-pixel exactness. It allows a several-pixel window while still rejecting coarse localization that would be unsafe for dense UI/image work.

## Terms and Abbreviations

- `JSON`: JavaScript Object Notation; the machine-readable oracle and answer format.
