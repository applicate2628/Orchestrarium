# Docs

This directory is the branch-level docs surface for the Orchestrarium monorepo common layer.

Use it together with:

- [../README.md](../README.md) for the repository overview
- [../INSTALL.md](../INSTALL.md) for install and runtime rules
- [../src.codex/README.md](../src.codex/README.md) for the Codex source subtree
- [../src.claude/README.md](../src.claude/README.md) for the Claude source subtree
- [../shared/references/README.md](../shared/references/README.md) for the shared design core
- [../references-codex/README.md](../references-codex/README.md)
- [../references-claude/README.md](../references-claude/README.md)

Current references and maintenance guidance:

- [distribution-runtime-project.md](distribution-runtime-project.md) indexes the planned installer delivery channels and the separate Rust and software development kit (SDK) release owners.
- [routing/gpt-6-2-production-hotfix-2026-11-17.md](routing/gpt-6-2-production-hotfix-2026-11-17.md) for the current factory Sol/Astra generation refresh and offline verification boundary
- [agents-mode-reference.md](agents-mode-reference.md) for the shared operator schema
- [external-worker-design.md](external-worker-design.md) for external execution adapter design notes
- [new-session-guide.md](new-session-guide.md) for new-session orientation and source-first maintenance rules
- [provider-runtime-layouts.md](provider-runtime-layouts.md) for cross-provider runtime path mapping
- [work-item-execution-tracking.md](work-item-execution-tracking.md) for the execution ledger helper and periodic active work-item checker
- [epics.md](epics.md) for grouping work-items under one goal or milestone (epic -> work-item -> phase)
- [decisions.md](decisions.md) for the cross-item architecture-decision registry (ADR store)
- [dependencies.md](dependencies.md) for cross-work-item `Depends-on` edges and the blocked/ready derivation
- [lessons.md](lessons.md) for the in-repo delivery-lessons registry (capture lessons learned so they survive a work-item's archival)
- [definition-of-ready-done.md](definition-of-ready-done.md) for the DoR/DoD vocabulary map onto existing admission and close gates
- [provider-receipt-planning.md](provider-receipt-planning.md) for source contracts of receipt planning and exact-current selection
- [effect-bound-filesystem-owner.md](effect-bound-filesystem-owner.md) for installer transaction boundaries and dated platform evidence

Dated design and evidence, not current implementation plans:

- [claude-instruction-unification.md](claude-instruction-unification.md) — Claude instruction discovery research and original implementation handoff; use the current runtime and install references above for the implemented layout
- [routing/sol-6-1-routing-proposal-2026-10-01.md](routing/sol-6-1-routing-proposal-2026-10-01.md) — prior Sol 6.1 generation decision and dated evidence
- [routing/12-lane-routing-matrix-v1-2026-04-18.md](routing/12-lane-routing-matrix-v1-2026-04-18.md) — superseded lane matrix
- [routing/full-v2-hard-r2-routing-evidence-2026-05-01.md](routing/full-v2-hard-r2-routing-evidence-2026-05-01.md) — historical routing benchmark, not validation of the current model families

## Terms and Abbreviations

- `agents-mode`: Orchestrarium operator overlay for delegation, provider routing, MCP use, and parallelism.
- `agent-runs.jsonl`: JSONL execution ledger stored beside `status.md` for machine-readable work-item state.
- `check-work-items-state.*`: helper script family that checks every active work item under a repository root.
- `Codex`: OpenAI Codex runtime and provider line.
- `Claude`: Anthropic Claude runtime and provider line.
- `decision registry`: flat cross-item store of durable architecture decisions under `work-items/decisions/` (the ADR pattern in task memory).
- `Definition of Ready/Done`: agile DoR/DoD vocabulary mapped onto existing admission and close gates by `definition-of-ready-done.md` (a pointer map, not a new checklist).
- `Depends-on`: standing cross-work-item dependency edge declared in `status.md`; drives the derived blocked-by / ready-set views.
- `lessons registry`: flat in-repo store of durable delivery lessons under `work-items/lessons/` (a recurring miss, wrong assumption, or process gap), captured so it survives a work-item's archival.
- `MCP`: Model Context Protocol; a protocol for exposing tools and resources to agent runtimes.
- `runtime`: installed provider-facing files and directories used by an agent tool.
