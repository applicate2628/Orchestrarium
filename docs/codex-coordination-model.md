# Codex coordination-inference candidate

Status: local, unqualified implementation candidate based on PR19
9f1e6df297c47a8edf5eb44d2919a6a0ade553cb. Not a provider-supplied CodexModel.
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

## Qualification holds

The native factory now uses the existing exact launch owner rather than a constant
hold. Selected sdkExecution v3 binds operationKind=coordination-inference, immutable
inner snapshot and distinct reservations, using the existing main/lead actor. The
same atomic claim/settle writers remain sole ledger owners. Subscription mode,
bounded profile and empty MCP scope are required. Fresh parent authority is still
required per effect; selected metadata is neither permission nor native readiness.
SdkCoordinationWorker persists scanned artifact/terminal readback before returning
outer evidence to Model. The public legacy review Executor rejects coordination
requests; its private operation lifecycle is shared, not a second supervisor.
Source wiring has offline coverage; real Runner, native process custody and live
provider qualification are distinct claims. No live launch has occurred.

A separately authorized isolated offline environment provisioned official PyPI
openai-agents 0.24.0 and pytest 9.1.1 with their mandatory binary-wheel closure,
verified primary hashes, full dependency hash lock and matching install report.
These are test reproducibility pins, not product admission allowlists. The real
public Runner and this Model passed seven fake-Codex-transport integration cases:
one Model call and execute_admitted with no post-tool inference, refused/malformed
intent, current-authority revocation and failed protocol close. The existing
artifact receipt, atomic ledger settlement and independent readback ran for real;
process receipts in these integration cases remain explicitly synthetic. Usage
retains unknown token evidence. No provider was called. Installed public RunHooks
is a parameterized generic alias; the capability check uses Python's normal base
resolution rather than requiring that alias itself to be a class.

The ordinary execution sandbox timed out in Python socketpair before test bodies.
One bounded approved current-user nonadmin probe passed outside that sandbox, with
sockets and loop closed. Offline tests ran in that approved mode; no firewall,
ACL, global Python or sandbox setting changed. Synthetic custody tests cover typed
receiving and refusal conditions but do not prove new-operation OS containment.
A real Windows Job-owned SDK worker also completed a bounded fail-closed fixture:
missing runtime selection was rejected before Codex startup, child exit 2, empty
owned tree, direct reap and closed Job/thread/resources. This qualifies that
startup/refusal cleanup path, not completed coordination/provider execution.
The historical venv retains Codex package files but its interpreter is absent;
it was neither repaired nor reused. Global Python was unchanged.

## Bounded future live plan, not a command to run

1. Review the typed launch/receiving wiring, provision a verified official compatible Agents/Codex
   environment in isolation, and pass real Runner plus fake transport and relevant
   legacy bridge/worker/receiving regression tests. Qualify async loop and creator
   resource settlement in the actual execution mode.
2. Preserve official subscription login, startup/account/tool/hook admission and
   exact executable/home/profile identity; account_read(refreshToken=False).
   No OAuth extraction, auth copying, private API, key/API billing or fallback.
3. Reserve at most one outer native turn and one inner native turn separately.
   Prefer gpt-6-luna/high only if current catalogs and both admitted profiles support
   it; otherwise stop, never substitute. max_turns=1 is not a monetary or native
   internal-inference/retry limit.
4. Use existing AgentsCoordinator Runner.run, forced execute_admitted,
   parallel_tool_calls=False and stop_on_first_tool, no Session/resume/streaming.
   Outer returns only the closed observed intent. Inner reviews one harmless
   in-memory arithmetic statement using the existing closed review schema.
5. Budget outer at most 45 seconds, inner at most 90 seconds, overall watchdog
   150 seconds including cleanup, through the existing owner. No post-tool model
   inference or automatic repeats; reconcile any uncertainty.
6. Retain outer and inner reservation/launch/terminal receipts, stdout/artifact,
   existing ledger readback, raw/unknown usage and final native tree/handle cleanup.
   No PASS when cleanup, actual provider result or provenance is uncertain.

Parent reviews the candidate and remaining holds before any live stage. No live
command is ready or authorized by this document.

## Terms and Abbreviations

- SDK / API: software development kit / public application interface.
- Model: public Agents inference interface; distinct from a coding-agent tool.
- MCP: Model Context Protocol.
- Intent: nonauthorizing proposed execution call, never an execution receipt.
- Provenance: actual operation/identity/launch/terminal evidence, not a role label.
