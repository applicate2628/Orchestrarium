# v2.1 4-profile routing evidence — first pass (2026-07-12)

Status: `MEASURED / near-peer` on the current families. This is the F21 re-benchmark result on the
v2.1 instrument. It supersedes the currency status of the frozen 2026-05-01 evidence (which stays the
immutable historical record for the retired gpt-5.5 / opus-4.7 families).

## Method

Instrument: v2.1 harness (blind-oracle isolation H2/H3 + exec-root split H9 + per-provider telemetry
H4), validated live (leak closed, canary clean, telemetry populated). Profiles (operator classification):
- systemic-mgmt = Opus 4.8 (`claude-opus-4-8`)
- stamina = Sonnet 5 (`claude-sonnet-5`)
- ultimate-depth = Sol (`gpt-5.6-sol`)
- working-audit = Terra (`gpt-5.6-terra`), all xhigh.

Run: the 10 designed 4-profile discriminator families (Scenarios-v3) × 4 profiles × 1 repeat = 40
cells, single-shot (no iteration), strict binary verifiers + graded sub-scores where the verifier emits
them. Raw: `.scratch/rf12-rerun-2026-07/bench-v3-results.json`.

## Result — the 4 current families are LARGELY NEAR-PEER on these discriminators

| scenario | opus | sonnet | sol | terra | binary |
|---|---|---|---|---|---|
| V3L00 owner-overreach (floor) | P | P | P | P | all-P |
| V3L01A analyst mis-citation | F | F | F | F | all-F |
| V3L01B product-analyst scope | P | P | **F** | P | **SPLIT** |
| V3L01C planner dep-order | F | F | F | F | all-F |
| V3L02 adr-long-horizon | F(12/100) | F | F | F | all-F |
| V3L04A exact-quantile | F | F | F | F | all-F |
| V3L05 stamina-migration-l | F(1.0 breadth) | F(1.0) | F(1.0) | F(1.0) | all-F |
| V3L11A perf-arch review | F | F | F | F | all-F |
| V3L12 visual-grounding | F(64) | F(64) | F(64) | F(**73**) | all-F |
| V3LTA blind-audit-sqli | P(1.0 recall) | P(1.0) | P(1.0) | P(1.0) | all-P |

**Binary: 1 split, 7 all-F, 2 all-P (of 10).** Only V3L01B separates the four (Sol weaker on
product-analyst scope-boundary). Graded sub-scores add small edges — Terra tops V3L12 visual-grounding
(73 vs 64) and Opus scores low on the ADR (12/100) — but no profile shows a broad, repeated advantage.

**This empirically confirms the 5-lane review-loop's central prediction:** these frontier models are
near-peer and hard to separate on the designed axes; systemic-mgmt and working-audit are not cleanly
P/F-separable (V3L00 and V3LTA are all-equal); and the stamina drop-off does not manifest on a
30-consumer migration for large-context models (V3L05 = all breadth-fraction 1.0).

## Honest caveats (do NOT over-read this as "the models are identical")

- **Single-shot + strict binary** produces many all-F: real strong models return good-but-imperfect
  answers that cluster below the strict pass threshold. Part of the all-F is instrument strictness,
  not proof of model-parity. A graded-only read (degree, not pass/fail) would likely widen small gaps.
- **N=1 per cell, no repeats** — the H6 variance policy (3x + stability rule) was NOT applied; single
  runs are noisy at near-peer separation. Any single split (V3L01B) is provisional until repeated.
- **10 v3 families only** — the v2 lane-representative slots were not run in this pass (the N22
  4-profile probe was also all-F). A fuller lane read needs them.
- **Provider-harness confound is LABELED, not eliminated** (codex-CLI vs claude-Agent transports;
  token accounting differs ~500K codex vs ~14K claude — see harness-equivalence.md).

## Routing implication — ASSUMPTION updated to measured near-tie, NOT lifted to a confident ordering

The wired routing surface is a 2-way provider order per lane (claude vs codex). This pass gives NO
empirical basis to re-order it to a confident per-lane model-tier winner: the current families are
near-peer, most lanes ABSTAIN under the >=2-stable-discriminating-families rule. Honest update to the
routing-evidence ASSUMPTION labels:

