# Verifiers

Run these checks from the bundle root:

- `python verifiers/check_ui_test_report.py --bundle-shape-only`
  Validates the seeded bundle contract, metadata, and required files. This is the author-side check
  for the fixture as committed.
- `python verifiers/check_ui_test_report.py`
  Validates a completed UI regression report against the oracle. This mode expects
  `candidate/ui-regression-report.md` to be fully filled in with no TODO markers.
