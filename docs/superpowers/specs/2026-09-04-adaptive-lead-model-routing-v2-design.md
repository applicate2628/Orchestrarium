# Adaptive routing: remaining comparison and continuation design

Status: proposed focused routing design; no runtime rollout or measured improvement.

The [Orchestrarium 2.0 product plan](../../orchestrarium-2.0-plan.md) owns complete
product scope, statuses, delivery dependencies, empirical evaluation and open
decisions. This document owns only the proposed routing comparison contract and
the safety boundary of deferred continuation. The product plan's general-mechanism
principle applies: task plans may adapt inside governed responsibility boundaries;
this comparison does not introduce a scenario engine or change existing controls.

## Purpose

The proposed remaining goal is better task-specific choice among already admitted exact model/effort profiles,
including useful complementary workers, using attributable evidence and total
cost/time to an accepted result. This document describes only remaining design
work. Existing admission, orchestration, execution, receiving and review remain
authoritative; their implementation is not part of this proposal.

## Change-Surface Contract

- Intended change surface: the product plan, this focused spec, their documentation-index links and release note.
- Approved extension seam: describe an advisory comparison between existing option discovery and existing dispatch resolution.
- Protected surfaces: current policy, resolver, installed roles, adapters, scheduler, run ledger, review state, receiving, installer and publication gates; all existing runtime tests.
- Declared blast radius: documentation only; no runtime, public API or persisted-state change.

The architect owns this boundary. The knowledge archivist owns documentation;
Lead owns admission of later implementation. A downstream implementer must not
expand this surface to create a new routing system.

## Current owning seam

The [ordinary resolver](../../../scripts/resolve-agents-mode.py) exposes:

- describe_ordinary_native_role_options(role, task_class, host_observation, repo_root=...)
- resolve_ordinary_native_dispatch(description, requested_model=..., requested_effort=..., caller_rationale=..., approved_execution_scope=..., user_approved_max=False)

Discovery intersects current task and role profile membership and applies host
observations. Each options entry carries profile, modelTier, exact model, effort,
useCriteria and hostCapability. The surrounding description retains taskClass,
role, profession, defaultInvocation, explicitInvocation, hostObservation,
failurePolicy and fallback. Effort is model-local; modelTier is not an admission
shortcut. Available options may still have controls-unavailable or capability-unknown.

The proposed comparison consumes this admitted description, accepted task criteria
and applicable evidence. It returns a recommendation to Lead, not an invocation.
Lead supplies the chosen exact model/effort pair, rationale and unchanged approved
scope to the existing resolver. Omission/default behavior is unchanged. Resolution,
host invocation and trusted receiving retain their existing checks and owners.
This caller contract does not itself force every native host invocation through
resolution. Distinguish resolver checks, actual host enforcement, independent
receiving verification and residual Lead judgment. Prompt compliance or an advisory
helper is not a machine guarantee for direct calls outside its boundary; examine
supported alternate entrypoints before claiming enforcement. Reuse actual owners,
not a new global gate or a longer instruction checklist.
Native discovery does not establish external-provider admission; any later external
comparison must trace that provider's actual existing admission path first.

[Shared governance](../../../shared/AGENTS.shared.md),
[current role policy](../../../shared/role-routing-policy.v1.json),
[Lead](../../../src.codex/skills/lead/SKILL.md) and the
[Codex caller contract](../../../src.codex/AGENTS.codex.md) remain authoritative.
No comparison can grant permission, broaden scope, supply a fallback or accept work.

## Remaining comparison behavior

A machine-readable comparator is conditional, not an accepted implementation task.
First admit a concrete caller/use case and its evidence contract; if existing
Lead judgment suffices, do not add another mechanism. The requirements below
bound that possible extension rather than establishing that it is needed now.

Use an explicit input snapshot and a side-effect-free comparison. Do not discover
providers, launch workers, retry, persist state or create a mutable model registry.
Compare only exact admitted candidates; resolve required capabilities, quality, useful scope coverage and independent
challenge before trading cost or latency. Preserve reasons for rejection and uncertainty.

Evidence must identify the relevant model, effort, task/context, source and
observation time/applicability. Missing, stale or conflicting evidence remains
visible. It is neither zero cost nor proof of inferiority/superiority. Unknown host
capability stays unknown until the existing host path establishes it.

When evidence cannot support a preference, return incomparable alternatives or an
explicit insufficient-evidence result to Lead. Do not force a total ranking or
fabricate a scalar quality score. Lead may still make an explained choice under
existing admission rules; insufficient comparison evidence is not itself execution
unavailability. Deterministic presentation ordering must not be
presented as evidence that a candidate is better. Exact result fields and tie
handling remain to be defined against an admitted consumer before implementation.

Compare the whole route to an accepted, verified outcome: repeated context,
failed attempts, retries, correction, required review and integration count once.
Keep cost units explicit; incompatible units remain incomparable without an
accepted conversion policy. Public pricing/capability documentation is a prior,
not proof of runtime availability, entitlement or measured task performance.
No performance, cost saving or universal profile ranking is established here.

Keep cumulative approved task budgets and causal request/run/attempt lineage across
retries, replanning and model/effort changes; changing a profile never resets the
budget. Existing execution/receiving owners distinguish ordinary unavailability,
authorization failure, contract/safety failure, quality failure and exhausted
budget. Comparison records those facts, not a new retry or fallback policy.
Data eligibility, redaction and destination restrictions apply at the actual
external transmission boundary through current policy/prompt/adapter owners.
A candidate's score cannot authorize sending data or bypass host denial. Do not
invent a universal budget engine, arbitrary ceilings or blanket human escalation.