> Re-benchmarked 2026-07-12 on the v2.1 instrument (current families opus/sonnet/sol/terra). Result:
> near-peer — 7/10 designed discriminators all-fail, 2/10 all-pass, 1/10 split (single-shot, N=1).
> No strong per-lane model-tier winner is empirically supported; treat the current families as near-tie
> per lane. The shipped 2-way `externalPriorityProfiles` order should stay balanced/near-tie pending a
> stronger multi-repeat + graded-only pass; do NOT hard-re-order on this data.

## Recommended follow-up — ALL COMPLETED 2026-07-12 (see the completion section below)

The three refinements this first pass named (graded-only degree read, 3× repeats to de-noise, v2
lane-representative slots) were all run, plus the Terra CRITICAL-2 host-FS mitigation. Their results
are in "Follow-up completion" below and fold into the Final conclusion. Net: the refinements
CONFIRMED and sharpened the near-tie finding (they did not overturn it) — the single-shot "splits"
proved to be mostly run-to-run noise, and only a small stable Sol-weakness / Terra-visual-edge survives.

---

## Follow-up completion (2026-07-12) — all four parked items finished

### (1) Graded-only degree read
Confirms near-tie: V3L05 stamina all 1.0 (tie), V3LTA blind-audit all recall 1.0 (tie),
**V3L12 visual-grounding: terra 73 vs opus/sonnet/sol 64 — a real graded edge to Terra** (consistent
with its working-audit / single-aspect-inspection profile). No other broad graded separation.

### (3) v2 lane-representative 12-lane read (48 runs, one strong slot per RF12 lane)
**11/12 lanes all-F (abstain).** Only L08 (S22 adversarial geometry) nominally split (opus-F, others
P) in single-shot. This starkly confirms near-peer: the strict single-shot gates fail all four models
across nearly every lane, so the RF12 lane read is overwhelmingly ABSTAIN.

### (2) 3× repeat variance on the split cells (H6 policy) — the splits were mostly NOISE
| cell | opus | sonnet | sol | terra |
|------|------|--------|-----|-------|
| S22 (geometry) | PFF `unstable` | FFP `unstable` | **FFF `stable-F`** | PFF `unstable` |
| V3L01B (product-analyst) | FPP `unstable` | **PPP `stable-P`** | **FFF `stable-F`** | FFP `unstable` |

Most cells FLIP P/F across three runs (`unstable`) — the single-shot "splits" were largely run-to-run
noise. This is direct empirical proof that **N=1 reads are unreliable at near-peer separation** (the
whole point of the H6 variance policy). The only STABLE cross-model signal after de-noising:
**Sol (ultimate-depth) stably fails geometry (S22) AND product-analyst-scope (V3L01B)** while the
others are unstable/pass — a real, repeated Sol weakness on those two task shapes; Sonnet stably
passes product-analyst scope.

### (4) Terra CRITICAL-2 (host-FS isolation) — mitigated
The provider-visible root is now staged OUTSIDE the repo (OS temp), closing the relative-traversal
path to the live source oracle (verified live). The residual absolute-path read is the documented
OS-jail escalation, intentionally unbuilt: the canary empirically shows honest models do not read a
decoy oracle planted directly in provider/, so the threat does not manifest for the benchmark's
subjects. See harness-equivalence.md.

## Final conclusion (all data)

Across 22 slots × 4 profiles (v3 40 + v2-lane 48 + 24 repeats): the current frontier families are
**near-peer**, single-shot reads are **noisy** (most nominal splits are unstable across repeats), and
the only stable cross-model signals are small and task-specific (**Sol weaker on geometry +
product-analyst-scope; Terra edges visual-grounding**). No broad per-lane model-tier ordering is
empirically supported. The routing ASSUMPTION is updated to a **measured near-tie**: the wired 2-way
provider order is NOT re-ordered, and the noise level shows single-run benchmarking is insufficient
for a confident per-lane routing decision — multi-repeat + graded scoring is required for any future
re-ordering. The v2.1 instrument (isolated harness + graded discriminators + variance policy) is built,
validated, and reusable for that.
