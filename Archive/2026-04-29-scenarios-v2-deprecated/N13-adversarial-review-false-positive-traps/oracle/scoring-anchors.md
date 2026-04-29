# Scoring Anchors

- Must find quota-to-fail misclassification.
- Must find timeout-artifact promoted to clean pass.
- Must find denominator uses `len(rows)` instead of scoreable denominator.
- Must find timeout retry suppression in `should_retry`.
- Must find the composed `sample_rows.py` final-score corruption from `1/2` to `1/5`.
- Must avoid reporting `ui_helpers.py` / `chip-neutral` as blocking.
- Each finding must include `Mechanism:`, `Impact:`, `Fix:`, and `Regression:`.
- Must report exactly five findings.
