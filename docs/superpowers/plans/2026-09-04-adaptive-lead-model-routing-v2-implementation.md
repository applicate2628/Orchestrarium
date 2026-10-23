# Adaptive Lead and Model Routing V2 — Current-main Integration Plan

Historical audit baseline: main 68ad6e733e049ad3f86b37af59ea806e8d1a5b25 (2026-10-21).
Integration base: main cc570f2df858b7ab34a7922becc10fbc53f32b76; scope reconciled 2026-10-23.
Status: proposed replacement plan; no execution, independent review, or runtime acceptance claimed.

## Goal and boundary

Extend current Orchestrarium with evidence-based comparison of admitted model/effort
profiles and complementary worker portfolios. Preserve correctness, scope coverage,
independent challenge, objective review and accepted-result economics.

Current main already implements much of the original V2 foundation. Do not import
the historical #6/#7 selectors or rebuild the Lead, provider launchers, review loop,
run ledger or work-item lifecycle. Use [current-main ownership](../../model-routing-v2/current-main-delta.md)
and the [design](../specs/2026-09-04-adaptive-lead-model-routing-v2-design.md).
A one-worker case is a first test case, not a replacement for multi-model goals.

## 1. Contract reconciliation in this proposal

- [x] Assign every retained definition and its inherited field responsibilities
  in [contract scope](../../model-routing-v2/contract-scope.md).
- [x] Separate initial in-memory comparison from deferred host-transfer records.
  Keep all original validation keywords and examples; do not silently weaken a
  required lease. No additional wire schema is created before an actual consumer.
- [x] Align the design, applicability notes and documentation tests. These are
  authored changes, not executed test evidence or independent acceptance.
- [x] Record per-PR disposition and complete changed-path inventory in
  [legacy disposition](../../model-routing-v2/legacy-pr-disposition.md).
- [ ] Execute focused tests and review the actual producer/consumer bindings
  before implementing runtime comparison. Unmapped runtime fields block that slice.
- [ ] Resolve independent optional-overlay and platform residuals; do not close
  their PRs based on this design consolidation.

## 2. Reuse admission; add bounded comparison input

Owners: scripts/resolve-agents-mode.py and shared/role-routing-policy.v1.json,
plus the existing external taxonomy and adapter boundary.

- [ ] Consume the existing profession/task/profile and host eligibility result.
  Do not duplicate native model floors in a second dictionary.
- [ ] Bind an immutable policy revision and explicitly supplied evidence snapshot.
  No automatic probing, new registry service, database or polling loop.
- [ ] Keep model identity, model-local effort, service tier and orchestration mode
  separate. Retain the current general Luna and exact mechanical corridors.
- [ ] Record capability support separately from actual adapter admission.
- [ ] Accept missing measurements as unknown. Do not fabricate acceptance rates,
  cost, latency, independence or inherited production admission.
- [ ] Test unknown identity, unsupported effort, stale evidence, forbidden provider,
  empty eligibility, policy revision mismatch and incompatible accounting units.

## 3. Add only the missing pure comparison function

Owner: existing routing-policy surface; exact placement follows the dependency review.

- [ ] Input: bounded admitted candidates, role/slot requirements, policy/evidence
  references, constraints and explicit resource ceilings.
- [ ] Output: deterministic ordered recommendation, rejection reasons and evidence
  references. The function performs no I/O, launches, retries or state mutation.
- [ ] Preserve ordering: admission, quality, coverage, independent challenge,
  evidence, accepted-result economics, latency, stable identifier.
- [ ] Do not turn heterogeneous qualitative evidence into an invented scalar score.
  If a required comparison is unsupported, return the explicit evidence gap.
- [ ] Model-specific wire settings stay in provider adapters. Adding an observed
  model/profile normally changes data, not provider-neutral control flow.
- [ ] Preserve multi-slot coverage and independence constraints in bounded
  assignments. Do not add a universal DAG executor or automatic optimizer.
