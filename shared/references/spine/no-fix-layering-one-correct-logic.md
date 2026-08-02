# No fix layering — one correct logic (full form)

Full form of the spine clause `No logic duplication / no fix layering` (`shared/AGENTS.shared.md`,
Scope and ownership discipline). The spine carries the always-on compact rule; this reference carries
the red flags, the decidable boundary test, the audit-lane methodology, and the canonical case. It is
a maintainer reference (not installed to targets); runtime surfaces (the spine clause, the
`$architecture-reviewer` audit section) are self-sufficient.

## Principle

Fixes NEVER pile up as a heap of patches. Every invariant, decision logic, or live textual artifact has
ONE owner and one coherent current truth. A fix corrects the owner rather than adding a neighboring
check because the owner "wasn't trusted" or wasn't found. A meaning-changing clarification supersedes
the prior wording: rewrite or remove stale prose, with correction history kept in version control or a
designated decision/closure record. Preserve both old and new detail only when they are genuinely
cumulative and non-conflicting. If the owner is wrong, fix it; if missing, name it; if you cannot name
it, that is an `$architect` question, not a license to patch locally.

## Red flags (each one is a finding)

1. **N guards of ONE invariant at M heights** — the same value re-checked at several call-path heights
   because the first check was not trusted. Trust is restored by fixing the first check, not by adding
   a second.
2. **Duplicated validation in producer AND consumer within one trust domain** — no untrusted/corruptible
   boundary crossed (whatever transport sits between them), so one side owns the validation. A comment justifying the duplicate ("X is WRITE, this is
   READ, not redundant") is an admission of two owners, not a resolution.
3. **A fix that papers over another fix** — a guard whose purpose is to hide the misbehavior of an
   earlier patch. The earlier patch is the defect.
4. **A clarification appended beside prose it invalidates** — the live document now tells two stories.
   Replace or remove the superseded statement; do not turn ordinary current prose into correction
   archaeology.
5. **An if-else pile in a validator begging for a table/loop** — each incremental special-case round
   added one more branch to the same loop. After ~3 rounds of edge-mining on one surface, stop and
   route a single-owner design to `$architect`.
6. **An interim/TODO stub without a tracked root-cause item** — a symptom-guard is allowed ONLY as an
   explicitly-temporary hold with a tracked root-cause item on the single owner (spine `no kostyl` rule
   owns this: explicit `WORKAROUND`, named root cause, scope, lifetime). A guard without such an item
   is a patch forever.

## The decidable defense-in-depth boundary test

The test is TRUST, not transport. Legitimate defense-in-depth exists ONLY when the value could actually
cross the boundary UNTRUSTED or CORRUPTED — untrusted user input, a third-party system, or a
persisted/generated artifact a different producer or a hand-edit could have written (e.g. a converter
and a solver with a file between them) — AND the two checks' thresholds are agreed (one constant, one
source), AND the commit names the boundary as the justification. A mere process or network hop between
two of YOUR OWN components is NOT such a boundary: re-checking a trusted internal producer's output
because you distrust it is red flag #1, whatever transport sits between you.

Distinguish two things the triad keeps separate:

- **Re-applying the owner's result** — calling it, using or enforcing its output downstream — is ALWAYS
  fine. That is consumption of the decision, not duplication of it.
- **Re-checking the result** — re-verifying that the owner's output is itself correct, because you do
  not trust it — is layering (red flag #1), UNLESS the output crossed an untrusted/corruptible boundary
  above. "Use the result" and "re-verify the result" are different acts; only the first is free.

Inside one trust domain: one owner, one check.

## Failure idiom per layer

The failure-reporting idiom is chosen per LAYER, and is uniform within a layer: process exit at the
composition root; typed returned status from libraries/leaves; an in-band poison value (e.g.
NaN-poison) only where no status channel exists. Two idioms for one failure class in one layer = a
finding. Law D1 of `shared/references/architecture-layering-hygiene.md` is the single owner of this
policy — this reference and the audit lane cite it, never redefine it.

## Anti-layering audit (per multi-fix batch)

A standing `$architecture-reviewer` gate lane (defined in the architecture-reviewer role, mirrored
across packs): for any batch containing 2+ defect fixes — or one fix touching a surface already fixed
this cycle — group the batch's changes by defect class and verify each class has exactly ONE owner
holding the corrected logic. Per-class verdicts:

- `CLEAN-SINGLE-OWNER` — one owner per class, no residual guards;
- `JUSTIFIED-DEPTH` — duplication passes the boundary test above; the justification is recorded;
- `PILED` — layered patches found; the verdict names the consolidation refactor. **PILED maps to
  `REVISE` and blocks push** until the consolidation lands or the operator explicitly parks it as a
  `WORKAROUND` with a tracked item.

The lane runs on an engine distinct from the batch's author/implementer — resolved through the normal
routing surface (external-reviewer adapter or a model override per the active `.agents-mode.yaml`
profile), never a hardcoded model name.

## Periodic repo-wide scan

The same per-class one-owner checklist applied to the whole tree (not only the new batch) — historical
layering counts too. Owned by the periodic `Refactor debt scan` row of the periodic-control matrix
(quarterly, `$architecture-reviewer`); findings enter normal intake as bounded refactor items.

## Canonical case (generalized)

A port-resolution question ("which port does the daemon own") accumulated TWO owners: a read-side
fallback resolver (display path) and a write-side convergence pass (startup backfill) — the read path's
own comment justified the duplicate ("the write pass does not make this redundant: it is WRITE, this is
READ"), which is red flag #2 verbatim. Incremental rounds (F1→F2→F4a→F5, P1a→P1b→P2a) each added one
more special-case to the same loop; the next proposed guard would have been the sixth (red flag #1).
The correct resolution, designed by `$architect` as a single owner: one pure lazy resolver
(`EffectiveDaemonPort`) after which the legacy descriptor field stopped being a source of truth — the
write-side pass became a deletable cache-warmer, BOTH special-cases were removed, no schema change. A
distinct-engine acceptance pass then caught that the interim guard itself had created one more layer
(a recovery hint pointing at the now-dead backfill path) plus stale comments — erased in the same
commit (law C6). Lessons: the symptom-guard was acceptable only WITH the tracked single-owner item;
each new special-case is the signal to stop and ask "where is the single owner"; a distinct-model
acceptance pass catches layering the author cannot see.

## Cross-references

- Spine: `No logic duplication / no fix layering` (compact form), `Fix means correct logic (no
  kostyl)` (owns the symptom-guard/WORKAROUND path), `Mechanism inventory before new paths`,
  `General-case over local symptoms`.
- Architecture-layering reference: law C1 (one owner per cross-cutting invariant), law D1 (failure
  idiom policy).

## Terms and Abbreviations

- **Layering / piling (наслоение)** — accumulating guards/patches for one invariant instead of
  correcting its single owner.
- **Defense-in-depth** — deliberate duplicate checking, legitimate only across a TRUST boundary (one
  the value could cross untrusted or corrupted), with agreed thresholds — not a mere process/network hop.
- **PILED / JUSTIFIED-DEPTH / CLEAN-SINGLE-OWNER** — anti-layering audit verdicts; PILED blocks push.
- **Poison value** — an in-band sentinel (e.g. NaN) propagating failure where no status channel exists.
- **D1 / C1 / C6** — laws of `architecture-layering-hygiene.md`: failure-idiom ownership; single owner
  per invariant; no stale residue after a superseding change.
