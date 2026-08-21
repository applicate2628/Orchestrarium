# Architecture Pattern Applicability

This reference is the normative semantic owner for AP0-AP5. It is an applicability contract, not a pattern encyclopedia: observed problem evidence controls which candidates are considered, explicit contraindications control rejection, and zero selected patterns is valid. Existing template admission and the smallest-durable-design rule remain unchanged.

The role projections below are deliberately narrow. Lead recognises routing evidence only; Architect owns `selected | rejected | deferred` disposition; Architecture Reviewer independently verifies the recorded decision. Backend, Data, and Reliability roles own consequences after an accepted design and do not select patterns.

<!-- APAT-BLOCK:LEAD-ROUTING:BEGIN -->
## Architecture-pattern routing recognition (APAT)

Inside already-admitted non-trivial work, route to `$architect` before Plan or Implement when accepted evidence shows at least one of these problem shapes. Lead recognises the shape and does not select a pattern:

- conflicting business meanings, invariants, owners, or change cadence across a proposed semantic boundary;
- a long-lived or branch-heavy lifecycle with legal and illegal transitions, retry, timeout, cancellation, restart, manual intervention, or audit requirements;
- materially asymmetric command/query models, scaling, authorization, or consistency needs;
- one local database mutation plus message publication that cannot currently be one atomic operation;
- one business transaction crossing autonomous services or data owners.

This route does not change template admission and is not a universal Architect prelude. Simple Create, Read, Update, Delete (CRUD), a coherent small domain, local linear control flow, one local transaction, and a flow with no dual write do not force Architect. An irreversible cross-owner invariant still routes Architect so saga can be rejected or deferred rather than assumed.

<a id="apat-en-apat-p01-semantic-boundary-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-P01-SEMANTIC-BOUNDARY.outcome" value="route-architect:consider-AP1:no-deployment-inference" -->
- `APAT-P01-SEMANTIC-BOUNDARY` -> `route-architect:consider-AP1:no-deployment-inference`.

<a id="apat-en-apat-p02-long-lived-lifecycle-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-P02-LONG-LIVED-LIFECYCLE.outcome" value="route-architect:consider-AP2:require-transition-evidence" -->
- `APAT-P02-LONG-LIVED-LIFECYCLE` -> `route-architect:consider-AP2:require-transition-evidence`.

<a id="apat-en-apat-p03-read-write-asymmetry-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-P03-READ-WRITE-ASYMMETRY.outcome" value="route-architect:consider-AP3:no-event-sourcing-inference" -->
- `APAT-P03-READ-WRITE-ASYMMETRY` -> `route-architect:consider-AP3:no-event-sourcing-inference`.

<a id="apat-en-apat-p04-dual-write-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-P04-DUAL-WRITE.outcome" value="route-architect:consider-AP4:require-relay-evidence" -->
- `APAT-P04-DUAL-WRITE` -> `route-architect:consider-AP4:require-relay-evidence`.

<a id="apat-en-apat-p05-cross-owner-transaction-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-P05-CROSS-OWNER-TRANSACTION.outcome" value="route-architect:consider-AP5:require-compensation-evidence" -->
- `APAT-P05-CROSS-OWNER-TRANSACTION` -> `route-architect:consider-AP5:require-compensation-evidence`.

<a id="apat-en-apat-n01-coherent-domain-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-N01-COHERENT-DOMAIN.outcome" value="no-force-architect:reject-AP1" -->
- `APAT-N01-COHERENT-DOMAIN` -> `no-force-architect:reject-AP1` when alternatives are otherwise requested.

<a id="apat-en-apat-n02-linear-flow-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-N02-LINEAR-FLOW.outcome" value="no-force-architect:reject-AP2" -->
- `APAT-N02-LINEAR-FLOW` -> `no-force-architect:reject-AP2` when alternatives are otherwise requested.

<a id="apat-en-apat-n03-simple-crud-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-N03-SIMPLE-CRUD.outcome" value="no-force-architect:reject-AP3" -->
- `APAT-N03-SIMPLE-CRUD` -> `no-force-architect:reject-AP3` when alternatives are otherwise requested.

