Date: 2026-04-18
Owner: `$lead`
Status: `PASS`

## Purpose

This is the human-facing guide for running the current upgraded-pack and bounded v2 tests.

Use this document when you want to:

- inspect what each test means
- run one model row on one admitted batch
- find the raw scratch outputs
- understand what to update after a run

## What exists today

| Surface | Current read |
|---|---|
| main admitted ranking surface | `Results-drafts/full-v2-hard-results-current.md` |
| compact operator table | `Results-drafts/short-results-current-2026-04-18.md` |
| legacy admitted upgraded-pack ranking | `Results-drafts/x1-x3-steady-state-core-results-2026-04-17.md` |
| supporting legacy runnable surface | `Results-drafts/x1-x3-current-runnable-pack-results-2026-04-17.md` |
| full v2 hard result surface | `Results-drafts/full-v2-hard-results-current.md` |
| deprecated pre-v3 full-v2 baseline | `Results-drafts/v2-full-s01-s33-n01-n07-results-2026-04-18.md` |
| reference extra-lane surface | `Results-drafts/v2-extra-lane-n08-n10-results-2026-04-20.md` |
| diagnostic top-pair rubric surface | `Results-drafts/v2-top-pair-rubric-e3-results-2026-04-20.md` |
| active upgraded-pack runner | `Tooling/run-active-cohort-batch.ps1` |
| active v2 runner | `Tooling/run-v2-cohort-batch.ps1` |
| diagnostic E3 scorer | `Tooling/score-top-pair-rubric.py` |
| canonical fixture area | `Fixtures/` |
| raw run sandboxes | ignored `.scratch/active-cohort-runs/` |
| raw v2 sandboxes | ignored `.scratch/v2-cohort-runs/` |

## Mental model

## V3 hardening rule

The old full-v2 `40 / 40` and `39 / 40` rows are pre-v3 baseline evidence, not final
classification. When a scenario is hardened, replace the live result/evidence line that described
the stale surface instead of adding a second competing result surface.

| Rule | Meaning |
|---|---|
| update in place | keep `short-results-current-2026-04-18.md` and `full-v2-hard-results-current.md` as the live operator surfaces |
| no stale forks | do not create new `short-results-current-v3-*` or duplicate full-result files unless a new archive snapshot is admitted |
| mark pre-v3 clearly | any remaining old score line must say `pre-v3 baseline`, `ceiling-effect baseline`, or `DEPRECATED / SUPERSEDED` |
| hardening before rerank | do not publish a stronger classification claim until hardened scenario contracts and rerun evidence exist |
| quota boundary | quota, provider-limit, and clean runtime timeouts remain `NOT-RUN` / `REQUEUE`, not model `FAIL` |

## Named report formats

Use these names when the user asks for a compact status report.

| Name                         | Use                                                                  | Contract                                                                 |
|------------------------------|----------------------------------------------------------------------|--------------------------------------------------------------------------|
| `RF12+1 Short-Rule Table`    | compact role-fit routing read for `X1` versus `X3` across `L00..L12` | one source-aligned Markdown table; rows stay ordered `L00` through `L12` |
| alias `RF12`                 | shorthand for the same report                                        | keep terse routing rules; no raw evidence dump unless explicitly asked   |

`RF12+1 Short-Rule Table` columns:

| Column       | Meaning                                                       |
|--------------|---------------------------------------------------------------|
| `Line`       | canonical lane id and lane name, for example `L06 systems`    |
| `Primary`    | current preferred row: `X1`, `X3`, `near-tie`, or `split`     |
| `Short rule` | one concise routing rule with the reason embedded             |

Keep the table horizontally readable. If a rule becomes too long, split it into a second row with
blank `Line` and `Primary` cells rather than making one very wide table cell.

