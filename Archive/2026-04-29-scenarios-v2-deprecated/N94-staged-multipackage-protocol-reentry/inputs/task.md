# Task: Staged Multipackage Protocol Reentry Migration

The candidate workspace contains four packages:

- `protocolmesh_core`
- `protocolmesh_sdk`
- `protocolmesh_plugins`
- `protocolmesh_cli`

The current implementation exposes legacy dictionary/boolean APIs across those package boundaries:

- `route_event(event, registry)` returns mixed dictionaries.
- `ProtocolClient.send_event(event)` hides routing, serialization, and delivery outcomes.
- `serialize_event` / `deserialize_event` use an unstable v1 wire shape.
- `upgrade_legacy(event)` mutates legacy envelopes and loses source/trace fields.
- `HttpAdapter.publish(payload)` returns a bare boolean and raises transport errors.
- `main(argv)` prints transport output and returns only a process code.

Refactor the packages to a structured v2 protocol while preserving downstream SDK semantics. This
scenario is not a one-shot patch: complete the phase plan in `inputs/phases/` and leave
machine-readable evidence that a fresh follow-up session could resume and verify the work.
Hidden checks import only public package exports and run clean-room SDK/CLI consumers.

Required public APIs after migration:

- `protocolmesh_core.HandlerRegistry.get(action)`
- `protocolmesh_core.route_envelope(envelope, registry) -> RouteDecision`
- `protocolmesh_sdk.ProtocolClient.send(envelope) -> SendResult`
- `protocolmesh_sdk.serialize_envelope(envelope) -> dict`
- `protocolmesh_sdk.deserialize_envelope(payload) -> WireEnvelope`
- `protocolmesh_sdk.migrate_legacy_envelope(event) -> WireEnvelope`
- `protocolmesh_plugins.HttpPluginAdapter.deliver(envelope, decision) -> PluginAck`
- `protocolmesh_cli.run_cli(argv, *, registry, transport) -> dict`

Required structured result models:

- `WireEnvelope`: `event_id`, `tenant`, `subject`, `action`, `payload`, `trace_id`, `source_id`, `schema_version`
- `RouteDecision`: `accepted`, `status`, `reason`, `owner`, `handler`, `retryable`, `source_ids`, `trace_id`
- `PluginAck`: `delivered`, `status`, `retryable`, `event_id`, `error_code`, `owner`, `reason`, `source_ids`
- `SendResult`: `accepted`, `status`, `retryable`, `event_id`, `owner`, `reason`, `wire`, `ack`, `source_ids`

Compatibility requirements:

- Remove the old public APIs. Do not keep wrappers named `route_event`, `send_event`,
  `serialize_event`, `deserialize_event`, `upgrade_legacy`, `HttpAdapter`, `publish`, or `main`.
- Export all required public APIs from their package roots and include them in `__all__`.
- Preserve v2 wire fields: `schemaVersion`, `eventId`, `tenant`, `subject`, `action`, `payload`,
  `traceId`, and `sourceId`.
- Preserve denied-without-delivery: rejected routes must not call transport.
- Preserve timeout semantics: transport `TimeoutError` must become a retryable queued result with
  error code `plugin-timeout`.
- Preserve idempotency: a duplicate event ID must not republish and must return error code
  `duplicate-event`.
- Preserve legacy migration without mutating the input envelope or losing `tenantId`, `resource`,
  `command`, `body`, `trace`, or `source`.
- Preserve CLI semantics: `run_cli(["--json", JSON], registry=..., transport=...)` and
  `run_cli(["--legacy-json", JSON], registry=..., transport=...)` must return structured
  dictionaries, not print-only process codes.
- Migrate visible tests to assert the new public APIs and edge cases.

Update these staged artifacts:

- `candidate/source-ledger.json`
- `candidate/migration-state.json`
- `candidate/sdk-compat-ledger.json`
- `candidate/reentry-state.json`
- `candidate/review-response.json`
- `candidate/closure.json`

The ledgers must cite `S1`..`S14`, reject stale `S13` and `S14`, map every interface and call site,
record hidden downstream SDK/CLI validation, and preserve the exact changed-path budget.

Staged reentry requirements:

- `source-ledger.json` must include one `phaseBindings` row for each phase in
  `inputs/phases/`, with `phaseId`, `owner`, accepted `sourceIds`, rejected stale source IDs when
  applicable, `stateBefore`, `stateAfter`, `visibleArtifact`, `validationCue`, and `handoffCue`.
- `migration-state.json` must include `phaseOrder` in the required phase order, plus complete
  `interfaceMap`, `callSiteMigration`, `compatibilityMatrix`, `validation`, and `patchBudget`
  records for the final code.
- `sdk-compat-ledger.json` must bind each compatibility case to the package owner, public API, source
  IDs, validation command, and replay cue.
- `reentry-state.json` must set `finalFreshSession` to `true` and replay these cases after the final
  edit: root exports, dataclass wire roundtrip, denied event without delivery, timeout retryability,
  duplicate idempotency, legacy migration, CLI `--json`, CLI `--legacy-json`, removal of legacy
  wrappers, and exact changed paths.
- `review-response.json` must answer every review item with decision, owner, source IDs, validation
  cue, and the visible return cue expected by a downstream reviewer.
- `closure.json` must set `status` to `ready-for-verifier`, repeat the phase order, confirm no legacy
  wrappers, confirm stale-source rejection, confirm exact scope, and set `nextAction` to
  `run-hidden-verifier`.

Narrative summaries alone do not satisfy the task. The verifier reads the JSON ledgers directly.
