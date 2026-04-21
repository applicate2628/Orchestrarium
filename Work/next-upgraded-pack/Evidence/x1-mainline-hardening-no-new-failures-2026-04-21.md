Date: 2026-04-21
Owner: `$lead`
Status: `PASS`

## Scope

This evidence records the in-place hardening pass requested after `X1` and `X3` still separated
poorly on the top-pair binary gates.

No new diagnostic scenario ID was created. The hardening replaced existing mainline scenario
contracts and inputs in place:

| Scenario | Mainline hardening applied |
|---|---|
| `N02` | added row-specific source-to-state trace checks for source failure, state response, owner, and visible return cue |
| `N11` | added migration/test expectations, per-claim verification/regression requirements, and exact machine-checkable decision JSON |
| `N12` | added exact `path:line` source citations plus manifest-vs-superseded-result conflict handling |
| `N13` | added structured findings, exact finding count, timeout retry issue, and composed `sample_rows.py` scoreability corruption |
| `S30` | added exact finding count, evidence-to-finding ledger, structured finding labels, and false-positive table rows |
| `S29` | added fifth accessibility finding for unannounced submit status plus exact finding count and finding order |

## X1 Runs

| Run | Scenario(s) | Result |
|---|---|---|
| `.scratch/v2-cohort-runs/2026-04-21_00-19-00-X1-x1-top-pair-separators-n11-n13-hardened-mainline-2026-04-21/` | `N11`, `N12`, `N13` | `PASS`, `PASS`, `PASS` |
| `.scratch/v2-cohort-runs/2026-04-21_00-27-44-X1-x1-top-pair-separators-n11-n13-hardened-mainline2-2026-04-21/` | `N11`, `N12`, `N13` | `PASS`, `PASS`, `PASS` |
| `.scratch/v2-cohort-runs/2026-04-21_00-35-52-X1-x1-top-pair-separators-n11-n13-hardened-mainline3-2026-04-21/` | `N11`, `N12`, `N13` | `PASS`, `PASS`, `PASS` |
| `.scratch/v2-cohort-runs/2026-04-21_00-46-43-X1-x1-n12-hardened-line-citations-2026-04-21/` | `N12` | `PASS` |
| `.scratch/v2-cohort-runs/2026-04-21_00-50-52-X1-x1-n13-compositional-hardening-2026-04-21/` | `N13` | `PASS` |
| `.scratch/v2-cohort-runs/2026-04-21_00-53-49-X1-x1-n11-machine-decision-hardening-2026-04-21/` | `N11` | `PASS` |
| `.scratch/v2-cohort-runs/2026-04-21_00-57-30-X1-x1-n12-result-manifest-conflict-2026-04-21/` | `N12` | `PASS` |
| `.scratch/v2-cohort-runs/2026-04-21_01-00-24-X1-x1-s29-current-mainline-2026-04-21/` | `S29` | `PASS` |
| `.scratch/v2-cohort-runs/2026-04-21_01-05-43-X1-x1-s29-live-status-hardening-2026-04-21/` | `S29` | `PASS` |
| `.scratch/v2-cohort-runs/2026-04-21_01-10-19-X1-x1-s29-finding-order-hardening-2026-04-21/` | `S29` | `PASS` |
| `.scratch/v2-cohort-runs/2026-04-21_14-43-50-X1-x1-v3-ui-review-e2-hardening-2026-04-21/` | `N02`, `S30`, `N11`, `N12`, `N13` | `PASS`, `PASS`, `PASS`, `PASS`, `PASS` |

## X3 Probe

| Run | Scenario | Result |
|---|---|---|
| `.scratch/v2-cohort-runs/2026-04-21_01-14-28-X3-x3-s29-finding-order-hardening-2026-04-21/` | `S29` | `NOT-RUN / REQUEUE`: worker output says `You've hit your limit - resets Apr 23, 10pm (Europe/Moscow)` |
| `.scratch/v2-cohort-runs/2026-04-21_15-00-47-X3-x3-v3-ui-review-e2-hardening-2026-04-21/` | `N02`, `S30`, `N11`, `N12`, `N13` | `PASS`, `PASS`, `PASS`, `PASS`, `PASS` |

The `X3/S29` probe is not scoreable and must not be counted as `FAIL`.

## Verdict

`X1` produced no new scoreable failures after this in-place hardening pass. The current hardened
mainline read is therefore:

| Row | Current read |
|---|---|
| `X1 / gpt-5.4` | no new failures on hardened `N02`, `S30`, `N11`, `N12`, `N13`, or `S29` |
| `X3 / opus 4.7max` | no new failures on the fresh hardened `N02`, `S30`, `N11`, `N12`, `N13` slice; old `S29` probe remains `REQUEUE` |

The next honest separator should be a more complex mainline UI/visual or multi-file review target,
or stricter table-row/ledger semantics on the existing top-pair artifacts, not more keyword-only
hardening of the same artifacts.

## 2026-04-21 Follow-Up: Table-Row Contract Hardening

The active goal is `X1` versus `X3` separation. `X2`, `X5`, and `X6` remain calibration rows only.

The manual E3 rubric identified the only observed `X1`/`X3` deltas:

