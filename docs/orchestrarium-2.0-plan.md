# Orchestrarium 2.0 product plan

Status: proposed consolidated product plan, reconciled 2026-10-23 against main
`a675640286f466d329a7bbd88841d93a8d1b7045`. This is not an implemented release,
a measured improvement, or permission to run providers, spend funds, or publish.

## Goal and boundary

Deliver an easier-to-distribute skill pack and better task-specific orchestration:
choose sufficient admitted model/effort profiles, add complementary expertise when
useful, learn from verified outcomes, and retain safe installation and future
continuation across hosts. Preserve the functional ambition, not every mechanism
from the earlier drafts.

This is the canonical product scope, status, dependency and acceptance register.
The [focused routing design](superpowers/specs/2026-09-04-adaptive-lead-model-routing-v2-design.md)
owns the proposed comparison contract, not the whole 2.0 roadmap. Current
[shared governance](../shared/AGENTS.shared.md), [Lead contract](../src.codex/skills/lead/SKILL.md),
[role policy](../shared/role-routing-policy.v1.json), [resolver](../scripts/resolve-agents-mode.py)
and [installer](../scripts/production_installer.py) remain the live owners.

**Change-Surface Contract**

- Intended change surface: this plan, the focused routing design, docs index and release note.
- Approved seams: product planning and a proposed advisory comparison at existing discovery → Lead → resolver boundaries.
- Protected surfaces: all runtime code, tests, schemas, installed packs, configuration, persistence, execution, review and publication gates.
- Blast radius: documentation only; no external contract or persisted-state migration.

Product Manager owns scope decisions; Lead sequences admitted delivery; Architect
owns any later structural boundary. The named specialist in each item owns its
future artifact, not new authority. Existing required independent reviews remain.
An unresolved decision blocks its dependent work only. Deferred does not mean
cancelled, and a proposal is not a commitment to a particular implementation.

## General mechanisms, revisable plans

An unfamiliar task should normally require new data and a revised plan, not a new
core branch, status or exception list. Lead already revises sequence, grouping and
parallelism at plan checkpoints; this is not a new engine. Preserve accepted goals,
criteria, ownership, authorized effects, budgets, useful results and unresolved
obligations. Methods may adapt; material boundary changes use existing controls.
Replanning never resets retry lineage or waives required review and safety rules.

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

**Status:** retained original 2.0 outcome; detailed distribution contract unresolved.
**Owner:** Toolchain Engineer, with Product Manager defining the user-facing package.