<a id="apat-en-apat-n04-no-dual-write-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-N04-NO-DUAL-WRITE.outcome" value="no-force-architect:reject-AP4" -->
- `APAT-N04-NO-DUAL-WRITE` -> `no-force-architect:reject-AP4` when alternatives are otherwise requested.

<a id="apat-en-apat-n05-local-atomic-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-N05-LOCAL-ATOMIC.outcome" value="no-force-architect:reject-AP5" -->
- `APAT-N05-LOCAL-ATOMIC` -> `no-force-architect:reject-AP5` when alternatives are otherwise requested.

<a id="apat-en-apat-n06-irreversible-invariant-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-N06-IRREVERSIBLE-INVARIANT.outcome" value="route-architect:reject-or-defer-AP5" -->
- `APAT-N06-IRREVERSIBLE-INVARIANT` -> `route-architect:reject-or-defer-AP5` and require a changed boundary, requirement, or actually supported transaction mechanism.
<!-- APAT-BLOCK:LEAD-ROUTING:END -->

<!-- APAT-BLOCK:ARCHITECT-DISPOSITION:BEGIN -->
## Architecture-pattern disposition (APAT)

Architect owns applicability decisions and retains the smallest-durable-design rule. Consider only candidates with accepted trigger evidence. Record every evidence-triggered candidate in a Pattern Disposition Record; zero selected patterns is valid. Pattern names, popularity, and model familiarity are not evidence.

### AP0 - evidence-first Pattern Disposition Record

<a id="apat-en-ap0-candidate"></a>
<!-- APAT-SEMANTIC id="AP0.candidate" value="evidence-triggered-candidate" -->
- `candidate`: the evidence-triggered AP1-AP5 candidate.

<a id="apat-en-ap0-trigger-evidence"></a>
<!-- APAT-SEMANTIC id="AP0.trigger-evidence" value="accepted-positive-evidence" -->
- `trigger evidence`: accepted positive problem evidence.

<a id="apat-en-ap0-contraindication-evidence"></a>
<!-- APAT-SEMANTIC id="AP0.contraindication-evidence" value="accepted-negative-evidence" -->
- `contraindication evidence`: accepted evidence against applicability.

<a id="apat-en-ap0-tradeoffs-cost"></a>
<!-- APAT-SEMANTIC id="AP0.tradeoffs-cost" value="operational-cost-and-tradeoffs" -->
- `tradeoffs/cost`: introduced operational, consistency, migration, and cognitive cost.

<a id="apat-en-ap0-composition-interactions"></a>
<!-- APAT-SEMANTIC id="AP0.composition-interactions" value="distinct-concern-and-boundaries" -->
- `composition interactions`: the distinct concern and the state, failure, message, and consistency boundaries shared with other candidates.

<a id="apat-en-ap0-disposition"></a>
<!-- APAT-SEMANTIC id="AP0.disposition" value="selected-or-rejected-or-deferred" -->
- `disposition`: exactly `selected`, `rejected`, or `deferred`.

<a id="apat-en-ap0-open-evidence-questions"></a>
<!-- APAT-SEMANTIC id="AP0.open-evidence-questions" value="missing-evidence-and-resolving-probe" -->
- `open evidence questions`: missing evidence and the concrete probe that resolves it; `deferred` is invalid without both.

### AP1 - Domain-Driven Design and bounded context

<a id="apat-en-ap1-trigger"></a>
<!-- APAT-SEMANTIC id="AP1.trigger" value="semantic-boundary-conflict" -->
- Trigger: the same domain words, invariants, ownership, or change cadence have materially different meanings and translation is needed at a boundary.

<a id="apat-en-ap1-contraindication"></a>
<!-- APAT-SEMANTIC id="AP1.contraindication" value="small-coherent-domain-no-artificial-split" -->
- Contraindication: the domain is small and coherent, or the proposed boundary only mirrors teams or tables or assumes a microservice split.

<a id="apat-en-ap1-tradeoff"></a>
<!-- APAT-SEMANTIC id="AP1.tradeoff" value="boundary-governance-and-translation-cost" -->
- Tradeoff: boundary governance and translation increase coordination and maintenance cost.

<a id="apat-en-ap1-question"></a>
<!-- APAT-SEMANTIC id="AP1.question" value="meanings-invariants-owners-crossings-modular-monolith" -->
- Questions: which meanings and invariants differ, who owns each model, what crosses the boundary, and can a modular monolith preserve it?

