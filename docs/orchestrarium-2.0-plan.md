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
core branch, status or exception list. Use existing owners to observe actual state,
choose an admissible next step, verify its result and revise the plan. This is a
design principle, not a new orchestration engine or a promise to execute every task.

Keep the accepted goal, acceptance criteria, ownership, authorized effects and
budget under their existing controls. Methods and step order may adapt within those
boundaries; changed authority, material scope/risk or acceptance criteria follow the
existing approval and review paths. Preserve useful accepted results, causal history
and unresolved obligations. Replanning neither resets budgets nor waives mandatory
review, retry or safety rules; any later change to those rules needs its own admitted
owner-scoped proposal. No runtime defect or root cause is established by this plan.

Distinguish unfamiliar task content from missing permission, execution capability
or trustworthy evidence. Lack of a scenario template is not itself a blocker when
existing capabilities and controls suffice. A real blocker holds dependent effects;
independent authorized work may continue unless shared-state or containment risk
requires a wider stop. Domain-specific checks remain necessary: a common workflow
does not make proofs, software tests and installation readback interchangeable.

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

**Next decision and dependencies:** recover or reconstruct that contract with the
user, choose supported install targets and upgrade/removal behavior, then use the
existing installer and ownership boundaries. Coordinate with item 2 only where
package lifecycle actually depends on native-role lifecycle; packaging research
need not wait for routing or cross-host continuation. No resurrection of removed
provider packs is implied.

**Acceptance:** an agreed package/command contract; a reproducible package with
only intended payload; clean-install, repeat-install, upgrade and removal evidence
on the agreed platform/target matrix; preservation of user-owned files and current
rollback guarantees. State which lifecycle actions remain unsupported. Publishing
a package and any paid operation require their own applicable authorization.

### 2. Fuller native-role lifecycle

**Status:** explicit 2.0 remainder, partially served by today's limited installer.
**Owner:** Toolchain Engineer at the existing production installer.

Complete the admitted adoption, update, deletion and reclaim cases without taking
ownership of customized or ambiguous files. Today's source manifest is validation,
not proof of installed ownership; current narrow stock migrations do not establish
a general lifecycle. [README](../README.md) and [INSTALL](../INSTALL.md) explicitly
reserve the remaining work for 2.0. This is a capability gap, not evidence that
today's conservative refusals are unsafe.

**Next decision and dependencies:** define ownership evidence and each authorized
transition before implementation, including existing-install migration and recovery.
First assess reuse of the installer's existing canonical-skill reconciliation of
recorded ownership, observed state and desired content for native roles, rather than
adding a special migration for each release. Preserve transaction/rollback machinery;
legacy installs without ownership evidence still need an explicit migration boundary.
Coordinate item 1 through this same owner, not a package-specific state manager.

**Acceptance:** agreed transitions succeed with independent installed readback;
custom files, unrelated configuration and ambiguous ownership are preserved or
refused visibly; interruption, rollback, reinstall and legacy-install cases retain
current guarantees. Test deletion/reclaim only within the accepted ownership and
authorization contract, never by treating filename equality as ownership.

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
consumer before coding. Use existing Lead judgment if sufficient; a pure comparator
is conditional. Item 4 supplies comparative evidence, not new execution permission.
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
later decisions through current evidence/lesson owners, with provenance and expiry
or invalidation after model, harness, tool, permission or material task changes. Negative
results must not disappear through success-only selection. No autonomous policy
promotion, background learning service or universal provider ranking follows.

Optional independent blind proposals, named-artifact cross-critique, Lead synthesis
and empirical arbitration may help demanding cases. Reuse the existing independent
review route: do not impose extra stages, new roles, peer-chat infrastructure or
mandatory paid reviews. Tests, proofs, counterexamples and measurements resolve
checkable disagreement; majority agreement does not establish truth.

### 5. Generic execution portability

**Status:** generic Windows command-line interface (CLI), including a possible Rust
implementation, remains deferred 2.0 work. Other limitations require scope decisions.
**Owner:** Platform/Toolchain Engineer at current process-supervision owners.

**Next decision and dependencies:** choose the actual supported commands/platforms
and containment oracle for the retained Windows goal. Rust is a deferred direction,
not permission to duplicate the Python production owner. Architect must resolve any
language/ownership change against current repository policy before implementation.
Separately decide whether generic POSIX execution and installation of the currently
source-only durable store/activation registry are needed by an accepted use case.
Their absence is not automatic admission of three new workstreams. Reuse the existing
process request/result contract and isolate real platform/provider differences in
its implementations; do not create a separate execution lifecycle per task scenario.

**Acceptance:** for every admitted route, prove bounded resource ownership,
cancellation, descendant settlement and trustworthy terminal evidence at its actual
boundary; unsupported routes stay typed unavailable before launch. Installation
changes require source-to-installed parity and lifecycle evidence. Implement only
prerequisites actually needed by a selected item, not a platform rewrite before
native comparison or npm planning can proceed.

### 6. Safe cross-host continuation

**Status:** retained, deferred future direction; not a comparison prerequisite.
**Owner:** Lead for admission; Architect and existing persistence/receiving owners
for the eventual boundary.

Restore task context, accepted artifacts, open findings, plans, dispatches and
evidence under one active logical owner when moving between hosts. The
[routing design](superpowers/specs/2026-09-04-adaptive-lead-model-routing-v2-design.md)
retains the required safety properties without preselecting leases or wire schemas.

**Next decision and dependencies:** admit a concrete transfer scenario; map durable
state, writer ownership, takeover and receiving boundaries. Item 5 matters only if
that scenario needs its execution/storage extension. Existing locks or a ledger
alone do not prove transfer safety. First assess whether an explicit stop, state
handoff, verification and resume meets the user's need before proposing transparent
live migration. This is a candidate, not a decision to remove broader continuation.

**Acceptance:** restored context is complete for the admitted route; old writers
cannot commit after transfer; stale results are rejected; cancellation and terminal
settlement survive admitted interruption/recovery paths. Independently verify the
prior owner's stop or exclusion, restored state and outstanding obligations. Test
concurrent takeover if supported; otherwise reject it without altering ownership.
Do not require a new lease service, registry or ledger merely to retain this outcome.

### 7. Optional named policy preferences from PR #5

**Status:** unresolved optional product decision, not a mandatory framework.
**Owner:** Product Manager for need; existing instruction/handoff owner if retained.

The old proposal packaged two named choices: `lean-implementation` and
`complexity-review`, for lean implementation and complexity-focused review. Simplicity, smallest coherent fixes, owner-first changes
and independent architecture review already belong to mandatory governance. They
must not become optional switches. Ordinary scoped instructions can already request
extra review focus.

The distinct missing capability is persistent named opt-in preferences, narrowed by
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
