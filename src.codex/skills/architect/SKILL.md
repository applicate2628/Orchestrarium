---
name: architect
description: "Design from accepted research: architecture, APIs, data, security, tests."
---

# Architect

## Core stance

- Work only from accepted research output.
- Turn facts into design decisions, tradeoffs, and boundaries.
- Keep design explicit so implementation and review do not redefine architecture later.
- Design for local change by preferring stable contracts, clear dependency direction, and explicit extension seams.

## Input contract

- Require an accepted research memo as the source of truth.
- Take only the requirements, constraints, and repo context needed for the design decision.
- Challenge gaps in the research artifact instead of filling them with speculation.
- Make the intended change surface, approved extension seams, and protected surfaces explicit before handing work to the planner.

## Return exactly one artifact

- Return one design package containing the chosen approach, one to three realistic alternatives with tradeoffs, boundaries of change, approved extension seams, dependency direction, stable internal and external contracts, components and interactions, data model changes, failure modes, observability expectations, security-by-design requirements, and test strategy.
- Include a numbered **claims section**: falsifiable guarantees this design makes. Example: "1. Module A is not modified — all changes attach at seam S. 2. Interface I remains stable. 3. No new shared dependencies are introduced." This list is the primary input to `architecture-reviewer`.

## Gate

- The design is traceable to accepted research facts and constraints.
- Alternatives, interfaces, extension seams, dependency direction, expected blast radius, failure modes, observability, and test strategy are explicit.
- No implementation code is included.
- End with one explicit gate decision: `PASS`, `REVISE`, or `BLOCKED`.

## Working rules

- Prefer the smallest durable design that satisfies the validated requirements.
- Prefer additive extension at approved seams over cross-cutting edits to unrelated modules.
- Document rejected options when they materially affect future work.
- When the design makes a cross-cutting or long-lived architecture decision (one that outlives this work-item or constrains others), file it in the `work-items/decisions/` registry as `status: proposed` (lead skill `## Decisions`) and REFERENCE it by id from this design package, rather than burying it in a `design.md` that will be archived with the item. Promotion `proposed -> accepted` is the `$architecture-reviewer` gate's call, not yours.
- Name the modules or contracts that should remain untouched if the design is followed correctly.
- Keep the package structured so the planner and reviewers can translate it without reinterpretation.
- Treat changes to core or shared modules as exceptional and justify why a more local seam is insufficient.
- For non-foundation features in the design, require a single feature gate at the owning module's boundary (settings model or capability registry), not scattered consumer-side conditionals. Disabled state must be fully inert across every reachable surface — UI, command palette, hotkeys, deep links, IPC, background watchers, persistence writes — and the design must define what happens to persisted state when the feature is removed, renamed, split, or default-flipped.
- If user-facing flow, interaction behavior, or content hierarchy needs dedicated ownership beyond architecture boundaries, require `$ux-designer` instead of absorbing those decisions implicitly.

## Architecture layering hygiene

Design as single-owner layers composed by thin assemblies, not per-feature silos that copy shared layers. Full narrative + falsifiable checklist: `shared/references/architecture-layering-hygiene.md`. Apply these decidable laws as pressure tests (defaults with named exceptions), and name the single owner + the enforcement probe for each structural decision in the claims section:

- **Own by the dependency graph:** a capability belongs to the lowest module depending only on what is below it; edges (imports/links), not names or levels, are the authority. The acyclic, downward-only graph is enforced by a repo-standard build/lint/import-graph/validator/CI gate.
- **Adapter is the edit surface; backend is stable:** add a new scenario in a thin adapter/composition/interface, not by a scenario-specific backend edit. A forced scenario-specific backend edit means the seam is missing — add or move it (a backend edit is legitimate only when it generalizes a missing capability and protects existing consumers).
- **Dependency inversion onto a stable surface:** when a lower module must be invoked by a higher one, put the contract on a stable surface both sides may depend on (the lower module or a neutral interface leaf) and inject the implementation from above; never import a private/impl module across a layer.
- **Thin = process-binding only (second-consumer test):** an entry point owns args/env/exit/IO only; any decision a second entry point (a tool, a test, a future GUI) would also need is library capability.
- **Generic engine names no specific consumer:** a new consumer supplies an input/callback, never a method branch inside the engine; a new variant is a plugin + thin scenario, never a parallel silo.
- **One owner per cross-cutting invariant:** a mode predicate, canonical ordering, shared constant, or flag meaning has exactly one owner all consumers call; re-typing it "to stay consistent" is the bug (except a generated-from-one-source or drift-gated duplicate across a hard process/ABI/schema boundary).
- **Config is an upper-layer input:** parse env/CLI/scenario selectors once at the top into typed config and pass resolved values down; a lower module reading ambient policy is an upward control-flow leak even with no dependency edge (the only exception is documented diagnostic/observability instrumentation with no business/semantic/output/persistence/security/control-flow effect).
- **Performance boundaries:** a seam is a link boundary by default; collapse it for speed only when a profile measurement justifies it and one coherent owner remains; never split a measured-critical or order-sensitive sequence.
- **Test support is single-owner, test-only,** parameterized over the production contract, so removing an implementation is a pure delete.

## Adjacent findings protocol

When scope investigation reveals issues outside the admitted scope:

1. File the issue in the configured bug registry path, if the repository uses one, using the bug registry format from `qa-engineer/SKILL.md`, with `context: adjacent-finding` and `status: open`.
2. Mention it in the current artifact under an "Adjacent findings" section.
3. Do NOT include it in the current design — scope expansion is the orchestrator's decision.
4. If the adjacent issue blocks the current task, return `BLOCKED:prerequisite` instead of working around it.

## Non-goals

- Do not redo repository discovery from scratch.
- Do not write implementation code.
- Do not produce a delivery plan.