<a id="apat-en-ap1-composition"></a>
<!-- APAT-SEMANTIC id="AP1.composition" value="bounded-context-not-deployment" -->
- Composition rule: `bounded-context-not-deployment`; a semantic boundary is not a deployment mandate.

### AP2 - explicit state machine or workflow

<a id="apat-en-ap2-trigger"></a>
<!-- APAT-SEMANTIC id="AP2.trigger" value="long-lived-branch-heavy-restartable-auditable-lifecycle" -->
- Trigger: a process is long-lived, branch-heavy, restartable, auditable, or has legal and illegal transitions plus timeout, cancellation, or manual paths.

<a id="apat-en-ap2-contraindication"></a>
<!-- APAT-SEMANTIC id="AP2.contraindication" value="short-local-linear-flow" -->
- Contraindication: the flow is short, local, linear, and ordinary typed control flow makes invalid states sufficiently visible.

<a id="apat-en-ap2-tradeoff"></a>
<!-- APAT-SEMANTIC id="AP2.tradeoff" value="persisted-state-replay-and-operational-cost" -->
- Tradeoff: persisted workflow state, replay, versioning, and operations add cost.

<a id="apat-en-ap2-question"></a>
<!-- APAT-SEMANTIC id="AP2.question" value="states-transitions-owner-persistence-cancel-timeout-settlement" -->
- Questions: enumerate states, transitions, forbidden transitions, writer-owner, persistence/replay, cancellation, timeout, and terminal settlement.

<a id="apat-en-ap2-composition"></a>
<!-- APAT-SEMANTIC id="AP2.composition" value="workflow-not-saga" -->
- Composition rule: `workflow-not-saga`; a workflow may coordinate a saga but is not the same pattern.

### AP3 - Command Query Responsibility Segregation (CQRS)

<a id="apat-en-ap3-trigger"></a>
<!-- APAT-SEMANTIC id="AP3.trigger" value="materially-asymmetric-command-query" -->
- Trigger: command and query models, load, authorization, or consistency needs are materially asymmetric.

<a id="apat-en-ap3-contraindication"></a>
<!-- APAT-SEMANTIC id="AP3.contraindication" value="simple-crud-one-adequate-model" -->
- Contraindication: ordinary CRUD has one adequate model, or eventual consistency and projection operations cost more than the measured asymmetry justifies.

<a id="apat-en-ap3-tradeoff"></a>
<!-- APAT-SEMANTIC id="AP3.tradeoff" value="eventual-consistency-projection-and-rebuild-cost" -->
- Tradeoff: eventual consistency, projection operations, rebuild, and reconciliation add cost.

<a id="apat-en-ap3-question"></a>
<!-- APAT-SEMANTIC id="AP3.question" value="asymmetry-staleness-projection-owner-rebuild-reconciliation" -->
- Questions: what asymmetry is observed, what staleness is tolerable, and who owns projection rebuild and reconciliation?

<a id="apat-en-ap3-composition"></a>
<!-- APAT-SEMANTIC id="AP3.composition" value="cqrs-not-event-sourcing" -->
- Composition rule: `cqrs-not-event-sourcing`; CQRS does not imply event sourcing.

### AP4 - transactional outbox

<a id="apat-en-ap4-trigger"></a>
<!-- APAT-SEMANTIC id="AP4.trigger" value="unsafe-database-message-dual-write" -->
- Trigger: a local state change and message publication form an unsafe database-plus-message dual write.

<a id="apat-en-ap4-contraindication"></a>
<!-- APAT-SEMANTIC id="AP4.contraindication" value="reject-when-no-dual-write-or-verified-atomic-mechanism" -->
- Contraindication: no dual write exists, or an evidenced atomic mechanism already spans both effects.

<a id="apat-en-ap4-tradeoff"></a>
<!-- APAT-SEMANTIC id="AP4.tradeoff" value="relay-retry-dedup-retention-replay-cost" -->
- Tradeoff: relay ownership, retry, deduplication, retention, replay, and cleanup add cost.

<a id="apat-en-ap4-question"></a>
<!-- APAT-SEMANTIC id="AP4.question" value="local-transaction-relay-idempotency-retention-replay" -->
- Questions: what is the local transaction boundary, and who relays, retries, deduplicates, retains, and replays?

