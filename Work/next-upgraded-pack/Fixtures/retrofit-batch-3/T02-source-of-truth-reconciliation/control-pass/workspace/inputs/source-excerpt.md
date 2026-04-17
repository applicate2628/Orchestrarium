M02 source-of-truth reconciliation packet

Use only these admitted excerpts.

Packet A
- `Archive/2026-04-16-first-baseline/` is frozen historical evidence
- `Work/next-upgraded-pack/` is the mutable execution workspace
- the historical archive label for `X3` remains `opus 4.6max`

Packet B
- the current mutable label for `X3` is `opus 4.7max`
- current default mutable restatements should align to `short-results-current-2026-04-17.md`
- mutable model-version changes must not silently rewrite archived result tables

Packet C
- when archive wording and mutable wording differ, preserve archive wording inside archive reads
- current-state restatements should prefer the live short table over older archive tables
