Date: YYYY-MM-DD
Owner: `$lead`
Status: `DRAFT`

## Task

Replace this section with the exact model-facing task.

## Role Trigger

| Field | Value |
|---|---|
| RF12 line | `Lxx` |
| primary role shape | `staged`, `compact`, `ordinary`, `visual`, `scientific`, or other admitted trigger |
| target separator | `X1 > X3`, `X3 > X1`, or `tie-probe` |

## Source Package

| Source | Authority | Required use |
|---|---|---|
| `inputs/...` | authoritative | model must cite or bind output to this source |

## Required Output

| Artifact | Required content |
|---|---|
| `candidate/...` | exact expected output path and shape |

## Forbidden Shortcuts

| Shortcut | Reason |
|---|---|
| unstated source claims | source binding must be scoreable |
| broad rewrite outside task scope | score must measure the intended role trigger |
| missing non-claim ledger | false-positive discipline is part of the scenario |

## Scoreability Notes

Runtime, quota, route, and wrapper failures must be recorded as `NOT-RUN`, not model `FAIL`.

## Terms and Abbreviations

- `NR`: Not Run; runtime, quota, or route status rather than a model fail.
- `RF12`: role-fit scorecard over twelve routing lines plus one owner/control line.
