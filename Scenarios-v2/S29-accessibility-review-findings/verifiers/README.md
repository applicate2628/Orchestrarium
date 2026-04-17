# Verifiers

Run these checks from the bundle root:

- `python verifiers/check_accessibility_review.py --bundle-shape-only`
  Validates the seeded bundle contract, metadata, and required files. This is the author-side check
  for the fixture as committed.
- `python verifiers/check_accessibility_review.py`
  Validates a completed accessibility review report against the oracle. This mode expects
  `candidate/review-report.md` to be fully filled in with no TODO markers.