<a id="apat-en-ap4-composition"></a>
<!-- APAT-SEMANTIC id="AP4.composition" value="outbox-not-distributed-atomicity-or-exactly-once" -->
- Composition rule: `outbox-not-distributed-atomicity-or-exactly-once`; outbox improves durable local publication, not cross-service atomicity or exactly-once delivery.

### AP5 - saga or compensation

<a id="apat-en-ap5-trigger"></a>
<!-- APAT-SEMANTIC id="AP5.trigger" value="cross-owner-transaction-no-safe-distributed-transaction" -->
- Trigger: a transaction crosses autonomous data owners, no safe distributed transaction exists, and compensations can preserve the required guarantees.

<a id="apat-en-ap5-contraindication"></a>
<!-- APAT-SEMANTIC id="AP5.contraindication" value="local-atomic-or-noncompensable-immediate-invariant" -->
- Contraindication: one local atomic transaction is available, or an immediate invariant and irreversible step cannot be compensated safely.

<a id="apat-en-ap5-tradeoff"></a>
<!-- APAT-SEMANTIC id="AP5.tradeoff" value="compensation-coordination-manual-repair-cost" -->
- Tradeoff: compensation, coordination, partial progress, and manual repair add cost.

<a id="apat-en-ap5-question"></a>
<!-- APAT-SEMANTIC id="AP5.question" value="local-steps-compensations-retry-timeout-idempotency-settlement" -->
- Questions: who owns each local transaction and compensation, and how are retry, timeout, idempotency, manual repair, and terminal settlement observed?

<a id="apat-en-ap5-composition"></a>
<!-- APAT-SEMANTIC id="AP5.composition" value="saga-not-local-transaction" -->
- Composition rule: `saga-not-local-transaction`; saga may use outbox but does not replace an available local transaction.

When more than one candidate is selected, state why each owns a distinct concern and how their state, failure, message, and consistency boundaries compose without two owners for one invariant.
<!-- APAT-BLOCK:ARCHITECT-DISPOSITION:END -->

<!-- APAT-BLOCK:ARCHITECTURE-REVIEW:BEGIN -->
## Architecture-pattern verification (APAT)

Architecture Reviewer verifies and does not redesign:

- every evidence-triggered candidate has a complete Pattern Disposition Record with `selected | rejected | deferred` and all AP0 fields;
- each selection has accepted positive evidence, and each tempting but unsuitable pattern has explicit negative evidence;
- zero selected patterns remains valid and no pattern name, popularity, or model familiarity is treated as evidence;
- dispositions preserve the smallest-durable-design, one-owner, stable-seam, failure-transparency, migration, and reliability contracts;
- composition does not conflate bounded context with deployment, CQRS with event sourcing, outbox with distributed atomicity or exactly-once delivery, saga with a local transaction, or workflow with saga;
- selection logic exists only in Architect; Lead only routes, while Backend, Data, and Reliability remain downstream consequence owners;
- a cross-cutting selection cites an accepted decision record and implementation consumes the accepted Change-Surface Contract;
- the Russian mirror receives a row-by-row bilingual semantic verdict; identifier, word, byte, or hash equality alone is insufficient.

Static source/install parity does not prove provider or model obedience. Without a separately admitted pinned fresh-context report, runtime fidelity remains `ASSUMPTION (UNVERIFIED)`.
<!-- APAT-BLOCK:ARCHITECTURE-REVIEW:END -->

## Failure meanings

<a id="apat-en-apat-e001-canonical-missing-meaning"></a>
<!-- APAT-SEMANTIC id="APAT-E001-CANONICAL-MISSING.meaning" value="canonical-missing-or-duplicate" -->
- `APAT-E001-CANONICAL-MISSING`: the canonical reference or a canonical projection block is missing or duplicated.

<a id="apat-en-apat-e002-projection-drift-meaning"></a>
<!-- APAT-SEMANTIC id="APAT-E002-PROJECTION-DRIFT.meaning" value="source-projection-differs" -->
- `APAT-E002-PROJECTION-DRIFT`: a source role projection differs from its canonical block or provider peer.

