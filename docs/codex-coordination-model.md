# Bounded Codex coordination inference

Status: opt-in implementation published in PR19. The runtime at commit
`fc5db5b7d67e078c96c3fde3a7da1e0072d7fab8`, tree
`acf9a9addb0ea73b5544f8b3070d1dff9a773841`, passed one bounded Windows
outer-to-inner live qualification on 2026-10-26. This is not a provider-supplied
CodexModel or qualification of arbitrary multi-step orchestration.
The adapter does not activate a provider, provision an SDK or call a model on import.

## Public interfaces and ownership

Inspected [Agents Model interface](https://github.com/openai/openai-agents-python/blob/0dc4cf152bff1f50bdc0e41f28808563406545b2/src/agents/models/interface.py)
requires get_response and stream_response. The adapter produces ModelResponse with
one ResponseFunctionToolCall only after a validated observed native dispatch intent
and completed outer process settlement. Agents Runner, not Model or a Codex approval
callback, owns execute_admitted. No tool output or successful execution is fabricated.
The [official Codex example](https://github.com/openai/openai-agents-python/blob/0dc4cf152bff1f50bdc0e41f28808563406545b2/examples/tools/codex.py)
is a tool integration, not this backend.

Public Codex APIs at
[970111f6cb62cc02fe36a82ea7d71b37a2889c97](https://github.com/openai/codex/tree/970111f6cb62cc02fe36a82ea7d71b37a2889c97/sdk/python)
include account_read, thread_start/thread_read, turn_start,
next_turn_notification, turn_interrupt and close. Existing transport retains its
explicit deny approval handler, refreshToken=False, startup/config/MCP/profile
checks, byte bounds and protocol cleanup. Output schema constrains the final
message, not native tool effects; no tools-free native capability is inferred from it.

CoordinationInferenceRequest/Result and infer_coordination/coordination_result
extend the existing worker channel and ProcessRunner; there is no new supervisor.
Intent is separate from ReviewResult/verdict. It binds operation, admitted request
and immutable inner request digest. Outer/inner dispatch, evidence, artifact and
budget identities remain distinct, while account/profile/scope bindings match
the selected first slice. Derived call IDs include request/native IDs/intent digest;
they are explicitly adapter IDs, not native Codex tool-call IDs.

Model input accepts equivalent JSON text and normalized Responses user-text items.
It rejects extra history/tools, incompatible schema/settings, handoffs, remote
prompts, stored conversation/previous response and streaming before worker effects.
Supported optional public defaults are not treated as hidden selected capabilities.
Explicit store=False/True is rejected: no equivalent Codex native-history control
is established. An unselected store=None does not promise absence of native history.
One use is consumed before the awaited worker call; no retry or resume follows
failure or uncertainty. Current authority is required before outer work and after
settlement/before inner dispatch. Required inner execution authority is checked
again by the existing coordinator/executor owner.

Raw usage and unknown completeness remain explicit. Public Usage defaults do not
establish observed zero tokens; a missing raw_usage capability does not manufacture
token evidence or independently veto an admitted-call budget.

## Implemented ownership and observed qualification

The native factory uses the existing exact launch owner. Selected sdkExecution v3
binds operationKind=coordination-inference, the immutable inner snapshot and distinct
reservations, using the existing main/lead actor. The same atomic claim/settle
writers remain sole ledger owners. Subscription mode, bounded profile and empty MCP
scope are required. Metadata is neither permission nor readiness.
SdkCoordinationWorker persists scanned artifact/terminal readback before returning
outer evidence. The review Executor rejects coordination requests; its private
operation lifecycle is shared, not a second supervisor.

The historical `LIVE-AGENTS-CHECKPOINT-v9` qualified the exact runtime tree above:
- One outer and one inner observed native turn/start on gpt-6-luna/high, through
  the existing subscription, official Codex SDK 0.163.0 and runtime 0.164.0.
- The actual Agents Runner dispatched the existing SDK executor; the inner
  arithmetic review completed with PASS. No repeated or post-tool turn was started.
- Account/profile/required-hook admission passed; no unexpected native tool items
  were observed. This does not establish that tool capabilities were absent.
- Caller and workers exited zero; Windows Job trees were empty, children reaped,
  resources closed, and receipt/artifact/ledger readback agreed.
- Outer usage payload was retained; inner usage is unknown, not observed zero.

Checkpoint SHA-256: `7f13e81558f62be309667a9e652117450d339a237f4d2c0dbe5712746fd11626`.
Inner receipt SHA-256: `a97f27bf0fe60931f6e9b04095b7362bf388828d2ba52aba11346a10f99e39d2`.
These digests identify retained private evidence; they are not downloadable logs.
The record is evidence of that historical run, not authorization for another run
or a claim that later changed callers have been live-qualified.

## Offline coverage and reproducibility boundary

The controlled earlier subset had 305 passed, 3 skipped and 71 passing subtests;
it preceded the final Windows binding correction. A separate host-local caller
suite after that correction had 26 passed. Do not combine those as one full-suite
result. The historical live caller SHA-256 is
`e1a45dd690d3a3c87a6dbb4eefadfa22fd92608b2ab40f78b6c1fa945a4255a2`.
The retrieved caller is now available as the explicit
[Windows qualification example](../examples/sdk/README.md). Only its checkout-root
locator changed; a byte-equivalence regression test verifies that boundary.
Execution, admission and resource behavior are retained, not generalized to other
platforms. The original 26-test host-local suite is not transferred, and the
relocated caller has not been live-qualified again.

Repository offline tests can be selected with an already provisioned test Python:

```sh
python -m pytest -q tests/test_sdk_coordination.py tests/test_sdk_coordination_owner.py tests/test_sdk_coordination_runner.py tests/test_sdk_dispatch.py tests/test_sdk_tracing_isolation.py tests/test_sdk_live_caller_example.py -rs
```

The real-Runner tests require the separately provisioned optional Agents SDK;
without it they skip rather than prove the integration. The historical test
environment used openai-agents 0.24.0 and pytest 9.1.1 with its recorded dependency
closure, not a product-wide admission allowlist. The repository Runner tests use
fake Codex transport and synthetic process custody; their inner executor is a
sentinel. They do not reproduce the complete historical live pair. No provider is
called by these tests. Trace state is restored after each test, including failure.

## Remaining qualification and future live-run constraints

Session/resume/crash recovery, streaming, arbitrary planning/tool selection,
other operating systems and live other-provider use remain unqualified by this
bounded smoke. The forced tool and fixed admitted request test the integration
chain, not the model's ability to choose or decompose arbitrary tasks.

Any future live run needs fresh explicit user authorization and current admission
for account, profile, required hooks, exact runtime and both separate reservations.
Use the existing subscription; do not copy credentials, extract OAuth tokens,
substitute API billing or weaken admission. Historical time and capture limits are
provenance, not authority for a fresh run. No test collection, import or ordinary
offline command may start live providers. The tracked example requires explicit opt-in before
effects, rejects automatic repetition of the same output, and retains
both operation receipts plus process/resource cleanup evidence.

## Terms and Abbreviations

- SDK / API: software development kit / public application interface.
- Model: public Agents inference interface; distinct from a coding-agent tool.
- MCP: Model Context Protocol.
- Intent: nonauthorizing proposed execution call, never an execution receipt.
- Provenance: actual operation/identity/launch/terminal evidence, not a role label.
