# Orchestrarium 2.0 product plan

Status: consolidated product plan with an admitted gradual Rust migration target,
reconciled 2026-10-23 against main
`84eefb6bbeec9ebbe032f00788f249ae59da05b5`. This is not an implemented release,
a measured improvement, or permission to run providers, spend funds, or publish.

## Goal and boundary

Deliver an easier-to-distribute skill pack and better task-specific orchestration:
choose sufficient admitted model/effort profiles, add complementary expertise when
useful, learn from verified outcomes, and retain safe installation and future
continuation across hosts. Preserve the functional ambition, not every mechanism
from the earlier drafts. Gradually replace mandatory installed Python, Bash and
PowerShell logic with a cross-platform Rust command-line interface (CLI), delivered
as native binaries through npm. This is an accepted target, not implemented behavior
or permission to start implementation. Installed runtime comes first; retirement of
remaining repository-owned Python/shell tooling/tests is a separate second phase, not a
literal file-for-file translation. Development scripts may remain during migration.

This is the canonical product scope, status, dependency and acceptance register.
The [focused routing design](superpowers/specs/2026-09-04-adaptive-lead-model-routing-v2-design.md)
owns the proposed comparison contract, not the whole 2.0 roadmap. Current
[shared governance](../shared/AGENTS.shared.md), [Lead contract](../src.codex/skills/lead/SKILL.md),
[role policy](../shared/role-routing-policy.v1.json), [resolver](../scripts/resolve-agents-mode.py)
and [installer](../scripts/production_installer.py) remain the live owners.

**Change-Surface Contract**

- Intended change surface: this plan, the focused routing design, docs index and release note.
- Approved seams: product planning, the staged native CLI target at existing hook/helper/installer owners, and a proposed advisory comparison at existing discovery → Lead → resolver boundaries.
- Protected surfaces: all runtime code, tests, schemas, installed packs, configuration, persistence, execution, review and publication gates.
- Blast radius: documentation only; no external contract or persisted-state migration.

Product Manager owns scope decisions; Lead sequences admitted delivery; Architect
owns any later structural boundary. The named specialist in each item owns its
future artifact, not new authority. Existing required independent reviews remain.
An unresolved decision blocks its dependent work only. Deferred does not mean
cancelled, and a proposal is not a commitment to a particular implementation.

## General mechanisms, revisable plans

Current shared governance already requires general solutions for unfamiliar
contract-valid scenarios; 2.0 does not introduce that rule. An unfamiliar task should
normally require new data and a revised plan, not a core branch, status or exception
list. Lead already revises sequence, grouping and
parallelism at plan checkpoints; this is not a new engine. Preserve accepted goals,
criteria, ownership, authorized effects, budgets, useful results and unresolved
obligations. Methods may adapt; material boundary changes use existing controls.
Replanning never resets retry lineage or waives required review and safety rules.
Parallelize independent read-only checks, hashing and tests only within explicit
worker/resource bounds; serialize writes to the same authoritative state and respect
dependencies. Collect results in deterministic order, propagate failures and settle
workers on cancellation. More threads are not a guarantee of lower total cost or
latency; compare against a measured baseline before claiming an optimization.

Instructions are not enforcement, and adding prose is not a reliability fix. The
recommended design is a short invariant core with task-relevant detail, without
hiding mandatory constraints, arbitrary token limits or a new context service.
For each critical property, distinguish within its existing design and acceptance:
- What the actual operation/host owner enforces before the effect, on which paths.
- What independent result readback or domain verification establishes afterward.
- What remains agent judgment or an uncontrolled-path limitation.

Prefer an existing operation that makes the valid path straightforward over manual
step lists, a hook per rule or new states. A supported alternate entrypoint must
preserve the same effect contract; a bypassable helper, advisory resolver or prompt
cannot establish machine enforcement. Direct host calls, shell or edits outside a
controlled boundary remain explicit limitations, not guarantees supplied by a
wrapper. The [Codex addendum](../src.codex/AGENTS.codex.md) explicitly records
incomplete edit-hook coverage and behavioral, not host-enforced, tool isolation.
Admit a concrete missing boundary separately if needed; do not prescribe a universal
gate or claim all semantic judgment can be automated.

