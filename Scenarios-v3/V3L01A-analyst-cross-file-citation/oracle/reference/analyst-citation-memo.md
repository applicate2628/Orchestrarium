# Analyst Cross-File Citation Memo

## Investigation goal

Establish, for the batch pipeline, the effective retry limit, request timeout, and profile the scorer
actually runs with, and cite each to the authoritative source. The declared defaults and the legacy
doc are surface sources that are overridden; they must not be cited as the effective values.

## Confirmed Facts

| # | Question | File | Line | Symbol | Fact |
|---|---|---|---|---|---|
| 1 | 1 | `candidate/repo-snapshot/config/effective.py` | 5 | EFFECTIVE_RETRY_LIMIT | the effective retry limit is 5, the effective override the scorer consumes |
| 2 | 2 | `candidate/repo-snapshot/config/effective.py` | 6 | EFFECTIVE_TIMEOUT_MS | the effective request timeout is 8000ms, the effective override value |
| 3 | 3 | `candidate/repo-snapshot/config/effective.py` | 7 | EFFECTIVE_PROFILE | the scorer runs under the batch profile |

## Mis-Cited Sources Rejected

| # | Mis-Cited Source | File | Why Wrong |
|---|---|---|---|
| 1 | declared default retry limit | `candidate/repo-snapshot/config/defaults.py` | defaults.py declares RETRY_LIMIT of 3, but effective.py overrides it to 5 for the batch pipeline |
| 2 | legacy config notes | `candidate/repo-snapshot/docs/legacy-config.md` | the legacy doc is stale and predates the overrides; effective.py is authoritative |
| 3 | declared interactive profile | `candidate/repo-snapshot/config/defaults.py` | defaults.py ACTIVE_PROFILE is interactive, but the scorer runs under the batch profile |

## Explicit Unknowns

| # | Unknown | Why |
|---|---|---|
| 1 | whether non-batch pipelines also override these defaults | not shown in the bounded slice |
| 2 | the override source (env or cli) that selects the batch profile | not present in the visible slice |

## Gate Decision

PASS
