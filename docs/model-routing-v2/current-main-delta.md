# Version 2 as a delta over current Orchestrarium

Historical audit baseline: main 68ad6e733e049ad3f86b37af59ea806e8d1a5b25 (2026-10-21).
Integration base: main cc570f2df858b7ab34a7922becc10fbc53f32b76; scope reconciled 2026-10-23.
Status: design revision, not a runtime implementation or acceptance claim.

## Proposed consolidation boundary

Version 2 extends current owners; it does not reinstall the September prototype
stack as a parallel orchestrator. This document supersedes old implementation
checklists only where they propose duplicating a capability listed below.
Security, scope, admission, independent review and publication requirements remain.

The former inventory of 68 absent files is historical source accounting, not an
import plan. A missing filename does not mean its responsibility is absent.
The prepared per-model V1 compatibility patch is a possible isolated maintenance
fix, not the architecture of the new V2 router.

## Existing capability and actual owner

| Responsibility | Current owner | V2 disposition |
|---|---|---|
| Native profession/task/profile intersection and host filtering | scripts/resolve-agents-mode.py: resolve_role_dispatch, resolve_ordinary_native_dispatch; shared/role-routing-policy.v1.json | Reuse. Do not introduce another Python model-floor dictionary as the authoritative policy. |
| Native exact mechanical corridor versus supervised general professions | Same resolver and policy; shared/AGENTS.shared.md | Reuse both distinctions. Luna is not globally mechanical-only. |
| Provider-specific execution, prompt delivery and contained settlement | scripts/provider_prompt.py and its existing projections/wrappers | Extend only for a demonstrated protocol capability gap. Do not add a second launcher or cleanup framework. |
| Explicit provider routing, profession mapping and restrictions | resolve_external_dispatch and shared/external-role-taxonomy.v1.json | Reuse. Catalog observation cannot override current unavailable or explicit-only routes. |
| Review rounds, retries, verdicts, frozen artifacts, operation idempotency and local transaction locking | scripts/review_loop_state.py | Reuse existing public owner operations. A V2 review JSON document is not another writable review store. |
| Run identity and provenance | scripts/agent-run-ledger.py and existing receiving contracts | Reference the existing run IDs and evidence. Do not dual-write a parallel execution ledger. |
| Work-item lifecycle and links | scripts/mutate-work-item.py and current lifecycle contracts | Reuse. Model routing cannot mark work complete or bypass receiving. |
| Canonical skill materialization and customization protection | scripts/production_installer.py and docs/new-session-guide.md | Reuse current producer. Historical Claude skill copies do not become a second live owner. |
| Publication safety and human authority | scripts/check-publication-gate.py and existing publication policy | Reuse unchanged; a routing success cannot satisfy this gate. |
| Model-local effort, task economics, independent reviewers and bounded parallelism | Current shared governance and role policy | Reference these rules; remove copied alternate wordings from V2 guides. |

This map establishes existing responsibilities, not blanket proof that every
V2 cross-record guarantee is implemented. In particular, review-loop local locking
is not a verified transferable Lead lease, and an append-only run ledger is not
by itself a multi-host scheduler.

## Current-baseline source anchors

- scripts/resolve-agents-mode.py:1475,1661,1776: ordinary native selection,
  role dispatch and external dispatch remain distinct entrypoints.
- scripts/production_installer.py:5030-5061: existing cleanup owner; the #9
  residual is separate platform work, not replaced by routing documentation.
- scripts/provider_prompt.py:2390-2462: current descriptor generation and
  comparison; publication of a platform repair needs its own exact-head evidence.
- scripts/review_loop_state.py:849: local lock, not proof of transferable leases.
- docs/new-session-guide.md: source map and canonical installer/projection ownership.
- shared/AGENTS.shared.md: current nonauthority, receiving, evidence and publication
  rules remain controlling. This proposal creates no exception to them.

Source responsibility inspection is not an end-to-end qualification of those
owners. Existing APIs may require narrow extensions; no field compatibility is
inferred solely from a similar name.

## Small initial V2 increment

Implement only what the use case requires:

1. One pure candidate-comparison function consumes an explicit bounded snapshot
   and the existing admitted role/task request. It performs no I/O, provider
   discovery, process launch, retry, persistence, installation or publication.
2. Model/profile facts and dated evidence are data. No model-name-specific
   control-flow branches in the provider-neutral core. Model-specific wire
   parameters remain with their provider adapter.
3. Current policy determines eligibility. The comparison function may narrow or
   recommend among eligible candidates; it must not create a second policy
   authority or silently expand supported profiles.
4. The result is an ordered proposal with reasons and explicit unknown evidence.
   The existing Lead decides whether to use it. Existing adapters and ledgers
   perform execution and receiving under their current contracts.
