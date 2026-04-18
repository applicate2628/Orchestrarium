# False-Positive Traps

Do not raise these as standalone findings in `N03`:

- `MAX_CHANGED_PATHS = 12` is an admitted local bound for a tiny packet size and is not a
  performance defect by itself
- `sha1` inside `stable_fingerprint` is a local deterministic dedupe helper, not a security or auth
  boundary
- the `ReviewPacketView` dataclass is a same-owner local structure, not architecture drift
- the helper staying in one module is acceptable; the real issues are changed-path loss, title-only
  finding collapse, and silent parse failure
