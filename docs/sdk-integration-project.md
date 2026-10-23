# SDK integration project

Status: standalone design and implementation backlog, extracted from
[PR #17](https://github.com/applicate2628/Orchestrarium/pull/17) at
`b67b150f197aa53fcf7a088aa67eecaec80e0cf6`. Based directly on
[main 84eefb6b](https://github.com/applicate2628/Orchestrarium/commit/84eefb6bbeec9ebbe032f00788f249ae59da05b5).
This PR changes documentation only; it delivers no SDK runtime, dependency install,
provider activation or launch authority. SDK work is the first implementation
workstream; it does not wait for Rust, npm or the rest of 2.0.

## Purpose and scope

Replace concrete fragile execution/coordination glue with maintained components,
without building another framework. OpenAI Agents SDK supplies coordination mechanics;
Agent Client Protocol (ACP) supplies a common agent transport through adapters.
They solve different problems: using ACP is not adopting an Agents SDK coordinator,
and a model API is not a substitute for a provider coding runtime.

This project owns SDK-1 contract fixtures, SDK-2 ACP plumbing replacement,
SDK-3 structured review and SDK-4 a bounded coordinator mode. Each implementation PR
names actual deleted glue and preserved receiving behavior. Native deterministic
operations, common-hook Rust replacement and npm distribution remain in PR17;
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
- Adapters own transport and provider-specific evidence/capabilities. Prefer one
  Python ACP client, not mandatory Python and Rust client stacks or proxy services.
- Existing deterministic operations and project-state writers retain their contracts
  and sole ownership. They remain Python today; later Rust replacements from PR17
  are consumed through those boundaries, not prerequisites for SDK integration.
- Each child has one lifecycle owner: SDK adapter for SDK-created children, native
  supervision for native-created children. Cancellation acknowledgement proves
  neither descendant settlement nor rollback. Missing required bounded capture,
  private-path or settlement evidence holds only that execution lane. A stream-reader
  limit alone is not a total-output bound.
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

## Python SDK and generic provider execution boundary

Evaluate the official
[manager-as-tools pattern](https://github.com/openai/openai-agents-python/blob/main/docs/multi_agent.md)
for unified Python coordination that retains control over specialist results.
The SDK supplies the agent loop and conversation/tool-call/session mechanics, not a
new homemade scheduler, Orchestrarium policy, project-state authority or permission.
Use one [Python ACP client](https://github.com/agentclientprotocol/python-sdk) behind
the Agents execution tool as the common agent transport, not a new wire protocol.
Keep the existing small domain execution contract; one ACP runtime maps it to the
protocol without leaking full ACP/Codex types into coordination or state owners.
Prefer stable ACP version 1; optional/draft extensions require a demonstrated need.
The [Rust ACP SDK](https://github.com/agentclientprotocol/rust-sdk) is an alternative
for a proven native-client requirement, not a second mandatory client. No proxy,
conductor or daemon is required merely to unify adapters.

Upstream candidates are [Codex ACP](https://github.com/agentclientprotocol/codex-acp)
over Codex App Server, [Claude ACP](https://github.com/agentclientprotocol/claude-agent-acp)
over Claude Agent SDK, [native Kimi ACP](https://github.com/MoonshotAI/kimi-code/blob/main/docs/en/reference/kimi-acp.md),
and [Grok Build ACP](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/15-agent-mode.md). Protocol availability
is not Orchestrarium admission or qualified capability/platform coverage: current
Codex/Claude/Kimi rules remain, and Grok stays unavailable here until separately admitted.
Codex-specific SDK/protocol extensions are adapter-local only for proven ACP gaps,
explicitly selected rather than automatic fallback or a second transport for the same
case. Codex is not restricted to rare tasks; existing admission selects eligible work.

The tool reuses run/work-item identity, role/scope, admitted route and constraints,
mapping required task capabilities to ACP rather than inventing parallel schemas.
Adapters must start an admitted scoped operation and return a verified terminal
result, using ACP requests/updates/cancellation/permission rather than parallel
messages. Reconciliation/resume and usage coverage are negotiated capabilities;
missing usage is unknown, not zero. Missing required capability fails typed
unsupported before effects. Resume is not a new turn or replay of uncertain effects;
cancel acknowledgement proves neither rollback nor descendant settlement. Permission
callbacks use existing human authority, not self-approval or an operating-system sandbox.
Keep capability data in existing routing, not a new registry.

The [current result parser](../scripts/provider_prompt.py) requires the v2 execution
path to be `direct-external-cli`. New SDK-owned routes need one narrowly admitted
contract extension across producer, result parser, ledger writer, JSON schema,
state validator and persisted readback before activation. Current bindings include
`shared/schemas/agent-runs.schema.json:107`, `scripts/agent-run-ledger.py:2358,2389`
and `scripts/validate-work-item-state.py:3918–3935`; changing only the adapter/parser
would produce rejected or falsely classified records. Preserve old-record decoding
and external nonauthority: never label SDK work as CLI or internal merely to pass.
Reuse existing versioned owners, not a new schema/exception per provider.
Apply this to genuinely new SDK-owned execution routes, including those using ACP.
Replacing ACP plumbing inside the existing Kimi CLI-owned lane does not by itself
change its execution path: retain truthful current provenance and record adapter/
version evidence. Transport readiness never establishes receiving parity.
Profile and identity evidence must also survive the boundary. Current model/effort
validation derives from actual `launchFlags` (`provider_prompt.py:1583–1601`;
`validate-work-item-state.py:4020–4042`); SDK routes must record their actual transport
configuration, not fabricate CLI arguments. Extend the existing versioned provenance
owner for that representation. Map SDK/ACP session/request IDs to existing admission,
launch, dispatch and evidence-run identities; do not replace those identities or
inject extended fields into legacy records that forbid them. Verify the complete
admission → launch → result → ledger write → validation/readback chain with mismatched
profile/run/role/artifact fixtures, old records, unsupported versions and duplicate
terminal delivery. Keep format adapters at the boundary, not provider branches in
the domain reducer. Inventory obsolete prompt/launch/parsing glue per supported host
before deleting it; retain shared semantic checks and any uncovered existing route.
For Kimi, preserve its existing ACP model/effort readback, selected/observed
capability receipts and explicit omissions, redaction, and session close/delete
settlement. Generic ACP availability is not equivalence to this existing adapter.

Application-programming-interface (API) model access, existing CLI capability,
provider admission and account billing are separate: ACP unifies agent transport,
not coordinator-model API access. Select and verify each adapter's authentication/
billing lane and credential environment; no coordinator-key inheritance or default
fallback may silently switch its intended account/billing route. Codex-specific SDK
alternatives need particular care with [API-key inheritance](https://github.com/openai/openai-agents-python/blob/main/docs/tools.md#experimental-codex-tool).
Explicitly configure and admit trace-export data/destinations before SDK execution;
SDK model guardrails are not action
permissions, and traces or session stores are not the authoritative project ledger.
Reuse existing admission, budget and owner checks at adapter entry, not new global
gates; a turn limit is not a monetary budget. No coordinator model is selected here.

## Concrete SDK cases: replacement, deletion and proof

Use ready components only where their ownership removes existing glue or avoids a
new duplicate mechanism. These are implementation choices, not qualified live routes.
No blanket hook-count reduction follows; host-mode hooks and foreign registrations
(including Graft) remain outside SDK-owned-lane deletion.

1. **Structured read-only review.**
   `scripts/provider_prompt.py:6139–6208` already extracts Codex JSONL but then
   interprets a prose final line (`GATE: PASS` / `GATE: REVISE`). For a separately
   admitted SDK-owned reviewer, use [Agents SDK output types](https://github.com/openai/openai-agents-python/blob/main/docs/agents.md#output-types)
   with a closed verdict and required evidence fields, mapped into the existing
   receiving owner. Remove that lane's format-only prompt and final-line parser;
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
3. **ACP transport plumbing, not another Kimi feature.**
   Current `scripts/provider_prompt.py:952–1446` already implements Kimi ACP.
   Replace only demonstrated duplicate serialization, request/response multiplexing
   and schema plumbing with the [official Python ACP SDK](https://github.com/agentclientprotocol/python-sdk).
   Replay `tests/test_kimi_transport.py` fixtures through both transports. Preserve
   strict message policy, fixed profile, model/effort readback, selected/observed
   capabilities and omissions, permissions, bounds, redaction and close/delete
   settlement. Unknown/malformed messages, capability refusal, cancellation and
   cleanup failures must remain distinguishable. No second ACP stack is retained.
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
GitHub on 2026-10-23; implementation must pin and qualify compatible revisions.

## SDK implementation backlog

1. **SDK-1: freeze the existing execution boundary and fixtures.**
   Owner: provider integration/QA with Lead. Trace admitted task, role, profile,
   artifact and run identity through the actual adapter/result/ledger/readback
   owners named above. Reuse existing fixtures; add only uncovered mismatch,
   cancellation, approval-resume and historical-record cases. Define one domain
   execution boundary implemented by adapters, not a new generic framework or
   duplicate schema. Deliverable: executable acceptance fixtures and exact migration
   map; production behavior and provider admission unchanged.
2. **SDK-2: replace ACP wire plumbing in the existing Kimi adapter.**
   Owner: provider integration. Use the official Python ACP client to remove only
   serialization/request multiplexing/schema boilerplate it actually replaces.
   Retain fixed profile, observed capability/readback, permissions, redaction,
   bounds and close/delete settlement. Same CLI-owned route retains truthful
   provenance; do not manufacture a new execution path. Deliverable: old/new
   fixture parity, then one selected production transport with superseded wire
   plumbing removed. This is protocol reuse, not Agents SDK orchestration or a
   new Kimi capability. Do not enable additional providers to complete this task.
3. **SDK-3: remove prose-only review verdict formatting.**
   Owner: review-result/provider owner. First use native structured output if the
   admitted provider route supports it without adding a coordinator. Use Agents
   SDK output types only for an explicitly SDK-owned review route. Map the closed
   verdict/evidence result through the existing receiving owner; retain semantic
   review and external nonauthority. Deliverable: malformed/refused/incomplete/
   mismatched-result tests and removal of the qualified route's format-only prompt
   and final-line parser. No extra model call to translate prose, no silent model,
   account or billing change, and no removal of parsers still used by other routes.
4. **SDK-4: one bounded Agents SDK coordination mode.**
   Owner: Lead/provider integration. Use manager-as-tools, typed execution events,
   Sessions and RunState for one agreed workflow, replacing the corresponding
   model/tool loop, transcript reconstruction and pause/history glue. Reuse the
   common execution tool from SDK-1/2; provider SDKs stay inside their adapters.
   Complete the versioned result/ledger chain before activation. Retain one
   coordinator, current authority on resume, exact operation identity and the
   existing state/process owners. Deliverable: restart/cancellation/permission/
   incomplete-stream fixtures and explicit route/dependency configuration. This
   mode does not run alongside the existing host Lead. If a smaller existing-host
   solution covers the case, do not add the SDK coordinator just to use the library.

SDK-1 is preparation for the following changes, not a stand-alone abstraction layer.
SDK-2 and SDK-3 can be separate bounded PRs after their affected contract fixtures;
SDK-4 depends on the common boundary and its own qualified use case, not Rust/npm.
No live qualification occurs without the required route, data, budget and permissions.

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
