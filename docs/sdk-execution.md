# Optional software development kit (SDK) execution implementation

This branch implements part of the SDK integration project separately from Rust/npm.
The current acceptance scope is full qualification of the selected Codex review
route and offline adapter checks for the other providers. Broader SDK-1 through
SDK-4 roadmap items, including live Grok account/tool enforcement and receiving,
remain outside that adapter-only acceptance. A synthetic Codex success does not
qualify live execution or activate a default route; the optional outer Agents
workflow remains separate from this Host-led path.
Existing host-led Codex/Claude command-line interface (CLI) execution remains the
default. The explicit Codex review bridge described below is an opt-in source
contract, not an automatically selected fallback or an installed-runtime
qualification claim. The historical installed Windows success and receiving-collision
checks and the bounded live Codex review passed on October 25; the outer Agents
cycle passed on October 26. Their exact evidence boundaries are recorded below.
These results do not enable a default route or qualify arbitrary general use.

## Explicit Codex review opt-in (repository-local contract)

The existing provider-prompt entrypoint accepts `--sdk-review-binding <path>` only
for a Codex `external-reviewer` invocation. Omission keeps the legacy route. Other
providers and worker/consultant roles are not migrated by this option. The same
invoking Host (the existing orchestration session) remains the authorization
owner; the binding file supplies constraints, not permission, a transferable grant,
a new coordinator or an automatic retry. No outer Agents model loop is started.

The bridge requires the existing ledger, explicit review-artifact locator and
absolute caller-owned terminal receipt, the policy-resolved model/effort, and a
read-only review profile. It refuses unsupported platforms before native effects:
the current containment path is Windows-only. Its Python worker requires the
separately provisioned compatible environment; installing helper files does not
install dependencies or authorize their execution. Existing login/account owners
remain in control; this opt-in does not require or create a separate API billing
lane, copy credentials, switch accounts, or pin an SDK/runtime release.

The strict UTF-8 JSON binding is bounded to 65,536 bytes and contains exactly:

| Field | Meaning |
|---|---|
| `schemaVersion` | Integer `1`; repository-local binding schema, not SDK version. |
| `accountBinding` | Nonsecret identifier for the selected existing account. |
| `expectedAccountEmail` | Existing account email for auth-file verification, or null where the selected auth mode permits it; not a credential. |
| `coordinatorBinding` | Existing Host/session binding label; does not start a coordinator. |
| `scope` | Nonempty list of explicit review-scope strings. |
| `artifactIdentity` | Identity of the artifact being reviewed, distinct from the output locator. |
| `maxEvents` | Positive bounded adapter-observation/query count budget. |
| `jobMemoryLimitBytes` | Positive Windows Job committed-memory budget. |

The binding cannot select extra tools, arbitrary launch flags or endpoints. This
bridge selects an empty Model Context Protocol (MCP) tool scope and fixed startup
isolation controls; it does not expose the lower-level adapter's selectable-MCP
interface. Empty scope is checked against returned thread inventories, not inferred
from an empty configuration table. This is not a proof that all native, dynamic or
extension tools are disabled, nor atomic isolation from configuration changes.

Resource bounds are separate, not interchangeable: existing `--ledger-max-events`
and `--ledger-max-bytes` govern durable ledger admission. Omit both to let each
locked ledger operation derive finite admission from its selected history and
planned writes; omission is not replaced by a fixed or launch-time ceiling.
Supplying only one bound is rejected. Current launch checks requalify the captured
ledger and selected participant identities before accepting their observations.
Binding `maxEvents` and
`--result-max-bytes` bound retained SDK evidence/result text; `--capture-max-bytes`
bounds the worker capture/serialized receipt and remains subject to the worker
transport ceiling; `jobMemoryLimitBytes` limits process-tree committed memory.
The existing finite timeout/cancellation owner also covers preparation and native
hook-trust work. None of these turns private SDK pipes into byte-complete evidence.

