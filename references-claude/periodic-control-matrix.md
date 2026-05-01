# Periodic Control Matrix

This repository uses periodic controls as a complement to stage gates, not a replacement for them.

Stage gates answer: "may this item move to the next phase?"  
Periodic controls answer: "what drift, staleness, or hygiene risk should we catch between phase transitions?"

## Cadence layers

| Layer | Purpose | Typical owner |
|---|---|---|
| Per-session | Catch stale active items and missing recovery state before work resumes | `$lead` |
| Weekly | Catch structural drift, risk-routing mistakes, repo consistency gaps, and publication-safety issues | `$lead`, `$knowledge-archivist`, or the relevant reviewer |
| Milestone / quarterly | Catch accumulated refactor debt, archive hygiene, and operating-model drift | `$lead`, `$knowledge-archivist`, `$architecture-reviewer` |

## Control matrix

| Control | Owner | Cadence or trigger | Evidence | Fail action |
|---|---|---|---|---|
| Work-items completeness audit | `$lead` (invoke `$knowledge-archivist` for multi-item or complex state) | Every session start (before lead routing) | Active item folders contain `roadmap.md`, `brief.md`, `status.md`; brief has scope/owners/stage; status has current snapshot | Lead creates missing artifacts before proceeding; incomplete items are parked until restored |
| Freshness audit for active items | `$lead` | Every resume or session start | `work-items/index.md` plus each active item `status.md` current snapshot | Update `status.md`, or park/archive the item before continuing |
| Completeness audit for required artifacts | `$knowledge-archivist` | Every resume or stage change | Item folder contains the stage-required artifacts for the current phase | Restore the missing artifact or route the item back to the required upstream stage |
| Index sync | `$knowledge-archivist` | Every resume, archive move, or completion | `work-items/index.md` matches actual active/archive folders | Update the index before delivery continues |
| Risk-routing audit | `$lead` | Weekly or on scope change | Item `brief.md` and `status.md` show the correct change class and required specialist lanes | Reclassify the item and add missing specialist or reviewer lanes |
| Repo consistency audit | `$knowledge-archivist` | Weekly | `CLAUDE.md`, `shared/references/`, `references-claude/`, and `.claude/agents/` links remain consistent | Open a bounded docs or hygiene follow-up; if the fix changes governance semantics, route it through `$architecture-reviewer` before publication |
| Publication-safety spot check | `$lead` or the relevant reviewer | Weekly or before publication | `$lead` runs the publication-safety command documented in the root repository docs or Claude runtime docs when preparing publication; relevant reviewers may run the same check for spot checks, and staged-diff review still shows tracked content is free of secrets, raw logs, full transcripts, and machine-specific paths | Redact or move raw material to `/.scratch/` before publication |
| Refactor debt scan | `$architecture-reviewer` | Milestone close or quarterly | Recent code-touching areas do not accumulate avoidable duplication, coupling drift, or seam erosion | Admit a bounded refactor item through normal intake |
| Closure and archive hygiene | `$knowledge-archivist` | Monthly or at milestone close | Completed or cancelled items are moved to `work-items/archive/` and indexed correctly | Archive the item and update the index |
| Documentation sync | `$knowledge-archivist` | Skill, role, or template added/removed/renamed | README, INSTALL, install scripts match actual counts and names | Update docs per root CLAUDE.md checklists |
| Operating-model alignment check | `$lead` with `$architecture-reviewer` when needed | Quarterly | Recent work still matches the documented routing and gate model | Update the docs or admit a governance follow-up item |

## What stays stage-gated

These checks remain stage-gated instead of periodic:

- Work-items completeness check at session start before any specialist delegation
- `roadmap.md`, `brief.md`, and `status.md` before non-trivial lead-routed work starts or resumes
- `plan.md` before implementation or review begins
- required upstream artifacts such as `research`, `design`, specialist constraints, and review reports before the next stage proceeds
- independent reviewer approval for security, architecture, performance, UX, accessibility, and QA gates
- human review before `git push`, release, or equivalent publication

## Minimal rule

Use periodic controls to catch drift between gates. Use stage gates to stop bad work from advancing.