<a id="apat-en-apat-e003-route-miss-meaning"></a>
<!-- APAT-SEMANTIC id="APAT-E003-ROUTE-MISS.meaning" value="positive-route-missed-or-negative-forced" -->
- `APAT-E003-ROUTE-MISS`: a positive scenario misses Architect or a negative/simple scenario forces Architect.

<a id="apat-en-apat-e004-cargo-cult-meaning"></a>
<!-- APAT-SEMANTIC id="APAT-E004-CARGO-CULT.meaning" value="pattern-selected-without-evidence-or-negative-not-rejected" -->
- `APAT-E004-CARGO-CULT`: a pattern is selected without positive evidence or is not rejected in a negative case.

<a id="apat-en-apat-e005-disposition-incomplete-meaning"></a>
<!-- APAT-SEMANTIC id="APAT-E005-DISPOSITION-INCOMPLETE.meaning" value="disposition-required-field-missing" -->
- `APAT-E005-DISPOSITION-INCOMPLETE`: a required disposition, contraindication, cost, composition, or evidence-question field is missing.

<a id="apat-en-apat-e006-installed-missing-meaning"></a>
<!-- APAT-SEMANTIC id="APAT-E006-INSTALLED-MISSING.meaning" value="disposable-install-projection-missing-or-drifted" -->
- `APAT-E006-INSTALLED-MISSING`: a disposable installed projection is missing or differs from provider source.

<a id="apat-en-apat-e007-model-fidelity-meaning"></a>
<!-- APAT-SEMANTIC id="APAT-E007-MODEL-FIDELITY.meaning" value="pinned-model-misapplies-installed-contract" -->
- `APAT-E007-MODEL-FIDELITY`: a pinned fresh-context provider/model run ignores or misapplies the installed contract.

<a id="apat-en-apat-e008-ru-semantic-drift-meaning"></a>
<!-- APAT-SEMANTIC id="APAT-E008-RU-SEMANTIC-DRIFT.meaning" value="russian-semantic-meaning-differs" -->
- `APAT-E008-RU-SEMANTIC-DRIFT`: Russian meaning omits, negates, weakens, strengthens, or otherwise changes a canonical field, rule, scenario outcome, or failure meaning.

## Regression guards

- `APAT-G01-NO-UNIVERSAL-PRELUDE`: negative/simple scenarios do not force Architect and unnecessary ceremony is rejected.
- `APAT-G02-MECHANICS-PRESERVED`: existing architecture-layering mechanics and their 19-role validator remain unchanged.
- `APAT-G03-ROLE-SEPARATION`: Lead routes, Architect disposes, Reviewer verifies; implementation and risk roles do not select.
- `APAT-G04-PROVIDER-PARITY`: each canonical block has one exact Codex and Claude Code projection.
- `APAT-G05-INSTALLED-PARITY`: disposable installed role files equal their provider sources.
- `APAT-G06-NO-RUNTIME-OVERCLAIM`: static fulfillment is not evidence of provider/model obedience.
- `APAT-G07-C6-CLEAN-STATE`: the live change surface retains one current AP0-AP5 truth.
- `APAT-G08-RU-SEMANTIC-PARITY`: every canonical semantic row has one Russian counterpart and independent bilingual review.

<!-- APAT-RUNTIME-FIDELITY: ASSUMPTION (UNVERIFIED) -->

## Russian semantic correspondence

The English anchor is normative. The Russian anchor is a translation target. `pending` is not a semantic PASS; the independent bilingual Architecture Reviewer supplies the Phase F verdict and evidence.

