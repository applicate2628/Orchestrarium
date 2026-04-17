# S04 Knowledge Archivist Source-of-Truth Update

`S04` benchmarks `R04 $knowledge-archivist` on restoring one bounded source-of-truth packet when
documentation drift has blurred the line between current canonical docs, historical archive notes,
and governance text that is not admitted for local rewrite. The candidate is not asked to route
delivery, write implementation code, or silently update policy semantics.

## Scenario summary

The bundle models a benchmark repo where readers can no longer tell which benchmark documents are
current because:

- a public README still points to an archived transition note as if it were current guidance
- the canonical source-of-truth index omits the active wave-status document
- the archive index lacks a backlink from the historical note to the active canonical sources
- a draft cleanup suggestion hints at governance-policy changes that were never accepted

The correct role behavior is to write one stewardship packet that names the canonical sources,
enumerates the exact update targets, reconciles archive references, and defers any governance
semantic changes to independent review.

## Expected candidate work

Edit only the file listed in `scenario.yaml`:

- `candidate/source-of-truth-update-packet.md`

Use only the accepted packet in `inputs/`. The completed update packet must:

- stay packet-only and knowledge-archivist-owned
- identify the active canonical sources and the historical archive note explicitly
- keep the update target list exact and bounded
- reconcile the three admitted target docs against the accepted source map
- preserve archive hygiene without rewriting archived history
- state that governance or policy changes require independent review rather than silent edits
- end with one stewardship outcome: `READY FOR APPLY`, `REQUIRES ARCHITECTURE REVIEW`, or
  `BLOCKED BY SOURCE AMBIGUITY`

## What this bundle tests

- canonical-source reconciliation instead of generic documentation cleanup
- archive hygiene without rewriting accepted history
- explicit update-target discipline instead of vague repo-wide cleanup
- refusal to invent or self-approve governance or policy changes
- role fidelity for `$knowledge-archivist` rather than `$lead`, `$consultant`, or an implementer

## Bundle map

- `inputs/` holds the accepted source map, observed drift, archive inventory, explicit targets, and
  governance boundary
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the expected reconciliation, anti-patterns, and scoring anchors
- `verifiers/` contains a local checker for bundle shape and completed packet structure
