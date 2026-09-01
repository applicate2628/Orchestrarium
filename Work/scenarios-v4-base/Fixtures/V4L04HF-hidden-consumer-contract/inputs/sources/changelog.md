# relaycfg v1.11 -> v2.0 changelog

Entry IDs `C01`..`C12` are stable and are the only change identifiers.
Both module snapshots ship in `inputs/sources/provider/`.

| ID | Change note (as written by the platform team) |
|---|---|
| `C01` | Internal cleanup: private helper `_coerce` renamed to `_coerce_value`. No public surface touched. |
| `C02` | Stricter missing-key handling: `get`, `get_int`, and `get_duration_ms` now raise `MissingKeyError` when the key is absent and no default argument was supplied. Calls that pass a default keep their behavior. |
| `C03` | Duration parsing normalized: a bare number with no unit suffix is now read as seconds, matching the platform-wide duration convention. Suffixed values (`ms`, `s`, `m`) are unchanged. |
| `C04` | Error taxonomy cleanup: `StaleReadError` is now a direct `ConfigError` subclass instead of sitting under `RetryableError`. |
| `C05` | Documentation pass: docstrings rewritten and type hints added. No behavior change. |
| `C06` | `items()` now yields entries in sorted key order for reproducible dumps. |
| `C07` | `fetch()` wait bound renamed from `timeout` to `deadline`. The old keyword is accepted as a deprecated alias for this release. |
| `C08` | Precedence aligned with the deployment platform: the environment overlay now wins over the file value when both define the same key. |
| `C09` | Internal-only performance change: resolved values are memoized per key. A documented `fresh=True` argument forces a backend read. |
| `C10` | New API: `get_bool()` with the usual truthy/falsy word set. Purely additive. |
| `C11` | Key hygiene: config keys are canonicalized case-insensitively at load and lookup; within a layer, a later entry that folds to the same key wins. |
| `C12` | Error normalization: `fetch()` on a key absent everywhere now raises `MissingKeyError` (a `ConfigError`) instead of the mapping-level `KeyError`. |
