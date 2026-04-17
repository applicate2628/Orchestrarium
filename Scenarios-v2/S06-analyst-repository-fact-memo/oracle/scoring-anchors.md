# Scoring Anchors

These anchors translate the shared `owner, advisory, factual, design, planning` profile into
`S06`-specific reads.

## Strong pass signals

- cites the current runtime path with file-and-line references from the repo snapshot
- separates confirmed facts, false leads, and explicit unknowns cleanly
- explains how `score_profile` moves from scenario metadata to `ScenarioRecord` to result output
- uses tests as supporting evidence instead of relying only on stale docs
- keeps the memo factual and recommendation-free

## Partial-pass signals

- identifies the right files but misses one important control-flow step or test clue
- notices the decoys but does not explain why they are weaker evidence than the runtime path
- includes bounded unknowns, but mixes them into the confirmed-facts section

## Failure signals

- treats `legacy-routing-notes.md` as current runtime truth without checking code
- claims archived v1 material is live without evidence from the collector path
- writes recommendations, design options, a phase plan, or implementation steps
- omits line-level references or hides the missing caller surfaces instead of marking them unknown