| Item | Meaning |
|---|---|
| one `Tnn` fixture | one runnable benchmark test with its own verifier |
| one `Snn` or `Nnn` scenario | one runnable v2 scenario bundle with its own verifier |
| one batch | one explicit set of `T` tests run together for one row |
| one v2 cohort | one explicit set of `S` scenarios run together for one row |
| one row | one model lane such as `X1`, `X2`, or `X3` |
| fixture `broken/` copy | canonical starting state used for every run |
| scratch run sandbox | disposable copied workspace where the model actually edits files |
| evidence doc | the human-written admitted interpretation after the raw run |

The runner never edits canonical fixtures in place.
It copies `broken/` into ignored scratch storage and runs there.

## Supported row IDs

| Row | Current label | Current use |
|---|---|---|
| `X1` | `gpt-5.5` | main active row |
| `X2` | `gpt-spark` | main active row |
| `X3` | `opus 4.7max` | main active row |
| `X4` | `Claude China` | full-v2 row on the repo-canonical secret-backed Claude path, with the same current `opus` `max` profile as `X3` |
| `X5` | `gemini3.1pro` | full-v2 row |
| `X6` | `gemini3.1flash-lite-preview` | full-v2 row |

## Current admitted execution slices

| Batch | Tests |
|---|---|
| `worker-heavy-first-batch` | `T08`, `T09`, `T10`, `T22`, `T23`, `T24`, `T25`, `T29`, `T30` |
| `remaining-core-batch` | `T01`, `T03`, `T05`, `T07`, `T12`, `T15`, `T18`, `T19`, `T21` |
| `v2-worked-example-pack` | explicit bounded slice: `S02`, `S07`, `S12`, `S21`, `S22`, `S26`, `S32` |
| `v2-core-full-surface` | core discovered `Scenarios-v2` roots through the current `12` routing lanes: `S01..S33` plus `N01..N07` |
| `v2-extra-worker-long-autonomous` | reference extra-lane slice: `N08`, `N09`, `N10` |
| `v2-top-pair-rubric-e3` | diagnostic scorer over supplied `N11`, `N12`, `N13` run roots; does not launch models itself |

The full steady-state core execution pack is the union of those two batches.

## Before you run anything

| Check | Why |
|---|---|
| use PowerShell | the runner is a PowerShell script |
| run inside the `benchmarks` worktree | paths and archive wrappers assume this workspace |
| make sure provider CLIs are already working | the runners call provider CLIs and wrapper surfaces directly |
| read the fixture README first if you are targeting a custom test | each fixture defines the owner seam and allowed output |

## Where to run from

Use the next-pack root:

```powershell
$repoRoot = git rev-parse --show-toplevel
Set-Location (Join-Path $repoRoot 'Work\next-upgraded-pack')
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

Run the default full discovered v2 cohort for `X1`:

```powershell
powershell -ExecutionPolicy Bypass -File .\Tooling\run-v2-cohort-batch.ps1 -RowId X1
```

Run the historical worked-example slice explicitly:

```powershell
powershell -ExecutionPolicy Bypass -File .\Tooling\run-v2-cohort-batch.ps1 `
  -RowId X1 `
  -BatchName v2-worked-example-pack `
  -ScenarioIds @('S02','S07','S12','S21','S22','S26','S32')
```

Run one narrow v2 scenario for `X5`:

```powershell
powershell -ExecutionPolicy Bypass -File .\Tooling\run-v2-cohort-batch.ps1 `
  -RowId X5 `
  -BatchName x5-s32-only `
  -ScenarioIds @('S32')
```

Run the `worker.long-autonomous` reference extra lane for `X1`:

```powershell
powershell -ExecutionPolicy Bypass -File .\Tooling\run-v2-cohort-batch.ps1 `
  -RowId X1 `
  -BatchName x1-n08-n10-2026-04-20 `
  -ScenarioIds @('N08','N09','N10')
```

Score supplied `N11..N13` outputs with the diagnostic E3 rubric:

