# Task

You are acting as an analyst producing a factual, citation-bound memo. Do not design or recommend;
establish facts and cite each to its authoritative source.

## Questions to answer (batch pipeline)

1. What retry limit does the scorer effectively run with?
2. What request timeout does the scorer effectively run with?
3. Under which profile does the scorer run?

## The trap

Some values are DECLARED in `config/defaults.py` and repeated in `docs/legacy-config.md`, but the batch
pipeline OVERRIDES them in `config/effective.py`, which is what `pipeline/scorer.py` actually consumes.
Citing the declared default or the legacy doc is a mis-citation. Cite the authoritative effective value.

## Output contract

Edit `candidate/analyst-citation-memo.md`. It must contain:

- `## Confirmed Facts` - table `| # | Question | File | Line | Symbol | Fact |`, one row per question,
  each cited to the authoritative `File` and `Line` with the effective value.
- `## Mis-Cited Sources Rejected` - table `| # | Mis-Cited Source | File | Why Wrong |` naming each
  plausible-but-wrong source and why the effective module supersedes it.
- `## Explicit Unknowns` - table `| # | Unknown | Why |` for anything the bounded slice does not show.
- `## Gate Decision` - `PASS`, `REVISE`, or `BLOCKED` on its own line.

## Constraints

- Cite the authoritative effective source, not the declared default or the legacy doc.
- Do not edit anything under `candidate/repo-snapshot/**` (read only), `inputs/**`, `oracle/**`, `verifiers/**`.
- Do not paste code blocks or diffs; this is a factual memo.
