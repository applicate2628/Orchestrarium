# V3L01A - Analyst Cross-File Mis-Citation

Target line: `L01` (analyst / factual). One of the three A9 sub-scenarios in build-plan F5 that repair
the L01 lane read (analyst, product-analyst, planner).

The candidate answers three factual questions about the batch pipeline's effective configuration and
cites each to its authoritative source. The trap: the declared defaults (`config/defaults.py`) and a
stale doc (`docs/legacy-config.md`) carry plausible-but-superseded values; the batch pipeline overrides
them in `config/effective.py`, which is what `pipeline/scorer.py` consumes.

## Why this separates near-peer strong analysts (not merely hard)

Harder-separating than S06's distractor-file traps: the wrong citation is a value that literally appears
verbatim in two surface sources. A near-peer analyst that cites the declared default (value 3 / 2000 /
interactive) mis-cites both the File and the value; a top analyst traces the override to effective.py
(5 / 8000 / batch) and explicitly rejects the surface sources. The File+value binding plus the mandatory
`## Mis-Cited Sources Rejected` table is the discriminator.

## Layout

- `inputs/` - task (three questions + the trap) and bounded scope.
- `candidate/repo-snapshot/` - the read-only slice (defaults, effective, scorer, legacy doc).
- `candidate/analyst-citation-memo.md` - the editable memo (blank start state).
- `oracle/` - contract, scoring anchors, and a passing `reference/`.
- `verifiers/check_analyst_citation.py` - deterministic, read-only, executes no candidate code.

## Terms and Abbreviations

- `authoritative source` - the module whose value is actually consumed at runtime (here `effective.py`).
- `mis-citation` - citing a plausible-but-superseded source instead of the authoritative one.
- `L01` - the analyst/factual routing line of the RF12 scorecard.
