# Numerical Stability Decision Memo

## Recommendation

Use Option A because it was fastest in the old smoke run.

## Notes

Rounded p95 is close enough for release gating, and negative variance can be clamped to zero.
