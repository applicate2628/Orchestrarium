# Operator Signals

## Duplicate alert report

Two `ops-summary` reruns with the same visible summary emitted duplicate notifications on the same
channel:

- `08:41` to `ops-summary`
- `08:42` to `ops-summary`

The payload body stayed the same across both sends, but the digest changed after the minute rolled
forward.

## Evidence anchor

- `inputs/review-target/src/alert_digest.py`
- the dedupe key includes `generated_at_minute`, so identical summaries from adjacent reruns are
  treated as different digests

## Triage implication

This is a likely regression tied to the recent digest-key simplification. It is not evidence of a
security boundary issue.