Known failure before SDK worker invocation is settled once by the runtime owner.
Receiving exports selected-only Version 3 (V3) blocked/none evidence after matching
durable readback and output scanning: its exit code is a wrapper failure code,
not a native exit observation, and cleanup remains conservatively incomplete.
An exception after worker invocation has uncertain effects; it must not be recast
as a preworker failure or replayed. Acquired execution evidence is retained before
receiving, and receiving/receipt failures remain failures rather than permission
to append another terminal. Diagnostic/recovery delivery across those failure
paths was exercised by the historical installed Windows receiving-collision check:
the diagnostic was retained and did not confer replay authority. This is evidence
for that tested scenario, not every possible crash or recovery path.

Installer-managed SDK helpers are shared by both host packs. The dispatch module
is registered in the source installer payload. The historical installed check
verified source and installed-file hashes together; subsequent changes must retain
their own source, installer and shared-owner regression evidence.

### Verified native evidence and subsequent changes

- October 25 installed Windows fixture: success and receiving-collision passed
  against candidate935, source-manifest SHA-256
  `bdd601615e7ef4bff2a595b5799c8e0744a544983965822e688508cb82307d5f`.
  The check verified 935 source files and 76 installed files, real hook-trust
  metadata probes, receipt/artifact/ledger agreement, retained nonreplayable
  collision diagnostics, and closure of the owned process trees and resources.
  The workers were synthetic; this fixture alone was not a model call.
- October 25 Host-led Codex review: one wrapper and one real Luna/high SDK turn
  completed in 18.343 seconds with coherent receipt/artifact/ledger readback and
  settled resources. This qualified the bounded review, not arbitrary tasks.
- October 26 outer Agents Runner to inner Codex SDK cycle: the separate
  [coordinator evidence](codex-coordination-model.md) records the live-qualified
  implementation tree `acf9a9addb0ea73b5544f8b3070d1dff9a773841`, two observed
  turns, current account/profile/hook checks and settled Windows Jobs.
- Through the October 27 custody correction, SDK modules, process supervision,
  provider-prompt and installer source are unchanged from that October 26 tree.
  Shared ledger/schema/validator changes are covered separately by the current
  delta-focused regression results; historical native results are not relabelled
  as a fresh complete-current-tree run.

The retained Windows archive has SHA-256
`b8dcc2c55fae195e438bc5f08f1bbe58a05f35fd2fd129e9374933de833d866c`;
its 20 manifest-listed payload hashes were independently checked during evidence
reconciliation. Raw operational logs and local account/configuration data are not
part of the published source. Offline fixtures alone still do not establish
native execution; the claims above rely on the separately retained native results.

### Bounded Codex CLI startup qualification

The explicitly opted-in `--sdk-review-binding` route selects an immutable
invocation-only profile: `features.memories=false`, `notify=[]`,
`model_provider="openai"`, `approvals_reviewer="user"`, followed by the existing
plugin, Apps, and native-delegation isolation controls. The complete ordered
selection is committed by the existing request hash and forwarded unchanged to
both the hook-trust probe and SDK worker. The low-level SDK default remains the
existing four controls. No global configuration, endpoint, or required hooks
are changed.

For this exact bounded profile, public `config/read` must explicitly report
memories false, notify an empty list, and provider/reviewer openai/user before
thread creation; missing, null, or incompatible values fail closed. This checks
raw layered configuration consistency, **not** complete effective managed state.
Before any native startup (including the hook probe), the Host must inventory
and admit the selected startup provider/endpoint, managed requirements, and
required versus unrelated hooks; incompatible requirements block qualification.
The bridge does not reset `openai_base_url` or automatically prove this gate.
Startup metadata discovery can precede config readback, and a one-turn guard
alone cannot bound background memory inference or legacy notification commands.
Normal native history/state writes remain possible.

## Boundaries

- Existing routing, role, artifact, permission, budget and ledger owners retain
  authority. A successful SDK call is external evidence, not an accepted review.