Missing a scenario template is not itself a blocker when capability, permission
and evidence suffice. A real blocker holds dependent effects; independent work
continues unless actual shared-state or containment risk requires a wider stop.
Domain checks remain essential: proofs, software tests and installed readback are
not interchangeable. No runtime root cause is established by this plan.

## Existing foundation and known limits

- Exact native profile admission, task classification, host filtering, ready-lane
  scheduling, execution provenance, independent review and receiving already have
  owners. Reuse them; 2.0 does not introduce a second scheduler, registry service,
  ledger, policy authority or approval pipeline.
- External `auto` already uses task/lane-specific Codex/Claude priority profiles.
  Configured priority is not current comparative evidence: the
  [routing evidence notice](routing/full-v2-hard-r2-routing-evidence-2026-05-01.md)
  explicitly marks carried-over rankings `ASSUMPTION (UNVERIFIED)` after model
  changes. Requalification and measured preference are separate from permission
  and actual execution availability.
- Kimi is explicit-only through fixed `kimi-code/k3`, for policy-admitted read work
  or scoped engineering mapped to the existing external worker. It remains
  independently verified, nonauthorizing and outside `auto`. Grok is a
  classifier-only policy realization with execution unavailable, not an enabled
  worker. The [external dispatch contract](../src.codex/skills/lead/external-dispatch.md)
  controls real paths. A native-profile comparator cannot automatically cover them.
- Known documentation drift: the comment on `externalProvider` in
  [defaults](../shared/agents-mode.defaults.yaml) still describes an older Kimi
  read-only/no-tools restriction, unlike current
  [provider realization policy](../shared/role-routing-policy.v1.json) and README.
  The configuration-documentation owner must reconcile it in an owner-scoped
  correction; this plan does not silently edit runtime configuration.
- [Installation rules](../INSTALL.md) retain limited create-only/hash-pinned native
  role handling and reserve broader adoption/update/deletion/reclaim for 2.0.
  [Runtime limitations](../README.md) include unavailable generic Windows command
  execution, a Rust implementation deferred to 2.0, unavailable generic POSIX
  Process Runner Version 1, and a source-only durable operation store and route
  activation registry. These are repository facts, not provider guarantees or
  proof of behavior in a particular installed environment.

## Outcome register

### 1. npm skill-pack distribution

**Status:** native-binary delivery target admitted; detailed distribution contract unresolved.
**Owner:** Toolchain Engineer, with Product Manager defining the user-facing package.

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
Package installation/update delivers files; applying to selected projects remains
explicit. npm uninstall is not full installed-pack removal. Do not introduce hidden
project mutation in package installation hooks. Define operating-system/architecture
targets, binary provenance, updates and removal with the existing installer owner;
unsupported targets fail clearly, not by silently compiling or selecting a fallback.
Trace all installer and installed-hook/helper resources, including dynamic validators;
packaging only the entrypoint and skills is insufficient.

Today Python 3.11+ is needed after installation by runtime helpers/hooks, not only
during setup. Item 5 replaces that mandatory runtime closure gradually, starting
with simple hooks, then required helpers and the installer. Any intermediate package
must declare the remaining Python/shell prerequisites; bundling or freezing Python
is not the target and does not establish a Python-free runtime. The current Python
production-owner policy remains binding until a separately admitted implementation
decision changes it and its owning documentation together.

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
choose supported native targets and delivery layout, then prove the payload from an
unpacked archive without a checkout. Trace runtime dependencies as well as installer ones;
verify supported parsing with and without optional dependencies, install/reinstall,
upgrade, explicit apply and the agreed removal scope. Preserve user files and
rollback. Define binary/resource version binding and retention with the existing
installer owner: npm update/removal must not silently change or break applied packs
through mutable or disappearing shared references. Item 2 is a dependency only where native-role lifecycle is required;
package-contract work does not wait for routing or cross-host work. A Python-/shell-
free installed-runtime claim waits for item 5's verified closure on every claimed
target. Publication/paid operations require applicable authorization; no removed
provider packs return implicitly.

### 2. Fuller native-role lifecycle

**Status:** explicit 2.0 remainder, partially served by today's limited installer.
**Owner:** Toolchain Engineer at the existing production installer.