```powershell
python .\Tooling\score-top-pair-rubric.py `
  --x1-root '..\..\.scratch\v2-cohort-runs\2026-04-21_14-43-50-X1-x1-v3-ui-review-e2-hardening-2026-04-21' `
  --x3-root '..\..\.scratch\v2-cohort-runs\2026-04-21_15-00-47-X3-x3-v3-ui-review-e2-hardening-2026-04-21' `
  --output-md '.\Results-drafts\v2-top-pair-rubric-e3-results-2026-04-20.md' `
  --output-json '.\Evidence\x1-x3-top-pair-rubric-e3-2026-04-20.json'
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

For v2 cohort runs, look under:

```text
benchmarks/.scratch/v2-cohort-runs/<timestamp>-<RowId>-<BatchName>/
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
| explicit quota, rate, or usage-limit failure | not a scoreable model result; admit as `NOT-RUN` / `REQUEUE` until rerun produces a clean attempt |
| bounded provider/runtime timeout without worker output | not quota; admit as `TIMEOUT` until a scoring decision or clean rerun exists |
| verifier `FAIL` | the model changed the wrong surface or did not satisfy the fixture |
| extra changed benchmark paths | likely scope widening or owner-seam drift |
| extra `.reports/` or `.plans/` paths | benchmark control-plane drift; scenario allowed surface overrides repo session-log rules inside scratch runs |

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
| the compact live table | `Results-drafts/short-results-current-2026-04-18.md` |
| the main admitted ranking surface | `Results-drafts/full-v2-hard-results-current.md` |
| the full v2 hard read | `Results-drafts/full-v2-hard-results-current.md` |
| a historical pre-v3 full-v2 caveat | `Results-drafts/v2-full-s01-s33-n01-n07-results-2026-04-18.md` |
| the `worker.long-autonomous` extra-lane read | `Results-drafts/v2-extra-lane-n08-n10-results-2026-04-20.md` |
| the diagnostic top-pair rubric read | `Evidence/x1-x3-top-pair-rubric-e3-2026-04-20.md`, `Results-drafts/v2-top-pair-rubric-e3-results-2026-04-20.md` |
| live resume point | `Checkpoints/status-2026-04-16.md` |

## Safety rules

| Rule | Meaning |
|---|---|
| do not edit `Archive/` during active reruns | archive is frozen evidence |
| do not run inside canonical fixture directories | use the runner so work stays in scratch |
| do not treat scratch output as admitted evidence by itself | only admitted docs under `Evidence/` and `Results-drafts/` count |
| do not rerank from one raw run without updating the written evidence surface | the docs are the canonical read |
| do not create `.reports/`, `.plans/`, or session logs inside a benchmark run root | benchmark workers must obey `scenario.yaml` allowed surfaces even when repo-level governance asks ordinary sessions to log |

## Recommended current usage

| Goal | What to do |
|---|---|
| inspect current state fast | read `Results-drafts/short-results-current-2026-04-18.md` |
| inspect the main admitted ranking | read `Results-drafts/full-v2-hard-results-current.md` |
| inspect the full v2 hard read | read `Results-drafts/full-v2-hard-results-current.md` |
| inspect the deprecated pre-v3 full-v2 baseline | read `Results-drafts/v2-full-s01-s33-n01-n07-results-2026-04-18.md` |
| inspect the `worker.long-autonomous` extra-lane read | read `Results-drafts/v2-extra-lane-n08-n10-results-2026-04-20.md` |
| inspect the diagnostic top-pair rubric | read `Results-drafts/v2-top-pair-rubric-e3-results-2026-04-20.md` |
| inspect the legacy upgraded-pack ranking | read `Results-drafts/x1-x3-steady-state-core-results-2026-04-17.md` |
| rerun one upgraded-pack row | use `run-active-cohort-batch.ps1` from the next-pack root |
| rerun one v2 row | use `run-v2-cohort-batch.ps1` from the next-pack root |
