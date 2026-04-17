# Verifiers

`check_factual_memo.py` supports two modes:

- `--bundle-shape-only` checks the fixture author's bundle contract. This is the mode used to sanity
  check the materialized bundle itself.
- default mode checks whether a scored run completed the factual memo correctly.

## What the full verifier expects after a run

- `candidate/repository-fact-memo.md` exists, has the required analyst-memo sections, and contains
  no `TODO` markers
- the memo includes multiple repo-snapshot file references with line numbers
- the memo anchors the live path to the collector, catalog, registry score profile, writer, and
  tests
- the memo explicitly rejects the main false leads and names bounded unknowns
- the gate decision is `PASS`

The verifier is intentionally role-specific. It checks factual structure and anchor presence, not
overall prose quality.
