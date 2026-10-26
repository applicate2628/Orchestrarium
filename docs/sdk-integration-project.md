# SDK integration project

Status: design reconciled on 2026-10-26 against implementation
[PR #19](https://github.com/applicate2628/Orchestrarium/pull/19), exact head
`9f1e6df297c47a8edf5eb44d2919a6a0ade553cb`. This PR remains documentation only.
The source matrix below supersedes future-tense implementation claims in the
original design; an implemented adapter is not proof of live qualification.
SDK, npm distribution and Rust operations are independent tasks.

## Source-pinned design-to-implementation matrix

All implementation links in this matrix select the exact PR19 head above, not a
moving branch. The implementation is still a draft, not merged product behavior.

| Work | Implementation and source evidence | Qualification and remaining work |
| --- | --- | --- |
| SDK-1 shared execution contract | Immutable [request/result/identity/schema](https://github.com/applicate2628/Orchestrarium/blob/9f1e6df297c47a8edf5eb44d2919a6a0ade553cb/scripts/sdk_execution/contracts.py), [parser](https://github.com/applicate2628/Orchestrarium/blob/9f1e6df297c47a8edf5eb44d2919a6a0ade553cb/scripts/provider_prompt.py), [ledger](https://github.com/applicate2628/Orchestrarium/blob/9f1e6df297c47a8edf5eb44d2919a6a0ade553cb/scripts/agent-run-ledger.py), schema and [receiving](https://github.com/applicate2628/Orchestrarium/blob/9f1e6df297c47a8edf5eb44d2919a6a0ade553cb/scripts/sdk_execution/receiving.py) extend existing owners. | Implemented and offline checked; old records and external nonauthority remain. Not a second ledger/framework. |
| SDK-2A Host-led Codex review | Opt-in [wrapper](https://github.com/applicate2628/Orchestrarium/blob/9f1e6df297c47a8edf5eb44d2919a6a0ade553cb/scripts/invoke-codex-prompt.py) with --sdk-review-binding uses [dispatch](https://github.com/applicate2628/Orchestrarium/blob/9f1e6df297c47a8edf5eb44d2919a6a0ade553cb/scripts/sdk_execution/dispatch.py) and the direct official Codex adapter. No outer Agents loop starts. | Source/offline receiving exists. Current-head installed Windows bridge and diagnostic/recovery qualification remain; historical Luna smoke is not that head's qualification. |
| SDK-2B optional Agents coordinator | [AgentsCoordinator](https://github.com/applicate2628/Orchestrarium/blob/9f1e6df297c47a8edf5eb44d2919a6a0ade553cb/scripts/sdk_execution/coordinator.py) requires an injected public Model and existing authority/executor. execute_admitted invokes the admitted executor; it does not supply the coordinator's Model. | Coordinator/session/resume contracts have offline coverage. Supported subscription-compatible Model binding, account/budget admission, live loop and Session/resume/crash evidence are separate remaining qualification. |
| SDK-3 adapters | [SDK execution modules](https://github.com/applicate2628/Orchestrarium/tree/9f1e6df297c47a8edf5eb44d2919a6a0ade553cb/scripts/sdk_execution) implement direct Codex/Claude and adapter-local ACP routes, including additional provider adapters. | Source and offline tests exist. Other-provider live qualification is deferred due to quotas, not absent implementation and not a blocker for Codex scope. Existing provider eligibility remains; Grok stays unavailable. |
| SDK-4 simplification | Structured results and the optional SDK-owned loop/session boundary avoid adding duplicate parser, loop and session glue. Existing owners validate and receive evidence. | Delete only superseded code whose consumers are covered. Still-used legacy routes and host hooks remain; there is no artificial task to remove every hook or CLI path. |

Reported qualification of reviewed tree
`872146aefc8e02277854a71cc2008d465ce8ac4e`: SDK 1103 passed / 5 skipped,
17 targeted passed; broad changed-owner suite 2171 passed / 97 skipped /
142 failure entries = 120 distinct failed IDs. All 120 IDs were reproduced on
clean main 24052b; this is not a green broad suite or full baseline equivalence.
Integration preserved all 68 non-release SDK paths; release notes were combined.
Historical Windows synthetic success/collision PASS and one Luna/high smoke PASS
(18.343 seconds, cleanup PASS) belong to the pre-merge candidate, not PR19 head.
No runtime tests are rerun by this documentation reconciliation.

## Selected next research goal: coordinator through the existing Codex subscription

Establish whether a public Agents Model can be implemented through the official
Codex SDK/App Server and the existing subscription login. Current code does not
contain such a backend. The official [Agents Codex example](https://github.com/openai/openai-agents-python/blob/17d994bd3045dae71acda676a4ef4762ed8ecd94/examples/tools/codex.py)
places Codex in tools; a tool integration does not make it the outer Model.
The [official tool documentation](https://openai.github.io/openai-agents-python/tools/#experimental-codex-tool)
likewise describes a tool, not a subscription-backed coordinator model.

Research must map the public Model request, tool-call/result, streaming, usage,
cancel/error and Session/resume contracts to supported Codex interfaces, with
fresh account/profile/budget admission, bounded output/time and owned cleanup.
Prove official support and honest limitations before implementation or live use.
No OAuth extraction, private API, copied credentials, API-billing substitution or
implicit model/account fallback. If the public contract cannot support the loop,
record the precise gap and retain Host-led mode. A later authorized bounded Codex
Agents-cycle qualification must include receipt, artifacts, ledger and crash/recovery
evidence; no such model invocation is authorized by this documentation stage.

## Purpose and scope

Replace concrete fragile execution/coordination glue with maintained components,
without building another framework. OpenAI Agents SDK supplies coordination mechanics;
Provider adapters use their selected native SDK or Agent Client Protocol (ACP).
ACP is local to Kimi/Grok adapters, not the common orchestration abstraction.
A model API is not a substitute for a provider coding runtime.

This project owns SDK-1 shared contract fixtures, SDK-2A a Host-led Codex bridge and SDK-2B an optional Agents coordinator, SDK-3 remaining provider adapters and SDK-4 qualified glue removal. Each implementation PR
names actual deleted glue and preserved receiving behavior. Independent [npm distribution](https://github.com/applicate2628/Orchestrarium/pull/17) and
[native Rust operations](https://github.com/applicate2628/Orchestrarium/pull/21) have independent main-based PRs and owning plans;
ranking/evaluation, expanded role lifecycle and cross-host takeover remain in
[PR #13](https://github.com/applicate2628/Orchestrarium/pull/13).
Neither design PR is a blanket merge prerequisite for this one. This extraction
moves the SDK design, not the earlier manual-trust documentation/test repair in PR17.

## Responsibility boundaries

- Existing shared governance, role/profile policy, budgets, permission and review
  owners retain authority. SDK guards/approval callbacks do not replace them or
  operating-system isolation.
- Python Agents SDK owns its model/tool iteration, conversation/session mechanics
  and paused-run state. Existing host-led mode remains supported; exactly one
  coordination owner is selected per run, never two competing Leads.
- One small domain execution-tool boundary carries admitted task/scope/profile/run
  identity to provider adapters and receives results/evidence. It is not a parallel
  schema registry or universal scheduler. Keep protocol/vendor types at adapters.
- Adapters own transport and provider-specific evidence/capabilities. Codex and
  Claude use direct official SDKs; Kimi/Grok use ACP stdio. The optional shared ACP
  client is an implementation dependency of those two adapters only, not a core
  protocol, mandatory prerequisite for other adapters or a proxy service.
- Existing deterministic operations and project-state writers retain their contracts
  and sole ownership. They remain Python today; later Rust replacements from PR21
  are consumed through those boundaries, not prerequisites for SDK integration.
- Each process tree has one OS containment/settlement owner. The adapter owns SDK
  protocol/session cleanup, not a competing tree-kill mechanism. SDK-created
  descendants must remain within the admitted containment boundary. Cancellation
  acknowledgement proves neither settlement nor rollback. Missing required capture,
  private-path or settlement evidence holds that lane; a stream-reader limit alone
  is not a total-output bound.
- SDK conversations, traces and RunState are not authoritative work-item/review/run
  ledgers. Source-only operation stores/activation registries remain disabled and
  nonauthorizing; changing SDK or transport does not activate them.

Canonical owners remain [shared governance](../shared/AGENTS.shared.md),
[Lead](../src.codex/skills/lead/SKILL.md),
[role policy](../shared/role-routing-policy.v1.json),
[external dispatch](../src.codex/skills/lead/external-dispatch.md),
[provider execution](../scripts/provider_prompt.py) and
[process supervision](../scripts/process_supervision/process_runner.py).
Current admitted Codex/Claude paths, Kimi explicit-only fixed-profile eligibility
and Grok unavailable execution remain unchanged. Missing transport capability is
not permission to switch providers, profiles, accounts or billing lanes.

## Dependencies and delivery boundary

The coordinator is optional, provisioned separately into an explicitly selected
isolated Python environment with tested dependency locks and compatible adapter
versions. Record compatible coordinator and consumed operation-interface/native
versions where used, the actual interpreter and route requirements; no hidden install,
environment discovery fallback or silent credential inheritance. The SDK project
owns that Python dependency contract; PR17 owns npm distribution and consumption
of the declared contract, not provisioning the environment. Existing CLI-owned ACP
operations retain their actual CLI/account prerequisites. No whole-product
Python-free claim follows from a future native hook port.

## Selected architecture and one source of truth

The common layer is Python plus the official
[OpenAI Agents SDK](https://github.com/openai/openai-agents-python), using its
[manager-as-tools pattern](https://github.com/openai/openai-agents-python/blob/main/docs/multi_agent.md).
Our small Python executor interface is exposed as an Agents SDK tool. It adapts
existing domain requests/results, not a new wire protocol or homegrown framework.
Provider-specific SDK/ACP types never become the coordinator's domain types.

One source of truth means one canonical owner per contract/state, not one giant
module or one physical file. Existing governance/profile/admission owners determine
allowed behavior; current project writers own durable state. Adapters translate
accepted inputs and observations, not copy rules, decide closure or maintain shadow
project ledgers. Native provider sessions and SDK conversation history may retain
transport/conversation state, but neither supersedes authoritative project state.

Selected adapter implementations:
- **Codex:** direct [official Python Codex SDK](https://github.com/openai/codex/blob/main/sdk/python/README.md)
  (`openai-codex`) over Codex App Server. No Codex-to-ACP wrapper and no alternative
  experimental Agents `codex_tool` for the same operation. The latter is a different
  integration, not an alias for the selected SDK.
- **Claude:** direct [official Claude Agent SDK for Python](https://github.com/anthropics/claude-agent-sdk-python).
  No extra Claude-to-ACP translation. Bind and qualify the SDK's selected bundled
  or explicit CLI instead of silently changing the installed runtime.
- **Kimi:** its [native ACP stdio interface](https://github.com/MoonshotAI/kimi-code/blob/main/docs/en/reference/kimi-acp.md).
  Preserve the existing fixed-profile/readback/cleanup contract. Reuse an official
  [Python ACP client](https://github.com/agentclientprotocol/python-sdk) only where
  it demonstrably replaces wire plumbing without weakening those guarantees.
- **Grok Build:** its [native ACP stdio interface](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/15-agent-mode.md).
  It remains unavailable under current Orchestrarium execution policy; this is a
  design target, not activation or permission to probe it. No WebSocket server,
  relay or alternate transport until a concrete remote use case justifies it.

These are selected integration paths, not measured reliability or universal
platform qualification. PR19's [capability-based compatibility contract](https://github.com/applicate2628/Orchestrarium/blob/9f1e6df297c47a8edf5eb44d2919a6a0ade553cb/docs/sdk-execution.md#capability-based-compatibility)
supersedes this draft's mandatory product-wide SDK/CLI pin. Admission checks required
public APIs, capabilities and actual observed contracts; release strings/digests
are evidence for a selected run, not an allowlist. Reproducible test dependency
locks remain useful and are not runtime admission. Preserve executable identity,
account and permissions within each run; no silent SDK/ACP/CLI fallback.

The executor accepts the existing admitted work-item/run/artifact, role, exact
provider/profile, scope and constraints. It yields normalized observations and the
existing nonauthorizing terminal/evidence result through current receiving owners.
It exposes only operations actually required by the initial workflow: execute and
cancel, with resume/reconciliation admitted when supported. A native session/call ID
is mapped to domain identity, never used as authority. External agent output enters
as untrusted tool/evidence content, not a user instruction or steering command.
Use supported native external-message semantics when needed and qualify their
version requirements; never upgrade authority by falling back to plain user text. Capability data stays with
existing routing/admission. Unsupported required capability is reported before
effects; absent usage is unknown, not zero. Permission callbacks consult current
human authority. Cancel acknowledgement is not rollback or descendant settlement.

### Conservative provider boundary requirements

- Codex [high-level API defaults](https://github.com/openai/codex/blob/main/sdk/python/docs/api-reference.md)
  include `auto_review`. For the first read-only slice explicitly select the SDK's
  read-only sandbox and `deny_all`; the latter means no approval escalation, not
  prohibition of all tool execution. Qualify actual filesystem/network/tool scope.
  High-level constructors do not expose a custom approval callback. The direct
  low-level [CodexClient](https://github.com/openai/codex/blob/main/sdk/python/src/openai_codex/client.py)
  does, but its default handler accepts command/file-change requests. Any later
  approval-required lane must qualify a supported explicit current-authority handler;
  do not patch private SDK fields, inherit permissive defaults or pretend the
  high-level client provides a callback it lacks.
- Codex client environment overrides merge with the parent environment, so an
  `env` dictionary alone does not prove credential isolation. Its direct-child
  shutdown does not prove descendant settlement; a line-count stderr buffer is
  not a byte bound. Qualify clean credential scope, total-output bounds and process
  settlement through supported interfaces and existing owners. If those required
  guarantees cannot be supplied, hold that lane; do not add a permissive fallback
  or claim a library selection has solved the gap.
- Claude's `allowed_tools` is an auto-approval allowlist, not removal of all other
  tools. Configure actual tool availability, denials and permission callbacks
  deliberately; never copy permissive example settings. Qualify instruction loading
  and resume behavior against the selected CLI version so revised rules are not
  assumed to replace a saved prompt automatically.
- Kimi/Grok approval requests use existing authority; no always-approve/yolo mode
  merely because an upstream automation example uses it. Local stdio avoids new
  ports/server credentials but still needs bounded capture and owned process cleanup.

PR19 implements the SDK-owned provenance extension across parser, ledger,
schema, validator and receiving instead of labelling SDK work as direct CLI.
Its immutable request binds provider/profile, work item, run and artifact identities.
Observed transport/profile data must not be fabricated as CLI flags. The matrix
above names these owners; their offline acceptance is not generic route activation.
Legacy records and still-used CLI parsing retain their interpretation. Kimi's
profile/capability, omission, redaction and close/delete obligations remain adapter
requirements, not proof supplied by generic ACP availability.

Application-programming-interface (API) model access, existing CLI capability,
provider admission and account billing are separate. An injected Agents Model does not automatically acquire a Codex/Claude
subscription or ACP account binding; the selected research goal above must prove
a supported Codex subscription path without introducing API billing.
Select and verify each adapter's authentication/billing lane and credential environment; no coordinator-key inheritance or default
fallback may silently switch its intended account/billing route. Keep coordinator
credentials out of adapter environments unless explicitly selected; the excluded
[experimental Codex tool](https://github.com/openai/openai-agents-python/blob/main/docs/tools.md#experimental-codex-tool)
is not a shortcut around this boundary.
Explicitly configure and admit trace-export data/destinations before SDK execution;
SDK model guardrails are not action
permissions, and traces or session stores are not the authoritative project ledger.
Reuse existing admission, budget and owner checks at adapter entry, not new global
gates; a turn limit is not a monetary budget. No coordinator model is selected here.

## Owned process settlement: required before activation

Every process-producing adapter must prove settlement of its owned process tree,
not just a completed model turn, cancel acknowledgement or closed SDK client.
This is a required receiving criterion for the first read-only slice too: read-only
filesystem intent does not prevent a coding runtime from creating children.

Reuse the existing process-supervision owner and its platform containment boundary;
do not write another general supervisor inside each adapter. Before execution, bind
which owner controls each process/containment object and which SDK owns session and
stream cleanup. Native containment and SDK session cleanup are different duties,
not competing process-tree managers. A supported way to place SDK-created children
inside that ownership boundary must be qualified before live use; selecting a library
or observing the parent PID is not evidence that this integration exists.

The bounded candidate is one adapter worker for one domain operation, created within
existing creator-owned OS containment before SDK initialization. The SDK runtime and
its descendants inherit that boundary; the supervisor settles it while the worker
performs protocol/session cleanup. This worker is a process-isolation boundary, not
another coordinator, daemon, protocol proxy or persistent service. On Windows use
existing atomic create-in-Job/suspended-start ownership, not adding PIDs after SDK
spawn. PR19 implements a narrow contained SDK worker and offline settlement coverage.
Current-head installed/native and crash/recovery evidence remain scoped acceptance
work, not activation of unrelated unavailable generic routes. POSIX needs
its own containment and crash-settlement proof; process groups alone are not a
universal guarantee against escaping descendants.

Acceptance must exercise successful completion, execution error, timeout, user cancel,
partial spawn/setup failure, coordinator crash and restart with acquired evidence.
Include a child that outlives its parent and resists ordinary cancellation. Prove no
owned descendant remains and required I/O/resources are settled, while unrelated
processes survive. Bind cleanup to creator-retained handles or an equivalently stable
owned containment identity, never process names or PID/parent-PID ancestry alone.
Required crash cleanup must be provided by the admitted platform/owner mechanism,
not an assumed finally block in a process that has already died. Windows and POSIX
need independent evidence; neither platform's semantics prove the other's.

Keep the operation unsettled under existing failure/recovery semantics when required
settlement evidence is missing; do not grant a successful terminal result, replay
uncertain work, or add a permissive fallback. Preserve captured outcomes even when
cleanup fails. If current public SDK and process-owner boundaries cannot supply the
required guarantee, the affected route remains unqualified until a narrow owner-level
integration closes it. Do not silently activate the currently unavailable generic
runner or introduce a Rust dependency just to claim this is solved.

## Concrete SDK cases: replacement, deletion and proof

Use ready components only where their ownership removes existing glue or avoids a
new duplicate mechanism. These are implementation choices, not qualified live routes.
No blanket hook-count reduction follows; host-mode hooks and foreign registrations
(including Graft) remain outside SDK-owned-lane deletion.

1. **Structured read-only review.**
   `scripts/provider_prompt.py:6139–6208` already extracts Codex JSONL but then
   interprets a prose final line (`GATE: PASS` / `GATE: REVISE`). The Codex executor
   uses native `output_schema` through the selected Codex SDK for its closed verdict
   and required evidence fields, mapped into the existing receiving owner.
   [Agents SDK output types](https://github.com/openai/openai-agents-python/blob/main/docs/agents.md#output-types)
   validate the coordinator's own output, not the nested executor's result. Remove that lane's format-only prompt and final-line parser;
   retain independent evidence checks, nonauthority, size bounds, failures and
   cleanup. Structured output alone does not require Agents SDK: a provider-native
   schema is the smaller alternative when the existing adapter already supports it.
   An SDK tool wrapping arbitrary ACP prose does not structure the inner result;
   do not add a model call merely to translate prose into JSON. Qualification covers
   missing/extra fields, refusal, truncation, unsupported schema, contradictory
   evidence, wrong run identity and incomplete execution. Legacy parsers/tests stay
   for uncovered routes (`tests/test_kimi_transport.py` contains existing verdict cases).
2. **Typed observations instead of rendered-transcript recovery.**
   `scripts/universal-hooks/scripts/hook_common.py:53–70,695–824` reconstructs call/result
   correlation and recognizes text such as `Exit code: N`;
   `check-passive-polling-stop.py:54–105` classifies waiting/probing prose.
   Use [SDK stream events](https://github.com/openai/openai-agents-python/blob/main/docs/streaming.md),
   call IDs and lifecycle callbacks for its own operations, or negotiated ACP
   updates inside adapters. Remove only that lane's transcript-shape reconstruction;
   feed existing semantic checks explicit observations, not a new policy engine.
   The executing tool must expose validated exit status: a generic output event is
   not proof. Test interleaved/duplicate/unknown IDs, missing output, cancellation,
   late events and incomplete streams; drain required events before completion.
   Preserve genuine-user provenance, host-mode parsing and external CI/reply waits.
   Reuse `tests/test_hook_common.py` and `tests/test_passive_polling_stop.py`.
3. **Adapter-local ACP plumbing, not the common layer.**
   Current `scripts/provider_prompt.py:952–1446` already implements Kimi ACP.
   Replace only demonstrated duplicate serialization, request/response multiplexing
   and schema plumbing with the [official Python ACP SDK](https://github.com/agentclientprotocol/python-sdk).
   Replay `tests/test_kimi_transport.py` fixtures through both transports. Preserve
   strict message policy, fixed profile, model/effort readback, selected/observed
   capabilities and omissions, permissions, bounds, redaction and close/delete
   settlement. Unknown/malformed messages, capability refusal, cancellation and
   cleanup failures must remain distinguishable. No second ACP stack is retained.
   This cleanup is not a prerequisite for Agents/Codex integration.
4. **Conversation and paused-call continuation.**
   In the new coordinator mode, use [Sessions](https://github.com/openai/openai-agents-python/blob/main/docs/sessions/index.md)
   and [RunState](https://github.com/openai/openai-agents-python/blob/main/docs/results.md)
   instead of writing a new history/replay/pause loop. This prevents new glue, not
   deletion of authoritative work-item/review/agent-run ledgers. Test same-session
   resume, stale state, restart, missing resume capability and no duplicate tool
   effects. Before a resumed new effect, reuse existing admission, ownership, budget
   and approval checks against current authoritative state and the original
   run/profile/artifact/account binding. A serialized approval is not fresh authority:
   changed or revoked bindings stop the dependent call under existing controls,
   without silent rebinding or new statuses. Test revoked approval and changed
   artifact/profile/account with no effect. An uncertain prior effect is reconciled,
   not replayed as a new user turn.
5. **Coordinator loop and approval mechanics, not new authority.**
   The [manager-as-tools pattern](https://github.com/openai/openai-agents-python/blob/main/docs/multi_agent.md)
   owns model/tool iteration and specialist returns in SDK mode; remove mechanical
   dispatch narration only where code actually tracks it. Role selection, scope,
   budget, independent review and completion obligations stay with their owners.
   Never run this coordinator alongside a host Lead or substitute API subagents for
   coding runtimes. [SDK approval interruptions](https://github.com/openai/openai-agents-python/blob/main/docs/human_in_the_loop.md)
   can retain an exact pending call; they do not grant consent. Local shell/apply-patch
   approvals are opt-in, and sticky tool-name/type approvals can cross agents or
   skip destination-policy re-evaluation. Configure per-call decisions without
   automatic sticky scope widening; test changed arguments/destination, rejection,
   nested tools, restart and replay, with no effect before required approval.

Do not replace publication/path/ownership checks with SDK guardrails, operating-system
isolation with permission callbacks, or process settlement with stream cancellation.
Tool discovery does not prove appropriate MCP use; reminders cannot be removed on
that basis. Trace/session storage is not project-state authority. For each replacement,
record actual deleted source and retained route coverage; a new dependency plus all
old glue is not a completed simplification. Upstream interfaces were inspected through
GitHub on 2026-10-23; implementation records inspected revisions and qualifies required capabilities.

## Remaining delivery plan

1. Preserve SDK-1's implemented identity/schema/receiving owners; extend only
   concrete uncovered cases at those owners.
2. Qualify SDK-2A's current-head installed Windows bridge and diagnostic recovery
   independently of the optional outer loop; preserve strict trust and profile gates.
3. Research SDK-2B's supported subscription-backed public Model contract, then,
   only after admission and separate launch authorization, qualify one bounded
   Agents cycle and Session/resume/crash receiving. Reuse SDK mechanics rather than
   creating a parallel scheduler, session store or authoritative ledger.
4. Keep SDK-3's implemented source/offline coverage; schedule other-provider live
   evidence when quotas and permissions permit. Codex work need not wait for it.
5. Apply SDK-4 deletion criteria within each qualified lane. Retain live legacy
   routes and hooks; do not create a whole-product deletion milestone.

Rust and npm are independent tasks, not blanket prerequisites. No default route
change, provider activation or new paid/live launch follows from this plan.

## Verification and completion

Use isolated fixtures/replayed observations and stubbed providers first. Do not run
duplicate live effects or paid models to compare implementations. Deterministic
transport/parsing/receiving changes preserve contract-visible bytes, errors,
ordering, bounds and effects; normalize only justified nondeterminism. Stochastic
model prose is not a byte-equality oracle. Intentional SDK behavior changes need
separate accepted outcome criteria; do not hide them inside a refactor.

Preserve current receiving, review, retry and recovery obligations through existing
owners. Required tests include valid and malformed input, unsupported capability,
selected-versus-observed profile drift, swapped IDs, partial/incomplete output,
permission rejection/revocation, resumed changed scope/account, cancellation,
cleanup failure, replay and persisted terminal readback. Reuse affected suites:
`tests/test_kimi_transport.py`, `tests/test_hook_common.py`,
`tests/test_passive_polling_stop.py`, `tests/test_agent_run_ledger.py`,
`tests/test_review_loop_state_v2.py` and `tests/test_solution_attempt_reducer.py`.
Source review/stubs do not qualify live providers or platform process guarantees.

Provider/runtime versions and the coordinator-model/account choice must be explicit
before live qualification, with applicable route, data, budget and permission.
Current generic Windows CLI remains unavailable at its private-directory boundary;
generic POSIX execution remains unavailable. Native-host/specialized paths are not
proof those generic entrypoints work. First SDK changes may preserve existing
admitted paths without claiming to enable the generic runner.

Review responsibility: provider integration owns adapters/SDK changes; Architect
and existing state/review/process owners accept implementation boundaries; Lead coordinates scope and
independent reviewers verify deletions and regressions. No new mandatory governance
engine is introduced. Completion names delivered route coverage, deleted code,
remaining qualification and actual limitations. No SDK benefit is proved merely by
adding a dependency. This design-only PR requires scope/link/diff review, not a claim
of runtime regression qualification.

## Terms and Abbreviations

- SDK: software development kit; here ready coordination or transport components.
- ACP: Agent Client Protocol; a transport between a client and coding-agent runtimes.
- API / CLI: application programming interface / command-line interface.
- Agents SDK: OpenAI coordination framework, not a universal provider runtime.
- RunState / Session: SDK paused-run state / conversation-history mechanism,
  neither a replacement for authoritative project state or current permission.
- JSON / JSONL: structured JSON data / newline-delimited JSON transport records.
- npm / Rust: separately owned delivery tooling / native deterministic implementation.
- Lead / PR: existing orchestration owner / pull request.
