# Distribution and hybrid runtime project

Status: standalone documentation/design project, extracted 2026-10-23 from the
2.0 roadmap. The npm distribution and hybrid Python/Rust target are retained;
package/command design and qualification targets are specified below; implementation
and live native/SDK routes are not delivered or qualified. This document grants no provider launch, payment,
publication, installation or runtime activation authority.

## Purpose, source baseline and scope

Make Orchestrarium easier to distribute and maintain through a versioned skill and
resource payload, a thin npm launcher, deterministic Rust operations, and Python
coordination using the OpenAI Agents software development kit (SDK). Provider work
crosses a provider-neutral execution-tool boundary using Agent Client Protocol
(ACP) and provider-specific adapters. Codex remains inside its adapter, not above
other providers. Python stays the coordination implementation, not a temporary
migration oracle. The target supersedes whole-Python retirement.

This project is independent of an Orchestrarium 2.0 release. Qualified bounded
slices may ship in the current version; packaging, native operations and SDK
coordination have their own admission and evidence, not an all-or-nothing cutover.
Historical outcomes 1 and 5 in [planning PR #13](https://github.com/applicate2628/Orchestrarium/pull/13)
are its provenance, recorded at commit `40b67327e086c0b5908549358e1b2af91f933b0c`.
That planning PR is not an implementation or merge prerequisite for this project.

Current-source baseline: [main at 84eefb6b](https://github.com/applicate2628/Orchestrarium/commit/84eefb6bbeec9ebbe032f00788f249ae59da05b5).
Repository observations below are source facts, not verified installed behavior.
Upstream references identify official component/protocol candidates, not qualified
Orchestrarium integrations; recheck versions and supported capabilities before
implementation. The [installation contract](../INSTALL.md) and [runtime overview](../README.md)
still describe live Python-owned behavior and unavailable generic execution. Their
historical Rust-to-2.0 deferral is superseded for project sequencing here, not a claim
that an unavailable runtime path is now enabled.

The Windows permission-rendering correction already belongs to its native descriptor
owner at [2e91ebee](https://github.com/applicate2628/Orchestrarium/commit/2e91ebeeb4cd693c13cea714f995cc3389972268),
not new Rust scope. Preserve the publication transcript frontier at
[54c11111](https://github.com/applicate2628/Orchestrarium/commit/54c11111a4fe1eb1073d2a259165edeca8a519ef)
and decision-admission/native-normalization custody at
[3a542fc5](https://github.com/applicate2628/Orchestrarium/commit/3a542fc5827d3b80c3203bf94943e900a95a4ba2).
These scoped corrections do not prove universal agent enforcement or installed receiving.

**Ownership and change surface:** Product Manager owns package/product scope;
Lead owns coordination admission and sequencing; Architect and affected existing
hook, helper, installer, process and state owners accept implementation boundaries.
Toolchain/Platform Engineer owns the admitted delivery work. This project changes documentation and its narrow manual-trust contract tests,
not production runtime code, schemas, installed files, configuration, state,
provider policy or gates. Later runtime implementation belongs in separate PRs.

The existing [shared governance](../shared/AGENTS.shared.md),
[Lead contract](../src.codex/skills/lead/SKILL.md),
[role policy](../shared/role-routing-policy.v1.json),
[external dispatch contract](../src.codex/skills/lead/external-dispatch.md),
[installer](../scripts/production_installer.py) and
[publication-safety contract](../shared/references/repository-publication-safety.md)
remain canonical. Reuse their admission, review, recovery, permissions and budget
controls instead of copying a second governance framework into this project.
Keep a short invariant core: one owner per effect/state/process lifecycle; immutable
operation inputs; verified readback; preserved obligations and retry lineage;
reconciliation before retry of uncertain effects; and no expansion of authority by
changing a language, transport or entrypoint. Instructions are not host enforcement.
Unsupported or uncontrolled paths remain explicit limits. A real blocker holds its
dependent lane, not unrelated authorized work.

**Non-goals:** the 2.0 routing comparator, new exact-profile rankings, empirical
model-evaluation program, expanded native-role adoption/update/deletion/reclaim,
live cross-host takeover and named policy preferences remain separately scoped.
No new provider admission, Kimi `auto`, Grok activation, removed provider packs,
autonomous learning, universal scheduler, state service, approval gate, daemon or
whole-product Python-free promise follows. Manual-transfer parity is within the
operation map below; new cross-host continuation semantics are not.

## Existing behavior and target architecture

Current host-led coordination remains a supported mode until an admitted replacement
qualifies. External `auto` remains limited to current admitted Codex/Claude profiles;
Kimi remains explicit-only through fixed `kimi-code/k3`, for policy-admitted read
work or scoped engineering mapped to the existing external worker. External results
remain independently verified and nonauthorizing. Grok remains classifier-only with
execution unavailable; listing its upstream adapter is not launch/probe permission.

The [process runner](../scripts/process_supervision/process_runner.py) already defines request/result,
cancellation, settlement and Windows native parsing contracts. The generic Windows
CLI is blocked at its private request-directory boundary; generic POSIX execution
is unavailable. Specialized POSIX supervision and native-host dispatch are not proof
that either generic entrypoint works. A source-only store/activation registry is
also not evidence of a live durable execution service.

a thin entry dispatcher selects a direct native operation
or the Python/Agents SDK coordinator, which invokes bounded Rust operation tools.
Provider work uses one common execution-tool boundary with provider-specific adapters,
not a claim that one provider's SDK supplies every provider's agent runtime.
It does not recursively start another coordinator. Current host-led operation is a
separate retained mode, not silently replaced; exactly one coordination owner is
selected per run. The native component uses one Cargo package (Rust build/package
unit) and one CLI per supported target, not one crate/service per script. This map
names logical boundaries; implementation admission fixes names and layout:
- [production_installer.py](../scripts/production_installer.py) → Rust installer
  plan/apply/reconcile, retaining coupled role/configuration ownership.
- [Universal-hook canon](../scripts/universal-hooks/) → Rust deterministic checks
  with narrow host/CLI adapters, not general-purpose Python coordination logic;
  pack-specific hooks retain their host semantics and consume the same canon.
- [resolve-agents-mode.py](../scripts/resolve-agents-mode.py) → Rust configuration/
  admission operations preserving precedence, normalization and role/profile policy;
  Python coordinates requests and consumes decisions, without duplicating that policy.
- [mutate-work-item.py](../scripts/mutate-work-item.py),
  [agent-run-ledger.py](../scripts/agent-run-ledger.py),
  [review_loop_state.py](../scripts/review_loop_state.py) and
  [solution_attempt/reducer.py](../scripts/solution_attempt/reducer.py) → distinct Rust
  state-operation submodules and pure reducer. Python coordinates workflow, not a
  second project-state store; SDK session mechanics do not replace these owners.
- [provider_prompt.py](../scripts/provider_prompt.py) and
  [process_runner.py](../scripts/process_supervision/process_runner.py) → separate
  Python SDK/provider coordination and Rust-owned native process operations; adapter
  replacement is limited to actual SDK/host coverage, not a claim that all providers
  or legacy CLI capabilities are supported.
- [skill_pack_validator_runtime.py](../scripts/skill_pack_validator_runtime.py),
  [publication canon](../scripts/universal-hooks/scripts/) and
  [check-publication-gate.py](../scripts/check-publication-gate.py) → distinct
  Rust validation and publication policy/scan/gate modules, not one universal gate.
- [repo_transfer.py](../src.codex/skills/manual-repo-transfer/scripts/repo_transfer.py)
  → Rust inventory/bundle, distinct archive-integrity/payload-source/trusted
  verification, and preview-only cleanup. Freeze and receiver restore remain with
  their workflow owners; this adds neither automatic restore/deletion nor live takeover.

## npm package and runtime-dependency contract

**Owner:** Toolchain Engineer with Product Manager and the existing installer owner.
These are selected design contracts, not installed commands or published packages.
The public CLI name is `orchestrarium`; the registry package identifier remains a
release-time publisher-ownership/name-availability check, not an architecture gap.

Historical npm scope is recorded in [24d0647](https://github.com/applicate2628/Orchestrarium/commit/24d064741b21e8e84dab78dfa2bfcb7091d972ce)
and [e55b246](https://github.com/applicate2628/Orchestrarium/commit/e55b2466281ecc50ad2a940a4de14a5ea90fb98c).
The detailed local-only epic was not recovered; the following is a new explicit
contract, not a claim to reproduce missing decisions. Current main has no root
`package.json`.

- Ship a thin JavaScript dispatcher, versioned rules/resources and exact-version
  native platform packages selected through npm `optionalDependencies`. No
  `postinstall` downloads, compilation, Python setup, providers or project mutation.
  Missing native binaries fail clearly; no implicit compilation or Python fallback.
- `orchestrarium apply --provider codex|claude --global` selects global application;
  `orchestrarium apply --provider codex|claude --target PATH --allow-unsafe-target`
  selects an explicit project. Preserve current target admission, exact-digest
  adoption, force/refusal and preservation semantics from
  `scripts/production_installer.py:585–625` and `INSTALL.md:9–53`.
  `--dry-run` retains existing preview semantics, not an unproved zero-host-query claim.
  Repeating `apply` is the existing idempotent reinstall/update operation.
- npm update changes only the distributable; installed packs change on explicit
  `apply`. npm uninstall removes only the npm distribution. No complete applied-pack
  removal command is promised in the first release: the current narrow owned-hook
  removal is not whole-pack uninstall (`INSTALL.md:287–335`).
- During staged migration, an explicitly selected legacy installer route may
  forward to the canonical Python installer with its declared prerequisite; it
  is not an automatic missing-native fallback. Remove that implementation only
  after the Rust installer qualifies. Native hook delivery can precede this port.
- Copy each applied executable and matching resources into the selected scope's
  resolved canonical agents root under `runtime/<release>-<content-digest>/<target>/`.
  The logical layout is `.agents/runtime/...`; derive it from the installer's
  admitted root/link authority (`production_installer.py:10977–10991`), not a
  reconstructed path that bypasses existing symlink/junction handling.
  Registrations bind this retained pair, never npm cache, mutable `node_modules`,
  `latest` links or PATH. Extend the existing installer owner/receipts for this
  resource, not a parallel manager. Failed apply preserves the prior pair and
  recovery; identity changes retain manual host trust. Initially retain old applied
  versions without native-runtime reclamation. Codex and Claude can share this
  root; later explicit removal must inspect all retained provider registrations
  and configured coordinator bindings in that scope. Current single-registration
  Python retirement (`production_installer.py:10846–10877`) is not that proof.
  Unknown references preserve the version; no garbage collector/refcount service.
- Python SDK coordination is optional and separately provisioned in an explicitly
  selected isolated Python environment using a tested dependency lock. Record the
  exact interpreter and compatible coordinator/native/adapter versions. npm does
  not provision it; missing/incompatible dependencies fail without hidden pip,
  environment search, account switch or fallback. Native hooks do not load Python
  or SDK. Legacy operations still require Python until their replacements qualify.
- First native qualification target: Windows x64 MSVC
  (`x86_64-pc-windows-msvc`). Subsequent candidates: Linux x64 GNU
  (`x86_64-unknown-linux-gnu`) and macOS arm64 (`aarch64-apple-darwin`). All are
  currently unqualified for the new native product; no other architecture is
  implicitly supported. Qualify hooks, installer and process runner independently.

Prove the complete payload from an unpacked archive without a checkout, including
validators and dynamic resources. Check dependency closure, explicit apply,
reinstall/update, failure recovery, foreign-file preservation, manual trust and
survival of applied registrations after npm update/uninstall. No package publication
or runtime activation is authorized by this design. Expanded native-role lifecycle
is a dependency only for operations actually needing its broader ownership changes.

Minimize dependencies per consumer, not by a zero-dependency slogan. The existing
`review_loop_state.py` standard-library JSON path avoids PyYAML for suitable owned
ledgers; keep supported legacy YAML parsing explicit. The weaker string/regex
fallback in `skill_pack_validator_runtime.py` is not equivalent validation: retain
an adequate parser rather than silently weakening checks. Test dependencies remain
separate. Python coordination is retained; there is no whole-product Python-free claim.

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

1. **First SDK slice: structured read-only review.**
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
   effects. An uncertain effect is reconciled, not replayed as a new user turn.
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

## State, process and cutover ownership

Dependencies run from adapters to existing domain owners to pure decisions/platform
operations; the process layer grants no dispatch authority. Each child has one
lifecycle owner: Rust supervision for Rust-created children, SDK adapter supervision
for SDK-created children; any native containment must assign noncompeting guarantees.
SDK bounded capture, private-path, cancellation and settlement are not yet qualified;
a stream-reader limit alone is not a total-output bound. Missing required guarantees
hold only that lane under existing controls, not a silent downgrade or dual manager;
current unavailable generic Windows paths stay unavailable.
The installer does not launch provider tasks/model inference. Preserve its existing
read-only Codex host health query (`hooks/list` through App Server), including CLI
availability, hook inventory and the separate manual-trust receiving step. Such a
query starts the host process; it is not an agent-task launch or proof of hook trust.
Publication policy, Git-object scanner and gate retain distinct validity, traversal
and authority/fresh-range responsibilities.

Entrypoints adapt input/output/errors; domain owners retain schemas, errors and
receipts. Pure checks/planners/reducers consume immutable inputs. The installer,
physical work-item lifecycle, agent-run ledger and review-loop state each retain
their own sole writer, transaction/recovery semantics and readback, not a universal
transaction/effect manager. Replace dynamic imports/subprocesses with typed calls only where
isolation or evidence boundaries are preserved; use per-operation consistent inputs,
not global mutable caches. The source-only
[operation store](../scripts/agent_run_persistence/operation_store.py) and
[route activation registry](../scripts/process_supervision/route_activation_registry.py)
remain disabled and nonauthorizing, including for matching supplied bindings; a Rust
port does not activate them.

Python remains the coordination implementation, not just a temporary test oracle.
Retire superseded deterministic Python/shell implementations only after their Rust
replacements qualify; retain useful development/test tools rather than mandate a
whole-language purge. Reuse state/contracts, not a new framework, registry or service.

Before the first production cutover, Architect and each affected owner must accept
the implementation boundary and update the binding Python production-owner policy
with its owning documentation. This plan changes neither that live policy nor any
runtime. Rust supports cross-platform implementation, not identical operating-system
semantics or verified binaries for every target. Keep real platform differences in
their owners; admit missing generic execution boundaries against concrete use cases.
Installation of source-only components remains a separate decision. Owner-equivalent
manual execution retains the same guarantees and is not a host-denial bypass.

## Native components to evaluate

[clap](https://github.com/clap-rs/clap) for CLI
arguments, [serde_json](https://github.com/serde-rs/json) for owned JSON data,
[toml_edit](https://github.com/toml-rs/toml/tree/main/crates/toml_edit) for TOML edits
retaining comments/layout where supported, not guaranteed byte preservation,
[tempfile](https://github.com/Stebalien/tempfile) for temporary resources, and
[walkdir](https://github.com/BurntSushi/walkdir) for filesystem traversal. Retain a
justified parser for supported legacy YAML; changing language cannot weaken validation.
Use [Rayon](https://github.com/rayon-rs/rayon) only for measured independent parallel
work with bounded workers and deterministic result assembly. Filesystem traversal
does not replace publication's complete commit/tree/blob object-graph scan; never
apply `.gitignore` exclusions to that publication scope.

For Rust-owned process operations, evaluate [process-wrap](https://github.com/watchexec/process-wrap)
with its Rust standard-library (`std`) frontend; add no mandatory Tokio asynchronous
runtime. Its Windows Job Object/POSIX process-group wrappers do not supply the full
runner lifecycle. Add a small Windows-specific adapter, using
[windows-rs](https://github.com/microsoft/windows-rs) only for proven uncovered native
operations; avoid duplicate wrappers already supplied transitively. Pin evaluated
revisions/features and inspect licensing, dependencies and supported targets before
implementation. These are upstream components, not verified Orchestrarium integration.

Libraries do not confer installer ownership, rollback/crash-atomicity, publication
authority, path confinement or process settlement. Preserve those application
contracts and their tests. Native publication needs an admitted replacement for held
Python-code closure/trusted-interpreter custody with executable/code-identity custody,
not erased isolation through an in-process call. Current main's Windows permission-rendering correction
already belongs to its native descriptor owner (see source baseline above); it is not
new Rust scope. Count packaging, updates, bridge removal and platform/dependency
maintenance when assessing complexity; claim no speed or reliability gain without
matched measurements.

## Acceptance, parity and deliberate improvements

Establish the current behavior and performance baseline.
For deterministic replacements require one-for-one parity of standard-output protocol, standard-error
output, exit codes, ordering, effects, persisted state/files and error behavior on
the same inputs, including malformed/missing data and preserved user content. Require
byte equality wherever the interface contract demands it. Structural comparison must
preserve all contract-visible distinctions; normalize only specifically justified
nondeterministic fields, never broad masking. Adjudicate known baseline defects
separately; neither enshrine them blindly nor disguise intentional semantic changes
as migration. SDK-native coordination improvements need separately accepted behavior
and outcome tests; stochastic model output is not subject to byte-identical parity.
Compare deterministic implementations only on isolated cloned fixtures/replayed
inputs with providers stubbed, never with
duplicate live effects or paid runs. Probe interruption/restart, partial writes and
rollback at the existing state owners, not just successful command output. For
parsing, preserve duplicate-key rejection or retention, strict/unknown-field rules,
number tokens, key ordering and canonical hashes at each actual owner; TOML edits
must retain accepted/refused configuration shapes, not merely parseable output.
Include encoding/byte-order marks/invalid bytes, Unicode matching/case-folding and
platform paths; preserve each hook's warn-only/fail-open/fail-closed outcomes rather
than strengthen gates. For
process slices also probe spawn/partial-setup failure, handles, timeout/cancellation
races, descendant cleanup and terminal evidence, including the actual Windows CLI
private-directory boundary. Reconcile uncertain outcomes before retry; missing
cleanup evidence is not success. Verify required Windows permissions and path-escape
behavior independently; unsupported routes stay typed unavailable before launch.
Require source-to-installed/package parity, upgrade/removal and recovery evidence
on each platform/architecture claimed by that slice, with bounded-parallel versus
serial checks. A simple hook need not wait for every generic process target. Verify
Windows/macOS/Linux support individually before advertising it. Verify native and
Python/SDK route dependencies separately, including adapter version compatibility,
auth/billing selection and trace-export behavior. No whole-product Python-free claim,
duplicate execution owner or second authoritative state store is introduced.

## Delivery sequence and first bounded implementation

**Admitted sequence:** first replace small deterministic hooks/checks; then required
deterministic helpers and the installer behind their existing ownership contracts.
Separately qualify a bounded Python/Agents SDK coordination route. Each cutover keeps
one canonical implementation per operation and removes the superseded production
logic. Temporary native launch adapters may forward only; no independent Python/Rust
state writers or automatic fallback after an uncertain effect. Preserve current supported
runtime paths until their replacement passes parity and recovery checks. The target
is not a new agent framework, scheduler or universal execution service. Implementation
belongs in a separate pull request (PR). A verified simple-hook slice may ship in the
current release independently of full 2.0 and unfinished generic process support.

The next work is bounded preparation and qualification, not a provider launch:

1. Toolchain Engineer implements the selected package/command contract and verifies
   the complete distributable and runtime dependency closure, including retained
   version binding, explicit apply and per-route Python/SDK prerequisites.
   Package-contract work can proceed without expanded native-role lifecycle, routing
   evaluation, generic process support or cross-host continuation.
2. First native slice: `orchestrarium hook mcp-usage-reminder`, owned by the existing
   hook/helper owner. Its 34-line current entrypoint emits unconditional SessionStart
   context without reading stdin, scanning transcripts, changing project state or
   spawning children. Freeze that contract and implement its Rust replacement
   against isolated cloned fixtures/replayed inputs. Stub providers;
   do not execute paid models, duplicate live effects or introduce packaging-driven
   project mutation. Keep the production Python path until the slice's parity,
   platform, recovery and source-to-installed checks qualify the replacement. Before
   production cutover, obtain the existing owner/Architect acceptance and update the
   binding language-owner policy and owning documentation together.
   Select direct-native registration; use a temporary forwarding-only adapter only
   for a verified host limitation, not a permanent extra layer. Current target
   selection, health classification and mirror membership are Python-only: update
   those owners, registration/inventory and tests together. Extend the existing hook
   metadata/target descriptor so one logical marker maps to the exact retained
   executable plus `hook <marker>` arguments, event, matcher and registration source.
   Registration, inventory/health, replacement and retirement consume that same
   binding, including health target extraction. Normalize only path operands, not
   literal selectors or arbitrary argument values: current `_command_identity`
   (`check-hook-health.py:353–358`) treats all argv as paths. Preserve argument
   boundaries through supported host serialization rather than adding shell-specific
   guessing. Current script-basename classification (`check-hook-health.py:1027–1117`)
   and removal (`install-hypothesis-hook.py:343–351`) cannot identify multiple hooks
   in one binary. Do not recognize ownership by binary name alone, arbitrary argv
   substring matching, per-hook exceptions or one executable per hook. Test wrong
   selector/path/source, duplicate markers, foreign commands and old Python entries.
   Generate the embedded
   policy from `mcp_continuity_policy.py::SESSION_START_CONTEXT` at build time and
   compare the exact projection; do not hand-copy a second authored policy.
   Reuse `test_universal_reminder_hooks.py` and
   `test_sessionstart_reminder_python_hooks.py`: verify exact JSON/UTF-8/order/newline,
   stdout/stderr/exit, startup/resume/clear/compaction/subagent inputs, malformed or
   open stdin (must not block), and output-failure fail-open behavior. Embedding
   removes Python sibling-import failure; record that packaging difference instead
   of claiming impossible failure parity. Missing/corrupt native payload remains an
   installer-integrity failure. Verify build-to-installed identity, reinstall,
   rollback, owned membership and preservation of foreign hooks. Changed identities
   require existing manual host trust and strict health receiving, not fixed total
   installed counts.
3. First SDK slice: the structured read-only review case above, with an explicit
   domain receiving-version change and format-only glue deletion. Use provider-native
   structured output instead if the same result needs no SDK coordinator. Use fixtures
   and stubbed adapters first to probe capability rejection, authentication/billing
   selection, trace-export configuration, result provenance and cancellation ownership.
   Live qualification requires its own accepted route, data, budget and permissions;
   it does not silently switch current host-led mode or enable providers.
4. Expand only to admitted deterministic helpers and installer operations whose
   consumer/owner evidence warrants the migration. Preserve one canonical production
   implementation per cutover; retain uncovered routes until replacements qualify.
   Release only the platform/architecture matrix actually verified for that slice.

The native-role lifecycle project is a dependency only for a package action that
actually requires its broader ownership transitions; consume that installer's
accepted operation rather than creating a second ownership manager. A concrete
future cross-host use case may consume qualified runtime operations, but neither
project blocks unrelated packaging or hook work by default.

Implementation acceptance and independent review remain with the existing owners.
For each rollout, state what is delivered, still unsupported, deferred with owner
and next step, or explicitly retired with rationale. Count native distribution,
Python/SDK updates, adapter/version compatibility, temporary-bridge removal and
platform maintenance in the cost of the change. No speed, reliability or dependency
reduction is established by selecting libraries or writing this project document.

Carry the existing regression probes at the affected owner, not only new happy-path
fixtures: `test_hook_runtime_installers.py` / `test_hook_runtime_transactions.py` /
`test_universal_hook_surfaces.py` for installed hooks; `test_kimi_transport.py` for
ACP receipts/cleanup; `test_manual_repo_transfer_security_contracts.py` for transfer;
`test_agent_run_ledger.py`, `test_review_loop_state_v2.py` and
`test_solution_attempt_reducer.py` for state/retry lineage. These files live under
`tests/`. Compare the same selected probes on the pinned baseline and candidate,
separating existing failures from new regressions; a source review or stub-only
suite does not qualify live SDK/provider/platform behavior.

This documentation extraction requires scope/coverage review, local-link and
cross-reference checks and diff-surface inspection. Those checks do not establish
runtime behavior, package availability, installed compatibility or benchmarks.

## Terms and Abbreviations

- npm: the JavaScript package registry/tooling ecosystem; CLI design is selected,
  registry identity and actual release availability remain unverified.
- Rust / Cargo / crate: native programming language / its build and package tool /
  a Rust compilation unit. The target starts with one Cargo package and CLI.
- Python: the retained coordination language; existing production script ownership
  stays binding until each admitted language-boundary change.
- SDK: software development kit. The OpenAI Agents SDK provides coordination
  mechanics, not universal provider runtimes or Orchestrarium authority.
- ACP: Agent Client Protocol, the common agent-transport candidate; protocol support
  is not provider admission, platform qualification or coordinator-model API access.
- API / CLI: application programming interface / command-line interface.
- Codex / Claude / Kimi / Grok: provider runtimes whose adapters and eligibility
  remain distinct; an upstream adapter is not proof of an admitted local route.
- Lead / admission: the existing orchestration owner / existing permission and
  policy eligibility, not a new scheduler or ranking result.
- PR: pull request; a proposal does not prove implementation or merge.
- JSON / YAML / TOML: JavaScript Object Notation / YAML Ain't Markup Language /
  Tom's Obvious Minimal Language, structured data/configuration formats.
- PyYAML: a Python YAML parser; the existing validator's weaker fallback is not
  equivalent supported validation.
- Differential parity: comparison on the same isolated inputs and effects;
  normalization may remove only specifically justified nondeterminism.
- Standard library: language-shipped facilities, including Rust `std`, distinct
  from third-party components; Tokio is a separate asynchronous Rust runtime.
- POSIX / Windows Job Object: Unix-like operating-system interface family /
  Windows mechanism for managing groups of processes.
- Foreign-function / interprocess bridge: a language-boundary call / communication
  between processes; neither transfers state ownership or authority implicitly.
- Trace export: transmission of execution/interaction observations to a configured
  destination, distinct from the authoritative project ledger.