npm (the JavaScript package registry/tooling ecosystem) distribution was a separate
`npm-skillpack-distribution` epic, not text deleted from the routing design.
[Commit 24d0647](https://github.com/applicate2628/Orchestrarium/commit/24d064741b21e8e84dab78dfa2bfcb7091d972ce)
names it; [commit e55b246](https://github.com/applicate2628/Orchestrarium/commit/e55b2466281ecc50ad2a940a4de14a5ea90fb98c)
explicitly preserves NPM/2.0 scope while removing obsolete Gemini/Qwen surfaces.
Current main has no root `package.json`. The original detailed local-only epic
was not recovered in this review. Do not invent its package name, commands,
registry arrangement, update semantics or runtime dependency contract.

**Recommended option, not an accepted implementation:** versioned source payload
and a thin npm launcher into the current Python installer, preserving its resource
layout and explicit apply. Package installation/update delivers files; applying to
selected projects remains explicit. npm uninstall is not full installed-pack removal.
Do not introduce hidden project mutation in package installation hooks. Trace all
installer reads/imports, including dynamic validators and installed helper resources;
packaging only the entrypoint and skills is insufficient.

Python 3.11+ is needed after installation by runtime helpers/hooks, not only during
setup. Prefer an external interpreter initially; the dependency decision remains
open. Bundling a maintained interpreter removes the user's Python-install step,
not Python code or platform/security maintenance. A frozen installer alone does
not satisfy installed hooks. A JavaScript/Rust rewrite is not the default: current
repository policy gives Python sole production-script ownership, and changing that
requires a separate admitted architecture decision.

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
choose targets and interpreter delivery, then prove the payload from an unpacked
archive without a checkout. Trace runtime dependencies as well as installer ones;
verify supported parsing with and without optional dependencies, install/reinstall,
upgrade, explicit apply and the agreed removal scope. Preserve user files and
rollback. Item 2 is a dependency only where native-role lifecycle is required;
packaging does not wait for routing or cross-host work. Publication/paid operations
require applicable authorization; no removed provider packs return implicitly.

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
probe interruption/rollback, customized or foreign roles, legacy adoption and repeated
apply. New ordinary roles/releases should be data, not a migration branch each time.
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

### 5. Generic execution portability

**Status:** existing execution contracts and native-host routes; incomplete generic
command-line interface (CLI)/platform coverage, not a missing universal runner.
**Owner:** Platform/Toolchain Engineer at current process-supervision owners.

The [process runner](../scripts/process_supervision/process_runner.py) already defines request/result,
cancellation, settlement and Windows native parsing contracts. The generic Windows
CLI is blocked at its private request-directory boundary; generic POSIX execution
is unavailable. Specialized POSIX supervision and native-host dispatch are not proof
that either generic entrypoint works. A source-only store/activation registry is
also not evidence of a live durable execution service.

**Recommended option:** use existing supported paths where sufficient, then finish
only the existing boundary required by a concrete command/platform use case. Keep
one request/result contract, with real platform differences inside its owners.
Decide optional POSIX support and installation of source-only components separately.
The unavailable boundaries do not establish that Python cannot implement them.
Owner-equivalent manual execution retains the selected operation's guarantees;
it is not a host-denial bypass.

**Conditional Rust-library alternative:** compare an owner-local Python completion
against replacing the smallest low-level process-ownership component with existing
libraries, not rewriting the orchestrator. [process-wrap](https://github.com/watchexec/process-wrap)
provides composable Windows Job Object and POSIX group/session wrappers, not the
complete runner lifecycle. Its `std` and Tokio frontends are alternatives; do not
add the Tokio asynchronous runtime without a demonstrated need. Check the selected
features and transitive dependencies: the current upstream manifest already uses
Unix `nix` and Windows bindings. Add [windows-rs](https://github.com/microsoft/windows-rs)
bindings or [rustix](https://github.com/bytecodealliance/rustix) Unix primitives only
for a proven uncovered operation, not as duplicate ownership layers.
[cap-std](https://github.com/sunfishcode/cap-std) is a separate directory-relative
capability candidate where path confinement is needed. Its protection applies to
operations through its API, not arbitrary process operations; it is neither a
whole-process sandbox nor a replacement for Windows access-control lists.

These are upstream capabilities, not observed Orchestrarium integration guarantees.
Installer text-ownership mistakes and Windows permission canonicalization errors
remain application-logic issues; changing language or adding bindings does not fix
them automatically. Before implementation, Architect and the current owner must
admit the language boundary against the binding Python production-owner policy.
Retain one owner and the existing request/result contract; remove superseded logic,
with no dual Python/Rust execution or automatic fallback after an uncertain launch.

Choose this alternative only if total complexity falls after counting any foreign-
function or interprocess bridge, failure handling, build/platform matrix, binary
packaging, updates and dependency maintenance. Pin the evaluated library revisions
and features in implementation evidence. A thin native component does not remove
Python from unrelated installed helpers; npm delivery is not blocked on this choice.
No speed, safety or maintenance improvement is claimed without comparative evidence.

**Acceptance:** compare both options against the same admitted contract. Probe spawn
and partial-setup failure, handle ownership/closure, timeout/cancellation races,
descendant cleanup and trustworthy terminal evidence at each supported entrypoint,
including the actual Windows CLI private-directory boundary. Reconcile uncertain
outcomes before retry; missing cleanup evidence is not success. For any directory
capability, test path escape and alternate access paths; separately verify required
Windows permissions. Unsupported routes stay typed unavailable before launch.
Require source-to-installed/package parity, upgrade/removal evidence and no duplicate
execution owner. Measured net simplification, not library presence or an unavailable
Python route alone, decides whether this alternative earns implementation.

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

## Delivery order and completion decisions

1. Accept this scope register and resolve package-contract recovery, representative
   evaluation tasks and policy-preference need. Record the execution-platform choices
   only when their concrete use cases are known. Unknown details remain open.
2. In parallel where owners are independent: specify npm delivery and native-role
   lifecycle; trace a real routing caller; design the matched evaluations. Do not
   sequence all work behind cross-host infrastructure.
3. Implement bounded, independently reviewed owner-local slices after their contracts
   are accepted. Evaluate first with existing mechanisms; add a comparator only if
   it delivers useful improvement. Carry only demonstrated dependencies between
   packaging, lifecycle, execution portability and continuation.
4. Verify the selected installed/platform matrix, matched task outcomes and failure
   cases. Update release/operator documentation from actual evidence. For the 2.0
   release, Product Manager and Lead explicitly settle every retained outcome as
   delivered, deferred with owner/next step, or intentionally retired with rationale;
   one comparator slice is not completion of the entire product plan.

Current hotfixes tracked in PRs #9, #14 and #15 were reported as taken into work by
their current owners, not proven merged here. Keep those corrections with their
owners; they are not new 2.0 features. Verify their actual landed state before using
them as prerequisites or claiming the corresponding defects fixed. This includes
installer preservation work; item 2 must consume the corrected owner, not duplicate
its repair. Keep the known Kimi documentation drift owner-scoped as well.

## Design economy and verification

**Generalization acceptance:** later implementation must demonstrate that:
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
- Admission: existing permission and policy eligibility, distinct from ranking.
- Empirical arbitration: settling checkable disagreement with observed evidence.
- JSON / YAML: JavaScript Object Notation / YAML Ain't Markup Language, structured
  data formats; PyYAML is a Python YAML parser.
- Standard library: language-shipped facilities (Python modules or Rust `std`),
  distinct from third-party packages.
- API: application programming interface; a library boundary, not a host sandbox.
- Foreign-function / interprocess bridge: calls across language / process boundaries.
- Windows Job Object: operating-system mechanism for managing a process group.
