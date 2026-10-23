# Distribution and hybrid runtime project

Status: standalone documentation/design project, extracted 2026-10-23 from the
2.0 roadmap. The npm distribution and hybrid Python/Rust target are retained;
implementation, package/command choices, supported targets and live SDK routes are
not delivered or qualified. This document grants no provider launch, payment,
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
Toolchain/Platform Engineer owns the admitted delivery work. This extraction changes
documentation only, not runtime code, tests, schemas, installed files, configuration,
state, provider policy or gates. Later implementation belongs in separate PRs.

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
  → Rust manual-transfer operations, preserving inventory/freeze/restore rather than
  activating live cross-host takeover.

## npm package and runtime-dependency contract

**Owner:** Toolchain Engineer with Product Manager and the existing installer owner.
The package contract remains unresolved; there is no selected package name or command.

npm (the JavaScript package registry/tooling ecosystem) distribution was a separate
`npm-skillpack-distribution` epic, not text deleted from the routing design.
[Commit 24d0647](https://github.com/applicate2628/Orchestrarium/commit/24d064741b21e8e84dab78dfa2bfcb7091d972ce)
names it; [commit e55b246](https://github.com/applicate2628/Orchestrarium/commit/e55b2466281ecc50ad2a940a4de14a5ea90fb98c)
explicitly preserves NPM/2.0 scope while removing obsolete Gemini/Qwen surfaces.
Current main has no root `package.json`. The original detailed local-only epic
was not recovered in this review. Do not invent its package name, commands,
registry arrangement, update semantics or runtime dependency contract.

**Admitted target, not an implemented package:** versioned skill/resource payload
and a thin npm launcher selecting the supported platform's native Rust binary.
This is the native part of the hybrid product, not a settled delivery mechanism for
the Python/Agents SDK coordinator or optional Codex adapter dependencies.
Package installation/update delivers files; applying to selected projects remains
explicit. npm uninstall is not full installed-pack removal. Do not introduce hidden
project mutation in package installation hooks. Define operating-system/architecture
targets, binary provenance, updates and removal with the existing installer owner;
unsupported targets fail clearly, not by silently compiling or selecting a fallback.
Trace all installer and installed-hook/helper resources, including dynamic validators;
packaging only the entrypoint and skills is insufficient.

Today Python 3.11+ is needed after installation by runtime helpers/hooks, not only
during setup. The target also retains Python for SDK coordination; replacing native
hooks/helpers does not make the product Python-free. Define Python/SDK installation,
compatible versions and optional adapter dependencies separately, without presuming
an npm package supplies them or adding implicit setup. Declare prerequisites per
supported route. The current Python production-owner policy remains binding until
an admitted implementation decision updates the relevant language boundaries and
their owning documentation together.

Minimize dependencies by actual consumer, not by a zero-dependency slogan. The
[review ledger loader](../scripts/review_loop_state.py) already supports standard-
library JSON; YAML ledgers require PyYAML. Prefer that existing JSON path for owned
machine ledgers where suitable, retaining explicit legacy YAML compatibility. The
[installed validator source](../scripts/skill_pack_validator_runtime.py) can use
PyYAML but falls back to weaker string/regular-expression checks when absent.
That is not equivalent validation. Retain a justified parser where supported YAML
needs it rather than inventing a parser or silently weakening checks. The inspected
production imports do not prove a complete dependency closure; development/test
dependencies are separate. No dependency removal is claimed implemented.

**Open decision and acceptance:** reconstruct the missing package/command contract,
choose supported native targets and hybrid delivery layout, then prove the payload from an
unpacked archive without a checkout. Trace runtime dependencies as well as installer ones;
verify supported parsing with and without optional dependencies, install/reinstall,
upgrade, explicit apply and the agreed removal scope. Preserve user files and
rollback. Define binary/resource version binding and retention with the existing
installer owner: npm update/removal must not silently change or break applied packs
through mutable or disappearing shared references. Expanded native-role lifecycle
is a dependency only for package actions that require its broader ownership
transitions; that separately scoped 2.0 outcome does not block package-contract work
or existing supported installer operations. Verify the actual dependency closure
per native/SDK route; do not claim a Python-free product. Publication/paid operations
require applicable authorization; no removed provider packs return implicitly.

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
path to be `direct-external-cli`. SDK routes therefore need a narrowly admitted
provenance/version extension and receiving-parser tests before activation; preserve
external nonauthority and independent verification, never mislabel an SDK path as CLI.
This applies to ACP routes too; transport readiness does not establish receiving parity.
Inventory obsolete prompt/launch/parsing glue per supported host before deleting
it; retain shared semantic checks and any uncovered existing route.

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

## State, process and cutover ownership

Dependencies run from adapters to existing domain owners to pure decisions/platform
operations; the process layer grants no dispatch authority. Each child has one
lifecycle owner: Rust supervision for Rust-created children, SDK adapter supervision
for SDK-created children; any native containment must assign noncompeting guarantees.
SDK bounded capture, private-path, cancellation and settlement are not yet qualified;
a stream-reader limit alone is not a total-output bound. Missing required guarantees
hold only that lane under existing controls, not a silent downgrade or dual manager;
current unavailable generic Windows paths stay unavailable.
The installer does not launch providers. Publication policy, Git-object scanner and
gate retain distinct validity, traversal and authority/fresh-range responsibilities.

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

1. Toolchain Engineer reconstructs the npm package/command contract and inventories
   the complete distributable and runtime dependency closure, including version
   binding, retention, explicit apply/removal and per-route Python/SDK prerequisites.
   Package-contract work can proceed without expanded native-role lifecycle, routing
   evaluation, generic process support or cross-host continuation.
2. With the existing hook/helper owner, select one small deterministic hook/check,
   freeze its current input/output/effect contract and baseline, and implement its
   Rust replacement against isolated cloned fixtures/replayed inputs. Stub providers;
   do not execute paid models, duplicate live effects or introduce packaging-driven
   project mutation. Keep the production Python path until the slice's parity,
   platform, recovery and source-to-installed checks qualify the replacement. Before
   production cutover, obtain the existing owner/Architect acceptance and update the
   binding language-owner policy and owning documentation together.
3. Separately specify one bounded SDK coordination use case, the existing domain
   contract/receiving-version change and obsolete-glue deletion scope. Use fixtures
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

This documentation extraction requires scope/coverage review, local-link and
cross-reference checks and diff-surface inspection. Those checks do not establish
runtime behavior, package availability, installed compatibility or benchmarks.

## Terms and Abbreviations

- npm: the JavaScript package registry/tooling ecosystem; no package or command is
  selected by this project.
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