Complete the admitted adoption, update, deletion and reclaim cases without taking
ownership of customized or ambiguous files. Today's source manifest is validation,
not proof of installed ownership; current narrow stock migrations do not establish
a general lifecycle. [README](../README.md) and [INSTALL](../INSTALL.md) explicitly
reserve the remaining work for 2.0. This is a capability gap, not evidence that
today's conservative refusals are unsafe.

**Recommended option:** extend the existing native-role planner and transaction
with recorded ownership reconciled against observed and desired state. Reuse the
canonical-skill reconciliation principle, not its skill-specific function or
receipt assumptions. Role files, configuration registrations and ownership evidence
form one coupled change; retain current rollback/readback. Update or remove only
proven-owned, unchanged content within the authorized transition. Foreign files
and unrelated configuration remain intact; filenames do not prove ownership.

**Alternatives and open decision:** continuing stock-hash migrations is the smallest
short-term bridge, not the general lifecycle. Legacy installs need explicit adoption
or refusal where evidence is missing. Versioned directories with pointer switching
would change provider paths, overrides and cleanup; do not prefer that larger design
without evidence. Define adoption/update/deletion/reclaim semantics with the existing
owner. Native-role removal is not whole-pack uninstall or shared-skill ownership.

**Acceptance:** independently read back files, registrations and ownership together;
probe managed rollback, customized or foreign roles, legacy adoption and repeated
apply. Existing transaction rollback does not prove crash-atomicity: test restart
after abrupt termination/power loss, reconcile partial persisted state before retry,
and preserve foreign changes. Reuse the existing owner, not a new recovery service.
New ordinary roles/releases should be data, not a migration branch each time.
Verify global/project and provider differences where they affect the accepted contract.
Coordinate npm through this owner, not a second package state manager.

### 3. Task-specific exact-profile choice and complementary work

**Status:** remaining design outcome; existing admission and scheduling are implemented.
**Owner:** Lead, with any comparison extension at the existing resolver caller seam.

Compare already-admitted exact model/effort choices for a concrete task, and compare
whole useful routes rather than one universal model winner. Keep quality, scope
coverage and independent challenge ahead of cost and latency. Retain useful coverage
of the admitted task, different methods and falsification without mandatory role rosters or
provider-family quotas. Follow the [routing design](superpowers/specs/2026-09-04-adaptive-lead-model-routing-v2-design.md)
for eligibility, uncertainty, evidence and accounting semantics.

**Next decision and dependencies:** identify a real caller and walk its discovered
options through Lead into the actual resolver. Accept evidence inputs and output
consumer before coding. Prefer existing Lead judgment and its recorded rationale;
a pure comparator is conditional on demonstrated repeated comparison needs. Item 4
supplies comparative evidence, not new execution permission.
External comparison separately needs the real provider admission/availability path.
Insufficient comparative evidence need not prevent Lead from making an explained
admissible choice; it must not become a fabricated ranking or capability assumption.

Provider follow-through stays explicit: Lead and the existing external-routing
owner must requalify current Claude/Codex profiles before claiming measured
priorities. Evaluate Kimi only within its currently admitted explicit route; Product
Manager and the routing owner must separately decide, from evidence, whether any
future `auto` inclusion is wanted and admissible. For Grok, the existing adapter
and routing owners must first establish a concrete available execution path and
admission contract before comparison or consideration for `auto`. None of these
steps is automatic promotion, permission to launch, or a promised new integration.

**Acceptance:** useful task-specific rationale and bounded complementary assignments;
no extra admitted profiles, scope, fallback or authority; explicit insufficient or
incomparable evidence; whole-route cost including failed attempts and required
review; unchanged resolver/host controls. No claim of improved selection before a
matched comparison supports it.

### 4. Empirical evaluation and curated outcome feedback

**Status:** retained outcome; current-family advantage unverified.
**Owner:** QA Engineer with the relevant mathematical, scientific, engineering and
review specialists; Lead owns acceptance of routing evidence.

Use representative NablaCAD tasks in mathematics, numerical methods, C++,
computer-aided design (CAD), user interfaces (UI), review and recovery. Compare
matched task/input/acceptance conditions and record exact profile, harness, tools,
permissions, task context and observation date. Use fixed acceptance oracles and
held-out tasks where applicable; report sample size, post-review defects, omissions
and rework. Evaluate correctness, coverage, independent defect discovery and
accepted-result quality before economics. Include
all attempts, repeated context, correction, review and integration in cost/time;
keep unknown or incompatible units explicit rather than manufacturing savings.

