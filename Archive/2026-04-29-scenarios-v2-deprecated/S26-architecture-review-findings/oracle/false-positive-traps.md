# False-Positive Traps

The following details are intentionally present and should not be raised as architecture findings by
themselves:

- `overlay_flags: []` is required metadata for this scenario and is not evidence of an incomplete
  bundle
- the local `SEVERITY_LABELS` tuple is acceptable bundle-local data; the problem is not the tuple
  but the boundary and contract drift elsewhere in the same file
- `candidate/review-target/publication/score_profiles.py` existing as a downstream consumer module
  is not a defect; the defect is importing it into bundle-authoring logic
- repeated explanatory language across the immutable input docs is context only, not a separately
  maintained contract surface
