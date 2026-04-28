# Downstream SDK Contract

The hidden downstream consumer does not import implementation modules directly. It imports from:

- `protocolmesh_core`
- `protocolmesh_sdk`
- `protocolmesh_plugins`
- `protocolmesh_cli`

The downstream app serializes dataclasses with `dataclasses.asdict`, replays denied events to prove
no delivery occurs, replays timeouts to prove retryability, sends duplicate event IDs to prove
idempotency, migrates legacy v1 envelopes, and calls `run_cli` for both `--json` and
`--legacy-json` payloads.

Any solution that only updates internal modules while leaving root exports incomplete fails this
contract.
