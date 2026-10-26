# Orchestrarium 2.0 product plan

Status: remaining 2.0 product scope after extracting npm distribution and the
hybrid runtime into an independent project; reconciled 2026-10-23 against main
`84eefb6bbeec9ebbe032f00788f249ae59da05b5`. This is not an implemented release,
a measured improvement, or permission to run providers, spend funds, or publish.

## Goal and boundary

Deliver better task-specific orchestration: choose sufficient admitted model/effort
profiles, add complementary expertise when useful, learn from verified outcomes,
complete the separately admitted native-role lifecycle, and retain safe future
continuation across hosts. Preserve functional ambition, not every mechanism from
earlier drafts.

npm distribution and the hybrid Python/Rust runtime are now owned by the
[independent distribution/runtime project](https://github.com/applicate2628/Orchestrarium/pull/17), not the 2.0
release. Outcomes 1 and 5 below retain their disposition and historical numbering,
not duplicate design or delivery obligations. Their qualified slices may ship in
current versions; 2.0 does not wait for them unless a selected outcome demonstrates
a concrete dependency.
This is the canonical scope, status, dependency and acceptance register for the
remaining 2.0 outcomes (2, 3, 4, 6 and 7), with external-project dispositions retained.
The [focused routing design](superpowers/specs/2026-09-04-adaptive-lead-model-routing-v2-design.md)
owns the proposed comparison contract, not the whole 2.0 roadmap. Current
[shared governance](../shared/AGENTS.shared.md), [Lead contract](../src.codex/skills/lead/SKILL.md),
[role policy](../shared/role-routing-policy.v1.json), [resolver](../scripts/resolve-agents-mode.py)
and [installer](../scripts/production_installer.py) remain the live owners.

**Change-Surface Contract**

- Intended change surface: this plan, the focused routing design, docs index and release note.
- Approved seams: remaining 2.0 product planning, external-project disposition, and a proposed advisory comparison at existing discovery → Lead → resolver boundaries.
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
  execution, unavailable generic POSIX Process Runner Version 1, and a source-only
  durable operation store and route activation registry. The historical Rust-to-2.0
  deferral in those runtime docs is superseded for sequencing by the independent
  project, not by enabling any unavailable path. These are repository facts, not
  provider guarantees or proof of behavior in a particular installed environment.

## Outcome register

### 1. npm skill-pack distribution

**Disposition:** extracted into the
[independent distribution/runtime project](https://github.com/applicate2628/Orchestrarium/pull/17); not a 2.0
release deliverable or prerequisite by default. Toolchain Engineer and Product
Manager retain package ownership there, including the unresolved package contract,
runtime prerequisites and installer-safe delivery. Consume outcome 2 only for
package actions that actually require its expanded native-role lifecycle.

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
The independent distribution/runtime project consumes this owner only where its
package actions require this expanded lifecycle; it does not add a second package
state manager or make all distribution work depend on outcome 2.

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

### 5. Hybrid SDK coordination, native operations and portability

**Disposition:** extracted into the
[SDK design/status PR18](https://github.com/applicate2628/Orchestrarium/pull/18),
[SDK implementation PR19](https://github.com/applicate2628/Orchestrarium/pull/19) and
[independent npm and Rust task documents in PR17](https://github.com/applicate2628/Orchestrarium/pull/17),
together with outcome 1. Each owning document retains its own boundaries and
qualification; the two PR17 tasks are independent. Lead and
existing operation owners retain their responsibilities. Qualified slices may ship
in current versions; no runtime migration or provider activation follows from this
2.0 plan, and no duplicate implementation is retained here.

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
not prove it. The independent distribution/runtime project is a dependency only
if the chosen scenario requires a qualified runtime extension; extracting outcome 5
does not admit takeover or block stopped-handoff work by default.

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

Remaining 2.0 outcomes are 2, 3, 4, 6 and 7; they are not all mandatory for the
first release. Outcomes 1 and 5 now have independent project ownership and rollout,
not a hidden 2.0 dependency. Current admission, replanning, review, recovery and
generalization governance are the foundation, not new deliverables. Product Manager
and Lead must accept the release scope; an open optional choice holds only its
dependent slice.

**Next bounded work, independently where inputs and owners permit:**
1. Toolchain Engineer with Architect: define native-role ownership transitions and
   the legacy-adoption boundary (item 2), using the existing installer transaction.
   Implement only after that contract is accepted. The external distribution/runtime
   project consumes this owner only for package actions that need the expanded
   lifecycle, not as a second ownership manager.
2. Lead and QA Engineer: trace one real admitted routing caller and select matched
   evaluation tasks/oracles (items 3–4). Start from existing rationale and evidence;
   identify missing comparative evidence without launching providers. New runs need
   approved candidates, data and budget. A comparator remains a later decision based
   on demonstrated benefit, not the first implementation deliverable.

**Separate conditional decisions:** choose a concrete stopped-handoff need before
item 6; live takeover is a separate conditional capability, not an implication of
runtime migration. Decide named preferences in item 7 only if ordinary instructions
fail a recurring need. Neither these choices nor Kimi `auto`/Grok integration block
independent work above. The extracted project retains its own admission, owners,
implementation boundaries and evidence; its npm/native/SDK design is not repeated
or selected for delivery here. No optional outcome is silently lost.

After accepting a remaining 2.0 slice, implement and independently review its
smallest coherent owner-local change against its outcome's acceptance and the
failure probes below. For release, verify the selected installed/platform matrix
and actual task outcomes; settle each retained 2.0 outcome as delivered, deferred
with owner/next step, or explicitly retired with rationale. Outcomes 1 and 5 remain
externally owned, not unfinished 2.0 obligations. A plan or comparator alone is not
2.0.
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
- Admission: existing permission and policy eligibility, distinct from ranking.
- Empirical arbitration: settling checkable disagreement with observed evidence.
- SDK: software development kit; [PR18](https://github.com/applicate2628/Orchestrarium/pull/18) owns design/status and
  [PR19](https://github.com/applicate2628/Orchestrarium/pull/19) owns the implementation, not this remaining 2.0 roadmap.
