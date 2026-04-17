Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the human-facing guide for running the current upgraded-pack tests.

Use this document when you want to:

- inspect what each test means
- run one model row on one admitted batch
- find the raw scratch outputs
- understand what to update after a run

## What exists today

| Surface | Current read |
|---|---|
| main admitted ranking surface | `Results-drafts/x1-x3-steady-state-core-results-2026-04-17.md` |
| compact operator table | `Results-drafts/short-results-current-2026-04-17.md` |
| supporting runnable surface | `Results-drafts/x1-x3-current-runnable-pack-results-2026-04-17.md` |
| active runner | `Tooling/run-active-cohort-batch.ps1` |
| canonical fixture area | `Fixtures/` |
| raw run sandboxes | ignored `.scratch/active-cohort-runs/` |

## Mental model

| Item | Meaning |
|---|---|
| one `Tnn` fixture | one runnable benchmark test with its own verifier |
| one batch | one explicit set of `T` tests run together for one row |
| one row | one model lane such as `X1`, `X2`, or `X3` |
| fixture `broken/` copy | canonical starting state used for every run |
| scratch run sandbox | disposable copied workspace where the model actually edits files |
| evidence doc | the human-written admitted interpretation after the raw run |

The runner never edits canonical fixtures in place.
It copies `broken/` into ignored scratch storage and runs there.

## Supported row IDs

| Row | Current label | Current use |
|---|---|---|
| `X1` | `gpt-5.4` | main active row |
| `X2` | `gpt-spark` | main active row |
| `X3` | `opus 4.7max` | main active row |
| `X5` | `gemini3.1pro` | exploratory retry row |
| `X6` | `gemini3.1flash-lite-preview` | exploratory retry row |

`X4` is not wired into the current runner.

## Current admitted batches

| Batch | Tests |
|---|---|
| `worker-heavy-first-batch` | `T08`, `T09`, `T10`, `T22`, `T23`, `T24`, `T25`, `T29`, `T30` |
| `remaining-core-batch` | `T01`, `T03`, `T05`, `T07`, `T12`, `T15`, `T18`, `T19`, `T21` |

The full steady-state core execution pack is the union of those two batches.

## Before you run anything

| Check | Why |
|---|---|
| use PowerShell | the runner is a PowerShell script |
| run inside the `benchmarks` worktree | paths and archive wrappers assume this workspace |
| make sure provider CLIs are already working | the runner calls archived provider wrappers directly |
| read the fixture README first if you are targeting a custom test | each fixture defines the owner seam and allowed output |

## Where to run from

Use the next-pack root:

```powershell
Set-Location D:\dev\Orchestrator\benchmarks\Work\next-upgraded-pack
```

## Quick start

Run the default worker-heavy batch for `X1`:

```powershell
powershell -ExecutionPolicy Bypass -File .\Tooling\run-active-cohort-batch.ps1 -RowId X1
```

Run the default worker-heavy batch for `X3`:

```powershell
powershell -ExecutionPolicy Bypass -File .\Tooling\run-active-cohort-batch.ps1 -RowId X3
```

Run the backfilled remaining-core batch for `X2`:

```powershell
powershell -ExecutionPolicy Bypass -File .\Tooling\run-active-cohort-batch.ps1 `
  -RowId X2 `
  -BatchName remaining-core-batch `
  -TestIds @('T01','T03','T05','T07','T12','T15','T18','T19','T21')
```

Run one custom narrow slice:

```powershell
powershell -ExecutionPolicy Bypass -File .\Tooling\run-active-cohort-batch.ps1 `
  -RowId X1 `
  -BatchName t29-only `
  -TestIds @('T29')
```

## How to inspect a test before running it

| What to read | Why |
|---|---|
| `Fixtures/<test>/README.md` | the task contract, tempting wrong surfaces, and allowed owner seam |
| `broken/` tree | the exact starting state that will be copied into scratch |
| `control-pass/` tree when present | the known passing reference state |

Example:

```powershell
Get-Content .\Fixtures\T29-toolchain-false-root-ambiguity\README.md
```

## What the runner writes

After a run, look under:

```text
benchmarks/.scratch/active-cohort-runs/<timestamp>-<RowId>-<BatchName>/
```

Inside each batch root:

| Path | Meaning |
|---|---|
| `batch-summary.md` | one quick summary across all tests in the batch |
| `<TestId>/run/` | copied disposable workspace that the model edited |
| `<TestId>/meta/prompt.txt` | exact prompt sent to the helper |
| `<TestId>/meta/worker-output.txt` | raw model output |
| `<TestId>/meta/summary.json` | machine-readable run summary |
| `<TestId>/meta/verify-*.txt` | local verifier output for that test |

## How to read success and failure

| Signal | Meaning |
|---|---|
| wrapper exit `0` and local verification `PASS` | raw run succeeded for that test |
| wrapper exit non-zero | provider or wrapper execution failed |
| verifier `FAIL` | the model changed the wrong surface or did not satisfy the fixture |
| extra changed benchmark paths | likely scope widening or owner-seam drift |

The runner exits `1` if any test in the batch fails.

## What the human does after a run

The runner does not automatically update admitted benchmark documents.

After a meaningful run:

1. inspect `batch-summary.md`
2. inspect the per-test `summary.json` and `verify-*.txt` files for any suspicious case
3. write or update the appropriate file under `Evidence/`
4. if the evidence changes the interpretation surface, update `Results-drafts/` or `Checkpoints/status-2026-04-16.md`
5. commit the completed pass as one bounded checkpoint

## Current canonical places to update

| If you changed | Update |
|---|---|
| one row on one batch | `Evidence/` |
| the compact live table | `Results-drafts/short-results-current-2026-04-17.md` |
| the main admitted core ranking | `Results-drafts/x1-x3-steady-state-core-results-2026-04-17.md` |
| live resume point | `Checkpoints/status-2026-04-16.md` |

## Safety rules

| Rule | Meaning |
|---|---|
| do not edit `Archive/` during active reruns | archive is frozen evidence |
| do not run inside canonical fixture directories | use the runner so work stays in scratch |
| do not treat scratch output as admitted evidence by itself | only admitted docs under `Evidence/` and `Results-drafts/` count |
| do not rerank from one raw run without updating the written evidence surface | the docs are the canonical read |

## Recommended current usage

| Goal | What to do |
|---|---|
| inspect current state fast | read `Results-drafts/short-results-current-2026-04-17.md` |
| inspect the main admitted ranking | read `Results-drafts/x1-x3-steady-state-core-results-2026-04-17.md` |
| rerun one active row | use `run-active-cohort-batch.ps1` from the next-pack root |
| retry Gemini safely | only after runtime-contract hardening, not ad hoc |
