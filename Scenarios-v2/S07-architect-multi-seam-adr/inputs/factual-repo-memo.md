# Factual Repo Memo

This memo is the accepted research source of truth for `S07`.

## Confirmed facts

1. `pack-specs-v1-2026-04-17.md` defines exactly ten required `scenario.yaml` fields:
   `id`, `surface_id`, `pack_id`, `role_class`, `artifact_type`, `modality_family`,
   `allowed_change_surface`, `must_not_touch`, `score_profile`, and `overlay_flags`.
2. The same pack-specs artifact defines the `S07` worked example as:
   - `surface_id: R07`
   - `pack_id: P02`
   - `role_class: design`
   - `artifact_type: ADR or design package`
   - `modality_family: architecture decision`
   - `allowed_change_surface: design packet only`
   - `must_not_touch: implementation files, upstream factual brief, unrelated planning docs`
   - `score_profile: owner, advisory, factual, design, planning`
3. The Phase 2 materialization plan requires `S07` to remain self-contained and says the oracle and
   verifiers must anchor seam choice, tradeoff coverage, and dependency-direction claims.
4. The scenario backlog defines `S07` as `ADR package with multiple plausible seams`, which means
   the design task must force an actual architecture decision rather than a generic summary.
5. The scoring model maps `role_class: design` to the shared
   `owner, advisory, factual, design, planning` profile; there is no accepted requirement to add a
   new profile for architect bundles.
6. The publication model keeps semantic role results separate from transport-adapter results.
7. The universal bundle contract already reserves `inputs/`, `candidate/`, `oracle/`, and
   `verifiers/` for scenario-local materials, so scenario-specific logic can live below the bundle
   root without changing global path conventions.

## Design implication

Any solution that redefines the universal metadata schema, global score-profile model, or adapter
separation is in direct tension with the accepted source of truth.