| Canonical field ID | English anchor | Russian anchor | Semantic verdict | Reviewer evidence |
|---|---|---|---|---|
| `AP0.candidate` | [English](#apat-en-ap0-candidate) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap0-candidate) | pending | Phase F bilingual review |
| `AP0.trigger-evidence` | [English](#apat-en-ap0-trigger-evidence) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap0-trigger-evidence) | pending | Phase F bilingual review |
| `AP0.contraindication-evidence` | [English](#apat-en-ap0-contraindication-evidence) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap0-contraindication-evidence) | pending | Phase F bilingual review |
| `AP0.tradeoffs-cost` | [English](#apat-en-ap0-tradeoffs-cost) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap0-tradeoffs-cost) | pending | Phase F bilingual review |
| `AP0.composition-interactions` | [English](#apat-en-ap0-composition-interactions) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap0-composition-interactions) | pending | Phase F bilingual review |
| `AP0.disposition` | [English](#apat-en-ap0-disposition) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap0-disposition) | pending | Phase F bilingual review |
| `AP0.open-evidence-questions` | [English](#apat-en-ap0-open-evidence-questions) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap0-open-evidence-questions) | pending | Phase F bilingual review |
| `AP1.trigger` | [English](#apat-en-ap1-trigger) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap1-trigger) | pending | Phase F bilingual review |
| `AP1.contraindication` | [English](#apat-en-ap1-contraindication) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap1-contraindication) | pending | Phase F bilingual review |
| `AP1.tradeoff` | [English](#apat-en-ap1-tradeoff) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap1-tradeoff) | pending | Phase F bilingual review |
| `AP1.question` | [English](#apat-en-ap1-question) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap1-question) | pending | Phase F bilingual review |
| `AP1.composition` | [English](#apat-en-ap1-composition) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap1-composition) | pending | Phase F bilingual review |
| `AP2.trigger` | [English](#apat-en-ap2-trigger) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap2-trigger) | pending | Phase F bilingual review |
| `AP2.contraindication` | [English](#apat-en-ap2-contraindication) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap2-contraindication) | pending | Phase F bilingual review |
| `AP2.tradeoff` | [English](#apat-en-ap2-tradeoff) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap2-tradeoff) | pending | Phase F bilingual review |
| `AP2.question` | [English](#apat-en-ap2-question) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap2-question) | pending | Phase F bilingual review |
| `AP2.composition` | [English](#apat-en-ap2-composition) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap2-composition) | pending | Phase F bilingual review |
| `AP3.trigger` | [English](#apat-en-ap3-trigger) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap3-trigger) | pending | Phase F bilingual review |
| `AP3.contraindication` | [English](#apat-en-ap3-contraindication) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap3-contraindication) | pending | Phase F bilingual review |
| `AP3.tradeoff` | [English](#apat-en-ap3-tradeoff) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap3-tradeoff) | pending | Phase F bilingual review |
| `AP3.question` | [English](#apat-en-ap3-question) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap3-question) | pending | Phase F bilingual review |
| `AP3.composition` | [English](#apat-en-ap3-composition) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap3-composition) | pending | Phase F bilingual review |
| `AP4.trigger` | [English](#apat-en-ap4-trigger) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap4-trigger) | pending | Phase F bilingual review |
| `AP4.contraindication` | [English](#apat-en-ap4-contraindication) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap4-contraindication) | pending | Phase F bilingual review |
| `AP4.tradeoff` | [English](#apat-en-ap4-tradeoff) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap4-tradeoff) | pending | Phase F bilingual review |
| `AP4.question` | [English](#apat-en-ap4-question) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap4-question) | pending | Phase F bilingual review |
| `AP4.composition` | [English](#apat-en-ap4-composition) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap4-composition) | pending | Phase F bilingual review |
| `AP5.trigger` | [English](#apat-en-ap5-trigger) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap5-trigger) | pending | Phase F bilingual review |
| `AP5.contraindication` | [English](#apat-en-ap5-contraindication) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap5-contraindication) | pending | Phase F bilingual review |
| `AP5.tradeoff` | [English](#apat-en-ap5-tradeoff) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap5-tradeoff) | pending | Phase F bilingual review |
| `AP5.question` | [English](#apat-en-ap5-question) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap5-question) | pending | Phase F bilingual review |
| `AP5.composition` | [English](#apat-en-ap5-composition) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-ap5-composition) | pending | Phase F bilingual review |
| `APAT-P01-SEMANTIC-BOUNDARY.outcome` | [English](#apat-en-apat-p01-semantic-boundary-outcome) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-apat-p01-semantic-boundary-outcome) | pending | Phase F bilingual review |
| `APAT-P02-LONG-LIVED-LIFECYCLE.outcome` | [English](#apat-en-apat-p02-long-lived-lifecycle-outcome) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-apat-p02-long-lived-lifecycle-outcome) | pending | Phase F bilingual review |
| `APAT-P03-READ-WRITE-ASYMMETRY.outcome` | [English](#apat-en-apat-p03-read-write-asymmetry-outcome) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-apat-p03-read-write-asymmetry-outcome) | pending | Phase F bilingual review |
| `APAT-P04-DUAL-WRITE.outcome` | [English](#apat-en-apat-p04-dual-write-outcome) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-apat-p04-dual-write-outcome) | pending | Phase F bilingual review |
| `APAT-P05-CROSS-OWNER-TRANSACTION.outcome` | [English](#apat-en-apat-p05-cross-owner-transaction-outcome) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-apat-p05-cross-owner-transaction-outcome) | pending | Phase F bilingual review |
| `APAT-N01-COHERENT-DOMAIN.outcome` | [English](#apat-en-apat-n01-coherent-domain-outcome) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-apat-n01-coherent-domain-outcome) | pending | Phase F bilingual review |
| `APAT-N02-LINEAR-FLOW.outcome` | [English](#apat-en-apat-n02-linear-flow-outcome) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-apat-n02-linear-flow-outcome) | pending | Phase F bilingual review |
| `APAT-N03-SIMPLE-CRUD.outcome` | [English](#apat-en-apat-n03-simple-crud-outcome) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-apat-n03-simple-crud-outcome) | pending | Phase F bilingual review |
| `APAT-N04-NO-DUAL-WRITE.outcome` | [English](#apat-en-apat-n04-no-dual-write-outcome) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-apat-n04-no-dual-write-outcome) | pending | Phase F bilingual review |
| `APAT-N05-LOCAL-ATOMIC.outcome` | [English](#apat-en-apat-n05-local-atomic-outcome) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-apat-n05-local-atomic-outcome) | pending | Phase F bilingual review |
| `APAT-N06-IRREVERSIBLE-INVARIANT.outcome` | [English](#apat-en-apat-n06-irreversible-invariant-outcome) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-apat-n06-irreversible-invariant-outcome) | pending | Phase F bilingual review |
| `APAT-E001-CANONICAL-MISSING.meaning` | [English](#apat-en-apat-e001-canonical-missing-meaning) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-apat-e001-canonical-missing-meaning) | pending | Phase F bilingual review |
| `APAT-E002-PROJECTION-DRIFT.meaning` | [English](#apat-en-apat-e002-projection-drift-meaning) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-apat-e002-projection-drift-meaning) | pending | Phase F bilingual review |
| `APAT-E003-ROUTE-MISS.meaning` | [English](#apat-en-apat-e003-route-miss-meaning) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-apat-e003-route-miss-meaning) | pending | Phase F bilingual review |
| `APAT-E004-CARGO-CULT.meaning` | [English](#apat-en-apat-e004-cargo-cult-meaning) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-apat-e004-cargo-cult-meaning) | pending | Phase F bilingual review |
| `APAT-E005-DISPOSITION-INCOMPLETE.meaning` | [English](#apat-en-apat-e005-disposition-incomplete-meaning) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-apat-e005-disposition-incomplete-meaning) | pending | Phase F bilingual review |
| `APAT-E006-INSTALLED-MISSING.meaning` | [English](#apat-en-apat-e006-installed-missing-meaning) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-apat-e006-installed-missing-meaning) | pending | Phase F bilingual review |
| `APAT-E007-MODEL-FIDELITY.meaning` | [English](#apat-en-apat-e007-model-fidelity-meaning) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-apat-e007-model-fidelity-meaning) | pending | Phase F bilingual review |
| `APAT-E008-RU-SEMANTIC-DRIFT.meaning` | [English](#apat-en-apat-e008-ru-semantic-drift-meaning) | [Russian](ru/architecture-pattern-applicability.md#apat-ru-apat-e008-ru-semantic-drift-meaning) | pending | Phase F bilingual review |

## Terms and Abbreviations

- **APAT** - Architecture Pattern Applicability contract and test namespace.
- **DDD** - Domain-Driven Design.
- **CQRS** - Command Query Responsibility Segregation.
- **CRUD** - Create, Read, Update, Delete.
- **PASS** - evidence is sufficient for the named gate.
- **ASSUMPTION (UNVERIFIED)** - a claim not established by current evidence and paired with a resolving probe.
