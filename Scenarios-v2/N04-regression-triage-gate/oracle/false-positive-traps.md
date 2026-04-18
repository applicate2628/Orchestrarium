# False-Positive Traps

Do not raise these as standalone regressions in `N04`:

- `sha1` in `alert_digest.py` is a local dedupe helper, not a security boundary issue
- the small list processing in `report_formatter.py` is not a separate performance regression; the
  real issue is the wrong count semantics
- `test_windows_timezone_stamp` is a known pre-existing Windows flake with no new packet-local
  evidence
- the older docs line-length warning is branch noise, not a regression caused by this packet
- the report should stay triage-only; turning it into an implementation plan or release sign-off is
  scope drift, not a finding
