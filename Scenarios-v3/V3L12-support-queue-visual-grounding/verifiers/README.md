# Verifier

`check_support_queue_visual_grounding.py` validates bundle shape and scores JSON answers. Forked
from N80's `check_screenshot_grounding_review.py` verifier logic (same scoring shape: exact-tuple
findings, `pass_min_matched`, calibrated coordinate tolerance, false-positive term scan, required
non-findings), pointed at this bundle's own `oracle/visual-review-oracle.json` contract and scene.