**Next decision and dependencies:** select a small representative corpus and its
acceptance oracles, admissible candidates, data permissions and approved budget.
Existing runs may supply evidence where applicable; new provider or paid runs are
not authorized by this plan. Start evaluation design alongside item 3, then use
verified results to judge whether a comparison mechanism earns its complexity.

**Acceptance:** reproducible matched evidence, unsuccessful and abandoned attempts
included, with uncertainty and limitations visible. Curate accepted outcomes into
later decisions through the existing run journal and [curated lessons](lessons.md),
not a new learning subsystem. Keep run facts distinct from generalizable lessons,
with provenance and expiry or invalidation after model, harness, tool, permission
or material task changes. Negative results must not disappear through success-only
selection. No autonomous policy
promotion, background learning service or universal provider ranking follows.

Optional independent blind proposals, named-artifact cross-critique, Lead synthesis
and empirical arbitration may help demanding cases. Reuse the existing independent
review route: do not impose extra stages, new roles, peer-chat infrastructure or
mandatory paid reviews. Tests, proofs, counterexamples and measurements resolve
checkable disagreement; majority agreement does not establish truth.

### 5. Cross-platform Rust CLI and execution portability

**Status:** staged replacement of mandatory installed scripts admitted, not implemented;
existing execution contracts remain, with incomplete generic CLI/platform coverage.
**Owner:** Platform/Toolchain Engineer with existing hook, helper, installer and
process-supervision owners; each retains its current behavioral contract.

The [process runner](../scripts/process_supervision/process_runner.py) already defines request/result,
cancellation, settlement and Windows native parsing contracts. The generic Windows
CLI is blocked at its private request-directory boundary; generic POSIX execution
is unavailable. Specialized POSIX supervision and native-host dispatch are not proof
that either generic entrypoint works. A source-only store/activation registry is
also not evidence of a live durable execution service.

**Admitted sequence:** first replace small deterministic hooks/checks; then required
runtime helpers, including stateful and process-supervision boundaries; then migrate
the installer behind its existing ownership/transaction contract. Each cutover keeps
one canonical implementation per operation and removes the superseded production
logic. Temporary launch adapters may forward only; no independent Python/Rust
writers or automatic fallback after an uncertain effect. Preserve current supported
runtime paths until their replacement passes parity and recovery checks. The target
is not a new orchestrator, scheduler or universal execution service. Implementation
belongs in a separate pull request (PR). A verified simple-hook slice may ship in the
current release independently of full 2.0 and unfinished generic process support.

**Target architecture:** one Cargo package (Rust build/package unit), one shipped
native CLI per supported target, and small owner-aligned internal modules. This map
names logical boundaries, not one crate/service per script or new command contracts;
the implementation decision fixes names and layout:
- [production_installer.py](../scripts/production_installer.py) → installer
  plan/apply/reconcile, retaining coupled role/configuration ownership.
- [Universal-hook canon](../scripts/universal-hooks/) → CLI/hook adapters plus pure
  checks; pack-specific hooks retain their host semantics and consume the same canon.
- [resolve-agents-mode.py](../scripts/resolve-agents-mode.py) → configuration/routing,
  preserving precedence, normalization and existing role/profile admission.
- [mutate-work-item.py](../scripts/mutate-work-item.py),
  [agent-run-ledger.py](../scripts/agent-run-ledger.py),
  [review_loop_state.py](../scripts/review_loop_state.py) and
  [solution_attempt/reducer.py](../scripts/solution_attempt/reducer.py) → distinct
  state submodules; the solution-attempt reducer remains pure and deterministic.
- [provider_prompt.py](../scripts/provider_prompt.py) and
  [process_runner.py](../scripts/process_supervision/process_runner.py) → separate
  provider adapters and process lifecycle; narrow platform primitives sit below them.
- [skill_pack_validator_runtime.py](../scripts/skill_pack_validator_runtime.py),
  [publication canon](../scripts/universal-hooks/scripts/) and
  [check-publication-gate.py](../scripts/check-publication-gate.py) → distinct
  validation and publication policy/scan/gate modules, not one universal gate.
