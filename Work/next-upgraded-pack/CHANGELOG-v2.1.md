Date: 2026-07-12
Owner: `$lead`
Status: `fork declared` — sections below are appended to by each build-plan item as it lands

## Purpose

This is the v2.1 fork declaration for the 4-profile measuring instrument (Option B,
operator-approved). Authoritative build plan: `.scratch/rf12-rerun-2026-07/BUILD-PLAN-v2.1.md`
(item S3). Constraint set: `.scratch/rf12-rerun-2026-07/review-loop-synthesis.md` (5-lane verdict).

This file is the running record of every change v2.1 makes to how the instrument runs or how a
v2.1 result should be read. Each numbered section below is a standing head; append a dated entry
under the matching section as its owning build-plan item lands with a `PASS`. Do not backfill a
section with content for an item that has not landed — leave the `Pending` placeholder until then,
so the changelog never claims a repair or family exists before its four-probe validation passes.

All v2.1 run summaries carry `harnessVersion: "v2.1"` (`BUILD-PLAN-v2.1.md` H4), so any result can
be traced back to the entries in this file by that field alone.

## Frozen-snapshot status (unchanged by this fork)

The embedded tables in
`Orchestrarium/docs/routing/full-v2-hard-r2-routing-evidence-2026-05-01.md` are the durable,
immutable 2026-05-01 snapshot. Neither this fork nor any v2.1 work item edits that file, with the
one scoped exception carried in `BUILD-PLAN-v2.1.md` P4 (a single Status-line supersession pointer
added only once the v2.1 evidence doc ships — not part of this declaration).

That doc's own "Purpose" section names `../benchmarks/Release/2026-05-01-full-v2-hard-r2` as the
local provenance input used to prepare the snapshot (`full-v2-hard-r2-routing-evidence-2026-05-01.md:14-16`,
read this session). As of this fork declaration, `Release/2026-05-01-full-v2-hard-r2/` is **not**
present anywhere in the current `benchmarks` tree — verified this session: `ls Release` at the
`benchmarks` repo root returns "No such file or directory" (own-probe). This absence makes the same
doc's own fallback rule the operative one for this repo state: "The tables in this file are the
publication-durable Orchestrarium routing evidence snapshot. The benchmark paths below are local
provenance inputs used to prepare this snapshot; the installed Orchestrarium routing policy must
not depend on those sibling-repository files being present at runtime or in a consumer checkout."
(`full-v2-hard-r2-routing-evidence-2026-05-01.md:23-26`, read this session). In other words: the
embedded tables themselves are the durable record regardless of whether the `Release/` provenance
package is ever restored locally, and v2.1 treats them as such — read-only, never regenerated from
a local `Release/` copy that does not exist.

Every v2.1 result lives in the separate fork surface `Work/next-upgraded-pack/Results-v2.1/` (this
directory) and never overwrites the frozen doc, its embedded tables, or the old runners.

## Old runners (immutable, never edited by this fork)

`run-v2-cohort-batch.ps1`, `run-v2-staged-cohort-batch.ps1`, `run-active-cohort-batch.ps1`, and
`run-v2-visual-localization-batch.ps1` under `Work/next-upgraded-pack/Tooling/` remain byte-untouched
as frozen-release provenance (`BUILD-PLAN-v2.1.md` H1). v2.1 work forks NEW runner files
(`run-v21-cohort-batch.ps1`, `run-v21-staged-cohort-batch.ps1`) rather than editing the old ones in
place.

---

## 1. Harness fork (Phase 0 — items H1-H9)

Pending. Will record, as each item lands: the new `Tooling/run-v21-cohort-batch.ps1` /
`run-v21-staged-cohort-batch.ps1` forks (H1); the 3-root execution topology (I1: `provider/` /
`out/` / `score/` / `exec-fixed/` / `exec-buggy/` / `meta/`); the provider-root staging tool and
import gate (H2/H3); the telemetry capture into `summary.json` (H4, see section 2 below for its
budget-surface consequence); the provider-harness equivalence ledger (H5); the repeated-run variance
policy and aggregator (H6); the 4-profile row configs (H7); the harness-sensitivity A/B (H8); the
exec-root split for the 28 subprocess-running verifiers (H9); and the Phase-0 exit-gate result.

## 2. Budget-surface semantics change (H4)

Pending. Will record the codex `worker-output.txt` semantics change (full exec transcript → final
answer text only, equalized against the claude side) once H4 lands, plus the resulting frozen-table
comparability caveat: the 14 historical operator-budget slots (N46-N58, N63, N74, N85) measured the
codex side's FULL TRANSCRIPT bytes, not final-answer bytes, under the frozen 2026-05-01 harness — a
v2.1 result on those slots is not directly comparable to the frozen 2026-05-01 table for the codex
side without accounting for this equalization.

## 3. Oracle/verifier repairs (Phase 2 — items R1-R9)

Pending. Will record, per repaired or restored bundle: which verifier/oracle mechanism changed, the
four-probe validation result (reference / vacuous-candidate / adversarial / repeated-strong-model),
and — for bundles restored from `.scratch/` archive (N98, N110) — the restore source and the sha256
provenance manifest path under `Work/next-upgraded-pack/Evidence/`.

## 4. Retired overlays (R8)

Pending. Will record the final retire list (4-6 overlays drawn only from the non-table set
{N46, N50, N51, N54, N55, N62, N63, N74}), the exemplar preserved per overlay subtype
(operator-budget hotfix, turnaround-budget, frame-inversion), and the `Archive/` breadcrumb path for
each retired bundle. Confirmed exclusions that will never appear in this retirement list: the live
40-slot rows N47, N48, N56, N57, N85, and N49 (N49 is folded into the L04 read by R9 instead of
retired).

## 5. New families (Phase 3 — items F1-F5)

Pending. Will record each new `Scenarios-v3` family as it is admitted: stamina (F1), Terra
working-audit (F2), owner over-reach self-validity gate (F3), independent L12 raster family (F4),
and the lane-repair scenario batch (F5) — each with its pre-registered `expected_winner` and its
four-probe validation result, required before the family may feed a published lane read.

---

## Terms and Abbreviations

- **Fork**: this v2.1 surface (`Work/next-upgraded-pack/`), forked from the frozen 2026-05-01
  harness and results without mutating either.
- **Frozen doc**: `Orchestrarium/docs/routing/full-v2-hard-r2-routing-evidence-2026-05-01.md`,
  immutable except for the single Status-line supersession pointer added under build-plan item P4.
- **harnessVersion**: the `summary.json` field (value `"v2.1"`) marking a run as produced by the
  v2.1 fork rather than the old (pre-fork) runners.
- **Old runners**: `run-v2-cohort-batch.ps1` and its siblings listed above, left byte-untouched.
- **Four-probe validation**: reference / vacuous-candidate / adversarial / repeated-strong-model
  probes, required to gate any new or changed discriminator before it feeds a lane read.
