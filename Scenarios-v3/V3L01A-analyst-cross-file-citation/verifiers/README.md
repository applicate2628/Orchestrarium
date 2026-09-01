# Verifier

`check_analyst_citation.py` - deterministic, read-only, executes no candidate code.

## Modes

- `--bundle-shape-only` - validate the bundle contract and scenario.yaml metadata.
- (default) - validate the completed `candidate/analyst-citation-memo.md` against the fact-table oracle.
- `--changed-path PATH` (repeatable) - assert only the allowed change surface was touched.

## Four-probe validation

1. Reference PASS: copy `oracle/reference/analyst-citation-memo.md` over the candidate -> PASS.
2. Vacuous FAIL: a memo with the section headers but empty/keyword tables -> FAIL.
3. Decoy FAIL: a mis-citation report that cites `config/defaults.py` (value 3 / 2000 / interactive) and
   the legacy doc as the effective values -> FAIL on File+value binding and missing rejections.
4. Near-peer separation: the trap value is plausible (written verbatim in defaults.py and the legacy
   doc); only tracing the override to effective.py answers correctly.
