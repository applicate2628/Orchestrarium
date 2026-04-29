# Verifier

Run:

```powershell
python verifiers/check_staged_ux_review_reentry.py --bundle-shape-only
python verifiers/check_staged_ux_review_reentry.py --expect-start-state
python verifiers/check_staged_ux_review_reentry.py
```

The verifier protects the review target, evaluates runtime witness cases, and
checks exact staged UX review artifacts.
