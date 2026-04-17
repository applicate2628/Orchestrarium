# Inputs

This directory is the immutable packet for the `S02` recovery scenario. It provides the accepted
artifact chain that the lead must use to rebuild the current resume point without inventing new
facts.

## Included materials

- `task.md` defines the benchmark task and the required output packet
- `interruption-record.md` records the side request that temporarily interrupted the lead lane
- `accepted-artifacts/roadmap.md` is the admission source
- `accepted-artifacts/plan.md` is the accepted phase plan and next-gate contract
- `accepted-artifacts/implementation-package.md` is the accepted implementation result that landed
  before the interruption was fully reconciled

The inputs are recovery-specific. They are intentionally written so a generic planning answer will
miss the current stage, the accepted implementation artifact, or the correct next role.