| Scenario | Delta area |
|---|---|
| `N11` | source specificity and adapter-boundary precision |
| `N12` | confirmed-fact precision and gap discipline |

Those deltas are now converted into in-place verifier requirements instead of a new stale result
fork:

| Scenario | New machine check |
|---|---|
| `N11` | `Evidence Binding Table` rows must bind each evidence ID to the exact concrete source, accepted claim, decision use, and conflict-risk semantics; `Forbidden Direction Test` rows must name `external-worker`, `external-reviewer`, and lane-taxonomy failure implications separately |
| `N12` | `Evidence Line Ledger` rows must carry citation-specific fact and status terms; `Non-Claim And Gap Ledger` must separately cover `X1 versus X3`, `X4` route/capability non-claim, and legacy-result/current-ranking non-claim |

Validation evidence:

| Check | Result |
|---|---|
| JSON parse for `N11` and `N12` contracts | `PASS` |
| `N11 --bundle-shape-only` | `PASS` |
| `N12 --bundle-shape-only` | `PASS` |
| strict `N11` verifier against latest `X1` artifact from `2026-04-21_02-54-05-X1-x1-v3-h1-h2-hardening-2026-04-21` via `.scratch/verifier-probes/2026-04-21-x1-current-n11-n12/` | `PASS` |
| strict `N12` verifier against latest `X1` artifact from `2026-04-21_02-54-05-X1-x1-v3-h1-h2-hardening-2026-04-21` via `.scratch/verifier-probes/2026-04-21-x1-current-n11-n12/` | `PASS` |

## 2026-04-21 Follow-Up: Fresh X3 Separator Run

`X3` is no longer blocked for this slice. The fresh `X1`/`X3` run over `N02`, `S30`, and `N11..N13`
completed without quota failures:

| Row | Scratch root | Binary read |
|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-21_14-43-50-X1-x1-v3-ui-review-e2-hardening-2026-04-21/` | `5 / 5 PASS` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-21_15-00-47-X3-x3-v3-ui-review-e2-hardening-2026-04-21/` | `5 / 5 PASS` |

Diagnostic E3 over the fresh `N11..N13` artifacts now reads `X1 60 / 60` and `X3 59 / 60`.
That is a narrow rubric delta, not a binary separator. The only current E3 delta is `N13`
denominator reporting: `X3` omitted the `route status` term while `X1` preserved it.

## 2026-04-21 Follow-Up: Calibration Rows X2/X5/X6

The same hardened separator surface was expanded to `X2`, `X5`, and `X6` as calibration rows.

| Row | Scratch root(s) | `S30` | `N02` | `N11` | `N12` | `N13` | Current read |
|---|---|---|---|---|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-21_14-43-50-X1-x1-v3-ui-review-e2-hardening-2026-04-21/` | `PASS` | `PASS` | `PASS` | `PASS` | `PASS` | `5 / 5` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-21_15-00-47-X3-x3-v3-ui-review-e2-hardening-2026-04-21/` | `PASS` | `PASS` | `PASS` | `PASS` | `PASS` | `5 / 5` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-21_15-41-13-X2-x2-v3-ui-review-e2-hardening-2026-04-21/` | `FAIL` | `FAIL` | `FAIL` | `FAIL` | `PASS` | `1 / 5` |
| `X5 / gemini3.1pro` | `.scratch/v2-cohort-runs/2026-04-21_15-44-40-X5-x5-v3-ui-review-e2-hardening-2026-04-21/`; `.scratch/v2-cohort-runs/2026-04-21_16-46-39-X5-x5-v3-e2-nonly-hardening-2026-04-21/`; `.scratch/v2-cohort-runs/2026-04-21_17-21-23-X5-x5-v3-n13-probe-2026-04-21/` | `TIMEOUT` | `TIMEOUT` | `NOT-RUN` | `NOT-RUN` | `TIMEOUT` | `0 / 0 scoreable` |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-21_16-15-38-X6-x6-v3-ui-review-e2-hardening-2026-04-21/`; `.scratch/v2-cohort-runs/2026-04-21_17-16-49-X6-x6-v3-e2-n11-n13-hardening-2026-04-21/`; `.scratch/v2-cohort-runs/2026-04-21_17-38-06-X6-x6-v3-n02-probe-2026-04-21/` | `FAIL` | `FAIL` | `FAIL` | `FAIL` | `FAIL` | `0 / 5` |

Notes:

- `X2` wrapper exits were `0`; the four failures are verifier-level failures, with `N13` passing.
- `X5` produced only `prompt.txt` for `S30`, `N02`, and the isolated `N13` probe; no `worker-output.txt`
  or `summary.json` was produced before timeout. A direct Gemini Pro smoke prompt also timed out before
  output. These are runtime timeouts, not verifier failures.
- `X6/S30` changed `candidate/review-report.md` but failed the stricter evidence and false-positive
  ledger checks. `X6/N02` changed `candidate/ux-structure-brief.md` and failed the trace/resume/boundary
  checks. `X6/N11` and `X6/N12` changed their artifacts but failed strict source/ledger checks with
  wrapper exit `1`; `X6/N13` changed its artifact with wrapper exit `0` but failed the strict review
  contract.