## Complementary assignments

Retain useful coverage of the admitted task and independent challenge as functional
goals, not permission expansion or a mandatory roster of new role types. Each proposed assignment needs its existing
profession, bounded scope, artifact and applicable gate. Value comes from useful
coverage or distinct methods/failure discovery, not number of models or majority
agreement. Required review independence remains under current governance.

Where useful, independent blind proposals can reduce anchoring; named-artifact
cross-critique can expose missed assumptions; Lead synthesis separates facts,
deductions, observations and hypotheses. Empirical arbitration uses appropriate
tests, proofs, counterexamples or measurements. These are optional uses of existing
assignments and independent review, not a mandatory debate graph or added stages.

Lead's current ready-lane and capacity rules decide whether an additional assignment
is useful and admissible. A one-worker comparison is an initial slice, not removal
of the multi-worker goal. No second scheduler or portfolio graph executor is needed
merely to describe alternatives. Contradictions are reported to existing review
owners; host mode does not introduce a stronger blanket human-escalation policy.

## Deferred host continuation

Cross-host continuation remains a separate future direction. Before it is admitted,
identify the concrete persistence/host boundary and its single writer/ownership
contract. Restore the admitted task context, accepted artifacts, plan, open findings,
outstanding dispatches and their evidence. First reuse the existing manual repository
transfer and Lead recovery contracts for explicit stop, verified handoff and resume;
the missing work is their orchestration-aware connection, not a new freeze/restore
mechanism. Require one active owner and prevent the previous owner from
committing after transfer through the chosen mode's verified stop or exclusion.
If live/concurrent takeover is admitted, prove atomic ownership change, commit-time
fencing of stale writers and crash recovery. Existing local locks or an append-only
ledger alone do not prove transfer safety.

Preserve causal request/run/attempt identity, cancellation and terminal settlement,
and rejection of stale results at their actual execution/receiving boundaries.
Worker assertions must not replace trusted receiving evidence. Wire validation
belongs at demonstrated trust boundaries; any resource bound needs its owning
rationale, units and safe overflow without lost acquired evidence.

Lead owns admission of this later scope; architect owns its boundary design.
Resolve the missing producer/consumer and persistence contracts, then test the
chosen mode's interruptions, recovery and delayed commits; reject unsupported
concurrent takeover without changing ownership. No lease
schema, transfer protocol, generic effort-intent vocabulary or new ledger is a
prerequisite for the comparison work above.

## Readiness and falsifying probes

The next bounded task is acceptance of the concrete use case, caller and evidence
contract, not comparator implementation. Then walk a real discovery result through the proposed consumer
and into the actual selector. Identify each evidence input's producer and each
output's consumer; define rejection, insufficient evidence and incomparable cases.
A responsibility map or an example invented here is not a runtime trace.

The minimum later behavioral probes are:
- No recommendation adds a profile or bypasses current controls/permissions.
- Missing/conflicting evidence and incompatible cost units remain explicit.
- All-attempt economics includes required review and never double-counts.
- Complementary coverage is distinguished from a correlated duplicate.
- If a deterministic comparator is adopted, identical admitted snapshots produce
  identical recommendations; this is not a constraint on Lead deliberation.
- Comparison cannot launch, settle or accept work.
- Skipped instructions/steps, stale state and alternate entrypoints do not bypass
  any claimed machine-enforced property within its declared effect boundary.
  Unknown outcomes are reconciled before retry; uncontrolled paths and remaining
  semantic judgment are explicit rather than hidden behind a helper.

No tests for a speculative schema or required prose phrases are introduced.
Existing runtime tests remain untouched. Add behavioral tests at the actual
implementation owner only when its contract and implementation are admitted.

## Claims

1. { guarantee: no runtime or persisted-state change; single-owner: Change-Surface Contract; enforcement-probe: the change contains only the product plan, focused spec, index and release note. }
2. { guarantee: no second admission authority; single-owner: existing resolver and policy; enforcement-probe: the producer-to-selector walk preserves exact tuple membership, host controls and approved scope. }
3. { guarantee: no invented evidence advantage; single-owner: proposed comparison; enforcement-probe: unknown/conflicting/incompatible inputs cannot yield an unsupported preference. }
4. { guarantee: complementarity and future continuation are retained without being claimed implemented; single-owner: this spec; enforcement-probe: review the respective goals, admission owners and unresolved boundary tests above. }

Diff-invisible invariants: documentation discoverability and no competing live
routing authority. Named regression guards: resolve retained links; inspect the
diff for protected-path changes; inspect remaining references for obsolete guides.
No external contract or persisted-state migration is introduced.

Gate: proposed documentation only. Runtime readiness requires the concrete input/
output walk and independent review; this text does not authorize execution.

## Terms and Abbreviations

- Exact profile: the policy-admitted model and its model-local effort setting.
- Lead: the existing orchestration owner that admits and integrates work.
- Host: the runtime providing execution capabilities and actual observations.
- Fencing: preventing an obsolete owner from committing after ownership changes.
- Incomparable: available evidence does not justify preferring either alternative.
- API: application programming interface.
- Empirical arbitration: resolving checkable disagreement through observed evidence.
