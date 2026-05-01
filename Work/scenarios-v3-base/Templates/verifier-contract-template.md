Date: YYYY-MM-DD
Owner: `$qa-engineer`
Status: `DRAFT`

## Verifier Contract

| Requirement | Rule |
|---|---|
| deterministic | verifier must not depend on wall clock, locale, filesystem order, or network |
| scoreable fail | wrapper success plus verifier failure is model `FAIL` |
| runtime separation | quota, route, wrapper, and timeout failures are `NOT-RUN` unless a summary proves model output was verified |
| artifact scope | changed-path or output-path scope must be checked where relevant |
| reference probe | a synthesized or reference candidate must pass before model runs |

## Required Commands

| Check | Command |
|---|---|
| contract parse | `python -c "import json; json.load(open('oracle/contract.json'))"` |
| bundle shape | `python Scenarios-v3/<root>/verifiers/<verifier>.py --bundle-shape-only` |
| reference probe | scenario-specific command |
| whitespace | `git diff --check` |

## Terms and Abbreviations

- `NR`: Not Run; runtime, quota, or route status rather than a model fail.
- `v3`: Scenarios-v3 benchmark generation.