- `scripts/sdk_execution/coordinator.py` uses the official Agents SDK with an
  explicitly supplied model and existing authority owner. Tracing is disabled.
  Model/tool effects and resumed requests recheck current bindings. No second
  ledger, retry scheduler or automatic account selection is introduced.
- `scripts/sdk_execution/codex.py` uses the official Python Codex SDK and native
  structured output for a read-only review. SDK types stay inside the adapter.
- `scripts/process_supervision/sdk_worker.py` composes a fixed worker with the
  existing process owner. Protocol cancellation and OS tree settlement are
  separate observations. Neither a final answer nor SDK close proves tree cleanup.
- `scripts/sdk_execution/receiving.py` receives the paired execution/process result
  and calls the existing atomic ledger writer. Independent validated readback is
  required. No new writer or direct JSONL append is used.

## Provenance and compatibility

SDK rows use `actualExecutionPath: direct-external-sdk` and the versioned
`sdkExecution` object in the existing agent-run schema. Selected schema version 2
binds the model, effort, sandbox/permission policy, non-secret account identifier
and request digest without inventing unobserved SDK/runtime versions. The adapter
records actual version metadata separately; successful version-2 artifacts retain
it alongside the structured review. Historical schema-version-1 records retain
their original validation and matching rules. These objects contain no credentials.
The existing launch, evidence, role and artifact identities remain authoritative.
Successful receiving additionally requires the adapter's actual profile checks; a
blocked early failure retains the selected launch configuration without inventing
missing observed profile or runtime evidence.

SDK rows do not fabricate `launchFlags`. CLI rows retain their existing decoding
and validation. The provider-result v3 reader is distinct from v2 CLI records;
all SDK-derived fields participate in the existing safety-scan projection.
External results remain nonauthorizing and cannot close another run's obligations.
An older reader must reject an unsupported SDK record rather than call it CLI.

## Capability-based compatibility

Orchestrarium does not pin SDK or CLI releases or admit them by a version
allowlist. Adapters check the public API and operation capabilities they actually
use, then validate observed profile, permissions, output and cleanup contracts.
A different version alone is not a rejection reason; a missing required API or
incompatible observed behavior is. This does not promise compatibility with every
past or future provider release.

Version strings and executable digests are evidence about a particular run, not
product-wide compatibility gates. Preserve the selected executable identity and
request binding across a run; accepting different releases must not permit an
executable swap, fabricated observation, changed account or weaker permissions.
Unknown prelaunch runtime metadata must not be filled with a historical release.

The following releases were inspected as source evidence on 2026-10-23, not as
required package versions or an installation lock:

