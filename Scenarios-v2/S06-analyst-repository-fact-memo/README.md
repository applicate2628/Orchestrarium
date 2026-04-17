# S06 Analyst Repository Fact Memo

`S06` benchmarks `R06 $analyst` on extracting repository facts from a bounded repo slice that
contains stale notes, legacy exports, and other plausible false leads. The candidate is not asked
to recommend a fix, choose an architecture, or produce a delivery plan. The scored behavior is to
produce one factual research memo with file-and-line evidence, explicit unknowns, and clear
separation between confirmed facts and rejected leads.

## Scenario summary

The bundle-local repo slice contains the scenario collector, score-profile plumbing, publication
writer, tests, and several legacy artifacts that look important but are not the visible runtime
path. The task is to determine what currently selects bundles for a requested surface, how the
score profile reaches result output, which legacy artifacts are live versus archival, and what
cannot be confirmed from the bounded evidence.

## Expected candidate work

Edit only the file listed in `scenario.yaml`:

- `candidate/repository-fact-memo.md`

Use the immutable materials in `inputs/` plus the read-only repo slice in `candidate/repo-snapshot/`.
The completed memo must remain factual and include:

- file-and-line references using forward-slash repo-relative paths
- confirmed current behavior and the files or symbols that support it
- false leads or decoys that appear plausible but are not the visible runtime path
- explicit unknowns where the repo slice does not prove a claim
- tests or coverage clues that confirm the observed behavior
- one explicit gate decision: `PASS`, `REVISE`, or `BLOCKED`

## What this bundle tests

- repository investigation under noisy and partly stale evidence
- clean separation between confirmed facts, rejected leads, and unknowns
- line-level referencing discipline instead of broad narrative claims
- resistance to drifting into architecture advice, phased plans, or implementation work

## Bundle map

- `inputs/` holds the task contract, noisy intake notes, and slice boundaries
- `candidate/` is the mutable run root copied per execution
- `candidate/repo-snapshot/` is the read-only repository slice to investigate
- `oracle/` defines the expected facts, decoys, and scoring anchors
- `verifiers/` contains a local checker for bundle shape and a completed factual memo
