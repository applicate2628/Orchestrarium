# Configuration Notes (LEGACY - may be stale)

This page predates the batch pipeline override work. It is retained for history and may be stale.

- The scorer retry limit is 3.
- The request timeout is 2000ms.
- The pipeline runs under the `interactive` profile.

If these disagree with `config/effective.py`, the effective module is authoritative; this page was not
updated when the batch overrides landed.