- [repo_transfer.py](../src.codex/skills/manual-repo-transfer/scripts/repo_transfer.py)
  → manual-transfer operations, preserving inventory/freeze/restore rather than
  activating live cross-host takeover.

Dependencies run from entrypoint to domain owner to pure decisions and narrow platform
operations. Provider adapters compose routing, run-record settlement and process
execution; the process owner remains consumer-neutral and nonauthorizing, without
role/routing/installer/publication dependencies. The installer consumes payload and
policy data, not provider launches. Publication policy, Git-object scanner and gate
retain distinct validity, traversal and authority/fresh-range responsibilities.
Pack-specific hooks remain host adapters, not mechanically merged provider behavior.

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

The second phase ports or retires remaining owned Python/shell development/test tools.
Python may serve temporarily as a differential-test baseline, then is retired after
the replacement's independent acceptance coverage is established. Reuse existing
state and contracts, not a new scheduler, framework, registry or service.

Before the first production cutover, Architect and each affected owner must accept
the implementation boundary and update the binding Python production-owner policy
with its owning documentation. This plan changes neither that live policy nor any
runtime. Rust supports cross-platform implementation, not identical operating-system
semantics or verified binaries for every target. Keep real platform differences in
their owners; admit missing generic execution boundaries against concrete use cases.
Installation of source-only components remains a separate decision. Owner-equivalent
manual execution retains the same guarantees and is not a host-denial bypass.