- OpenAI Agents SDK 0.24.0:
  [inspected source](https://github.com/openai/openai-agents-python/tree/17d994bd3045dae71acda676a4ef4762ed8ecd94).
- Codex Python SDK and bundled runtime 0.163.0:
  [inspected source](https://github.com/openai/codex/tree/83086188ae0614bd882818ff1aa23f3194962012/sdk/python).
- Claude Agent SDK 0.2.173 and bundled CLI 2.1.309:
  [inspected source](https://github.com/anthropics/claude-agent-sdk-python/tree/163f50ed56fa8c3fd9346148b6e56e7696794b58).

A provider package can constrain its own bundled dependencies; that upstream
packaging detail is not an Orchestrarium runtime-version requirement. A reviewed
source revision or reproducible test environment records evidence, not an
exclusive set of admitted versions. This compatibility contract supersedes the
SDK project draft's requirement to pin tested SDK/CLI combinations.

Provisioning and complete native qualification remain separate from API checks.
This branch performs no implicit package install, upgrade, downgrade,
authentication, credential copying or provider activation. The user-selected
execution route is subscription-backed; a separate API account/billing lane is
not a prerequisite and must not be silently introduced. Direct Codex SDK uses
the existing Codex login. Any optional outer Agents Model needs an explicitly
supported subscription-compatible binding before use; no OAuth token extraction
or private API bridge is implied by its injectable Model interface.

## Typed observations and applicable semantic checks

The bounded dispatched SDK review consumes native item/call identities and actual
terminal command state instead of synthesizing a host transcript. Codex rejects
`item/completed` command data that is missing a recognized terminal status, even
if the event envelope or later turn claims completion. A completed command still
requires an observed integer exit code. A failed, declined or nonzero command is
retained as evidence, not automatically converted into failure of the final review.
The same checks apply to full-history reconciliation.
A live terminal that declares `itemsView=full` must also include every captured
completed item; `summary` and `notLoaded` retain their explicitly partial semantics.
A failed history reconciliation does not automatically interrupt a prior turn
that this lookup did not start. Explicit caller cancellation remains the separate
bound cancellation operation; client closure and owned process settlement remain
required on every path.

The main-conversation passive-polling Stop guard explicitly excludes dispatched
reviews/subagents, so this selected SDK lane must not fabricate input to that hook.
Publication-scan correlation remains with the existing publication owner; SDK
review evidence cannot replace its receipts. Existing receiving independently
checks request/profile identities, structured results, actual process outcomes and
settlement. This scenario mapping supersedes the earlier overly broad inference
that absent direct hook imports necessarily required a new SDK-to-hook bridge.

## Caller-owned conversation history

`AgentsCoordinator` and `create_review_coordinator` accept an optional public SDK
`session`. The selected object is passed unchanged to `Runner.run` for both new
runs and authenticated RunState resume. Without it, the existing no-session call
shape stays unchanged. Required public Session methods and Runner support are
checked before consuming a resume snapshot; a changed session ID is rejected.
No Session backend, history writer or cleanup owner is created by this module.
The caller and current authority owner must bind the ID **and backend** to the
admitted conversation/account and snapshot. A stable ID alone does not attest
backend identity. After restart, the caller supplies the same admitted Session
ID/backend; offline composition tests do not prove actual SDK persistence or
combined crash recovery.

## Per-run controls are not native-role customizations

`CodexRuntimeSelection.config_overrides` defaults to an empty tuple and is passed
to the public Codex configuration for that invocation. It must not rewrite native
role TOMLs, global configuration or the stock role manifest. In particular,
`features.plugins=false` and `features.apps=false` in a no-tools synthetic probe
are test-specific controls, not defaults for `architect` or
`architecture-reviewer`. Adding them to a stock role changes its identity; the
ordinary role router must continue rejecting that mismatch. SDK execution must
not bless modified hashes or bypass the role owner. Regression coverage preserves
real temporary config/role/manifest bytes and both stock-accepted and drift-denied
routing outcomes through runtime composition; it does not claim the external
runtime can never write its own state.

## Current completion and adapter-only acceptance scope

As confirmed by the user on 2026-10-24, Codex is the full end-to-end completion
priority, including integration with the existing orchestrator owners. Claude,
Kimi, Grok, MiniMax and MiMo are limited to adapters and offline protocol/contract
verification for this task. Real model calls for those providers are outside the
current acceptance scope; their missing live qualification must not block Codex
completion or be worked around by buying API access or changing authentication.
Do not describe offline support as live-qualified support. Existing closed live
gates remain closed until later authorization. This scope does not waive
capability, account, tool-policy, receiving or process-settlement checks for
Codex or any subsequently activated route.

Before PR integration, identify each existing orchestrator owner and caller that
the SDK retains or supersedes. Verify the dispatch transition and rollback;
passing an isolated SDK suite is not proof that the installed orchestrator uses
the intended single execution path.

## Dormant Grok ACP slice

`scripts/sdk_execution/grok.py` implements source-backed ACP protocol exchange and
a composition over the existing `ProcessRunnerV1`. It negotiates capabilities,
uses explicit authentication selection, sets model before reasoning effort with
observed configuration readback, denies permission requests, correlates messages,
and retains cancellation/terminal/close evidence. Configuration transitions and
flat/grouped selectors are distinguished; malformed terminal data preserves
already acquired output. Cleanup obeys the selected byte/event budgets.

The narrow `grok-acp-one-shot-v1` dialogue uses the existing native-parser contract,
exact executable binding and owned Windows lifecycle; it is not a second launcher
or supervisor and does not bypass the POSIX hold. Its selected command is
`<exe> --no-auto-update agent --no-leader --model <selected-id> stdio`; the command
shape is a protocol/profile contract, not a claim of installed-runtime qualification.
There is no release allowlist or inferred account identity.

**Live admission remains unconditionally held before process creation.** Empty ACP
client capabilities, a deny callback and `mcpServers: []` do not establish that
Grok's internal tools obey this read-only executor contract. Authentication also
can have external effects. No caller callback can remove the fixed unsupported
live boundary. Offline composition fixtures explicitly replace that boundary to
exercise borrowed channels and typed process receipts; an unpatched test proves
zero launches. This is source/offline evidence, not a real Grok run.

Durable Grok receiving, actual account selection/readback, internal-tool policy
and native compatibility remain unqualified. A clean protocol or process fixture
therefore does not become a fully received native terminal like the existing
Kimi owner. The adapter preserves the exact acquired process result even if
result scanning/reduction fails. Existing role/provider routing stays unavailable.

Official sources: [Grok agent mode](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/15-agent-mode.md),
[session configuration implementation](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-shell/src/agent/session_config.rs),
[ACP session configuration](https://agentclientprotocol.com/protocol/v1/session-config-options).
The Grok guide's nested config-value example conflicts with the declared ACP
schema; scalar `value` follows the actual public schema, without fallback retry.

## MiniMax Code ACP addition

MiniMax Code (`mcode`, published as `@minimax-ai/code`) is the coding agent,
not the separate `mmx-cli` platform client. Its public `mcode acp` entry point
is the selected integration target. The SDK request provider identity is
`minimax`; this does not activate installed routing or alias a Codex/Claude
runtime selection.

The optional adapter uses the official Python `agent-client-protocol` public
connection API (`acp`) behind an explicitly borrowed client boundary. It does
not introduce a second JSON-RPC implementation, subprocess supervisor, credential
store, model API client or ledger. Dependencies are not installed automatically.
No particular MiniMax or ACP release is a product compatibility requirement.

**The production acquisition path remains held before constructing a client.**
Official source omits an empty `mcpServers` list when creating the runtime session;
therefore `mcpServers=[]` does not prove that inherited tools are excluded.
The `permissionMode` configuration option changes runtime-level permissions and
broadcasts to attached sessions; the adapter must not use it as a per-run override.
Model option values must be selected from the advertised catalog and checked
after selection. Effort uses `thinkingEffort`, not Grok's `reasoning_effort`.

The supported native Node/entry-script launch binding, inherited tool isolation,
subscription/account readback, owned pipe lifetime and durable receiving still
require qualification. Windows `mcode.cmd` / `mcode.ps1` wrappers are not silently
admitted as native executables. Protocol fixtures are not a real provider run;
no global profiles, auth state or default routes are changed by this addition.

Official source evidence (not a pinned required release):
[MiniMax ACP implementation](https://github.com/MiniMax-AI/minimax-code/blob/da22f11c55d4748155d7162c1030414228a00565/packages/tui/src/acp/agent.ts),
[MiniMax config controls](https://github.com/MiniMax-AI/minimax-code/blob/da22f11c55d4748155d7162c1030414228a00565/packages/tui/src/acp/control-state.ts),
[official ACP Python SDK](https://github.com/agentclientprotocol/python-sdk).

## MiMoCode ACP addition

MiMoCode (`mimo`, published as `@mimo-ai/cli`) has both an ACP entry point
and a native local HTTP interface. The admitted first route is ACP through the
public Python `acp.core.Connection` and `acp.client.router.build_client_router`
interfaces. This avoids a TypeScript compiler or additional JavaScript worker.
The official library retains framing, request IDs and response correlation;
Orchestrarium retains provider policy, bounded capture and process ownership.
The explicit request identity `mimo` does not activate runtime selection.

Model selection uses public `send_request("session/set_model", ...)`, not
`ext_method` (which prefixes an underscore). Validate the separate model ID,
variant and advertised variants returned in `_meta.opencode`; a model name
ending in `/low` is not evidence that the low variant was selected. Observe and
drain received notifications before freezing a terminal result, including
notifications whose handler has not started yet. Callback failures must remain
visible even when the transport logs rather than propagates them.

**Live acquisition remains closed.** An empty ACP MCP list does not remove
inherited runtime servers. Effective tool permissions, subscription/account
binding, native executable and private HTTP shim ownership, process settlement
and durable receiving are not qualified by protocol fixtures. No installation,
login, credentials, profile change or model request is implied by this addition.
MiMo's `end_turn` is not a cancellation receipt; the inspected implementation
has no `session/close` operation. Do not substitute history deletion for cleanup.

The native local HTTP API remains an alternative for per-session permission
readback, durable queue receipts and richer history. It is not a direct billed
model API, but neither interface proves subscription coverage. Its official SDK
ships compiled JavaScript; using that client would add a JavaScript runtime,
not necessarily a TypeScript build. A Python HTTP client would be our maintained
binding rather than an official MiMo Python SDK.

Official source evidence (provenance, not required version pins):
[MiMo ACP agent](https://github.com/XiaomiMiMo/MiMo-Code/blob/e37f2c2d01460df19b31d67b8116d6c66fe33db8/packages/cli/src/acp/agent.ts),
[public ACP Connection](https://github.com/agentclientprotocol/python-sdk/blob/2ad204bb86111da9594bfe13f4a560249603feea/src/acp/connection.py),
[public client router](https://github.com/agentclientprotocol/python-sdk/blob/2ad204bb86111da9594bfe13f4a560249603feea/src/acp/client/router.py).

## Owned ACP byte streams

The public ACP SDK owns JSON serialization, newline framing and request
correlation. A byte-stream facade over the existing ProcessRunner dialogue
channel must not open another stdout reader, acquire descriptors or introduce
another subprocess owner. Connection shutdown and OS process settlement are
separate obligations.

Cancelling an asyncio await does not stop a blocking executor read. The process
owner closes child stdin only after the dialogue callback returns; waiting for
executor shutdown before releasing that read can therefore form a shutdown
cycle. The owner-local read-stop operation wakes the dialogue reader without
claiming provider EOF, closing stdin or settling the process. The facade drains
its retained I/O work before leaving the event loop. Existing pipe closure,
deadlines, capture and Windows Job settlement remain with ProcessRunner.

Close the official ACP Connection before closing the borrowed stream facade.
ACP sender shutdown does not itself close the supplied writer. A stalled write
remains subject to the process owner's deadline and cleanup result; it must not
be reported as graceful protocol completion. Local read-stop must remain
identifiable separately from peer EOF and capture/transport failure.

This capability does not admit a MiMo executable or activate a provider route.
MiMo needs its own exact argv profile and startup/configuration qualification;
it must not be disguised as the Grok, Kimi or SDK-worker profile.

## Selective MCP access: provider support versus this implementation

A per-run tool subset must not be implemented by modifying stock native-role
TOMLs or by treating `plugins=false` / `apps=false` as a selective allowlist.
The upstream mechanisms are different:

- OpenAI Agents SDK exposes only the MCP servers supplied to an Agent and supports
  server tool filters. This controls the functions exposed through that agent
  loop, not independent direct access to the server.
- Codex App Server accepts per-thread configuration and MCP server enablement plus
  `enabled_tools` / `disabled_tools`. An override is not automatically an exclusive
  replacement of every inherited server; plugin MCP and app connectors have
  separate configuration surfaces. The selected effective set must be established.
- Claude Agent SDK supports explicit `mcp_servers` with `strict_mcp_config` and
  per-subagent `tools`, `mcpServers` and `disallowedTools`. Its `allowed_tools`
  setting is auto-approval, not by itself a closed tool allowlist.
- ACP `session/new.mcpServers` supplies connections but does not establish exclusion
  of ambient configuration or provider-specific per-tool enforcement.

These are upstream capabilities, not a claim that Orchestrarium currently has a
qualified common selective-MCP path. The current Claude adapter explicitly has an
empty strict MCP set and verifies that fact; Codex carries selected per-invocation
configuration with an implemented thread-inventory validation gate whose current
live qualification remains open. Optional-null inventory fields follow the public
SDK schema; explicit null does not independently prove catalog completeness.
An extension must reuse current admission and adapter boundaries, preserve the selected subset on
resume, and exclude unexpected inherited tools without copying secrets into the
request. Filesystem read-only sandboxing does not constrain remote mutations made
through an MCP tool. No MCP server is activated by documenting this design.

Official references: [Agents MCP filtering](https://openai.github.io/openai-agents-python/mcp/#tool-filtering),
[Codex MCP configuration](https://developers.openai.com/codex/mcp/),
[Claude Python SDK](https://code.claude.com/docs/en/agent-sdk/python),
[Claude permissions](https://code.claude.com/docs/en/agent-sdk/permissions),
[ACP session setup](https://agentclientprotocol.com/protocol/session-setup).

## Limits beyond the bounded native qualification

1. The inspected Codex release uses an unbounded internal stdout line reader and
   line-count-bounded stderr storage. That release's public configuration does not expose a
   byte-bounded transport. The selected integration separates bounded public SDK
   evidence retention from a creator-applied Windows Job committed-memory budget
   and the existing hard deadline/settlement. The memory cap addresses uncontrolled
   decoder/buffer allocation without a private SDK fork; it is not a raw-output
   byte limit or complete capture of unavailable internal diagnostics. Allocation
   failure or missing required public evidence never counts as success. The bounded
   Windows runs established native ownership and settlement; they are not exhaustive
   memory-pressure or failure-path qualification. Another platform or materially
   changed containment path requires its own qualification.
2. Existing Windows atomic Job ownership is reused. The native runs above verify
   their owned descendant cleanup; source/unit evidence alone would not. Generic
   POSIX execution remains unavailable; process groups do not prove containment
   of escaping descendants. No generic private-directory hold is bypassed.
3. The caller must retain the actual Host/account/budget admission owner. Only
   the separate optional coordinator route additionally requires a coordinator
   model binding; only resume requires authenticated atomic snapshot ownership.
   Injected test owners do not establish real authority, account isolation or
   durable replay safety. These are existing host responsibilities, not a new
   policy, credential or session store in the SDK integration.
4. Claude has a direct SDK adapter and Kimi reuses its existing complete ACP owner
   through the same execution interface. Kimi results remain native CLI evidence,
   not fabricated structured SDK reviews; its existing owner receives them once.
   Claude selection currently requires a concrete model ID: existing short-alias
   parity is not established and no guessed alias mapping is used. Grok remains
   unavailable under the existing execution policy.

## Explicit runtime composition

`runtime.run_codex` is the parent callable, not an automatic install action. It
requires an explicit runtime executable/digest, Codex home/auth mode/account
selection, finite process/ledger budgets, deadline, cancellation probe and current
policy owner. It frames the task with the existing governance owner, claims one
launch atomically, checks native hook trust and creates the fixed SDK worker.
The creator reads back its retained outer Windows Job limits before process
creation and verifies direct-process membership before resuming it. Nested Python
venv Jobs do not replace this ancestor boundary; workers do not mistake an inner
Job for the owner. All Job handles remain parent-owned and non-inherited. API-key account readback identifies its mode, not a unique account;
exact key selection stays with the existing auth/environment owner.

`run_admitted_review` accepts the exact already-admitted Codex or Claude request.
Codex governance framing happens before admission; Claude retains its native
preset and receives common/Claude instructions through the existing owned file
transport. Provider-specific SDK factories remain behind the fixed worker boundary.
Kimi continues through its existing complete CLI/ACP owner, not this SDK receiver.

`create_review_coordinator` returns the Agents coordinator and its concrete
`SdkReviewExecutor`. The executor joins the owned runtime to scanned artifact
materialization, atomic ledger receiving and independent readback before returning
tool evidence. It preflights known artifact-path conflicts without reserving a new
store; final exclusive creation remains authoritative. The caller retains the
executor for cancellation and acquired evidence, including receiving failures.

The returned `RuntimeRun` retains the effective request, admitted selection,
output-scan context and sealed worker observation. Receiving uses these exact
objects and the existing receipt owner, closes its exclusive writer before
independent reading, then calls the existing atomic writer and validated reader.
`requestSha256` commits the explicit request/runtime selection, not every native
config file that Codex may load. Codex selection can carry an immutable sequence
of nonsecret public SDK `config_overrides`; the same exact overrides reach the
owned hook-trust probe and worker, and participate in that commitment. Empty
MCP scope selects no MCP tools; startup isolation controls are fixed before
admission, and explicit override tuples must already include those controls.
Overrides are caller-selected data, not permission or proof of the complete effective configuration; the existing owner
must admit them and account for managed requirements and inherited integrations.
Do not put credentials in command-line overrides. An unresolved prior launch is
never replayed.

A bounded single-model live test must separately establish which native agents,
MCP servers, apps and plugins can start or be called under its actual profile.
An empty MCP table is not an isolation guarantee, and model approval denial is not
a universal external-tool switch. Preserve the required owned hooks and current
account/permission controls; do not edit the user's global profile to make a test
pass. Normal authorized account/model metadata requests are distinct from model
turns. No such live-profile qualification is implied by the offline suites.

The worker's native nonblocking-pipe bridge requires Python 3.12 or later on
Windows. Normal host-pack installation does not provision this optional environment
or start it. Offline fixtures use synthetic adapters/process observations; those
cannot grant activation or prove native platform behavior.

## Before and after: what can be measured

| Aspect | Existing route | Optional SDK route | Required evidence |
|---|---|---|---|
| Review format | Final-line `GATE` parsing after CLI output | Native structured review and independent shape/identity checks | Malformed, missing, extra and contradictory result fixtures |
| Profile identity | Actual argv-derived model/effort | Actual SDK config and observed profile | Drift, swapped run and account fixtures |
| Receiving | Existing atomic ledger and independent reader | Same owners with explicit SDK representation | Launch-to-terminal round trip, conflict and replay tests |
| Coordination | Host-led workflow | Explicit review bridge keeps the same Host; a separate optional SDK coordinator is not started by it | Offline current-authority/resume tests; separate native qualification |
| Processes | Existing platform-specific supervisor | Same owner enclosing SDK worker | Cancellation, failure, descendant and crash tests per platform |

The existing common wrapper is already present; one common call is not a new
benefit. Legacy parsers/hooks stay while their host routes use them. No reduced
hook count, model-quality improvement, throughput gain or live reliability claim
follows from adding SDK dependencies. This branch removes no legacy execution
route or hook: their host-mode consumers remain supported. The new SDK review
route avoids a new final-line verdict parser and prose-to-structure model call;
Agents SDK supplies its model/tool iteration and paused-call representation rather
than a new custom loop or session store. These are avoided additions, not deletions
or measured maintenance savings. Offline fixture parity is not a live benchmark.

## Terms and Abbreviations

- Host: the existing invoking orchestration session; it retains launch authority.
- Binding: a bounded per-invocation constraint document, not authorization.
- V3: version-three provider-result envelope; selected SDK metadata has its own schema version.
- MCP: Model Context Protocol, used by connected external tool servers.
- SDK: software development kit; maintained provider or coordination library.
- CLI / API: command-line / application programming interface.
- JSON: JavaScript Object Notation, the strict binding and envelope serialization.
- UTF-8: Unicode text encoding.
- V2: version-two legacy CLI provider-result envelope.
- OS: operating system.
- ACP: Agent Client Protocol, used only inside applicable provider adapters.
- Job: Windows operating-system ownership boundary for a process tree.
- Provenance: recorded actual execution identity/configuration, not permission.
