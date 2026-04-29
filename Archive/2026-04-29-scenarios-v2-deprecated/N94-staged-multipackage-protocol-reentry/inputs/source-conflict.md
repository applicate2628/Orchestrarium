# Source And Conflict Notes

Authoritative sources:

- `S1`: v2 envelope schema uses `schemaVersion`, `eventId`, `tenant`, `subject`, `action`,
  `payload`, `traceId`, and `sourceId`.
- `S2`: core routing owns handler selection, accepted/rejected status, invalid schema rejection,
  and handler-missing rejection.
- `S3`: `HandlerRegistry` owns action lookup through `get(action)` and must not leak handler
  dictionaries as public mutable state.
- `S4`: SDK client owns the end-to-end `SendResult` contract and must expose `send(envelope)`.
- `S5`: SDK serializer owns v2 wire round trips and dataclass compatibility.
- `S6`: SDK legacy compatibility owns non-mutating legacy envelope migration.
- `S7`: plugin adapter owns delivery, timeout, retryability, duplicate suppression, and no-send
  behavior for rejected decisions.
- `S8`: CLI owns argument parsing and structured return dictionaries for both v2 and legacy JSON.
- `S9`: downstream consumers import only package roots and require `__all__` completeness.
- `S10`: validation must replay visible tests, hidden downstream SDK import, CLI contract replay,
  duplicate/no-send cases, and exact changed paths.
- `S11`: review response must reject legacy wrappers and accept public facade/downstream gates.
- `S12`: patch budget is exact: only the declared staged JSON files and package/test files may
  change, aside from verifier-created cache directories.

Stale or rejected sources:

- `S13`: stale v1 proxy note says to keep `send_event` and `serialize_event` wrappers for one more
  release. Reject it; this scenario requires a breaking migration with no legacy wrappers.
- `S14`: stale CLI note says stdout plus process exit code is sufficient. Reject it; downstream
  automation now consumes the structured dictionary returned by `run_cli`.
