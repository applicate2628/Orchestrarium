# Native operations in Rust

[Goal](#goal-quality-attributes-and-architecture) · [Delivery](#delivery-channels-and-native-installer-ownership) · [Ownership](#state-process-and-cutover-ownership) · [Release sequence](#delivery-sequence-and-review-loop) · [First slice](#candidate-first-vertical-slice-mcp-usage-reminder) · [Work plan](#bounded-work-plan-and-audit-receiving-2026-11-12) · [Verification](#acceptance-parity-and-deliberate-improvements) · [Admission](#receiving-and-implementation-admission) · [Terms](#terms-and-abbreviations)

Status: independent design with an isolated publication matcher candidate; no native activation. Historical
observation baseline main `317e1448a020aeaa58f65aaceb180e835741d6de`; source observations do not prove
installed behavior. The plan tracks native operations, PowerShell and optional
npm distribution, and software development kit (SDK) coordination separately.

## Publication matcher candidate

The isolated [publication matcher](../native/publication-match/) uses PCRE2
just-in-time compilation and Rayon. The current scanner remains the sole
owner of line framing, review identity, classification and Git decisions.
The candidate accepts already-framed rows and returns ordered UTF-8 byte
spans only. Its batch threshold selects scheduling; it does not limit coverage.
An error is not an empty result. The qualified Windows x64 matcher worker
ships as an internal scanner component in the normal pre-SDK bundle and has no
SDK dependency. The selected Rust scanner release has its own qualification
under the [delivery sequence](#delivery-sequence-and-review-loop).

Before activating the worker, verify the exact retained artifact, complete
gate and receiver effects, and full VFEM timing at the ordinary gate budget.
Lexical equivalence or packaging alone does not constitute activation.

## Goal, quality attributes and architecture

Priorities: preserve operation/security semantics; maintain one owner for each
state/process; reduce lifecycle complexity. No measured speed or reliability gain
is claimed. Start with one Cargo package/CLI and internal operation modules, not
one service/crate per script. Python remains SDK coordination and unmigrated
operations. Do not introduce a daemon, scheduler, ledger or transaction framework.

| Decision | Benefit | Cost / acceptance boundary |
| --- | --- | --- |
| One common hook implementation and descriptor | Avoid host copies and basename-based ownership | Qualify all currently supported consumers before shared cutover |
| One installer operation owner, migrated from Python to Rust | Reuse admission, recovery and readback | Thin PowerShell/npm channels never implement managed-file changes or trust |
| Candidate reminder slice has no child processes or state writes | Small deterministic parity surface | Provides no proof for process, publication, transfer or installer ports |
| Independent later operation slices | Keeps risky owners separate | Each retains its own evidence and platform qualification |

## Delivery channels and native installer ownership

The accepted target is Rust CLI plus a thin PowerShell bootstrap, with npm retained
as a compatible delivery channel. [PR17](https://github.com/applicate2628/Orchestrarium/pull/17)
owns release selection, download/verification and dispatch. This PR owns native
operation behavior; the installer is not reimplemented in PowerShell or JavaScript.

Rust install/update and, when separately qualified, managed-file removal preserve
the current installer's target admission, user-file preservation, coupled
configuration/registration ownership, trust boundaries, interruption recovery and
persisted readback. Uninstalling a distribution channel does not remove applied
packs. Full-pack removal is not inferred from the existing narrow hook-retirement
operation; inventory, all consumers and foreign/unknown content must be qualified
before enabling it. No global garbage collector or parallel installer is added.

Both delivery channels invoke the same qualified Rust executable/resources for
an admitted release and target. Native installation must not require npm. Existing
Python installation remains explicit until Rust parity/cutover, with no silent
fallback or competing writer. This plan does not override the live Python-owner
policy; update its owner documents only with the admitted production cutover.

The installer migration is a bounded operation slice, not a prerequisite for all
other native hooks or optional SDK coordination. Neither selecting this architecture
nor implementing a bootstrap authorizes building, publishing, trusting or activating
native binaries. The reminder below has an isolated pilot, not a production
launch. Accept its evidence against the selected receiving base before choosing
any production implementation or activation.

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

The native entry dispatcher exposes deterministic operation commands. Optional
coordination follows PR19's implementation contract; it can consume current Python
operations before their native replacement and does not require Rust to start.
The native component uses one Cargo package (Rust build/package unit) and one CLI
per supported target, not one crate/service per script. This map names logical
boundaries; implementation admission fixes names and layout:
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

## GUI-independent functional boundary

Apply the shared **State-synchronization ownership** rule and its
[architecture acceptance](https://github.com/applicate2628/Orchestrarium/blob/63f355253d66f9c319904214ff419d857666df6c/shared/references/architecture-layering-hygiene.md#gui-independent-functional-boundary)
to the native operations and to projects developed under this workflow. Keep the
Rust operation owners callable without a GUI; the existing CLI/module contract
serves SDK callers and any replaceable future presentation client. Do not add a
daemon, network service or wrapper solely to express this boundary. UI-specific
rendering remains presentation-only; functional operations, results, errors,
cancellation and mandatory decisions retain a headless route and their existing
authority/lifecycle owners.

For each admitted migration slice, qualify its functional scenarios without a GUI
package or display/event loop, then exercise the same contract with a substitute
client. Where applicable, disconnect/reconnect the client without duplicating an
operation or losing its current state. Existing parity tests still own semantics
and safety; record any untested scope or explicitly requested, concretely justified
exception in the same slice evidence. This is planned acceptance, not evidence of
implemented Rust code or a new gate blocking independent work.

## State, process and cutover ownership

Dependencies run from adapters to existing domain owners to pure decisions/platform
operations; the process layer grants no dispatch authority. Each child has one
lifecycle owner: Rust supervision for Rust-created children, SDK adapter supervision
for SDK-created children; any native containment must assign noncompeting guarantees.
PR18 retains the historical SDK design. PR19 and its SDK execution document own
current implementation status, qualification evidence and remaining delivery work.
This plan owns Rust-operation parity and cutover. Native operations must preserve their own
capture, private-path, cancellation and settlement contracts; an SDK caller cannot
bypass them. Current unavailable generic Windows paths stay unavailable.
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


## Progressive reduction of model instructions

Treat instruction-budget reduction as migration of obligations, not text compression
or an automatic benefit of changing language. The SDK supplies supported session,
context, event, cancellation and result transport. Existing domain owners retain
decisions and state; Rust replaces qualified deterministic operations, not the
Lead's judgment or a second policy engine. The current reminder candidate improves
runtime packaging only; porting a reminder does not itself reduce rule volume.

| Obligation | Existing owner and planned boundary |
| --- | --- |
| Route, role and context selection | The existing resolver/dispatch validates supported choices; SDK adapters bind the selected context/session and report actual capabilities. The Lead chooses task fit. |
| Task/run lifecycle, ownership and review state | `mutate-work-item.py`, `agent-run-ledger.py`, `review_loop_state.py` and the existing reducer retain their distinct state and recovery contracts. Structural validation does not establish substantive completion. |
| Configuration and artifact shape | Existing resolver and validators own precedence, schema and compatibility checks; a qualified Rust replacement preserves those contracts. |
| Installed-file ownership and recovery | The existing installer owns plan/apply/readback and rollback. SDK events do not create installation authority. |
| Publication and process effects | Existing publication owners retain authority/currentness checks. Process supervision retains its actual containment/settlement boundary, separately from SDK-created child ownership. |

These are the owners mapped above, not newly implemented guarantees. For each
bounded slice, extend its existing work-plan entry with the source obligation,
affected consumers, current owner, replacement/interception boundary, verification
and uncovered routes, and the exact procedural text eligible for retirement.
This is review evidence, not a new tracker, runtime gate or parallel rules registry.

Qualify the supported SDK bindings and the selected Rust scanner slice in parallel.
Release the scanner first under the [delivery sequence](#delivery-sequence-and-review-loop).
Additional Rust migrations under O0--O6 have individual admission and qualification.
Remove procedural duplicates only for consumers whose actual path is covered and verified;
retain the concise obligation and necessary instructions for unsupported hosts.
Update the owning shared source and affected provider projections together, not
one provider's text by analogy. Keep a practical recovery path if a mechanism is
unavailable, without bypassing mandatory safety or permission controls.

Verification covers accepted and rejected inputs, direct and alternate supported
entrypoints, stale bindings, interruption/retry and recovery where relevant.
A callable SDK thread API does not prove interception of native subagent actions.
Distinguish runtime enforcement, advisory checks and remaining model instructions;
never advertise a model reminder as a hard guarantee.

Localize file-identity mismatches, checker failures and timeouts to the affected
operation and its dependent effects; do not turn them into a global stop until a
new release. Preserve owned state, diagnose and repair the responsible mechanism,
reconcile uncertain effects before retry, and continue independent admitted work.
For genuine safety or authority failures, retain the required hold on the affected
effect; a broken checker is neither permission to bypass it nor a reason to abandon
all work. Regression evidence includes an injected mismatch/checker failure,
continued independent work, preserved state, and successful authorized recovery
without duplicate effects. Timeout budgets need an operation-specific basis, not
a fixed arbitrary limit or an unbounded retry loop.

Retain model guidance for interpreting intent, architectural tradeoffs, choosing
skills and context, semantic review, prioritization and honest user explanation.
Runtime can validate required fields and provenance, but not prove that a rationale
or review is substantively correct. This migration adds no arbitrary depth, time
or count limits, approval stages or provider-name bans; existing mandatory controls
and route-specific provider boundaries remain with their owners.

Measure authored and composed instruction size alongside retained obligations,
coverage and maintenance burden, rather than chase an invented token quota.
A slice is complete when its own replacement and consumer checks pass and its
eligible duplicate instructions are retired; do not wait for a whole-product port.

## Workflow automation target and phased design

This is a design proposal for review, not completion or activation of the Rust
runtime. The target is less repeated procedural work, shorter model instructions,
and recoverable local failures. Keep the existing SDK coordinator and domain
owners. A future UI consumes their state; it is not another source of truth.
Do not make unrelated work wait for a monolithic Rust rewrite.

### Responsibility and migration slices

| Slice | Existing source owner | Rust responsibility | SDK / Lead responsibility | Focused acceptance |
| --- | --- | --- | --- | --- |
| Configuration and dispatch | `resolve-agents-mode.py`, `model_routing/launch_policy.py` | Deterministic precedence, role/capability compatibility and bounded input validation | SDK reports real capabilities; Lead chooses suitable role, route, context and effort under current authority | Invalid combinations rejected; existing permitted combinations retained; no fallback spending or account switch |
| Current plan and evidence | `docs/stale-plan-readmission.md`, existing handoff and review owners | Validate known revision/owner/evidence bindings and classify affected stale dependencies | Lead/Architect decide whether requirements or architecture changed; lack of a change marker is not proof of freshness | Changed relevant premise invalidates dependent evidence only; unchanged work continues; neighboring implementation is considered without automatic age veto |
| Work-item and review lifecycle | `mutate-work-item.py`, `agent-run-ledger.py`, `review_loop_state.py`, `solution_attempt/reducer.py` | Preserve typed transitions, identity, replay/conflict handling and each owner's recovery/readback | Lead supplies substantive acceptance and ownership decisions; SDK sessions do not own archive state | Replay does not duplicate effects; concurrent ownership conflict preserves both parties' work; restart resumes known intent; structural PASS is not completion |
| Skills and rule delivery | Shared governance, canonical skills and existing installer/projection validators | Check selected resource identity, projections and supported deterministic contracts | Lead selects relevant skills and restores missing governing context | No duplicate canon, stale projection or missing obligation; no count-based skill quota; changed instructions affect only actual consumers |
| Install and managed files | `production_installer.py` and its existing domain helpers | Qualified plan/apply/repair/rollback and installed readback | SDK does not authorize installation; user/host trust remains with its current owner | Preserve user content and rollback evidence on partial writes/close errors; distinguish wrong version from corrupt/missing content |
| Execution resources | Existing process supervisor and provider adapters | Own native-created handles/children, platform containment, cancellation and settlement | SDK owns its created sessions/children through supported controls; native provider descendants require actual capability evidence | Partial spawn/cancel/timeout closes acquired resources; independent tasks survive; no PID/name-wide termination; no success from an unconfirmed exit |
| Publication | Existing policy, complete Git-object scanner and publication gate | Port deterministic checks and identity/currentness mechanisms independently | Existing authority and review remain separate from a clean scan | No incomplete range credited clean; genuine findings hold only dependent publication; checker defects have diagnostic and repair paths |
| Transfer and residue | Existing transfer, artifact-disposition, cleanup coordinator and creator owners | Qualified inventory/integrity and selected owner-bound settlement operations | Lead classifies required results; cleanup remains coordination, not a universal deleter | Preserve unique/uncommitted/unpushed/user data; move only proved disposable material to designated trash; unknown items remain preserved and scoped |

Paths in this table refer to the owner map above and existing source tree, not
permission to move all implementations at once. A port does not activate source-only
stores or unsupported routes. Existing state formats remain with their domain owners;
use typed calls where they remove duplication without erasing an isolation boundary.
Do not add a scheduler, universal transaction manager, blanket policy engine,
resident cleanup daemon or second persistent ledger for this program.

### Failure and recovery contract

At each actual effect boundary preserve the operation identity, affected scope,
current outcome, diagnostic cause, reconciliation action and next permitted action
in the existing result/status contract. Distinguish rejection before effects,
failure after partial effects, unknown outcome and verified success. Extend a
schema only where its existing contract cannot express a needed distinction.

Read-only aggregate diagnostics must not become a global dispatch gate. In the
current work-item checker, aging and blocked dependencies include advisory or
informational results; preserve their meaning. A corrupt unrelated item must not
prevent inspecting or repairing that item or executing an independent admitted
task. Refuse only mutations whose required inputs cannot be trusted; do not invent
missing history to make an audit pass.

A mismatch invalidates only evidence depending on that exact identity, not every
task or check in the repository. A transient connection failure can be retried
after current-state reconciliation; an explicit authorization denial is not
retried through another shell, account or transport. A checker implementation
defect is work for its owner, not a permanent project prohibition. Preserve
required publication/security holds while repairing the checker; continue safe
nondependent implementation and tests. Do not discard a good result because a
later reporting or cleanup step failed; retain both the result and unsettled duty.

Budget every actual bounded operation from its contract, measured work and risk.
Inventory existing round/retry, parser, output, memory and time limits before
porting: identify their source and purpose, and separately propose removal or
correction of unsupported constraints. Do not copy a constant as architectural
truth, silently relax a protection, or disguise a changed limit as behavior parity.
Prefer bounded incremental consumption and backpressure to unbounded buffering;
a budget exhaustion records the unfinished scope instead of a fabricated PASS.

Inspection and owner-bound reconciliation remain reachable before validation of a
broken state. Unsupported schemas may be inspected without mutation; preserve
actual receipts and bytes rather than rewrite history. Keep project topology and
derived README generation with the existing lifecycle owner. A stale historical
review or ledger diagnostic is not a current veto without an affected obligation.

Later workflow helpers may bind PR-bot work to the exact repository, head, review
thread and permitted cursor, and validate changed-material skill/MCP evidence.
They consume the existing bot and freshness protocols, not another polling loop.
Read-only metrics may report overhead, residue and instruction size; missing
telemetry is not permission to stop an otherwise admissible operation.

### Concrete audit follow-ups

- Installer exception rollback is not proof of recovery after process loss. Current
  in-memory transaction mapping needs a bounded design for the minimal durable
  phase/identity evidence needed to reconcile an interrupted owned effect. Start
  with read-only reconciliation and protect user changes; uncertain state holds
  only the affected mutation. Prove actual process-loss recovery separately from
  managed-exception tests, without asserting that data loss has been observed.
- Batch planning/dry-run must report each independent target rather than hide later
  results after one target fails. Preserve mutation ordering and existing rollback
  semantics; separate partial diagnostic results from all-target success.
- An incomplete dependency environment must be distinguishable from an owned
  completed setup and an unrelated user environment. Reconcile its exact selected
  identity and completion evidence before repair; do not overwrite a user
  environment or silently reuse partial setup as success.
- The SDK ledger audit found metadata-write failure after lock acquisition could
  leave the selected item's descriptor/lock unsettled. Consume the independently
  owned correction rather than duplicate it. The native port must close acquired
  resources on every exit, handle partial writes, preserve the primary failure,
  and leave replaced or foreign lock identities untouched. Crash recovery needs
  proof of inactive ownership; a stale-looking path is not takeover authority.
- Existing review-round/retry caps and parser-size constants need the risk/source
  classification above. Their presence in Python alone is not a reason to impose
  them on every future workflow or to remove them without understanding the owner.

These are scoped follow-ups and evidence gaps, not claims that all corresponding
repairs have shipped. Consume separately owned fixes when received rather than
reimplement them in this branch.

### Resource settlement and skill audit

At creation, bind disposable resources to their producing operation using existing
custody evidence. On success, failure, cancellation and interruption, preserve
durable results first, then settle owned handles/processes, temporary outputs and
unused worktrees through their respective owners. Release in-memory buffers and
subscriptions on all exits. Cleanup failure must not overwrite the primary error.
Settlement still runs through the existing owner if result serialization or
persistence fails. Retain acquired outcomes incrementally, report unavailable
evidence, and never discard the only surviving copy of a result or recovery input.

Use the current `post-spawn-cleanup` and `repo-cleanup` contracts, not a new
machine-wide sweep. Recheck exact ownership and active use before action; a PID,
name, age or directory label alone is not ownership. Preserve shared/borrowed
processes, unknown files, unique commits, uncommitted changes and recovery payloads.
Temporary worktree retirement requires verified durable Git custody and released
ownership; it never implies deleting the branch. Trash must contain no required
result or live recovery material. Permanent deletion requires its own existing
authorization, and a RAM-disk placement does not waive that requirement.

Audit each affected skill with the same migration: keep semantic guidance, replace
covered mechanical instructions with the owning operation, and remove stale
duplicates rather than layering exceptions. Check for universal stop language,
unsupported numeric thresholds, mandatory ceremony without risk basis, duplicated
canonical text, and provider-specific behavior presented as universal. Preserve
actual mandatory safety/authority controls. Unknown residue holds its destructive
action; it does not automatically stop unrelated delivery. A cleanup report must
not claim whole-host cleanliness from a selected-resource check.

### Delivery sequence and review loop

1. Keep the tagged pre-SDK baseline as the reference and reconcile the selected
   Rust scanner slice with receiver-aware main. Qualify findings and receipt
   parity on small changes over receiver history and large new disclosures.
   Verify progress, interruption and recovery, resource settlement, and actual
   receiving on supported installation targets before release. Follow the
   release order in the [Orchestrarium 2.0 product plan](https://github.com/applicate2628/Orchestrarium/blob/debdf7b9cf8f0078b62dd5d40f45318655572677/docs/orchestrarium-2.0-plan.md#current-delivery-order-and-completed-work).
2. Qualify the selected SDK contracts and their input, session and result bindings
   in parallel. Release the SDK after the independently qualified scanner slice.
   Qualify PowerShell, POSIX and optional npm distribution in its own delivery lane.
3. Admit further deterministic operations individually under O0--O5 when they
   demonstrate a maintenance benefit. The reminder remains a candidate for
   this broader migration. Use each operation's own tests and supported
   packaging and installer path.
4. Proceed through pure validation/reducers, then state/resource/install operations
   according to dependency and risk. Publication and transfer retain separate
   qualification. Independent slices may proceed in isolated ownership lanes.
5. For each covered consumer, shorten the corresponding procedures in shared rules,
   skills and projections together, preserving semantic obligations and unsupported
   consumer guidance. Read back the actual delivered instruction composition.
6. Review the final candidate across architecture, failure/resource lifetime,
   authority/data preservation, compatibility and skill economy. Fix concrete
   findings and re-review affected deltas; do not restart unrelated passed scopes.
   Unresolved semantic choices return to their owner, not an automatic new gate.
7. Keep verified changes committed and published in the existing PR scope.
   Production cutover/installation remains a separate admitted effect. Record
   remaining unsupported targets and cleanup duties without calling them success.

Each slice reuses the relevant current test families (work-item/ledger/review,
installer transactions, process supervision, publication, scratch lifecycle and
cleanup) and adds only missing native cases. Include failure injection for resource
creation, partial write, stale identity, checker failure, timeout, restart and
concurrent updates. Verify independent progress alongside dependent holds, and
recovery without duplicate effects. Test actual claimed platform boundaries;
stubs and source checks are not installed or provider-native acceptance.

## Candidate first vertical slice: mcp-usage-reminder

Source: [canonical entrypoint](https://github.com/applicate2628/Orchestrarium/blob/317e1448a020aeaa58f65aaceb180e835741d6de/scripts/universal-hooks/scripts/mcp-usage-reminder.py),
[emitter](https://github.com/applicate2628/Orchestrarium/blob/317e1448a020aeaa58f65aaceb180e835741d6de/scripts/universal-hooks/scripts/hook_common.py),
[policy](https://github.com/applicate2628/Orchestrarium/blob/317e1448a020aeaa58f65aaceb180e835741d6de/scripts/universal-hooks/scripts/mcp_continuity_policy.py),
[health identity](https://github.com/applicate2628/Orchestrarium/blob/317e1448a020aeaa58f65aaceb180e835741d6de/scripts/check-hook-health.py)
and [installer](https://github.com/applicate2628/Orchestrarium/blob/317e1448a020aeaa58f65aaceb180e835741d6de/scripts/production_installer.py).
The current Python hook imports SESSION_START_CONTEXT and emits SessionStart JSON
unconditionally. It reads no stdin, writes no project state, creates no children,
catches import/output errors and returns zero. Existing thin launchers are not
another maintained implementation.

### Invocation and payload contract

Define one common descriptor for logical marker, retained executable identity,
exact argv, event, matcher, source and matching resource identities. Registration,
inventory, health target extraction, replacement and retirement consume it.
Current _command_identity normalizes every argument and _invoked_script identifies
interpreter/script operands; neither alone identifies multiple native selectors.
Normalize only typed path operands; preserve selectors, case and argv boundaries
under the supported host serialization. No substring/binary-basename ownership,
per-hook exception or permanent forwarding layer.

Extend the existing installer to place the immutable executable and resources
under its admitted resolved agents root, independent of npm caches or node_modules.
The same owner performs explicit apply, recovery, source/inventory registration
binding, manual native trust, readback, replacement and retirement. Unknown foreign
references preserve old versions. No automatic collection or reference-count service.
Generate the exact embedded policy projection from SESSION_START_CONTEXT at build
time; a hand-copied text block is not another policy source. The migrated runtime
has no Python dependency. Keep the Python policy module while other live consumers
need it; only later move authored policy to one neutral single-source resource.

### Isolated pilot evidence (2026-11-21)

The receiving baseline for this plan is pre-SDK main
`b9d11278f435fa1c20de61d83449b405a95469d2`. The isolated pilot's
`native/mcp-usage-reminder/` is retained at
`ea30a80c61f0ae348adeb18ab7beff74b7e3820b`, outside this plan PR. It does
not add a production executable, selector or trust change to the receiving tree.

| Evidence | Observed scope and limit |
| --- | --- |
| Standalone Windows and Linux checks | The Rust reminder built and matched the Python oracle in isolated fixtures; this is not provider dispatch or supported-platform rollout evidence. |
| Retained descriptor and preview (`51896d8c9345988b7daa1468fdbeba4c44124ca7`) | Explicit isolated preview used the existing installer and health owner, with native apply still refused in the public route. |
| Real Codex command-line client 0.170.0 (`1f27c477e1c31110d41daa0b5058466646d340f2`) | Read-only hook listing in fresh isolated profiles identified the native candidate and Python control. Both were enabled but untrusted; report returned `PENDING_MANUAL_TRUST` and require refused. No hook invocation, model turn or trust write was qualified. |
| Windows isolated native predecessor lifecycle (`66d54906860f98386fbdb32a3cac11902f7c6829`, `ea30a80c61f0ae348adeb18ab7beff74b7e3820b`) | Selected native-to-native update/retirement and late-refusal rollback through the existing owner, not a live Python-to-Rust migration or crash/restart proof. |

Next, recheck the bounded pilot against the accepted receiving source and
preserve its exact code and evidence independently of this plan. Before any
production selector, qualify actual manual-trust verification and hook dispatch
without a provider inference call; check build-to-installed identity, repeat
install, interruption/restart, retirement and rollback for each claimed
consumer and platform. Codex listing alone does not qualify Codex dispatch,
and no Claude dispatch is claimed. Python remains the only production default
and owner. No policy changes, silent fallback or live cutover are admitted here.

### Acceptance and cutover

1. Capture the consumer inventory and baseline for Codex and Claude, every supported
   host/architecture, event/matcher/argv/source and output contract. Windows x64 is
   first qualification target, not permission to drop existing consumers.
2. Compare JSON shape, literal UTF-8, property/order/newline, stdout, stderr and exit
   status on startup/resume/clear/compaction/subagent cases, malformed and open
   stdin (must not block), and output failure. No stdin read, file write or child
   creation is added. Preserve fail-open. Record removal of Python sibling-import
   failure as a packaging difference, not fabricated failure-byte equality.
3. Verify wrong selector/path/source, duplicate and foreign registrations, host
   serialization, native trust, resource drift and build-to-installed identity.
   Exercise reinstall, interruption and conditional rollback/readback through the
   existing owner; do not mask failures with a mock process owner.
4. Once every existing supported consumer qualifies, one cutover changes their
   registrations and removes the superseded Python entrypoint/canon/mirrors.
   No permanent Python/Rust switch or maintained duplicate. Retained installed old
   binaries for rollback are historical resources, not a second source implementation.
   Update the binding Python-production-owner policy and owning docs together
   before production cutover; this design does not change that live rule.

Reuse tests/test_universal_reminder_hooks.py,
tests/test_sessionstart_reminder_python_hooks.py,
tests/test_hook_runtime_installers.py, tests/test_hook_runtime_transactions.py
and tests/test_universal_hook_surfaces.py as behavior/receiving oracles; extend only
missing native descriptor and lifecycle cases. Source review is not installed proof.

## Bounded work plan and audit receiving (2026-11-12)

This section refines the existing proposal; it does not authorize implementation,
change the live Python-owner policy, or certify SDK acceptance. Before starting,
refresh the accepted source and the SDK owner evidence. An open or merged PR alone
is not the acceptance record. Historical baseline links above identify observations,
not immutable instructions to implement against an obsolete checkout.

### Work packages

| Step | Work and existing owner | Required evidence / exit condition |
| --- | --- | --- |
| O0 | Reconcile current source, SDK acceptance and actual hook consumers; choose one operation with the user under this proposal. | One named operation, preimage revision, supported consumers and effects; no implicit installation or model launch. |
| O1 | Extend the existing reminder tests on isolated fixtures before native code. | Full-process stdout, stderr, exit, effects and nonblocking open stdin; normal, partial-write, closed-output and shutdown cases distinguished. |
| O2 | Implement one operation in one Cargo package with a small dispatcher. Reuse an existing native package if one has since been admitted. | Canonical generated payload; no runtime Python for that operation, no state writes, children or network; unknown selectors do not impersonate a successful reminder. |
| O3 | Extend existing installer/registration/health owners for retained native payloads. | Exact operation/argv/event/source/resource identity, foreign-reference preservation, interrupted-update recovery and installed readback. |
| O4 | Qualify the source-to-installed path for all affected supported consumers. | Behaviour and platform evidence remain separate; compare complete invocation and delivery cost with the maintained Python alternative. |
| O5 | Perform one explicitly admitted cutover through the existing owner. | No competing writers or silent fallback; retire only superseded source after checking consumers; keep required rollback material outside trash. |
| O6 | Select one further justified deterministic operation. | Its own acceptance and removal boundary; installer, process, publication and transfer ports do not inherit the reminder's proof. |

O0--O6 are planned work, not completed native implementation. A first operation
that produces no useful delivery or maintenance benefit may end this experiment;
there is no whole-product Python-removal objective. Desktop UI and MPI/HPX
execution are separate projects, not dependencies of this sequence.

### Output and payload boundary

A function returning zero is not proof that the process exits zero: buffering,
flush and interpreter teardown must be observed in the O1 subprocess oracle.
Keep the existing intended fail-open policy, but record any observed discrepancy
as a separate baseline defect or explicitly admitted semantic correction; do not
silently normalize it away as migration parity.

The native emitter uses checked byte writes and handles write/flush failures
under that contract; a panicking convenience print is not error handling.
Compare required bytes, ordering and newlines at the actual output boundary.
Open stdin must not be read merely to learn that this event needs no input.
Unexpected selector errors belong to the dispatcher, not the reminder result.

Generate the embedded projection in an explicit packaging step from the canonical
policy/emitter at the selected source revision. Record the source and generated
payload identity with the executable/resource descriptor. Build-time use of the
existing trusted Python producer is permitted; the delivered reminder has no
Python runtime dependency. Do not hide arbitrary interpreter discovery, downloads
or source execution inside a Cargo build script, and do not maintain copied policy
text in Rust. Toolchain, target, enabled features, lockfile and native dependencies
are part of receiving, not proof of release authenticity by themselves.

### Focused verification and change boundaries

Reuse the reminder, universal-hook, installer and transaction tests named above.
Native tests add only missing contract cases. A unit writer that fails is useful,
but does not replace an actual closed-pipe subprocess or installed-host receiving.
Record Windows and each other claimed target independently; missing prerequisites
are unavailable evidence, not passes. No provider inference is needed for parity.

Keep the work in this responsibility line. A bounded implementation PR contains
its causal tests; a broader installer/process/publication migration is separate,
not a stack of duplicate proposals. Normal source review, publication safeguards
and user permissions continue to apply. A document-only audit does not grant a
production cutover, new dependency installation, reviewer/model launch or merge.

## Independent subsequent slices

After the reminder pilot, a possible order is another simple shared hook, then
justified pure reducers/validators, then state-owner/installer operations. Admit
each production slice separately; the order here is not implementation
authorization. Process supervision,
publication and repository transfer are separate high-risk migrations with their
own authority, creator-custody and complete-graph/settlement requirements.
Unavailable generic routes stay unavailable. A simple hook does not wait for
every generic process target; npm and SDK do not wait for this full roadmap.
Use each existing state owner, not one universal Rust transaction manager.

## Complete source coverage and incident preservation

The [source inventory](native-rust-source-inventory.csv) is a design appendix, not
a runtime registry or permission source. It records every tracked Python source,
Python fragment, POSIX/PowerShell launcher and non-document hook-directory artifact
in the union of Rust-plan commit `ae9081173e159c74eb1e9d756dedfc58942924c2`
and SDK commit `5b19ab8852385d2bb0362b35a2856f48b220ab19`: 676 distinct paths
(546 in the Rust snapshot, 643 in the SDK snapshot). Each row carries both available
Git blob identities, category, planned disposition and owning responsibility.
An absent blob means absent from that snapshot, not a safe deletion candidate.

This closes inventory coverage, not implementation or per-file acceptance. Refresh
the inventory against accepted receiving revisions before the relevant slice;
incorporate newer separately received fixes before comparison. Compare the exact
`git ls-tree -r` set with the CSV: all `.py`, `.pyfrag`, `.sh`, `.ps1`
and non-Markdown artifacts in `/hooks/` or `/universal-hooks/`; require no
missing or duplicate paths and matching blob identities. Generated host hook
registrations are separately inventoried through the existing installer, health
and `universal_hooks_manifest.py` owners; source filenames do not prove actual
event/matcher/argv/trust registration. No installed or untracked file is silently
claimed to be covered by this tracked-source snapshot.

| Inventory category | Count | Treatment |
| --- | ---: | --- |
| Canonical projections | 51 | Migrate the single canon and all supported receiving bindings, not separate copies. |
| Hook candidates | 22 | Capture event/input/output/failure semantics and host consumers before porting. |
| Native operation candidates | 46 | Migrate the existing deterministic owner by qualified slice. |
| Provider boundaries | 13 | Use supported SDK/native transport; preserve vendor and account constraints. |
| Launchers | 24 | Retarget or retire only with the owning operation; do not port logic that is only forwarding. |
| Validation tooling | 20 | Reuse or port when beneficial; preserve actual blocking/advisory semantics. |
| Historical oracles | 16 | Keep immutable baseline evidence, not a competing production implementation. |
| SDK bridges | 22 | Retain the vendor-supported SDK coordination boundary until an equivalent official route qualifies. |
| Development oracles | 16 | Keep useful verification tooling; runtime migration is not a ban on Python tests. |
| Delivery tooling | 3 | Align existing distribution owners; no duplicate installer. |
| Third-party parser sources | 72 | Evaluate a maintained upstream crate instead of manually translating vendored code. |
| Maintenance tooling | 2 | Preserve bounded owner operations; no machine-wide cleaner. |
| Tests and test fixtures | 369 | Reuse as behavior oracles and add only missing native cases. |

All categories are included in the project; inclusion does not mean copying every
test, vendored dependency or official Python SDK into Rust. The design goal is
native ownership of qualified deterministic production operations with explicit
SDK bridges and retained useful tooling. Any proposed full Python-free runtime
would require a supported replacement for each remaining bridge, not a language
purge. Source-only components stay inactive until their own admission qualifies.

### Skills and activation-surface coverage

The [skill inventory](native-rust-skill-inventory.csv) covers the same two frozen
revisions: 228 distinct paths (175 per snapshot), including 90 skill-body paths,
70 provider-role entrypoints, 52 activation-metadata files and 16 historical
fixtures. These are paths across layouts, not 228 distinct skills. The canonical
Codex skill tree contains 54 skills; historical Claude copies and SDK adapter
entrypoints must not become additional semantic owners. Verify actual installer
projection/binding rather than infer ownership from a similar filename.

| Canonical skill family (count) | Rust-capable mechanics | Retained semantic responsibility |
| --- | --- | --- |
| Coordination (6) | Scope/lineage/dependency/artifact binding and current-state projection | Outcomes, priorities, decomposition and architecture; no universal stage chain |
| Implementation (11) | Scope/revision binding, admitted test invocation and result capture | Correct implementation and domain judgment; route-specific prerequisites |
| Research/advice (6) | Provenance, linking, retention and currentness through existing owners | Research, mathematical validity and synthesis; advice does not grant authority |
| Assurance (8) | Evidence identity, coverage links and state/result contracts | Threat/severity, test adequacy, architecture and performance judgment |
| UI/UX (5) | Capture lifecycle and state/environment identity | Visual quality and usability; keep accessibility severity with its specialist |
| External execution (3) | Scope/result bindings and supported SDK transport | Lead selects context/route/role; output does not grant permission |
| Review utilities (2) | Existing revision/attempt/delta and settlement contracts | Finding relevance and option comparison; no new owner or mandatory loop |
| Git/resources (4) | Existing Git, transfer, lifecycle and creator-bound settlement | Consent, value/ownership classification and substantive completion |
| Diagnosis (2) | Scoped evidence acquisition and capture cleanup | Hypothesis selection and observer effects; correct overbroad logs-first gates |
| Specialized toolchains (2) | Existing process/evidence primitives | Project-specific build/update policy is not universal admission |
| Explanation/documents (5) | Optional shared artifact/lifecycle helpers | Communication, generalization, scientific/document judgment |


The inventory maps all 54 canonical skill names to these 11 families. The audit
read every description/heading and contract excerpts, with high-risk sections
read in full; it is family-level semantic coverage, not line-by-line proof.

Apply the per-skill migration review to the actual body and activation/reference
consumers, not only this family table or file count. Keep a skill's governing
workflow owner; extracting a mechanical helper does not authorize another model
launch, another approval gate or a second copy of the methodology.

The source audit identified concrete correction or reconciliation targets before
mechanical translation:
- `bug-hunting/SKILL.md` requires absolute runtime logs before every edit, stops
  all edits after a second cross-break, and describes logging as effectively
  zero-risk/no timing effect. Correct these overbroad claims through its existing
  owner: evidence appropriate to the affected hypothesis, scoped diagnosis, and
  explicit observer effects. The separately owned skill correction must be
  received, not duplicated in this plan branch.
- `reliability-engineer/SKILL.md` has a blanket research/design input requirement
  to reconcile with route-aware neighboring contracts; do not automatically impose
  research/design on every bounded repair.
- `performance-engineer/SKILL.md` sampling and live-profile requirements belong
  to the relevant performance claim, not every task's launch quota. Reconcile its
  approval wording with current lifecycle/standing authority instead of compiling
  a duplicate unconditional gate.
- Transfer parser-size caps and cleanup free-space thresholds are existing
  resource contracts to justify in their actual scope, not global progress
  thresholds or permission to purge data.
- Preserve the UX/accessibility owner separation; reusing verification machinery
  must not duplicate substantive specialist gates.

These findings do not declare every skill defective, every line reviewed, or every
mechanical requirement portable. Each implementation slice supplies the affected
body/consumer evidence and closes its concrete findings through independent review.
No rule is removed solely because an SDK or Rust library is present.


### Incident-to-regression map

Every affected slice binds its actual old and new revisions, input/environment,
expected result and side effects. The following existing regression families are
starting points, not claims that every incident is already reproduced natively.

| Incident / obligation | Existing evidence or regression family | Native comparison / additional probe |
| --- | --- | --- |
| Declared validator actions not executed | `tests/test_python_validator_runtime.py` | Verify required checks actually run; declared inventory and green summary alone are insufficient. |
| Baseline bytes changed by checkout line endings | `tests/test_pinned_source_checkout.py`, `tests/test_orche_baseline_pin.py` | Preserve byte-pinned evidence through Windows checkout, packaging and installed readback. |
| Managed/user Markdown and encoding preservation | `tests/test_markdown_bom_preservation.py`, `tests/test_markdown_private_semantic_contract.py` | BOM, CRLF/LF, fenced text and user-owned bytes match the owning contract; parser replacement must not rewrite unrelated content. |
| Canonical hook/mirror drift or import failure | `tests/test_universal_hook_surfaces.py`, `tests/test_universal_audit_hooks_hook_common_unimportable.py` | All supported projections updated together; preserve each hook's advisory/fail-open/fail-closed behavior. |
| Copy/descriptor-close failure hides primary outcome | `tests/test_installer_cleanup_primary.py`, `tests/test_production_installer_receiving_errors.py` | Preserve primary and cleanup errors, actual effects and rollback custody on all exit paths. |
| Installer metadata, user edits and rollback | `tests/test_installer_transaction_metadata.py`, `tests/test_installer_projection_rollback.py` | Compare owned writes and rollback; add real process-loss recovery, not only caught exceptions. |
| Partial SDK environment or failed batch preview | SDK `tests/test_sdk_setup.py` and SDK `tests/test_install_selection.py` | Do not accept incomplete setup; report unaffected preview targets without changing apply semantics. |
| Ledger metadata-write leak / unknown outcome | SDK `tests/test_agent_run_ledger.py` and separately received lock failure tests | Partial writes, close failure, replaced/foreign locks and crash recovery; no PID-only takeover or duplicate events. Cooperative path checks are not atomic fencing. |
| Publication scanner timeout or incomplete range | `tests/test_publication_native_timeout.py`, `tests/test_publication_safety_scanner.py`, `tests/test_publication_prior_disclosure.py` | Reap owned processes, retain full required graph scope, refuse only affected publication; independent repair continues. |
| Stale plan resumes despite changed implementation | `tests/test_plan_currency_contract.py`, `docs/stale-plan-readmission.md` | Validate relevant bindings and preserve required architectural judgment; no age-only automatic veto. |
| Review/context evidence binds the wrong revision or session | `tests/test_review_loop_state_v2.py`; SDK `tests/test_sdk_context_selection.py`, `tests/test_sdk_runtime.py` | Changed scope invalidates dependent evidence only; fresh/handoff/resume/fork claims match actual supported behavior. |
| Cleanup removes useful data or leaves owned resources | `tests/test_scratch_evidence_lifecycle.py`, `tests/test_retained_scratch_file_lifecycle.py`, `tests/test_cleanup_engine.py` | Preserve unique results, release owned resources despite reporting failure, and keep foreign/unknown identities untouched. |

The SDK snapshot includes received fixes: lock-acquisition cleanup
`e558ecf2184abc286d1c693f9e0ede727fe55ed6`, independent dry-run previews
`26a3c934`, and process-lineage-aware Windows timeout tests `5b19ab88`.
Their combined focused check passed 47 tests; this is not a full-suite, native Rust
or hard-crash qualification. Partial-environment and process-loss recovery remain
separate open design/acceptance work.

Receiving each later fix extends the affected row rather than starting a duplicate
bug catalog. Same-item ledger integrity can legitimately hold that item's dispatch;
do not weaken integrity to achieve finer isolation. Unrelated work-items remain
independent. Simulated process/provider checks do not establish native provider,
crash or installed-platform acceptance.

### Old/new qualification and cutover

For each operation, run the current Python oracle and Rust candidate on isolated
copies or deterministic replay inputs, not twice against live mutable state.
Compare protocol bytes where required, structural values without hiding meaningful
differences, error/exit behavior, owned effects and protected data. Classify known
Python defects explicitly: approved fixes may differ intentionally; do not enshrine
a bug as parity or quietly normalize it away.

Bind publication/installation to the qualified executable, resources and consumer
descriptor. Preview, apply and read back through the existing owner; on partial
failure reconcile the real effect before retry. Keep known-good recovery material
until the owning rollback conditions no longer need it. Rollback means an
identity-checked restoration compatible with current user changes and state formats,
not overwriting newer work or blindly installing an old binary.

Retire the replaced Python production entrypoint and mirrors only after its
supported consumers qualify. Retain needed historical evidence and development
oracles, not a permanent second live implementation. No absolute guarantee of
bug-free operation is claimed: completion means the declared coverage and evidence
are met, remaining limitations are named, and failure/recovery paths are usable.


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

### Library reuse decisions to qualify

Prefer maintained upstream primitives where they reduce custom code, but keep
application authority, custody and recovery with the existing owners. The following
licenses were checked in upstream manifests/license files on 2026-11-17; no version
is selected or installed by this plan. At implementation, review the exact release,
features, compiler requirement, transitive licenses, advisories and supported targets.

| Need | Candidate / existing path | License and acceptance boundary |
| --- | --- | --- |
| Source-span Markdown parsing | [pulldown-cmark](https://github.com/pulldown-cmark/pulldown-cmark) | [MIT](https://github.com/pulldown-cmark/pulldown-cmark/blob/main/LICENSE). Use offsets to preserve untouched bytes; not a lossless reserializer or assumed markdown-it replacement. |
| JSON Schema | [jsonschema](https://docs.rs/jsonschema/latest/jsonschema/) | [MIT](https://github.com/Stranger6667/jsonschema/blob/master/Cargo.toml). Match the actual draft/formats and offline refs; reject duplicates before a value tree loses them. Keep semantic validators separate. |
| SHA-256 identities | [sha2](https://github.com/RustCrypto/hashes/tree/master/sha2) | [MIT OR Apache-2.0](https://github.com/RustCrypto/hashes/blob/master/sha2/Cargo.toml). Preserve exact bytes/domain separation and existing persisted IDs; hashing grants no authority. |
| Git graph traversal | Keep [Git cat-file](https://git-scm.com/docs/git-cat-file)/[rev-list](https://git-scm.com/docs/git-rev-list) first; evaluate [gix](https://github.com/GitoxideLabs/gitoxide) only for demonstrated benefit | [gix MIT OR Apache-2.0](https://github.com/GitoxideLabs/gitoxide/blob/main/Cargo.toml). Require complete-graph parity, tags/noncommit roots, missing objects, worktrees and exact blobs; not filesystem traversal. |
| Lock primitives | [standard-library File locks](https://doc.rust-lang.org/std/fs/struct.File.html), then missing native APIs | Platform semantics must qualify. Neither a lock nor path existence proves fencing, dead ownership or safe takeover. |
| Scoped temporary files / single-file writes | [tempfile](https://github.com/Stebalien/tempfile); [atomicwrites](https://docs.rs/crate/atomicwrites/latest/source/Cargo.toml.orig) only if useful | tempfile MIT OR Apache-2.0; atomicwrites MIT. Select an authorized workspace explicitly; test permissions/durability/partial effects. Neither RAII cleanup nor rename is a multi-file crash-recovery protocol. |
| Process containment | [process-wrap](https://github.com/watchexec/process-wrap/blob/main/Cargo.toml), missing APIs through [windows-rs](https://github.com/microsoft/windows-rs/blob/master/crates/libs/windows/Cargo.toml) | Both MIT OR Apache-2.0. Qualify partial spawn, cancellation, capture and descendant settlement; no mandatory Tokio runtime. |
| CLI / JSON / TOML / file inventory / parallelism | Existing candidates clap, serde_json, toml_edit, walkdir, rayon above | clap's MIT option verified; serde_json/toml_edit/rayon MIT OR Apache-2.0; walkdir MIT OR Unlicense. Preserve byte/number/order/duplicate contracts, link policy and deterministic assembly. Add parallelism only with measured benefit. |

A rejected crate remains a documented tradeoff, not a reason to invent a large
replacement framework. Check the actual old/new incident corpus before replacing
a parser or persistence primitive. Unavailable capabilities stay explicit; library
installation or compilation is not runtime acceptance.


## Acceptance, parity and deliberate improvements

Establish the current behavior and performance baseline.
For deterministic replacements require one-for-one parity of standard-output protocol, standard-error
output, exit codes, ordering, effects, persisted state/files and error behavior on
the same inputs, including malformed/missing data and preserved user content. Require
byte equality wherever the interface contract demands it. Structural comparison must
preserve all contract-visible distinctions; normalize only specifically justified
nondeterministic fields, never broad masking. Adjudicate known baseline defects
separately; neither enshrine them blindly nor disguise intentional semantic changes
as migration. Current SDK behavior/outcome criteria belong to PR19; native parity here concerns
deterministic operations, not stochastic model prose.
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
Windows/macOS/Linux support individually before advertising it. Verify native dependencies and interface compatibility with declared SDK consumers
without duplicating PR19's adapter/account/tracing qualification. No whole-product Python-free claim,
duplicate execution owner or second authoritative state store is introduced.


## Receiving and implementation admission

Affected owners and independent architecture/security reviewers accept each
implementation boundary and its removed code, preserved obligations and unqualified
targets. This document is a source-based plan, not that production cutover approval.
Matched benchmarks must include packaging/update/bridge maintenance and actual
platform behavior before claiming speed or reliability improvements.

The [independent delivery task (PR17)](https://github.com/applicate2628/Orchestrarium/pull/17) owns PowerShell/bootstrap and npm distribution; this task consumes
only the existing installer's minimal retained payload contract. Historical SDK design is
in [PR18](https://github.com/applicate2628/Orchestrarium/pull/18). Current SDK implementation,
qualification and remaining work are tracked in [PR19](https://github.com/applicate2628/Orchestrarium/pull/19)
and its [SDK execution document](https://github.com/applicate2628/Orchestrarium/blob/c444277e0faa4f3875adc7c11252f29064ecf092/docs/sdk-execution.md). Neither activates
an unavailable route or grants native/provider launch authority.

## Terms and Abbreviations

- CSV: comma-separated table; the inventory is a frozen design snapshot.
- RAII: resource acquisition is initialization; object lifetime owns cleanup, not crash recovery.
- Rust / Cargo: native programming language / its build and package tool.
- CLI / argv: command-line interface / exact argument vector.
- PowerShell bootstrap: download/verification/launch channel, not managed-state logic.
- npm: compatible optional distribution channel for the same native release.
- JSON / UTF-8: structured interchange data / Unicode byte encoding.
- SDK / ACP: software development kit / Agent Client Protocol.
- TDD: test-driven development; reproduce or specify a failing case before the fix.
- Fail-open: failure of this advisory hook does not block the primary operation.
- MPI / HPX: Message Passing Interface / High Performance ParalleX; outside this plan.
- MCP: Model Context Protocol; the reminder names no particular server.
- POSIX / Windows Job Object: Unix-like interface family / Windows process container.
- Native trust: existing host review/qualification, not a descriptor self-assertion.