- [ ] Test determinism, input immutability, ties, missing required slots, correlated
  reviewers, contradictory evidence and cost that cannot compensate for quality.

## 4. Integrate through existing execution and review owners

Owners: existing Lead/ready-lane contract, scripts/provider_prompt.py,
scripts/review_loop_state.py, scripts/agent-run-ledger.py and scripts/mutate-work-item.py.

- [ ] The Lead accepts or rejects a recommendation under current authority.
  Selection is never permission to launch.
- [ ] Preserve ready-input boundaries, bounded leaf roles and nonauthorizing results.
- [ ] Revalidate actual admission before launch; changed policy invalidates stale
  recommendations instead of silently rerouting.
- [ ] Reuse existing attempt/run identities, result receiving, review retries and
  finding dispositions. Add only demonstrated missing provenance references.
- [ ] Preserve blind proposals where required, named artifact critique, scope
  expansion, objective arbitration and review of persisted final synthesis.
- [ ] Extend existing tests for replay, cancellation, stale result identity,
  mismatch, exhausted budget and changed scope. Do not create a second retry engine.

## 5. Modernize model evidence and adapter compatibility

- [ ] Preserve current main's Sol 6.1 routing instead of reapplying the closed
  historical model proposal.
- [ ] Date and source observations for current Claude, Kimi, Grok and GLM models.
  Public documentation is a prior, not proof of installed CLI support.
- [ ] Review each changed provider protocol at its existing adapter. Unsupported
  capabilities remain unavailable until their own conformance checks pass.
- [ ] Keep API token prices, subscription/quota accounting and accepted-task cost
  distinct. Never infer task savings from the price ratio alone.
- [ ] Use existing evaluation receipts if available. Any new paid evaluation,
  provider run, external review or quota-consuming check is user-operated.

## 6. Resolve independent legacy changes separately

- [ ] #5: retain genuinely missing optional overlay behavior only after checking
  existing composition; no new plugin engine or mandatory Ponytail dependency.
- [ ] #6/#7: retain useful evidence and regression cases; avoid parallel Astra and
  generic-worker policy authorities. Keep a thin compatibility facade only if a
  verified consumer requires it.
- [ ] #9: rebase each surviving platform correction against its current owner,
  including removal permissions, implicit interpreter resolution and Windows
  descriptor normalization. Preserve existing filesystem identity safeguards.
- [ ] Do not mix installer repairs into a claim that V2 routing is implemented.

## 7. Deferred extensions, with retained requirements

Transferable Lead leases, cross-host failover and stale-epoch fencing remain an
explicit future feature. Existing local locks do not prove these guarantees.
Activate the retained lease contracts only with actual cross-host requirements
and their own concurrency, crash, recovery and adapter tests.

Automatic evidence ingestion, self-learning selection, provider discovery and a
second portfolio scheduler are not prerequisites. Evaluate them only when a
specific missing capability cannot be served by current owners and bounded data.

This deferral does not remove multi-model comparison, scope expansion, challenge,
review or future host neutrality from the product goals.

## 8. Acceptance and publication

- [ ] Review the exact final graph and all changed contract consumers.
- [ ] Run relevant repository validators and focused compatibility tests.
- [ ] Obtain independent review required by repository policy.
- [ ] Verify no duplicate authoritative configuration, mutable store or execution
  loop was introduced; each new mechanism has a concrete missing capability.
- [ ] Confirm documentation describes actual implementation status.
- [ ] Publish only under applicable approval and repository gates. Unrun checks
  remain explicitly unrun; static inspection is not a substitute.
- [ ] Release/default changes remain separately authorized.

Historical checkmarks and test totals from older branches do not satisfy these
current-baseline gates.

## Terms

Admission: current permission to perform a class of work. Snapshot: immutable
policy/evidence revision. Portfolio: complementary bounded role assignments.
Receiving: verification and acceptance of a result. Lead: accountable work owner.
