# Operating Model Reference

Reference for routing, interaction types, periodic controls, and role aliases. Read on demand.

## Template-based routing

Team templates in `.claude/agents/team-templates/` define the team composition and execution chain for each task type.

- Templates with `requiresLead: false` — main conversation manages the chain directly, invoking specialists in stage order and passing accepted artifacts to the next role.
- Templates with `requiresLead: true` — `$lead` coordinates work-items, risk owners, integration, and gates.
- Re-classify immediately if scope widens beyond the current template.

## Routing principles

When lead coordinates, or when the main conversation needs to decide between roles within a template:

1. **Risk owners trigger reviewers**: if a specialist constraint role participated in design, add the corresponding reviewer after QA.
2. **UX lane**: if user-facing interaction design is needed, add `ux-designer` in design and `ux-reviewer` after QA.
3. **Parallel read-only**: research roles (analyst, product-analyst) can run in parallel. Write-heavy roles need explicit ownership boundaries.
4. **Re-intake**: if the admitted item itself changed materially, route back to `product-manager`. Cap: 2 re-intakes, then escalate to user.

## Interaction types

Eight interaction types classify how roles communicate.

| Type       | Symbol   | Purpose                                                                |
|------------|----------|------------------------------------------------------------------------|
| `DIRECT`   | `->`     | Direct artifact handoff. Default for `requiresLead: false` chains.     |
| `LEAD_MED` | `->L->`  | Every handoff through lead. Default for `requiresLead: true` chains.   |
| `PARALLEL` | `\|\|`   | Parallel execution; single aggregator point.                           |
| `CLAIMS`   | `=>`     | Traveling artifact via `constraints/claims.md`.                        |
| `RETURN`   | `<=`     | Reviewer returns finding to named specialist (structural gaps only).   |
| `ESCALATE` | `^`      | Bounded escalation with specific metrics and question.                 |
| `ADVISORY` | `~>`     | Consultant advisory only; never a pipeline gate.                       |
| `NONE`     | `.`      | No direct interaction.                                                 |

`PARALLEL`, `CLAIMS`, `RETURN`, `ESCALATE` require lead or main conversation authorization.

## Periodic controls

Periodic controls complement stage gates. Stage gates answer "may this item advance?" Periodic controls answer "what drift or staleness should we catch between transitions?"

| Control | Owner | Trigger | Fail action |
| --- | --- | --- | --- |
| Work-items completeness | `$lead` | Session start | Create missing artifacts or park item |
| Freshness audit | `$lead` | Resume / session start | Update `status.md` or park/archive |
| Artifact completeness | `$knowledge-archivist` | Stage change | Restore artifact or route back upstream |
| Index sync | `$knowledge-archivist` | Resume, archive, completion | Update index |
| Risk-routing audit | `$lead` | Weekly or scope change | Reclassify and add missing lanes |
| Repo consistency | `$knowledge-archivist` | Weekly | Open bounded hygiene follow-up |
| Publication-safety spot check | `$lead` | Weekly or before publication | Redact or move to `/.scratch/` |
| Refactor debt scan | `$architecture-reviewer` | Milestone close | Admit bounded refactor item |
| Closure and archive hygiene | `$knowledge-archivist` | Monthly / milestone close | Archive and update index |
| Governance alignment | `$knowledge-archivist` | Governance change | Propagate to all governance files in same commit |

## Non-obvious routing pairs

These pairings are not derivable from classification alone — lead must know them:

| Work type | Design role | Implementation role | QA / Review |
| --- | --- | --- | --- |
| Scientific / data visualization | `$computational-scientist` | `$visualization-engineer` | `$qa-engineer` |
| Geometry / spatial computation | `$computational-scientist` | `$geometry-engineer` | `$qa-engineer` + `$architecture-reviewer` |
| Qt model-view heavy | — | `$model-view-engineer` | `$qa-engineer` + `$ui-test-engineer` (both) |
| Graphics with hard GPU/frame budgets | `$performance-engineer` | `$graphics-engineer` | `$qa-engineer` + `$performance-reviewer` |
| Combined critical (max risk) | stack all relevant constraint roles | implementation specialist | `$qa-engineer` + all triggered reviewers |

## How to instruct reviewers

**Claim-Verify**: pass the claims list from the builder's artifact. Tell the reviewer: *"Verify each claim against the artifact. Also identify any risk surfaces not covered by any claim."*

**Adversarial**: pass the implementation artifact only. Tell the reviewer: *"Do not read the upstream design package. Assume an adversary with full knowledge of the implementation. Find the three highest-probability failure or attack vectors and show the exact mechanism for each."*

## Common alias map

- roadmap owner, PM, or milestone owner = `$product-manager`
- `researcher` = `$analyst`
- product clarification = `$product-analyst`
- `backend-dev` = `$backend-engineer`
- `frontend-dev` = `$frontend-engineer`
- `qa` = `$qa-engineer`
- `mathematical-algorithm-scientist` = `$algorithm-scientist`
- `computational scientist` or `numerical-methods-scientist` = `$computational-scientist`
- `archivist`, `knowledge archivist`, or `repo curator` = `$knowledge-archivist`
- `graphics engineer` or `rendering engineer` = `$graphics-engineer`
- `visualization engineer` = `$visualization-engineer`
- `geometry engineer` = `$geometry-engineer`
- `build engineer` or `toolchain engineer` = `$toolchain-engineer`

## Governance sources

- `.claude/CLAUDE.md` is the governance source of truth (auto-loaded into every conversation).
- `lead.md` is the self-contained lead operating guide (loaded when lead is invoked).
- This file is the on-demand reference for routing, controls, and aliases.