**Small component set to evaluate:** [clap](https://github.com/clap-rs/clap) for CLI
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

For process ownership, evaluate [process-wrap](https://github.com/watchexec/process-wrap)
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
already belongs to its native descriptor owner (see reconciliation below); it is not
new Rust scope. Count packaging, updates, bridge removal and platform/dependency
maintenance when assessing complexity; claim no speed or reliability gain without
matched measurements.

**Acceptance per slice:** establish the current behavior and performance baseline;
require one-for-one differential parity of standard-output protocol, standard-error
output, exit codes, ordering, effects, persisted state/files and error behavior on
the same inputs, including malformed/missing data and preserved user content. Require
byte equality wherever the interface contract demands it. Structural comparison must
preserve all contract-visible distinctions; normalize only specifically justified
nondeterministic fields, never broad masking. Adjudicate known baseline defects
separately; neither enshrine them blindly nor disguise intentional semantic changes
as migration. Run both implementations
only on isolated cloned fixtures/replayed inputs with providers stubbed, never with
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
Windows/macOS/Linux support individually before advertising it. Only a complete
installed-runtime dependency inventory and tests without Python/Bash/PowerShell
establish their removal as prerequisites; tooling/test retirement is separately
verified in phase two. No duplicate execution or transaction owner is introduced.

### 6. Safe cross-host continuation

**Status:** retained, deferred future direction; not a comparison prerequisite.
**Owner:** Lead for admission; Architect and existing persistence/receiving owners
for the eventual boundary.

The existing [manual repository transfer](../src.codex/skills/manual-repo-transfer/SKILL.md)
contract already covers portable/local inventory, writer freeze and verified restore;
Lead already has a recovery contract. Preserve dirty/staged/local-only state as applicable,
without forcing a clean commit or copying credentials as project state. The gap is
verified orchestration-aware continuation, not inventing archive transfer.

**Recommended first option:** connect existing transfer and Lead recovery for an
explicitly stopped handoff: verify prior writer stop/exclusion, received artifacts,
open obligations/dispatches, current host capabilities and the next admissible step.
Reuse existing records; do not add a transfer service by default. An unknown external
job outcome must be reconciled before retry, not interpreted as a fresh start.

**Alternative and open decision:** decide whether stopped handoff meets the actual
need. Live/concurrent takeover remains conditional and retained, not cancelled.
If the old host could resume writes to the same authoritative target, a claimed stop
is insufficient: require verified exclusion. Live takeover requires atomic ownership
change and commit-time rejection of stale writers; local locks or a ledger alone do
not prove it. Item 5 matters only when the chosen scenario needs that extension.

**Acceptance:** restore accepted context and outstanding obligations; reject stale
results and unsupported concurrent takeover without changing ownership. Verify old-
writer exclusion, capability changes, interruption/recovery, cancellation and terminal
settlement at actual owners. The [routing design](superpowers/specs/2026-09-04-adaptive-lead-model-routing-v2-design.md)
retains this boundary without imposing a new lease, registry or ledger service.

### 7. Optional named policy preferences from PR #5

**Status:** unresolved optional product decision, not a mandatory framework.
**Owner:** Product Manager for need; existing instruction/handoff owner if retained.

The old proposal packaged two named choices: `lean-implementation` and
`complexity-review`, for lean implementation and complexity-focused review. Simplicity, smallest coherent fixes, owner-first changes
and independent architecture review already belong to mandatory governance. They
must not become optional switches. Ordinary scoped instructions can already request
extra review focus.

The recommended option now is ordinary task-specific instructions, not a selector.
The unresolved distinct capability is persistent named opt-in preferences, narrowed by
project restrictions and applicable task/provider context. Decide whether that
convenience solves a recurring need before retaining a selector. Persistence and
context filtering are not equivalent to generic prompt text; do not call them
implemented merely because ordinary instructions work today.

**Dependencies and acceptance if retained:** define the actual choices and consumer;
no selection leaves prompts unchanged, projects may restrict but not enable choices,
malformed owned restrictions fail visibly, and explicit selection still respects
restrictions. Optional guidance cannot weaken governance or grant provider/role
permission. Reuse existing handoff, prompt composition and installation. No new
policy platform, hook, transport, mandatory review stage or plugin runtime. If not
needed, explicitly retire the mechanism rather than silently losing the outcome.

## Delivery decisions and next slices

The gradual native CLI target is admitted; implementation slices still need their
existing admission and review. Not all seven outcomes are mandatory for the first
release. Current admission,
replanning, review, recovery and generalization governance are the foundation, not
new 2.0 deliverables. Product Manager and Lead must accept the release scope; an
open optional choice holds only its dependent slice.

**Next bounded work, independently where inputs and owners permit:**
1. Toolchain Engineer: reconstruct the npm contract and trace the distributable
   payload/runtime dependencies (item 1). Present supported targets, explicit apply
   and removal semantics, native-binary delivery and transitional prerequisites.
   With the existing hook/helper owners, inventory the required runtime closure and
   select the first simple Rust hook slice (item 5); retain current runtime until
   implementation admission and parity checks. Package-contract investigation does
   not wait for native-role mutation or cross-host work.
2. Toolchain Engineer with Architect: define native-role ownership transitions and
   the legacy-adoption boundary (item 2), using the existing installer transaction.
   Implement only after that contract is accepted; npm consumes this slice only for
   lifecycle actions that actually need it, not as a second ownership manager.
3. Lead and QA Engineer: trace one real admitted routing caller and select matched
   evaluation tasks/oracles (items 3–4). Start from existing rationale and evidence;
   identify missing comparative evidence without launching providers. New runs need
   approved candidates, data and budget. A comparator remains a later decision based
   on demonstrated benefit, not the first implementation deliverable.

**Separate conditional decisions:** item 5's gradual language target is no longer
an optional Python-versus-Rust choice; select each bounded owner/contract and target
platform before implementation, with process-library and parallelism choices driven
by evidence. Choose a concrete stopped-handoff need before item 6;
live takeover is a separate conditional capability. Decide named preferences in
item 7 only if ordinary instructions fail a recurring need. Neither these choices
nor Kimi `auto`/Grok integration block the independent work above; each retains its
own admission, owner and evidence requirement. No optional outcome is silently lost.

After accepting a slice, implement and independently review its smallest coherent
owner-local change against its outcome's acceptance and the failure probes below.
For release, verify the selected installed/platform matrix and actual task outcomes;
settle each retained outcome as delivered, deferred with owner/next step, or explicitly
retired with rationale. A plan, library selection or comparator alone is not 2.0.

The separate Claude current-version research in PR #16 is outside this 2.0 package.
Do not absorb its work or make it a release dependency without an identified shared
contract; consume accepted findings through their existing owners when relevant.

Current-source reconciliation, not a claim about PR merge state or installed behavior:
- [b719ef77](https://github.com/applicate2628/Orchestrarium/commit/b719ef77bd2ebfad44daa7088c71595c9825403b)
  integrates the PR #9 Russian advisory correction; the hook behavior already existed.
- [2e91ebee](https://github.com/applicate2628/Orchestrarium/commit/2e91ebeeb4cd693c13cea714f995cc3389972268)
  integrates the PR #14 Windows private-permission correction through native descriptor
  rendering, preserving exact access checks. Do not carry it as a new 2.0 fix.
- [54c11111](https://github.com/applicate2628/Orchestrarium/commit/54c11111a4fe1eb1073d2a259165edeca8a519ef) seals the
  publication transcript input frontier; [3a542fc5](https://github.com/applicate2628/Orchestrarium/commit/3a542fc5827d3b80c3203bf94943e900a95a4ba2)
  unifies current decision admission and native normalization custody. Reuse these
  owner-level corrections, not new parallel guards or a new state engine. Their scoped
  checks do not prove universal agent enforcement or installed receiving.
PR #15's instruction-preservation status is not established by those commits; verify
its own correction before claiming it landed. Keep any remaining repair with its
existing owner, not duplicated under native-role lifecycle. The known Kimi comment
drift likewise remains an owner-scoped correction.

## Design economy and verification

**Generalization acceptance under current governance:** later implementation must
demonstrate these properties, not add another governance framework:
- A previously unlisted task within existing capabilities can use a new plan without
  adding a task-specific core branch, status or exception; genuine new capabilities
  still require an admitted owner and contract, not a generic bypass.
- A permitted plan revision preserves accepted results, remaining obligations,
  identity and budget, while material boundary changes reach existing controls.
- Skipped instructions or omitted manual steps do not bypass claimed machine
  guarantees on supported effect paths. Test alternative entrypoints and stale state;
  report uncontrolled paths and semantic judgment limits, not false enforcement.
- Repeated requests and delayed results neither duplicate effects nor accept stale
  results. Reconcile uncertain prior effects before retry; otherwise hold the affected
  action. Event replay alone does not prove exactly-once external execution, and an
  unknown outcome must not become success.
- Unrelated authorized work remains possible during a local blocker unless the actual
  dependency or containment boundary requires stopping it too.

Test these properties with varied inputs and failure points at the actual owner,
not only scripted happy paths. Retain domain-specific and integration checks; do not
add a new schema, state service or mandatory stage just to express these properties.

Earlier PR #8/#13 proposals are historical inputs, not parallel normative manuals.
Keep exact-profile evidence, complementary work, empirical challenge, full-attempt
accounting and safe future recovery. Do not carry speculative schema bundles,
universal effort-intent scales, arbitrary fixed ceilings, duplicate ownership,
phrase-presence tests or stronger blanket human escalation. Budget and data-boundary
requirements remain in the focused routing contract and existing owners.

This documentation change is accepted only after scope review, local-link checks,
diff-surface inspection and preservation of existing release-note bytes/line endings.
These checks do not prove runtime behavior, installed compatibility or benchmarks.
Later implementation needs the probes under its own outcome and current gates.

## Terms and Abbreviations

- Exact profile: an admitted model and its model-local effort setting.
- Lead: current orchestration owner, not a new scheduler.
- Harness: the execution tools, instructions and environment around a model.
- npm: package registry/tooling ecosystem; no package or command is selected here.
- CAD / UI / CLI: computer-aided design / user interface / command-line interface.
- POSIX: portable operating-system interface family used by Unix-like systems.
- PR: pull request; a proposal is not evidence that its changes have landed.
- Differential parity: comparison of old and new implementations on the same isolated
  inputs and effects; justified nondeterminism is not permission to mask differences.
- Admission: existing permission and policy eligibility, distinct from ranking.
- Empirical arbitration: settling checkable disagreement with observed evidence.
- JSON / YAML: JavaScript Object Notation / YAML Ain't Markup Language, structured
  data formats; PyYAML is a Python YAML parser.
- TOML: Tom's Obvious Minimal Language, a configuration format; preserving its text
  structure does not establish ownership of the values being edited.
- Standard library: language-shipped facilities (Python modules or Rust `std`),
  distinct from third-party packages.
- API: application programming interface; a library boundary, not a host sandbox.
- Foreign-function / interprocess bridge: calls across language / process boundaries.
- Windows Job Object: operating-system mechanism for managing a process group.
