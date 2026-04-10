# Periodic Control Matrix

This repository uses periodic controls as a complement to stage gates, not a replacement for them.

## Cadence layers

| Layer | Purpose | Typical owner |
|---|---|---|
| Per-session | Catch stale active items and missing recovery state before work resumes | `$lead` |
| Weekly | Catch structural drift, risk-routing mistakes, repo consistency gaps, and publication-safety issues | `$lead`, `$knowledge-archivist`, or the relevant reviewer |
| Milestone / quarterly | Catch accumulated refactor debt, archive hygiene, and operating-model drift | `$lead`, `$knowledge-archivist`, `$architecture-reviewer` |

## Control matrix

| Control | Owner | Cadence or trigger | Evidence | Fail action |
|---|---|---|---|---|
| Freshness audit for active items | `$lead` | Every resume or session start | The repository-defined recovery entry point plus each active item's `status.md` current snapshot | Update `status.md`, or park/archive the item before continuing |
| Completeness audit for required artifacts | `$lead` | Every resume or stage change | Item folder contains the stage-required artifacts for the current phase | Restore the missing artifact or route the item back to the required upstream stage |
| Recovery-entry-point sync | `$knowledge-archivist` | Every resume, archive move, or completion | The configured recovery entry point and any linked active/archive locations match the actual repository layout | Update the recovery entry point or linked locations before delivery continues |
| Risk-routing audit | `$lead` | Weekly or on scope change | Item `brief.md` and `status.md` show the correct change class and required specialist lanes | Reclassify the item and add missing specialist or reviewer lanes |
| Repo consistency audit | `$knowledge-archivist` | Weekly | `README.md`, `INSTALL.md`, `docs/`, `shared/references/`, `references-gemini/`, and `src.gemini/` remain consistent | Open a bounded docs or hygiene follow-up; if the fix changes governance semantics, route it through `$architecture-reviewer` before publication |
| Publication-safety spot check | `$lead` or the relevant reviewer | Weekly or before publication | Staged-diff review shows tracked content is free of secrets, raw logs, full transcripts, and machine-specific paths | Redact or move raw material to `/.scratch/` before publication |
| Closure and archive hygiene | `$knowledge-archivist` | Monthly or at milestone close | Completed or cancelled items are moved to the configured archive location and any linked recovery metadata is updated correctly | Archive the item and update the linked recovery metadata |
| Operating-model alignment check | `$lead` with `$architecture-reviewer` when needed | Quarterly | Recent work still matches the documented routing and gate model | Update the docs or admit a governance follow-up item |

## Minimal rule

Use periodic controls to catch drift between gates. Use stage gates to stop bad work from advancing.
