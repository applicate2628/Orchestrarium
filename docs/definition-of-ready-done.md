# Definition of Ready / Definition of Done

This file is a vocabulary pointer, not a checklist; the criteria live in the
cited owners and are NOT duplicated here. It maps the agile **Definition of
Ready** (DoR) and **Definition of Done** (DoD) terms onto the gates Orchestrarium
already enforces, so the vocabulary resolves to one authoritative owner instead
of a parallel checklist (governance rule: no logic duplication). When a criterion
changes, edit the owner — not this map.

**Definition of Ready** (admitted + brief) is DISTINCT from the dependency
ready-set (no open `Depends-on`); an item must be BOTH before implementation
starts. DoR is "should we and can we describe it" (admission + brief); the
dependency ready-set is "are its prerequisites done" (`docs/dependencies.md`).

## Definition of Ready

| Term | Owning file + section (Claude) | Owning section (Codex) |
| --- | --- | --- |
| Admission filter (Coherence / Improvement-hypothesis / Non-redundancy gates) | `product-manager.md` `## Research admission filter` | product-manager `SKILL.md` `## Research admission filter` |
| Admission Priority set at admission | `product-manager.md` `## Working rules` | product-manager `SKILL.md` `## Working rules` |
| Accepted `brief.md` + `status.md` before any delegation | `subagent-contracts.md` `## Artifact gate` | lead `subagent-contracts.md` `## Artifact gate` |
| Dependency ready-set (no open `Depends-on`) — separate gate, see note above | `lead.md` `## Dependencies` | lead `SKILL.md` `## Dependencies` |

## Definition of Done

| Term | Owning file + section (Claude) | Owning section (Codex) |
| --- | --- | --- |
| Completion-reconciliation discipline (the spine rule) | `shared/AGENTS.shared.md` `Completion reconciliation discipline` | same spine rule (shared `AGENTS.shared.md`) |
| Pre-close reconcile of brief / status / artifact / checks / open obligations | `lead.md` `## Task-memory rule` (pre-close reconcile) | lead `SKILL.md` `## Task-memory rule` (pre-close reconcile) |
| QA gate — every acceptance criterion mapped to evidence | `qa-engineer.md` `## Gate` | qa-engineer `SKILL.md` `## Gate` |
| `closure.md` written (with `## Retrospective` when proportionate, `Closed:` date) | `lead.md` `## Task-memory rule` (closure.md step) | lead `SKILL.md` `## Task-memory rule` (closure.md step) |

## Terms and Abbreviations

- **DoR (Definition of Ready)**: the agile term for "this item is described well
  enough to start" — here it maps to the `$product-manager` admission filter plus
  an accepted `brief.md`/`status.md`. Distinct from the dependency ready-set.
- **DoD (Definition of Done)**: the agile term for "this item is finished" — here
  it maps to the spine Completion-reconciliation discipline, the `$lead` pre-close
  reconcile, the `$qa-engineer` gate, and a written `closure.md`.
- **admission filter**: the `$product-manager` Coherence / Improvement-hypothesis
  / Non-redundancy gates that decide whether a candidate enters discovery or
  delivery.
- **ready-set**: active items whose every `Depends-on` target is done (see
  `docs/dependencies.md`) — a SEPARATE gate from DoR.
- **acceptance criterion (AC)**: a per-phase pass condition the `$qa-engineer`
  gate maps to evidence (`AC1`, `AC2`, ... assigned by `$planner`).
