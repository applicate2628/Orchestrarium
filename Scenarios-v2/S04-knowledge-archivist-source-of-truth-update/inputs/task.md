# Task

Produce one `source-of-truth update packet` for `R04 $knowledge-archivist`.

## Constraints

1. Edit only `candidate/source-of-truth-update-packet.md`.
2. Reconcile the admitted target docs in `inputs/explicit-update-targets.md` against the accepted
   canonical sources in `inputs/accepted-source-map.md`.
3. Keep `archive/2026-03-transition-notes.md` historical only; do not present it as a current
   source of truth.
4. Do not turn the task into lead routing, consultant advice, a design ADR, a review report, or an
   implementation patch.
5. Do not silently change `docs/process/role-routing-policy.md` or `AGENTS.md`.
6. If a real policy or governance semantic change is needed, defer it for independent
   `$architecture-reviewer` approval instead of applying it in this packet.

## Required packet elements

- the canonical sources reviewed
- the exact update targets and their planned reconciliations
- archive hygiene actions
- governance and policy boundary notes
- risks and follow-ups
- one stewardship outcome:
  - `READY FOR APPLY`
  - `REQUIRES ARCHITECTURE REVIEW`
  - `BLOCKED BY SOURCE AMBIGUITY`