5. Keep multi-model comparison, scope expansion and independent challenge as
   functional goals. Represent a portfolio as bounded role assignments consumed
   by the existing Lead/ready-lane execution loop; do not introduce a universal
   portfolio DAG or a second review state machine unless a concrete missing
   guarantee requires one. A one-worker case is a testable slice, not a reduction
   of the intended multi-worker capability.
6. Lack of usable evidence is an explicit unknown/denied recommendation, not an
   automatic fallback, retry storm, or synthesized quality score.

Keep the provider-neutral profile/evidence representation, but use it as input
data, not justification for adding a registry service, polling daemon or mutable
database. Effort support, service tier, thinking/tool protocol and billing basis
must be attributable to existing snapshot references. Public documentation is
a prior, not observed runtime admission.

## Remove or demote from the initial implementation plan

- Dedicated Astra scheduler: its useful task-specific evidence belongs in the
  shared profile comparison. Keep any retained V1 entrypoint only as a thin,
  explicitly deprecated compatibility adapter if an actual consumer requires it.
- A second general-worker selector with copied model floors: use the current
  native/external policy owners. Do not import #6 and #7 as two competing runtime
  decision layers merely because their tests exist.
- Automatic Lead transfer, lease election and distributed recovery: deferred
  until real cross-host continuation is admitted. Do not fake it with a local lock.
- A second automatic portfolio executor, graph scheduler, online self-learning
  and retrospective evidence-ingestion service: not justified merely by the V2
  label. Reuse existing bounded parallel execution and result receiving; identify
  any missing functionality before proposing additional machinery.
- Automatic model discovery or entitlement probing: no background provider calls.
  Accept explicit observations through the existing authorized acquisition route.
- New plugin engines or a second general configuration loader for policy overlays:
  decide whether the existing instruction composition already supplies the need.
  Ponytail remains external and optional; it is not a V2 prerequisite.
- Extra schema/state/envelope layers that duplicate an existing authoritative
  record: use a reference or a narrow versioned extension instead of dual truth.

The [contract scope map](contract-scope.md) assigns retained definitions and field
responsibilities. Their exact wire bindings remain deferred design, not existing
runtime APIs. They are not a demand to implement every envelope now.
Do not delete an invariant just because its original script is being removed.

## Complexity acceptance criteria

Each proposed script or state field must identify:
- a user-visible capability not already owned in main;
- one owner and its public input/output contract;
- why data or an existing function is insufficient;
- one objective failure case and its regression test;
- compatibility and removal/migration consequences.

Prefer fewer state transitions, configuration sources, fallbacks and mutable
stores, not simply fewer files or shorter code. The CLI boundary and pure decision
core may stay separate. Do not merge unlike Windows/POSIX file-identity checks
into a vague helper or relax them to shrink a diff.

Regression focus: unknown model/profile, unsupported effort, missing evidence,
stale snapshot, forbidden provider, no eligible candidate, budget exhaustion,
replay, cancellation, changed policy, and adapter result mismatch. Each has one
typed outcome and no implicit retry. Existing negative tests remain until their
underlying guarantee has an explicit surviving owner.

## New model policy

Current main Sol 6.1 and supervised Luna policies are inputs, not work to redo.
New Claude, Kimi, Grok and GLM releases add observed data and adapter conformance
requirements; they do not automatically change production admission.

Keep four axes separate:
- model identity;
- model-local reasoning effort;
- service/speed tier;
- orchestration mode.

For example, OpenAI Ultrafast is a service tier, while provider-native multi-agent
execution is an orchestration capability. Neither is another universal effort
level. Subscription quotas and API prices are separate accounting bases.
No mandatory weakest-first escalation: choose the fitting admitted profile
directly and preserve objective review.

## Integration disposition

Use current main as the base. Review #5–#9 by responsibility, not file count.
Transfer only missing useful behavior, modernized tests and retained evidence.
Do not close old PRs until each meaningful change is retained, deliberately
superseded, or assigned a bounded independent follow-up. #9's platform corrections
need their own current-owner review; do not bury them in routing architecture.

The current task's completion boundary is a cleaned, main-aligned V2 proposal
with every required capability mapped to an existing owner or an explicit minimal
extension. A pure comparison increment is a proposed implementation slice, not
an assertion that it alone completes V2. Distributed scheduling, automatic host
transfer and production model admission remain separate decisions; no functional
goal is silently cancelled to achieve a smaller script count.

## Terms and Abbreviations

V2: the proposed second-version extension. Lead: accountable orchestration owner.
CLI: command-line interface. DAG: directed acyclic dependency graph.
Snapshot: immutable input/evidence revision. Admission: actual policy/capability
permission before execution. Receiving: verification and acceptance of a result.
