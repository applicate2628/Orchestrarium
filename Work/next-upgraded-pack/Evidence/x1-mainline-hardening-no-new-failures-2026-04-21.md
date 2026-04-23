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

## 2026-04-21 Follow-Up: N06 Tuple-Exact Hardening Wave

This wave targets `N06-authz-trust-boundary-review` — a core routing lane (`N01..N07`) — as
pilot for a stricter verifier shape that replaces keyword-substring matching with tuple-exact
`(file, line, category, severity, title-keyword, evidence-term)` matching. The goal is to
remove the answer-leak path that currently lets compliance-retelling pass review scenarios,
and to test whether near-ceiling `X1`/`X3` separate once that path is closed.

Motivation traces to `Evidence/separator-audit-2026-04-21.md`, which classified `N06` as
`high leak, high separation potential`: `inputs/review-observations.md` enumerated all three
expected findings verbatim, and the existing verifier only required keyword presence in the
candidate report.

### In-place hardening delta

| Path | Change |
|---|---|
| `inputs/review-observations.md` | deleted; this file enumerated all three oracle findings as bullet points |
| `inputs/task.md` | rewritten from a 3-line abstract framing to a full structured-table requirement with `\| # \| File \| Line \| Category \| Severity \| Title \| Evidence \|` header, per-column validation rules, allowed-category and allowed-severity enums, and a `## False Positives Avoided` discipline section — without enumerating any answer |
| `oracle/authz-trust-review-contract.json` | replaced `required_findings` keyword-term shape with tuple shape `{id, file, acceptable_lines[], category_terms[], severity, title_keywords[], required_evidence_terms[]}`; added `forbidden_findings[]` with title-keyword groups that trigger FAIL; added `exact_finding_count: 3`; removed `inputs/review-observations.md` from `required_bundle_paths`; preserved `required_false_positive_terms`, `prohibited_report_snippets`, `expected_gate_decision` |
| `oracle/expected-findings.md` | rewritten to tuple-table ground truth with `acceptable_lines` per finding; documents forbidden-finding keyword groups |
| `verifiers/check_authz_trust_review.py` | rewrote finding-check routine to parse `## Findings` markdown table, match each oracle tuple to at least one candidate row with `file == oracle.file`, `line in acceptable_lines`, exact severity, any category-term and any title-keyword match, and all required-evidence-terms substring-present in the `Evidence` cell; reject any row matching forbidden-finding keyword groups; enforce `len(rows) == exact_finding_count`; preserve `--bundle-shape-only` fast path |
| `candidate/review-report.md` | placeholder refreshed to the new structured-table schema |

### Oracle tuples (hardened contract)

| id | file | acceptable_lines | severity | category_terms | title_keywords | required_evidence_terms |
|---|---|---|---|---|---|---|
| F1 | `candidate/review-target/access-surface/grant_console.js` | `[2, 7]` | `high` | `[authz, privilege, role]` | `[query, role, escalation, client, reviewerrole, privileged]` | `[reviewerRole, params]` |
| F2 | `candidate/review-target/access-surface/grant_console.js` | `[27, 28, 29]` | `high` | `[trust, boundary, origin]` | `[parent, tenant, trust, boundary, message, postmessage]` | `[payload.trusted, effectiveTenant]` |
| F3 | `candidate/review-target/access-surface/grant_console.js` | `[15, 18, 19]` | `medium` | `[authz, replay, forward]` | `[replay, authority, forwarded, client, header]` | `[X-Reviewer-Role, tenantId]` |

Forbidden findings reject any candidate row whose title keywords include `policy.css`,
`opacity`, `cosmetic`, `css`, `disabled button`, `approve-grant disabled`, or `button disabled`.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse of `oracle/authz-trust-review-contract.json` | `PASS` (3 required_findings, 2 forbidden_findings, `exact_finding_count: 3`) |
| `--bundle-shape-only` on hardened bundle | `N06 verifier PASS (bundle shape)` |
| dry-run valid synthesized candidate at `.scratch/verifier-probes/2026-04-21-n06-hardened/` | `N06 verifier PASS (completed review report)` |
| dry-run variant A — wrong line (`F1 line=99`) | `FAIL` with `Oracle finding F1 has no matching candidate row ... acceptable_lines=[2, 7]` |
| dry-run variant B — over-count (4 findings) | `FAIL` with `Findings table row count mismatch: expected exactly 3, got 4` |
| dry-run variant C — forbidden trap (`policy.css opacity` in findings) | `FAIL` with `Finding row 3 title '...' matches forbidden trap (CSS decoration; no security impact)` and `Oracle finding F3 has no matching candidate row` |
| `git diff --check` | exit `0` |

One verifier bug was caught and fixed during the dry-run: `finding_matches_oracle` compared
`Evidence`-cell content without lowercasing, while `all_terms_in` applied `term.lower() in text`.
Mixed-case required terms (`reviewerRole`, `X-Reviewer-Role`) never matched. Fix: lowercase the
evidence cell before the term-presence check. Without the dry-run step, this bug would have
surfaced first as an apparent X1/X3 FAIL on legitimate output and been misread as a model signal.

### X1 and X3 Runs

| Row | Scratch root | Wrapper exit | Verifier | Binary read |
|---|---|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-21_19-33-37-X1-x1-n06-authz-tuple-hardening-retry2-2026-04-21/N06/` | `0` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-21_19-13-40-X3-x3-n06-authz-tuple-hardening-2026-04-21/N06/` | `0` | `PASS` | `1 / 1` |

### Candidate tuple reads

| Row | F1 line | F2 line | F3 line | F1 category | F2 category | F3 category | All severities match | Forbidden trap in findings | False-positive bullets |
|---|---:|---:|---:|---|---|---|---|---|---:|
| `X1` | `7` | `28` | `15` | `authz` | `trust-boundary` | `authz` | yes | no | `4` |
| `X3` | `2` | `28` | `15` | `authz` | `trust-boundary` | `authz` | yes | no | `3` |

All X1 and X3 tuples fall within the hardened `acceptable_lines` sets. The only observed delta
is the F1 line choice: `X1` cited line `7` (the first authorization decision using
`reviewerRole`), `X3` cited line `2` (the URL read of `reviewerRole`). Both sit in
`acceptable_lines: [2, 7]`. This is not a correctness difference. X1 and X3 diverged only on
false-positive bullet count (`X1: 4`, `X3: 3`) — X3's shorter list includes an adversarial
observation that `claims.allowAdminOverride` at line 7 is not a separate finding because it is
already subsumed under F1, which is a non-trivial anti-double-counting read.

### N06 Verdict

`binary tie remains` on the hardened N06 tuple-exact contract. Both near-ceiling models produce
legitimately correct tuples — the hardened verifier successfully blocks compliance-retelling
(without reading `grant_console.js` the candidate cannot reconstruct the `(file, line)` pairs),
but both `X1` and `X3` actually read the code and match the oracle. The ceiling at N06 is
honest; paraphrase of a deleted observation file is no longer the separation path.

### Runtime footnote (X1 attempt lineage)

The first X1 launch stalled on a `stdin` dead-lock when codex was started via
`run_in_background: true` inside the pwsh tool path — the background pipe held `stdin` open
and codex blocked on read. After ~17 minutes the process had accumulated `0.03s` total CPU
(versus typical multi-hundred-second CPU for real codex runs), confirming the hang. The
process was killed and relaunched through `cmd /c "pwsh -File ... < NUL"`, which forces
`stdin` to `NUL` and gives codex an immediate EOF. The third attempt completed in a few
minutes with the X1 PASS result above. This is a runtime invocation incompatibility between
the provider-direct codex path in `run-v2-cohort-batch.ps1 Invoke-CodexDirect` and the tool
harness's background stdin handling; it is not a model failure and is not a verifier failure.

### Post-Wave Decision

Because binary gates still tie on hardened N06, the next wave extends the same tuple-exact
template to additional review cells identified by the separator audit as `high leak, high
separation potential`:

- `S27-security-review-findings`
- `S28-performance-review-findings`
- `S29-accessibility-review-findings` (already partially hardened, but shares the
  `review-observations.md` leak pattern)
- `N05-secret-exposure-review`
- `N07-scalability-maintainability-cross-review`

Each of these retains the same `review-observations.md` answer-leak shape and the same
keyword-substring verifier today; each is structurally capable of surfacing X1/X3
separation once leak removal and tuple-exact checks are applied. The template is now
reusable: the JSON contract shape, verifier parsing logic, and dry-run protocol carry
over with only per-scenario oracle tuples to calibrate.

## 2026-04-21 Follow-Up: Wave 2 Tuple-Exact Hardening (S27, S28, S29, N05, N07)

After the `N06` pilot confirmed that the tuple-exact verifier blocks compliance-retelling but
does not separate near-ceiling models in isolation, the same template was applied in-place to
the remaining five `high leak, high separation potential` review cells identified by
`Evidence/separator-audit-2026-04-21.md`.

### Scope

| Scenario | Role | Severity anchors | Exact finding count | Leak file deleted |
|---|---|---|---|---|
| `S27` security-review-findings | security | `high/medium/low` | `3` | `inputs/review-observations.md` |
| `S28` performance-review-findings | performance | `high/medium/low` | `3` | `inputs/review-observations.md` |
| `S29` accessibility-review-findings | accessibility | `blocking/major/minor` | `5` | `inputs/keyboard-and-at-observations.md` |
| `N05` secret-exposure-review | security (exposure) | `high/medium/low` | `3` | `inputs/review-observations.md` |
| `N07` scalability-maintainability-cross-review | architecture / memory | `blocking/major/minor` | `3` | `inputs/review-observations.md` |

Total ground-truth tuples per model: `17` (`3+3+5+3+3`).

### In-place hardening delta (per scenario)

Every cell got the same five-file delta as `N06`: the answer-leak file was deleted; `inputs/task.md`
was rewritten to require a structured `## Findings` table without enumerating any answer; the
oracle contract JSON was rewritten with the tuple shape (`id`, `file`, `acceptable_lines`,
`severity`, `category_terms`, `title_keywords`, `required_evidence_terms`), plus
`forbidden_findings[]`, `exact_finding_count`, and allowed category and severity enums; the
oracle `expected-findings.md` was rewritten to match the new tuple ground truth; the scenario
verifier was rewritten to parse the findings markdown table and match tuples; the candidate
`review-report.md` placeholder was refreshed to the new schema.

### Verifier parser robustness fix

During pre-run dry-run, a synthesized valid candidate for `S27` failed because the Evidence
cell contained `targetOrigin || "*"` — the naive `|`-split produced `9` cells instead of `7`
and truncated the Evidence cell to just `targetOrigin` without `"*"`, which then failed the
required-evidence-terms check. The fix applied to all five wave-2 verifiers:

- `\|` inside a cell is now honored as an escape; a literal `\|` becomes `|` after parse.
- Rows whose cell count exceeds the header are folded: extra trailing cells are merged back
  into the last column with `" | "` as separator, so raw `||` inside the Evidence cell no
  longer breaks tuple matching.

This closes a real failure mode for real `X1`/`X3` reports that quote JS code containing `||`.
`N06` was not re-patched because its admitted PASS reports did not exercise the path; the
wave-2 verifiers are the forward-compatible version, and the same fix should be back-ported
to `N06` if the cell is ever re-run.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for all 5 new oracle contracts | `PASS` (3/3/5/3/3 required findings; 2/2/2/2/3 forbidden-finding groups) |
| `--bundle-shape-only` on all 5 hardened bundles | `PASS` for each (`S27 / S28 / S29 / N05 / N07 verifier PASS`) |
| dry-run synthesized valid candidate (first attempt) | `S27` failed on pipe-split bug; `S28` failed because my synthesis wrote `sorting once` instead of the required substring `sort once`; the other three passed |
| dry-run synthesized valid candidate (after parser fix + synthesis fix) | `PASS` for all 5 |
| `git diff --check` before launch | exit `0`; staged changes are limited to the wave-2 bundles and the wave-2 plan, audit, and evidence surfaces |

### X1 and X3 runs

`X3` ran all five scenarios in one sequential batch through `run-v2-cohort-batch.ps1 -RowId X3
-ScenarioIds S27,S28,S29,N05,N07`. `X1` ran each scenario as an independent parallel background
task, because the `cmd /c "pwsh -File ... -ScenarioIds S27,S28,S29,N05,N07"` invocation path
loses array-binding across the cmd boundary and pwsh `-File` mode sees the whole comma-joined
string as a single scenario id. Five separate `cmd /c "pwsh -File ... -ScenarioIds S27 < NUL"`
launches sidestep that issue and also preserve the `< NUL` stdin fix needed to avoid the
codex stdin dead-lock observed in `N06 X1` attempt 1.

| Row | S27 | S28 | S29 | N05 | N07 | Wave-2 subtotal |
|---|---|---|---|---|---|---:|
| `X1 / gpt-5.4` | `PASS` | `PASS` | `PASS` | `PASS` | `PASS` | `5 / 5` |
| `X3 / opus 4.7max` | `PASS` | `PASS` | `PASS` | `PASS` | `PASS` | `5 / 5` |

All ten runs: `wrapperExitCode = 0`, `verificationPassed = true`, changed paths strictly
`candidate/review-report.md`. Across the 17 ground-truth tuples per model, all 17 matched for
both `X1` and `X3`; no forbidden-finding rows appeared in either run set; all required
false-positive terms were mentioned in every `## False Positives Avoided` section.

### Wave-2 run roots

| Row | Run root |
|---|---|
| `X1 / S27` | `.scratch/v2-cohort-runs/2026-04-21_20-16-55-X1-wave2-s27-tuple-hardening-2026-04-21/S27/` |
| `X1 / S28` | `.scratch/v2-cohort-runs/2026-04-21_20-16-56-X1-wave2-s28-tuple-hardening-2026-04-21/S28/` |
| `X1 / S29` | `.scratch/v2-cohort-runs/2026-04-21_20-16-58-X1-wave2-s29-tuple-hardening-2026-04-21/S29/` |
| `X1 / N05` | `.scratch/v2-cohort-runs/2026-04-21_20-17-01-X1-wave2-n05-tuple-hardening-2026-04-21/N05/` |
| `X1 / N07` | `.scratch/v2-cohort-runs/2026-04-21_20-17-03-X1-wave2-n07-tuple-hardening-2026-04-21/N07/` |
| `X3 batch (all 5)` | `.scratch/v2-cohort-runs/2026-04-21_20-16-10-X3-wave2-tuple-hardening-2026-04-21/{S27,S28,S29,N05,N07}/` |

### Observed tuple deltas (binary gates tied; qualitative differences)

Binary gates tie on all five cells; qualitative review of the reports shows:

- `S27 F3` wildcard `postMessage`: `X1` cited line `9` in a single concise Evidence cell; `X3`
  cited line `9` and described lines `7`–`10` with explicit `||` JS snippet in a richer
  Evidence cell that exercised the parser pipe-escape fix.
- `S29 F3` focus-order: `X1` cited line `53` (the `tabindex="1"` on `Sharing policy`); `X3`
  cited line `22` (the `tabindex="2"` on the close button) and discussed both tabindex values
  together. Both lines are in `acceptable_lines = [22, 53]`.
- Across all five scenarios, `X3` reports carried richer Evidence prose, more `## False
  Positives Avoided` bullets (for example, `5` for `S29 X3` versus `2` for `S29 X1`), and more
  explicitly disciplined exclusions (for example, `S29 X3` explicitly excluded the
  visually-hidden `scope-hint` and the body-text contrast as non-findings, even though the
  verifier only required the two minimum false-positive mentions).

None of these qualitative deltas flip the binary gate. They are the same anti-double-counting
pattern first observed in `N06 X3`.

### Wave-2 Verdict

`binary tie remains` across all five hardened cells. Combined with the `N06` pilot, the
tuple-exact hardening template now covers `6` review cells in the core `12+1` surface, every
one of which is a legitimate `PASS` for both `X1` and `X3`. The hardening succeeded
structurally — the verifier rejects paraphrase-only candidates, because the candidate cannot
guess the real `(file, line)` tuples without actually reading the code — but the near-ceiling
separation was not broken by leak removal alone. Both models actually read the code and
produce correct tuples.

### Post-Wave-2 Options

With six near-ceiling-capable review cells now hardened and still tied, the next separator
direction should shift away from structured-review tasks. The separator audit flagged three
under-explored surface classes that could still separate near-ceiling models:

- **Harder tests inside the already-functional implementation scenarios** (`S15`–`S24`,
  `N08`–`N10`). They already run real `pytest` / `node --test` / JSON-equality checks, but
  near-ceiling models pass them reliably. Tightening the tests with more adversarial inputs
  or property-based checks could turn the functional bar into a binary separator.
- **Rebuilding `S06` analyst-repository-fact-memo** with fewer enumerated repo anchors. The
  audit classified it `high leak, high separation potential` and it sits in a different
  reasoning surface (multi-hop repository investigation, not single-file review); a rebuild
  without enumerated paths forces real slice investigation.
- **A new multi-file code patch scenario** with hidden dependency coupling and tuple-exact
  `(file, line, category)` findings on adversarial decoy defects. No current cell exercises
  that surface.

These are strategic choices, not part of wave 2. They are the next admission decision for the
operator.

## 2026-04-21 Follow-Up: Wave 3 S06 Tuple-Exact Hardening (Repository Investigation)

With the six review cells now hardened and still tied, wave 3 applied the tuple-exact template
to `S06 analyst-repository-fact-memo` — a different reasoning surface (multi-hop repository
investigation instead of structured review). The separator audit had classified `S06` as
`high leak, high separation potential` on different grounds from the review-class cells:
`S06` has no answer-leak file enumerating findings, but `inputs/noisy-intake-notes.md`
directly named three of the four false-lead files (`legacy-routing-notes.md`,
`legacy_score_profiles.py`, `role_matrix.yaml`), and the previous verifier used
keyword-substring matching across a 12-section prose memo with a fixed list of required
anchor paths.

### In-place hardening delta

| Path | Change |
|---|---|
| `inputs/noisy-intake-notes.md` | rewritten to five abstract themes with no filenames — the candidate must discover the actual files through investigation rather than copy names from the notes |
| `inputs/task.md` | rewritten to require three structured tables (`## Confirmed Facts`, `## False Leads Rejected`, `## Explicit Unknowns`) with per-column rules and no answer enumeration |
| `oracle/fact-contract.json` | replaced keyword-substring shape with tuple shape for three match tables: `required_confirmed_facts[]` with `{id, question_values, file, acceptable_lines, symbol_keywords, fact_terms}`; `required_false_leads[]` with `{id, theme_keywords, file, rejection_terms}`; `required_unknowns[]` with `{id, term_keywords, why_terms}`; plus exact counts; preserved disallowed markers/headings; preserved `expected_gate_decision: PASS` |
| `oracle/expected-findings.md` | rewritten to tuple-table ground truth mirroring the new contract |
| `verifiers/check_factual_memo.py` | rewrote `check_completed_memo` to parse all three tables (reusing the wave-2 `\|` escape and trailing-cells merge parser), match each oracle tuple against one distinct candidate row, enforce exact counts, preserve `--bundle-shape-only` |
| `candidate/repository-fact-memo.md` | placeholder refreshed to the new three-table schema with `## Investigation goal` header |
| `candidate/repo-snapshot/**` | unchanged — preserves the real codebase the memo investigates |

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse of `oracle/fact-contract.json` | `PASS` (4 confirmed facts, 4 false leads, 2 unknowns) |
| `--bundle-shape-only` on hardened bundle | `S06 verifier PASS (bundle shape)` |
| dry-run valid synthesized memo (first attempt) | `L3` failed because my synthesis used `scenario metadata` instead of the required substring `scenario.yaml` |
| dry-run valid synthesized memo (after wording fix) | `S06 verifier PASS (completed factual memo)` |

The `L3` miss exercised the intended signal: the oracle insists on `scenario.yaml` as a literal
substring because citing that filename is direct evidence the reviewer looked at
`collect_scenarios.py:13`'s `glob("*/scenario.yaml")` rather than hand-waving about
"metadata". A model that only reads the abstract `noisy-intake-notes.md` cannot produce that
substring without investigating `candidate/repo-snapshot/`.

### X1 and X3 runs

| Row | Run root | Wrapper exit | Verifier | Binary read |
|---|---|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-21_20-56-02-X1-wave3-s06-tuple-hardening-2026-04-21/S06/` | `0` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-21_20-56-04-X3-wave3-s06-tuple-hardening-2026-04-21/S06/` | `0` | `PASS` | `1 / 1` |

Both models produced the four correct confirmed facts with correct `(file, line, symbol)`
tuples, the four correct false leads mapped to the real repo-snapshot files, and the two
correct unknowns — despite the abstract `noisy-intake-notes.md` giving them no filenames.
Both investigated `candidate/repo-snapshot/` to locate each piece of evidence.

### Candidate tuple reads (X1 vs X3)

| Section | X1 | X3 | Notes |
|---|---|---|---|
| `F1` line | `15` | `13` | both in `acceptable_lines = [7, 13, 15, 19]` |
| `F2` line | `15` | `15` | same |
| `F3` line | `21` | `21` | same |
| `F4` line | `5` | `5` | same |
| False-lead file mapping | all 4 correct | all 4 correct | identical file set |
| Unknown `U1` phrasing | `Requested surface caller` | `Upstream caller or scheduler CLI entrypoint supplying the requested surface id` | `X3` cell is more specific; both match |
| Unknown `U2` phrasing | `External publication runtime logs` | `Other consumer of the legacy profile module outside the visible writer` | different emphasis; both match |

`X3` wrote longer and more structured prose across `Investigation goal`, fact and rejection
cells; `X1` wrote compact cells. Same qualitative pattern as `N06` and wave 2 — richer
anti-double-counting and richer evidence prose on `X3`. None of the deltas flip the binary
gate.

### S06 Verdict

`binary tie remains` on hardened `S06`. Combined with the `N06` pilot and wave 2's five cells,
seven near-ceiling-capable cells are now tuple-exact hardened and every one of them
legitimately ties PASS/PASS. The hardening successfully rules out the compliance-retelling
path on both review-class and factual-investigation surfaces, but near-ceiling separation is
not unlocked by leak removal on either surface class.

### Post-Wave-3 Options

The two remaining surface classes that could plausibly separate near-ceiling models are:

- **Harder tests inside the already-functional implementation scenarios** (`S15`–`S24`,
  `N08`–`N10`). They already run real `pytest` / `node --test` / JSON-equality checks and both
  models pass them reliably. Tightening the tests with adversarial inputs or property-based
  checks could turn the functional bar into a binary separator.
- **A new multi-file code patch scenario** with hidden dependency coupling and tuple-exact
  `(file, line, category)` findings on adversarial decoy defects. No current cell exercises
  that surface.

Seven hardened cells now form a stable `compliance-retelling-resistant anchor set` inside the
`12+1` baseline — they do not separate the top pair, but they are honest about why they do
not, and they are the correct cells to retain in any final publication as ceiling-legitimacy
indicators.

## 2026-04-21 Follow-Up: Wave 4 S22 Adversarial Geometry Hardening

Wave 4 tested the cheapest remaining separator path after review-class and factual-investigation
hardening both tied: functional test tightening inside an existing implementation cell.
`S22 geometry-predicate-patch` was selected because its verifier already evaluates a deterministic
truth-table oracle (`orientation_cases[]` and `segment_cases[]`) against real candidate code.

### In-place hardening delta

| Path | Change |
|---|---|
| `Scenarios-v2/S22-geometry-predicate-patch/oracle/truth-table.json` | added 12 adversarial geometry cases: 6 orientation cases and 6 segment-intersection cases; total oracle coverage is now 23 cases (`11` orientation, `12` segment) |
| `Scenarios-v2/S22-geometry-predicate-patch/oracle/geometry-contract.json` | updated `expected_start_state_failures` from 3 to 7 so `--expect-start-state` remains coherent after the oracle extension |
| `candidate/**` | unchanged in the mainline bundle; dry-run valid implementation was synthesized only under `.scratch/verifier-probes/2026-04-21-s22-adversarial/` |

### Added adversarial cases

| Class | Case IDs | Purpose |
|---|---|---|
| orientation | `degenerate-duplicate-start`, `small-scale-near-collinear-negative` | degenerate triangle and near-zero signed-area collapse |
|  | `small-scale-not-collinear`, `large-scale-near-collinear-negative` | distinguish fixed global epsilon from scale-aware area tolerance |
|  | `right-handed-swapped-negative`, `large-scale-left-handed-not-collinear` | preserve right-handed sign convention and left-handed negative orientation |
| segment | `zero-length-point-on-segment`, `zero-length-point-near-segment-end` | point/zero-length segment boundary contact, including coordinate tolerance at endpoint |
|  | `zero-length-point-outside-tolerance`, `near-endpoint-diagonal-outside-tolerance` | prevent tolerance inflation from turning clearly outside points into intersections |
|  | `near-endpoint-diagonal-within-tolerance`, `shared-endpoint-reversed-boundary` | span-scaled endpoint tolerance and reversed shared-endpoint boundary contact |

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse of `oracle/truth-table.json` | `PASS` (`11` orientation cases, `12` segment cases) |
| JSON parse of `oracle/geometry-contract.json` | `PASS` (`7` expected start-state failures) |
| `python Scenarios-v2/S22-geometry-predicate-patch/verifiers/run_geometry_checks.py --bundle-shape-only` | `S22 verifier PASS (bundle shape)` |
| `python Scenarios-v2/S22-geometry-predicate-patch/verifiers/run_geometry_checks.py --expect-start-state` | `S22 verifier PASS (start state)` |
| dry-run valid synthesized candidate at `.scratch/verifier-probes/2026-04-21-s22-adversarial/S22/` | `S22 verifier PASS (completed run)` |
| `git diff --check` before launch | exit `0` |

The synthesized dry-run implementation used the oracle tolerance formulas directly:
`base_area_epsilon * max(|ab|^2, |ac|^2, |bc|^2, 1.0)` for orientation and
`base_coordinate_epsilon * max(abs(dx), abs(dy), 1.0)` for on-segment bounds. This confirmed the
new oracle cases are internally consistent and not over-tightened.

### X1 and X3 runs

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-21_21-38-17-X1-wave4-s22-adversarial-geometry-2026-04-21/S22/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-21_21-38-16-X3-wave4-s22-adversarial-geometry-2026-04-21/S22/` | `0` | `PASS` | `PASS` | `1 / 1` |

Launch notes:

- `X1` used the admitted stdin-safe pattern:
  `cmd /c "pwsh -ExecutionPolicy Bypass -File ...run-v2-cohort-batch.ps1 -RowId X1 -BatchName wave4-s22-adversarial-geometry-2026-04-21 -ScenarioIds S22 < NUL"`.
- `X3` used direct PowerShell invocation:
  `& "...run-v2-cohort-batch.ps1" -RowId X3 -BatchName wave4-s22-adversarial-geometry-2026-04-21 -ScenarioIds S22`.
- `X4` and `X5` were intentionally `NOT-RUN` for this pilot; their route/runtime caveats remain unchanged as of `2026-04-21`.

### Truth-table reads

| Row | Orientation cases | Segment cases | Total truth cases | Verifier failures |
|---|---:|---:|---:|---:|
| `X1 / gpt-5.4` | `11 / 11` | `12 / 12` | `23 / 23` | `0` |
| `X3 / opus 4.7max` | `11 / 11` | `12 / 12` | `23 / 23` | `0` |

Both models repaired the same underlying defect class: fixed absolute epsilon was replaced by a
scale-aware signed-area tolerance for `orientation`, and `on_segment` gained segment-span coordinate
tolerance. Both changed only the two allowed benchmark paths:

- `candidate/geometry-owned/src/geometry/predicates.py`
- `candidate/geometry-owned/tests/test_predicates.py`

Qualitative delta: `X1` produced a compact implementation and 4 direct tests; `X3` separated
area and coordinate constants more explicitly and produced 20 direct tests. The oracle verifier
does not score direct-test breadth, and both candidate implementations matched every truth-table
case. This is not a binary correctness difference.

### S22 Verdict

`binary tie remains` on hardened `S22`. The adversarial geometry extension closed additional
near-miss functional paths, but both near-ceiling models solved the tolerance policy correctly.
This means the cheapest remaining functional-test pilot did not produce an honest binary
separator.

### Next-session handoff

Because `S22` tied after adversarial functional tightening, the next admitted separator route is
Option (c): a net-new multi-file code patch scenario. Suggested next-session prompt:

```text
Working directory: D:\dev\Orchestrator\benchmarks

Continue X1/X3 separation after Wave 4. Do not touch the admitted anchor set
N06/S27/S28/S29/N05/N07/S06 or the hardened S22 oracle unless explicitly requested.

Current result: Wave 4 S22 adversarial geometry hardening added 12 truth-table cases,
validated the extended oracle with a synthesized correct candidate, then ran X1 and X3.
Both wrapperExitCode=0, both verifier PASS, both 23/23 truth cases; binary tie remains.

Next task: design Option (c), a new multi-file code patch scenario that tests cross-file
dependency reasoning with real defects and adversarial decoy defects. Keep it as a new
scenario root rather than mutating review-class/factual-investigation cells. The design
should specify candidate/review-target files, real defect tuples, forbidden decoys,
verifier shape, pre-run protocol, and expected X1/X3 separator hypothesis.
```

## 2026-04-21 Follow-Up: Option (c) N14 Multi-file Dependency Patch

Option (c) materialized a new implementation scenario instead of further tightening the tied
review/factual/geometry surfaces. `N14 multi-file-dependency-patch` tests whether a model can fix
one coupled behavior across profile resolution, attempt classification, score denominators, and
report rendering while ignoring plausible but forbidden decoy files.

### Scenario materialization

| Path | Change |
|---|---|
| `Scenarios-v2/N14-multi-file-dependency-patch/scenario.yaml` | new `N14` scenario on diagnostic surface `E4`; role class `implementation`; allowed change surface restricted to four source files and one test file |
| `inputs/task.md` and `inputs/decoy-map.md` | task asks for a real multi-file patch and names decoy regions that must not be edited |
| `candidate/workspace/src/routing_eval/` | buggy start state spans `config.py`, `status.py`, `scorecard.py`, and `render.py`; `api.py` is intentionally protected |
| `candidate/workspace/docs/`, `legacy/`, `ui/` | adversarial decoys for stale profile advice, legacy denominator logic, and UI-label wording |
| `oracle/behavior-cases.json` | 3 behavior cases covering active-profile precedence, route-unavailable rows, wrapper-zero verifier failures, timeouts, and missing worker output |
| `verifiers/check_multi_file_dependency_patch.py` | completed-run oracle verifier with exact JSON-equality against the three behavior cases and hardcoded-oracle-literal guards |
| `verifiers/check_scope.py` | scope guard for benchmark changed paths |

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse of `oracle/behavior-cases.json` | `PASS` (`3` cases) |
| JSON parse of `oracle/multi-file-contract.json` | `PASS` (`3` expected start-state failures) |
| `python Scenarios-v2/N14-multi-file-dependency-patch/verifiers/check_multi_file_dependency_patch.py --bundle-shape-only` | `N14 verifier PASS (bundle shape)` |
| `python Scenarios-v2/N14-multi-file-dependency-patch/verifiers/check_multi_file_dependency_patch.py --expect-start-state` | `N14 verifier PASS (start state)` |
| direct start-state unit tests | expected failing start state: existing candidate still fails before patching |
| dry-run valid synthesized candidate at `.scratch/verifier-probes/2026-04-21-n14-multifile-reference/N14/` | `N14 verifier PASS (completed run)` |
| `python Scenarios-v2/N14-multi-file-dependency-patch/verifiers/check_scope.py --bundle-root .scratch/verifier-probes/2026-04-21-n14-multifile-reference/N14 --changed-path ...` | `N14 scope PASS (changed paths are in bounds)` |
| `git diff --check` before launch | exit `0` |

### X1 and X3 runs

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-21_22-08-32-X1-optionc-n14-multifile-dependency-2026-04-21/N14/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-21_22-08-32-X3-optionc-n14-multifile-dependency-2026-04-21/N14/` | `0` | `PASS` | `PASS` | `1 / 1` |

Both summaries are scoreable: `verificationPassed=true`; `python check_multi_file_dependency_patch.py`
exited `0`; `python check_scope.py` exited `0`.

### Behavior-case reads

| Row | Behavior cases | Source/code paths changed | Test path changed | Verifier failures |
|---|---:|---|---|---:|
| `X1 / gpt-5.4` | `3 / 3` | `config.py`, `status.py`, `scorecard.py`, `render.py` | yes | `0` |
| `X3 / opus 4.7max` | `3 / 3` | `config.py`, `status.py`, `scorecard.py`, `render.py` | no | `0` |

Qualitative delta: `X1` made the broader local patch by also extending `tests/test_routing_eval.py`
to four tests and used a slightly richer runtime-reason normalization helper. `X3` left the tests
unchanged and produced a more compact source-only patch. Both matched all three oracle behavior
cases and stayed inside the allowed benchmark paths, so this is not a binary correctness difference.

`X1` worker output included unrelated Cloudflare/plugin fetch noise before its final patch summary;
the admitted result uses `summary.json` and verifier logs, not free-form stdout, as the scoreable
source of truth.

### Calibration rows

After the `X1`/`X3` top-pair read, calibration rows were launched on the same `N14` bundle.

| Row | Run root | Wrapper / tool status | Verifier | Scope guard | Binary read |
|---|---|---|---|---|---:|
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-21_22-20-40-X2-optionc-n14-calibration-2026-04-21/N14/` | wrapper `0` | `FAIL` | `PASS` | `0 / 1` |
| `X5 / gemini3.1pro` | `.scratch/v2-cohort-runs/2026-04-21_22-20-39-X5-optionc-n14-calibration-2026-04-21/N14/` | shell timeout `900s` | not invoked | no summary | `0 / 0` |
|  | `.scratch/v2-cohort-runs/2026-04-21_22-37-36-X5-optionc-n14-calibration-stdin-null-2026-04-21/N14/` | shell timeout `600s` | not invoked | no summary | `0 / 0` |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-21_22-20-39-X6-optionc-n14-calibration-2026-04-21/N14/` | shell timeout `900s` | not invoked | no summary | `0 / 0` |
|  | `.scratch/v2-cohort-runs/2026-04-21_22-37-36-X6-optionc-n14-calibration-stdin-null-2026-04-21/N14/` | shell timeout `600s` | not invoked | no summary | `0 / 0` |

`X2` is a scoreable verifier failure, not runtime: `summary.json` exists,
`wrapperExitCode=0`, `worker-output.txt` exists, benchmark changed paths were in bounds, and the
scope guard passed. The verifier failed with:

```text
ERROR: Top-level bundle entries drifted: ['.reports', 'README.md', 'candidate', 'inputs', 'oracle', 'scenario.yaml', 'verifiers']
```

The worker wrote a disposable-run `.reports/2026-04/report-implementation-2026-04-21_22-20-40-N14-X2-row.md`
inside the bundle. That extra top-level entry is enough to fail the N14 bundle-shape contract even
though the model also patched the intended source/test files.

`X5` and `X6` are not scoreable on `N14` in this calibration attempt. Direct PowerShell launch and
stdin-null retry both reached Gemini CLI processes with `--prompt=` but produced no
`worker-output.txt`, no `summary.json`, and no verifier logs before timeout. The leftover Gemini
`cmd`/`node`/`pwsh` processes for both batch IDs were stopped after timeout. This is recorded as
runtime `NOT-RUN`, not model `FAIL`.

### N14 Verdict

`binary tie remains` on `N14`. The new multi-file dependency scenario is a valid hardened cell and
it closed a more implementation-shaped surface than the review/factual/geometry pilots, but it did
not separate `X1` and `X3` by binary verification.

Calibration does separate `X2` lower (`0 / 1`) and leaves Gemini rows runtime-blocked (`0 / 0`
scoreable). The remaining top-pair decision is to design a materially harder implementation surface
with stateful sequencing, larger owned code, and hidden mutation/order coupling. Do not count
qualitative test breadth as a separator unless the verifier or rubric is explicitly upgraded to
score it.

## 2026-04-21 Follow-Up: N15 Stateful System Gauntlet

After `N14` still tied the top pair, the separator surface was changed more radically instead of
adding more small cases. `N15-stateful-batch-rollback-gauntlet` materializes a stateful execution
system with journal, checkpoint, retry, rollback, planner, executor, report, and in-memory store
ownership boundaries.

### Scenario materialization

| Path | Change |
|---|---|
| `Work/next-upgraded-pack/Planning/next-phase/n15-stateful-gauntlet-design-2026-04-21.md` | compact approved design note for the new stateful gauntlet |
| `Scenarios-v2/N15-stateful-batch-rollback-gauntlet/scenario.yaml` | new diagnostic `E5` implementation scenario with `top-pair-separator` and `stateful-gauntlet` flags |
| `candidate/workspace/src/batchflow/` | 10-file Python package: protected public API plus owned state machine modules |
| `candidate/workspace/docs/`, `legacy/`, `ui/` | protected decoys for stale rollback advice, sorted retry archives, and UI-only status labels |
| `oracle/stateful-contract.json` | exact bundle metadata, allowed surfaces, prohibited literals, and calibrated start-state failure set |
| `verifiers/check_stateful_batch_gauntlet.py` | deterministic sequence verifier covering 9 stateful invariants |
| `verifiers/check_scope.py` | changed-path scope guard |

The verifier pressure is materially different from `N14`: it checks behavior across repeated API
calls, not one local output. Covered invariants include input immutability, causal plan order,
idempotent completed reruns, per-batch checkpoint isolation, crash resume, current-attempt rollback,
retry queue causal order, global journal sequence, and event-log based reporting.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse of `oracle/stateful-contract.json` | `PASS` |
| `python Scenarios-v2/N15-stateful-batch-rollback-gauntlet/verifiers/check_stateful_batch_gauntlet.py --bundle-shape-only` | `N15 verifier PASS (bundle shape)` |
| `python Scenarios-v2/N15-stateful-batch-rollback-gauntlet/verifiers/check_stateful_batch_gauntlet.py --expect-start-state` | `N15 verifier PASS (start state)` |
| direct start-state unit tests | expected failing start state: `2` visible failures before patching |
| scratch reference at `.scratch/verifier-probes/2026-04-21-n15-stateful-reference/N15/` | `N15 verifier PASS (completed run)` |
| scratch reference scope guard | `N15 scope PASS (changed paths are in bounds)` |
| `git diff --check` before launch | exit `0` |

The start-state failure set is calibrated, not accidental: the supplied candidate fails state
mutation/order/checkpoint/rollback/retry/report invariants while the scratch reference passes the
full verifier.

### X1 and X3 runs

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-21_23-07-21-X1-n15-stateful-gauntlet-2026-04-21/N15/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-21_23-07-21-X3-n15-stateful-gauntlet-2026-04-21/N15/` | `0` | `PASS` | `PASS` | `1 / 1` |

`X1` exceeded the outer shell timeout at `1204s`, but the underlying Codex process was still
actively writing output and later produced `summary.json` with `wrapperExitCode=0` and
`verificationPassed=true`. The admitted result is therefore the runner summary and verifier logs,
not the outer shell timeout.

### Invariant reads

| Row | Stateful invariant suite | Benchmark paths changed | Tests changed | Verifier failures |
|---|---:|---|---|---:|
| `X1 / gpt-5.4` | `9 / 9` | 7 source files | yes | `0` |
| `X3 / opus 4.7max` | `9 / 9` | 7 source files | no | `0` |

Both models repaired the core ownership boundaries:

- planner copies without mutating or reordering caller input
- journal sequence is global
- checkpoints are keyed by `batch_id`
- retry queue preserves arrival order
- rollback is attempt-scoped
- executor rewinds checkpoint after rolled-back failed attempt
- report derives summary counts from journal events

Qualitative delta: `X1` added broader local regression tests and took materially longer; `X3`
produced a compact source-only patch. The binary verifier does not score runtime duration or
test breadth, and both candidates matched the full stateful invariant suite.

### N15 Verdict

`binary tie remains` on `N15`. This was a real step-change in task class, not incremental
hardening, and both top models still passed. The current evidence says binary patch/verifier tasks
may no longer be a productive way to separate `X1` and `X3` unless the next task adds a larger
long-horizon planning surface, hidden-scale system integration, or a non-binary quality rubric.

## 2026-04-22 Follow-Up: N16 Long-Horizon Integration Rubric

After `N15` still tied the top pair, the separator surface moved from binary-only patch success to
a larger long-horizon integration task plus a separate diagnostic rubric.
`N16-release-lane-integration-gauntlet` materializes a release-lane execution package with config,
intake, dedupe, planning, scheduling, ledger, notification, rollback, audit, report, executor, and
store seams.

### Scenario materialization

| Path | Change |
|---|---|
| `Work/next-upgraded-pack/Planning/next-phase/n16-long-horizon-integration-rubric-design-2026-04-22.md` | compact design note for the long-horizon integration task and score layer |
| `Scenarios-v2/N16-release-lane-integration-gauntlet/scenario.yaml` | new diagnostic `E6` implementation scenario with `top-pair-separator`, `long-horizon`, and `scored-rubric` flags |
| `candidate/workspace/src/releaseflow/` | multi-module Python package with protected public API/models and eleven editable implementation seams |
| `candidate/workspace/docs/`, `legacy/`, `ui/` | protected decoys for migration advice, stale dedupe helper, and UI-only badge changes |
| `oracle/integration-contract.json` | exact bundle metadata, allowed surfaces, prohibited literals, and calibrated start-state failure set |
| `verifiers/check_release_lane_integration.py` | deterministic integration verifier covering 10 long-horizon invariants |
| `verifiers/check_scope.py` | changed-path scope guard |
| `Work/next-upgraded-pack/Tooling/score-n16-integration-rubric.py` | post-run scorer for correctness, patch quality, elapsed proxy, and output-size cost proxy |
| `Work/next-upgraded-pack/Evidence/n16-long-horizon-rubric-2026-04-22.json` | machine-readable score output for the admitted `X1` and `X3` runs |

Covered invariants include active profile precedence, caller input immutability, semantic dedupe
idempotency, dependency order, canary-before-prod order, frozen lane deferral, exactly-once
notifications, rollback scoping, source trace preservation, and ledger/audit-based reporting.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse of `oracle/integration-contract.json` | `PASS` |
| `python Scenarios-v2/N16-release-lane-integration-gauntlet/verifiers/check_release_lane_integration.py --bundle-shape-only` | `N16 verifier PASS (bundle shape)` |
| `python Scenarios-v2/N16-release-lane-integration-gauntlet/verifiers/check_release_lane_integration.py --expect-start-state` | `N16 verifier PASS (start state)` |
| direct start-state unit tests | expected failing start state: `4` visible failures before patching |
| scratch reference at `.scratch/verifier-probes/2026-04-22-n16-integration-reference/N16/` | `N16 verifier PASS (completed run)` |
| scratch reference direct unit tests | `Ran 4 tests ... OK` |
| scratch reference scope guard | `N16 scope PASS (changed paths are in bounds)` |
| scorer missing-summary smoke | `NOT-RUN` row with total `0` |
| `git diff --check` before launch | exit `0` |

### X1 and X3 runs

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-22_00-33-10-X1-n16-long-horizon-integration-2026-04-22/N16/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-22_00-33-09-X3-n16-long-horizon-integration-2026-04-22/N16/` | `0` | `PASS` | `PASS` | `1 / 1` |

Both rows are scoreable: `summary.json` exists, `wrapperExitCode=0`, `verificationPassed=true`,
the integration verifier passed, and the scope guard passed.

### Rubric read

| Row | Binary | Rubric | Correctness | Patch quality | Time | Cost | Elapsed proxy | Output bytes | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `X1 / gpt-5.4` | `PASS` | `89 / 100` | `40` | `30` | `15` | `4` | `338.689s` | `393174` | changed 12 benchmark paths, including tests; `173` added, `29` deleted |
| `X3 / opus 4.7max` | `PASS` | `95 / 100` | `40` | `25` | `15` | `15` | `502.532s` | `2829` | changed 11 benchmark paths, tests unchanged; `99` added, `25` deleted |

The rubric is diagnostic, not a replacement for the binary gate. It separates on cost/compactness:
`X3` wins the admitted N16 rubric by `6` points because it produced a much smaller worker output
while still passing the full integration verifier. `X1` receives the stronger patch-quality score
because it changed tests in addition to source.

### N16 Verdict

`binary tie remains` on `N16`, but the non-binary scored read gives a measurable `X3` diagnostic
edge on long-horizon integration efficiency: `95 / 100` versus `89 / 100`. This should be kept as
an `E6` diagnostic rubric result, not merged into the old full-v2 denominator and not promoted into
a routing lane without an explicit scoring-policy decision.

## 2026-04-22 Follow-Up: N17 Owner Orchestration Routing Rubric

After the first role-fit scorecard identified owner/orchestration as an evidence gap,
`N17-owner-orchestration-routing-gauntlet` was added as diagnostic `E7`. It tests whether a row can
preserve the primary lane-fit task, classify interruptions, keep diagnostic evidence separate from
routing policy, order owner/QA/architecture gates correctly, and define bounded `X2`/`X5`/`X6`
calibration policy.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse of `oracle/owner-routing-contract.json` | `PASS` |
| `python Scenarios-v2/N17-owner-orchestration-routing-gauntlet/verifiers/check_owner_routing.py --bundle-shape-only` | `N17 verifier PASS (bundle shape)` |
| `python Scenarios-v2/N17-owner-orchestration-routing-gauntlet/verifiers/check_owner_routing.py --expect-start-state` | `N17 verifier PASS (start state)` |
| scorer missing-summary smoke | `NOT-RUN` row with total `0` |
| scratch reference at `.scratch/verifier-probes/2026-04-22-n17-owner-reference/N17/` | `N17 verifier PASS (completed packet)` |
| scratch reference scope guard | `N17 scope PASS (changed paths are in bounds)` |
| `git diff --check` before launch | exit `0` |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-22_01-37-48-X1-n17-owner-routing-2026-04-22/N17/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-22_01-37-48-X3-n17-owner-routing-2026-04-22/N17/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-22_01-40-22-X2-n17-owner-routing-calibration-2026-04-22/N17/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-22_01-43-32-X6-n17-owner-routing-calibration-2026-04-22/N17/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X5 / gemini3.1pro` | `.scratch/gemini-smoke-n17-2026-04-22/` | timeout `180s` | not launched | no semantic run | `NOT-RUN` |

`X5` stayed out of the semantic N17 run because the required direct smoke did not write
`x5-output.txt` before timeout. `X6` smoke wrote `OK` and was admitted for semantic calibration.

### Rubric read

| Row | Binary | Rubric | Primary | Diagnostic | Routing | Calibration | Interruptions | Elapsed proxy | Output bytes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `X1 / gpt-5.4` | `PASS` | `100 / 100` | `20` | `20` | `20` | `20` | `20` | `121.745s` | `97344` |
| `X3 / opus 4.7max` | `PASS` | `100 / 100` | `20` | `20` | `20` | `20` | `20` | `116.485s` | `1965` |
| `X2 / gpt-5.3-codex-spark` | `PASS` | `100 / 100` | `20` | `20` | `20` | `20` | `20` | `33.741s` | `81627` |
| `X6 / gemini3.1flash-lite-preview` | `PASS` | `100 / 100` | `20` | `20` | `20` | `20` | `20` | `58.275s` | `977` |

### N17 Verdict

`binary tie remains` on owner/orchestration routing; the exact owner-boundary task is not a
top-pair separator. However, it is useful for role-fit calibration: `X1`, `X3`, `X2`, and `X6` can
all preserve the required owner routing boundaries on this constrained packet. The strongest
non-binary signal is again output compactness: `X3` and `X6` are far smaller than `X1` and `X2`.
`X5` remains runtime-blocked for this pilot and is not a model failure.

## 2026-04-22 Follow-Up: N18 Scientist Constraints Decision Rubric

`N18-scientist-constraints-decision-gauntlet` was added as diagnostic `E8` for the
scientist/constraint lane. It forces a release decision across conflicting security,
performance, reliability, and stale-advice evidence. The correct answer is `Option C - keyed index
plus exact ledger replay`; candidates must reject faster-looking but inadmissible options, preserve
exact measured values, write a non-claim ledger, define falsification checks, and assign residual
risk owners.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse of `oracle/constraint-contract.json` | `PASS` |
| `python Scenarios-v2/N18-scientist-constraints-decision-gauntlet/verifiers/check_constraint_decision.py --bundle-shape-only` | `N18 verifier PASS (bundle shape)` |
| `python Scenarios-v2/N18-scientist-constraints-decision-gauntlet/verifiers/check_constraint_decision.py --expect-start-state` | `N18 verifier PASS (start state)` |
| scratch reference at `.scratch/verifier-probes/2026-04-22-n18-constraints-reference/N18/` | `N18 verifier PASS (completed memo)` |
| scratch reference scope guard | `N18 scope PASS` |
| scorer missing-summary smoke | `NOT-RUN` row with total `0` |
| `git diff --check` before launch | exit `0` |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-22_02-09-59-X1-n18-scientist-constraints-2026-04-22/N18/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-22_02-09-59-X3-n18-scientist-constraints-2026-04-22/N18/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-22_02-14-52-X2-n18-scientist-constraints-calibration-2026-04-22/N18/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-22_02-14-51-X6-n18-scientist-constraints-calibration-2026-04-22/N18/` | `1` | `FAIL` | `PASS` | `ROUTE-FAIL` |
| `X5 / gemini3.1pro` | `.scratch/v2-cohort-runs/2026-04-22_02-50-07-X5-n18-scientist-constraints-calibration-2026-04-22-rerun/N18/` | timeout `900s` | no summary | no semantic output | `NOT-RUN` |

`X5` direct smoke first wrote `X5_SMOKE_OK` with exit `0`, so a semantic run was admitted. The
semantic run then timed out at `900s` without `summary.json` or `worker-output.txt`, so it remains
runtime `NOT-RUN`, not a model failure. `X6` produced a partial candidate but the Gemini CLI route
hit missing `run_shell_command` tool errors and `AbortError`; it is recorded as `ROUTE-FAIL`, with
partial artifact rubric retained only as a diagnostic.

### Rubric read

| Row | Binary | Scoreability | Rubric | Decision | Evidence | Non-claim | Falsification | Risk | Elapsed proxy | Output bytes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `100 / 100` | `20` | `20` | `20` | `20` | `20` | `124.214s` | `93786` |
| `X3 / opus 4.7max` | `PASS` | `scoreable` | `100 / 100` | `20` | `20` | `20` | `20` | `20` | `181.701s` | `2122` |
| `X2 / gpt-5.3-codex-spark` | `PASS` | `scoreable` | `100 / 100` | `20` | `20` | `20` | `20` | `20` | `36.402s` | `67739` |
| `X6 / gemini3.1flash-lite-preview` | `ROUTE-FAIL` | `runtime-route` | `60 / 100` | `20` | `0` | `20` | `20` | `20` | `46.079s` | `1579` |
| `X5 / gemini3.1pro` | `NOT-RUN` | `runtime-no-summary` | `0 / 100` | `0` | `0` | `0` | `0` | `0` | `n/a` | `n/a` |

### N18 Verdict

`binary tie remains` for `X1` and `X3` on scientist/constraint reasoning. The lane-fit signal is
style/cost rather than correctness: `X3` gives the same scoreable `100 / 100` with a much smaller
output footprint, while `X1` is also correct and more verbose. `X2` unexpectedly passes this
bounded scientist packet and should stay as cheap calibration, not primary routing evidence. `X6`
and `X5` remain runtime-route caveats for this lane.

## 2026-04-22 Follow-Up: N19 Systems Toolchain Rubric

`N19-systems-toolchain-cache-gauntlet` was added as diagnostic `E9` for the
systems/toolchain lane. It tests profile/env precedence, cross-platform build-root validation,
portable cache keys, dependency ordering, feature-conflict rejection, cache-hit reporting, source
trace, and lock cleanup after failure.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse of `oracle/toolchain-contract.json` | `PASS` |
| `python Scenarios-v2/N19-systems-toolchain-cache-gauntlet/verifiers/check_toolchain_systems.py --bundle-shape-only` | `N19 verifier PASS (bundle shape)` |
| `python Scenarios-v2/N19-systems-toolchain-cache-gauntlet/verifiers/check_toolchain_systems.py --expect-start-state` | `N19 verifier PASS (start state)` |
| local start-state unit tests from `candidate/workspace` | expected `3` failing tests |
| scratch reference at `.scratch/verifier-probes/2026-04-22-n19-toolchain-reference/N19/` | `N19 verifier PASS (completed run)` |
| scratch reference local unit tests | `Ran 3 tests ... OK` |
| scratch reference scope guard | `N19 scope PASS` |
| `git diff --check` before launch | exit `0` |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-22_03-16-13-X1-n19-systems-toolchain-2026-04-22/N19/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-22_03-16-13-X3-n19-systems-toolchain-2026-04-22/N19/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-22_03-21-39-X2-n19-systems-toolchain-calibration-2026-04-22/N19/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-22_03-21-38-X6-n19-systems-toolchain-calibration-2026-04-22/N19/` | `0` | `FAIL` | `PASS` | `0 / 1` |
| `X5 / gemini3.1pro` | not launched | n/a | n/a | n/a | `NOT-RUN` |

`X6` is a scoreable model/verifier fail on N19: it changed only source files and stayed in scope,
but missed portable cache-key equality and source-trace reporting. `X5` was not relaunched for N19
after the immediately preceding N18 semantic run timed out at `900s` without summary or worker
output.

### Rubric read

| Row | Binary | Scoreability | Rubric | Correctness | Patch quality | Time | Cost | Elapsed proxy | Output bytes | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `86 / 100` | `40` | `30` | `12` | `4` | `295.278s` | `281440` | changed 7 paths including tests; `133` added, `26` deleted |
| `X3 / opus 4.7max` | `PASS` | `scoreable` | `95 / 100` | `40` | `25` | `15` | `15` | `201.068s` | `2786` | changed 6 source paths; tests unchanged; `93` added, `30` deleted |
| `X2 / gpt-5.3-codex-spark` | `PASS` | `scoreable` | `84 / 100` | `40` | `25` | `15` | `4` | `63.006s` | `215440` | changed 5 source paths; tests unchanged; `96` added, `36` deleted |
| `X6 / gemini3.1flash-lite-preview` | `FAIL` | `scoreable` | `65 / 100` | `10` | `25` | `15` | `15` | `74.852s` | `1655` | missed cache-key portability and source-trace report |

### N19 Verdict

`binary tie remains` for `X1` and `X3`, but N19 gives a stronger role-fit signal than N18:
systems/toolchain routing should prefer `X3` for compact, low-output production patches and keep
`X1` as secondary when test augmentation is explicitly valuable. `X2` is a passing calibration row
but not better than the top pair. `X6` separates lower with a scoreable verifier failure.

## 2026-04-22 Follow-Up: N20 UI Interaction Implementation Rubric

`N20-ui-command-palette-interaction-gauntlet` was added as diagnostic `E10` for the UI
implementation lane. It uses executable Node interaction tests plus Python verifier checks for
keyboard navigation, filtering, disabled-action handling, focus recovery, ARIA rendering, visible
return cues, and CSS stability.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse of `oracle/ui-contract.json` | `PASS` |
| `python Scenarios-v2/N20-ui-command-palette-interaction-gauntlet/verifiers/check_ui_palette.py --bundle-shape-only` | `N20 verifier PASS (bundle shape)` |
| `python Scenarios-v2/N20-ui-command-palette-interaction-gauntlet/verifiers/check_ui_palette.py --expect-start-state` | `N20 verifier PASS (start state)` |
| local start-state Node test from `candidate/workspace` | expected assertion failure on disabled focus |
| scratch reference at `.scratch/verifier-probes/2026-04-22-n20-ui-reference/N20/` | `N20 verifier PASS (completed run)` |
| scratch reference local Node contract | `PASS` |
| scratch reference scope guard | `N20 scope PASS` |
| `git diff --check` before launch | exit `0` |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-22_03-29-41-X1-n20-ui-interaction-2026-04-22/N20/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-22_03-29-41-X3-n20-ui-interaction-2026-04-22/N20/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-22_03-34-20-X2-n20-ui-interaction-calibration-2026-04-22/N20/` | `0` | `FAIL` | `PASS` | `0 / 1` |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-22_03-34-20-X6-n20-ui-interaction-calibration-2026-04-22/N20/` | `1` | `FAIL` | `PASS` | `ROUTE-FAIL` |
| `X5 / gemini3.1pro` | not launched | n/a | n/a | n/a | `NOT-RUN` |

`X2` is a scoreable verifier failure because it created a top-level `.reports/` entry inside the
benchmark bundle, causing bundle-shape drift despite staying within the benchmark changed-path
scope. `X6` hit the Gemini route/tool-loop path and left a partial candidate that still missed
disabled focus skipping, filter stability, escape restore, visible return-cue text, and CSS
stability.

### Rubric read

| Row | Binary | Scoreability | Rubric | Correctness | Patch quality | Time | Cost | Elapsed proxy | Output bytes | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `87 / 100` | `40` | `28` | `15` | `4` | `155.955s` | `126621` | changed 3 source/CSS paths; tests unchanged; `60` added, `11` deleted |
| `X3 / opus 4.7max` | `PASS` | `scoreable` | `95 / 100` | `40` | `28` | `12` | `15` | `250.417s` | `1406` | changed 3 source/CSS paths; tests unchanged; `97` added, `15` deleted |
| `X2 / gpt-5.3-codex-spark` | `FAIL` | `scoreable` | `57 / 100` | `10` | `28` | `15` | `4` | `51.658s` | `144661` | created forbidden top-level `.reports/`; source/CSS patch otherwise in scope |
| `X6 / gemini3.1flash-lite-preview` | `ROUTE-FAIL` | `runtime-route` | `0 / 100` | `0` | `24` | `15` | `15` | `38.598s` | `2097` | route/tool abort with partial state/render patch |

### N20 Verdict

`binary tie remains` for `X1` and `X3`, but the UI implementation lane now has a useful routing
signal: prefer `X3` for compact UI state/render patches, keep `X1` as a safe top-pair secondary,
and do not promote `X2` or `X6` for this lane. `X2` failed the benchmark control-plane rule, while
`X6` did not complete a scoreable route and its partial patch missed multiple UI invariants.

## 2026-04-22 Follow-Up: W2 / N22 Numerical Stability Constraint Rubric

`N22-numerical-stability-constraint-gauntlet` was added as diagnostic `E12` for the
scientist/numerical-constraints lane. It replaces the easier N18 option-selection ceiling with
machine-checkable witnesses: exact bounded-histogram p95, population variance after Welford/Chan
style shard merge, p95 boundary traps, stale benchmark rejection, and a structured
`witness-ledger.json`.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for `inputs/cases.json`, `oracle/numerical-contract.json`, and starter witness | `PASS` |
| `python Scenarios-v2/N22-numerical-stability-constraint-gauntlet/verifiers/check_numerical_stability_decision.py --bundle-shape-only` | `N22 verifier PASS (bundle shape)` |
| `python Scenarios-v2/N22-numerical-stability-constraint-gauntlet/verifiers/check_numerical_stability_decision.py --expect-start-state` | `N22 verifier PASS (start state)` |
| scratch reference at `.scratch/verifier-probes/2026-04-22-n22-numerical-reference/` | `N22 verifier PASS (completed packet)` |
| scratch reference scope guard | `N22 scope PASS` |
| `git diff --check` before launch | exit `0` |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-22_03-52-19-X1-wave-w2-n22-numerical-2026-04-22/N22/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-22_03-52-19-X3-wave-w2-n22-numerical-2026-04-22/N22/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-22_03-57-40-X2-wave-w2-n22-numerical-2026-04-22/N22/` | `0` | `FAIL` | `PASS` | `0 / 1` |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-22_03-57-40-X6-wave-w2-n22-numerical-2026-04-22/N22/` | `1` | `FAIL` | `PASS` | `ROUTE-FAIL` |
| `X5 / gemini3.1pro` | not launched | n/a | n/a | n/a | `NOT-RUN` |

`X2` is a scoreable verifier failure: `wrapperExitCode=0`, no candidate files changed, and the
verifier still saw the starter-state failures. `X6` produced a partial candidate, but the Gemini
CLI route hit missing `run_shell_command` tool-loop errors and `AbortError`; record it as
runtime `ROUTE-FAIL`, not a model-quality failure.

### Rubric read

| Row | Binary | Scoreability | Rubric | Correct | Role | Scope | Synthesis | Verify | Runtime | Elapsed proxy | Output bytes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `100 / 100` | `30` | `20` | `15` | `20` | `10` | `5` | `161.522s` | `135379` |
| `X3 / opus 4.7max` | `PASS` | `scoreable` | `99 / 100` | `30` | `20` | `15` | `20` | `10` | `4` | `280.685s` | `2266` |
| `X2 / gpt-5.3-codex-spark` | `FAIL` | `scoreable` | `10 / 100` | `0` | `0` | `5` | `0` | `0` | `5` | `9.230s` | `37081` |
| `X6 / gemini3.1flash-lite-preview` | `ROUTE-FAIL` | `runtime-route` | `0 / 100` | `30` | `20` | `15` | `12` | `10` | `0` | `45.672s` | `2097` |

### N22 Verdict

`binary tie remains` for `X1` and `X3`; both top-pair rows solved the exact witness gauntlet.
The scored read gives `X1` a narrow `100 / 100` versus `X3 99 / 100` edge only because of elapsed
proxy, while `X3` keeps the much stronger output compactness signal (`2266` bytes versus `135379`).
For `worker.reasoning-constraints`, the current practical read is still top-pair co-primary:
prefer `X1` for trace-heavy numerical evidence and `X3` for compact exact decision packets.
`X2` separates lower scoreably on this harder numerical packet; `X6` remains a runtime-route caveat.

## 2026-04-22 Follow-Up: W3 / N23 Owner Recovery Stale-Source Routing Rubric

`N23-owner-recovery-stale-source-routing-gauntlet` was added as diagnostic `E13` for the owner
recovery/orchestration lane. It tightens N17 by forcing current-source selection, stale-source
rejection, interruption continuity, next-owner/gate routing, bounded calibration policy, and exact
path:line anchors. Its scorer does not award `100` merely for binary verifier pass.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse of `oracle/owner-recovery-contract.json` | `PASS` |
| `python Scenarios-v2/N23-owner-recovery-stale-source-routing-gauntlet/verifiers/check_owner_recovery.py --bundle-shape-only` | `N23 verifier PASS (bundle shape)` |
| `python Scenarios-v2/N23-owner-recovery-stale-source-routing-gauntlet/verifiers/check_owner_recovery.py --expect-start-state` | `N23 verifier PASS (start state)` |
| scratch reference at `.scratch/verifier-probes/2026-04-22-n23-owner-reference/` | `N23 verifier PASS (completed packet)` |
| scratch reference scope guard | `N23 scope PASS` |
| `git diff --check` before launch | exit `0` |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-22_04-06-09-X1-wave-w3-n23-owner-recovery-2026-04-22/N23/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-22_04-06-08-X3-wave-w3-n23-owner-recovery-2026-04-22/N23/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-22_04-10-41-X2-wave-w3-n23-owner-recovery-2026-04-22/N23/` | `0` | `FAIL` | `PASS` | `0 / 1` |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-22_04-10-41-X6-wave-w3-n23-owner-recovery-2026-04-22/N23/` | `1` | `FAIL` | `PASS` | `ROUTE-FAIL` |
| `X5 / gemini3.1pro` | not launched | n/a | n/a | n/a | `NOT-RUN` |

`X2` is a scoreable verifier failure. It produced a strong-looking owner packet but also created a
top-level `.reports/` entry inside the disposable benchmark bundle, so bundle-shape validation
failed. `X6` again followed the Gemini missing-tool/AbortError route failure path and left only a
partial artifact; keep it as runtime `ROUTE-FAIL`.

### Rubric read

| Row | Binary | Scoreability | Rubric | Source | Continuity | Routing | Calibration | Citations | Compact | Elapsed proxy | Output bytes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `90 / 100` | `25` | `18` | `20` | `15` | `10` | `2` | `124.862s` | `89826` |
| `X3 / opus 4.7max` | `PASS` | `scoreable` | `100 / 100` | `25` | `20` | `20` | `15` | `10` | `10` | `239.588s` | `1994` |
| `X2 / gpt-5.3-codex-spark` | `FAIL` | `scoreable` | `70 / 100` | `25` | `18` | `20` | `15` | `10` | `2` | `45.798s` | `130952` |
| `X6 / gemini3.1flash-lite-preview` | `ROUTE-FAIL` | `runtime-route` | `0 / 100` | `15` | `0` | `0` | `0` | `8` | `10` | `36.577s` | `1827` |

### N23 Verdict

`binary tie remains` for `X1` and `X3`, but W3/N23 gives a clear owner-lane scored separation:
`X3 100 / 100` versus `X1 90 / 100`. The decisive difference is compact, complete recovery output:
`X3` preserved every source, stale-source, routing, calibration, and citation requirement in a
small artifact; `X1` passed the binary verifier but was much larger and lost two continuity rubric
points. For owner/recovery packets, prefer `X3` as primary and keep `X1` as secondary when verbose
trace narration is explicitly desired. `X2` and `X6` should not be promoted for owner recovery:
`X2` scoreably failed bundle-shape discipline, and `X6` did not complete a scoreable route.

## 2026-04-22 Follow-Up: W1 / N21 Visual Raster Provider-Fit Rubric

`N21-visual-provider-fit-raster-gauntlet` was added as diagnostic `E11` for visual/graphics
implementation work. It uses a deterministic raster oracle rather than prose review: transparent
grid gaps, selected-cell focus layering, zero-centered legend color order, annotation pixels, and
PPM metadata are checked from actual rendered frame state.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for `inputs/panel-cases.json` and `oracle/visual-contract.json` | `PASS` |
| `python Scenarios-v2/N21-visual-provider-fit-raster-gauntlet/verifiers/check_visual_panel.py --bundle-shape-only` | `N21 verifier PASS (bundle shape)` |
| `python Scenarios-v2/N21-visual-provider-fit-raster-gauntlet/verifiers/check_visual_panel.py --expect-start-state` | `N21 verifier PASS (start state)` |
| scratch reference at `.scratch/verifier-probes/2026-04-22-n21-visual-reference/` | `N21 verifier PASS (completed run)` |
| scratch reference scope guard | `N21 scope PASS` |
| `git diff --check` before launch | exit `0` |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-22_11-07-41-X1-wave-w1-n21-visual-provider-2026-04-22/N21/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-22_11-07-41-X3-wave-w1-n21-visual-provider-2026-04-22/N21/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-22_11-11-53-X2-wave-w1-n21-visual-provider-calibration-2026-04-22/N21/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X5 / gemini3.1pro` | `.scratch/v2-cohort-runs/2026-04-22_11-43-33-X5-wave-w1-n21-visual-provider-calibration-2026-04-22/N21/` | timeout | no summary | n/a | `RUNTIME-FAIL` |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-22_11-11-53-X6-wave-w1-n21-visual-provider-calibration-2026-04-22/N21/` | timeout | no summary | n/a | `RUNTIME-FAIL` |

`X5` was admitted to launch only after a same-session smoke wrote
`.scratch/gemini-smoke-n21-2026-04-22/x5-output.txt` with `X5_SMOKE_OK`. Both Gemini semantic N21
runs timed out at the controller boundary without `summary.json` or `worker-output.txt`; classify
those as runtime no-summary events, not model-quality failures.

### Rubric read

| Row | Binary | Scoreability | Rubric | Visual | Patch | Tests | Runtime | Cost | Elapsed proxy | Output bytes | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `89 / 100` | `45` | `25` | `10` | `5` | `4` | `143.817s` | `113449` | tests changed; `72` added, `6` deleted |
| `X3 / opus 4.7max` | `PASS` | `scoreable` | `100 / 100` | `45` | `25` | `10` | `5` | `15` | `191.406s` | `2175` | tests changed; `64` added, `13` deleted |
| `X2 / gpt-5.3-codex-spark` | `PASS` | `scoreable` | `85 / 100` | `45` | `25` | `6` | `5` | `4` | `38.988s` | `80821` | source-only patch; tests unchanged |
| `X5 / gemini3.1pro` | `RUNTIME-FAIL` | `runtime-no-summary` | `0 / 100` | `0` | `0` | `0` | `0` | `0` | `0.0s` | n/a | no `summary.json` after launch |
| `X6 / gemini3.1flash-lite-preview` | `RUNTIME-FAIL` | `runtime-no-summary` | `0 / 100` | `0` | `0` | `0` | `0` | `0` | `0.0s` | n/a | no `summary.json` after launch |

### N21 Verdict

`binary tie remains` for `X1` and `X3`; both top-pair rows solved the visual raster state oracle.
The diagnostic read favors `X3 100 / 100` versus `X1 89 / 100`, but the split is an efficiency and
compactness split rather than a visual-correctness split: visual correctness, scope, patch quality,
tests, and runtime all tie, while output-size cost separates strongly. `X2` passes as a useful
calibration row but does not beat the top pair. The intended Gemini visual-provider preference is
not benchmark-proven by N21 because both Gemini semantic runs timed out after a successful direct
smoke.

## 2026-04-22 Follow-Up: W4 / N24 Systems Toolchain Repeat

`N24-systems-toolchain-staging-repeat` was added as diagnostic `E14` to repeat the `N19`
systems/toolchain signal on a different surface: artifact staging, portable fingerprints,
dependency ordering, cache restore trace, and lease lifecycle. This is a same-lane confirmation
scenario, not a new global denominator cell.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for `oracle/toolchain-staging-contract.json` | `PASS` |
| `python Scenarios-v2/N24-systems-toolchain-staging-repeat/verifiers/check_stagegate_systems.py --bundle-shape-only` | `N24 verifier PASS (bundle shape)` |
| `python Scenarios-v2/N24-systems-toolchain-staging-repeat/verifiers/check_stagegate_systems.py --expect-start-state` | `N24 verifier PASS (start state)` |
| scratch reference at `.scratch/verifier-probes/2026-04-22-n24-toolchain-reference/` | `N24 verifier PASS (completed run)` |
| scratch reference scope guard | `N24 scope PASS` |
| `git diff --check` before launch | exit `0` |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-22_12-31-40-X1-wave-w4-n24-toolchain-repeat-2026-04-22/N24/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-22_12-31-39-X3-wave-w4-n24-toolchain-repeat-2026-04-22/N24/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-22_12-38-33-X2-wave-w4-n24-toolchain-repeat-2026-04-22/N24/` | `0` | `FAIL` | `PASS` | `0 / 1` |
| `X5 / gemini3.1pro` | `.scratch/v2-cohort-runs/2026-04-22_12-41-43-X5-wave-w4-n24-toolchain-repeat-2026-04-22/N24/` | `0` | `FAIL` | `PASS` | `0 / 1` |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-22_12-38-33-X6-wave-w4-n24-toolchain-repeat-2026-04-22/N24/` | `0` | `FAIL` | `PASS` | `0 / 1` |

`X5` was admitted only after a same-session direct smoke wrote
`.scratch/gemini-smoke-n24-2026-04-22/x5-output.txt` with `X5_SMOKE_OK`. Its semantic N24 run then
produced a scoreable verifier failure, not a runtime caveat. `X2` also failed scoreably by creating
a forbidden top-level `.reports/` directory inside the disposable bundle, which tripped bundle shape.
`X6` produced a small partial patch but missed multiple functional invariants.

### Rubric read

| Row | Binary | Scoreability | Rubric | Correctness | Patch quality | Time | Cost | Elapsed proxy | Output bytes | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `X3 / opus 4.7max` | `PASS` | `scoreable` | `95 / 100` | `40` | `25` | `15` | `15` | `233.975s` | `2705` | tests unchanged; `84` added, `53` deleted |
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `86 / 100` | `40` | `30` | `12` | `4` | `371.585s` | `363208` | tests changed; `170` added, `50` deleted |
| `X2 / gpt-5.3-codex-spark` | `FAIL` | `scoreable` | `54 / 100` | `10` | `25` | `15` | `4` | `79.149s` | `239859` | forbidden `.reports` bundle-shape drift |
| `X5 / gemini3.1pro` | `FAIL` | `scoreable` | `65 / 100` | `10` | `25` | `15` | `15` | `133.314s` | `1577` | missed cache restore reason and summary source trace |
| `X6 / gemini3.1flash-lite-preview` | `FAIL` | `scoreable` | `65 / 100` | `10` | `25` | `15` | `15` | `76.754s` | `1286` | missed env fallback, dependency order, fingerprint portability, conflicts, and trace |

### N24 Verdict

`binary tie remains` for `X1` and `X3`, but W4/N24 confirms the same systems/toolchain shape seen
in N19: the top pair both solve the functional oracle, while `X3` is materially more compact and
lower-cost (`95 / 100` versus `86 / 100`). Because this is an independent same-lane repeat, the
systems/toolchain recommendation can move from `X3 provisional-primary` to `X3 primary` for compact
path/cache/fingerprint/lease patches, with `X1` as the test-rich secondary. `X2`, `X5`, and `X6`
are not primary candidates for this lane after scoreable verifier failures.

## 2026-04-22 Follow-Up: W4 / N25 UI Dirty-State Repeat

`N25-ui-dirty-state-navigation-guard-gauntlet` was added as diagnostic `E15` to repeat the `N20`
UI implementation signal on a different UI surface: dirty baselines, guarded navigation,
validation-gated save, failed-save rollback, focus return, ARIA status/error rendering, and stable
CSS constraints.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for `oracle/ui-dirty-contract.json` | `PASS` |
| `python Scenarios-v2/N25-ui-dirty-state-navigation-guard-gauntlet/verifiers/check_ui_dirty_state.py --bundle-shape-only` | `N25 verifier PASS (bundle shape)` |
| `python Scenarios-v2/N25-ui-dirty-state-navigation-guard-gauntlet/verifiers/check_ui_dirty_state.py --expect-start-state` | `N25 verifier PASS (start state)` |
| scratch reference at `.scratch/verifier-probes/2026-04-22-n25-ui-reference/` | `N25 verifier PASS (completed run)` |
| scratch reference scope guard | `N25 scope PASS` |
| `git diff --check` before launch | exit `0` |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-22_12-59-55-X1-wave-w4-n25-ui-dirty-repeat-2026-04-22/N25/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-22_12-59-55-X3-wave-w4-n25-ui-dirty-repeat-2026-04-22/N25/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-22_13-06-45-X2-wave-w4-n25-ui-dirty-repeat-2026-04-22/N25/` | `0` | `FAIL` | `PASS` | `0 / 1` |
| `X5 / gemini3.1pro` | `.scratch/v2-cohort-runs/2026-04-22_13-09-52-X5-wave-w4-n25-ui-dirty-repeat-2026-04-22/N25/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-22_13-06-44-X6-wave-w4-n25-ui-dirty-repeat-2026-04-22/N25/` | `1` | `FAIL` | `PASS` | `ROUTE-FAIL` |

`X5` was admitted only after a same-session direct smoke wrote
`.scratch/gemini-smoke-n25-2026-04-22/x5-output.txt` with `X5_SMOKE_OK`. Unlike N21, the semantic
Gemini Pro run completed and passed the verifier. `X2` is a scoreable fail: it left the candidate
unchanged, created a forbidden top-level `.reports/` entry, and failed every dirty-state invariant.
`X6` remains a runtime route failure because the Gemini route hit missing-tool loop recovery and
`AbortError`.

### Rubric read

| Row | Binary | Scoreability | Rubric | Correctness | Patch quality | Time | Cost | Elapsed proxy | Output bytes | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `X5 / gemini3.1pro` | `PASS` | `scoreable` | `98 / 100` | `40` | `28` | `15` | `15` | `181.236s` | `873` | tests unchanged; CSS changed; `95` added, `21` deleted |
| `X3 / opus 4.7max` | `PASS` | `scoreable` | `97 / 100` | `40` | `30` | `12` | `15` | `377.336s` | `2293` | tests changed; CSS changed; `328` added, `45` deleted |
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `86 / 100` | `40` | `30` | `12` | `4` | `277.103s` | `194944` | tests changed; CSS changed; `187` added, `25` deleted |
| `X2 / gpt-5.3-codex-spark` | `FAIL` | `scoreable` | `43 / 100` | `10` | `14` | `15` | `4` | `58.244s` | `78266` | no candidate edits; forbidden `.reports` bundle-shape drift |
| `X6 / gemini3.1flash-lite-preview` | `ROUTE-FAIL` | `runtime-route` | `0 / 100` | `0` | `24` | `0` | `0` | `110.986s` | `1984` | Gemini missing-tool loop / `AbortError` |

### N25 Verdict

`binary tie remains` for `X1` and `X3`, but N25 independently confirms the N20 UI implementation
edge: `X3` is again materially ahead of `X1` (`97 / 100` versus `86 / 100`). UI implementation can
move from `X3 provisional-primary` to `X3 primary` versus `X1`. N25 also produces the first healthy
modern `X5` UI implementation pass after smoke, and it narrowly tops the rubric at `98 / 100`; keep
`X5` as a UI contender when the Gemini Pro route is healthy, but require another UI-family pass
before promoting it over `X3` globally.

## 2026-04-22 Follow-Up: W6 / N26 Owner Recovery Repeat

`N26-owner-recovery-wave-roadmap-reconciliation-gauntlet` was added as diagnostic `E16` to repeat
the `N23` owner/orchestration signal after N24/N25 changed the live lane state. The packet forces
source-of-truth reconciliation, stale winner rejection, denominator discipline, lane-state mapping,
spawn/result-file policy, bounded calibration, and a parseable JSON decision block.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for `oracle/owner-wave-contract.json` | `PASS` |
| `python Scenarios-v2/N26-owner-recovery-wave-roadmap-reconciliation-gauntlet/verifiers/check_owner_wave_reconciliation.py --bundle-shape-only` | `N26 verifier PASS (bundle shape)` |
| `python Scenarios-v2/N26-owner-recovery-wave-roadmap-reconciliation-gauntlet/verifiers/check_owner_wave_reconciliation.py --expect-start-state` | `N26 verifier PASS (start state)` |
| scratch reference at `.scratch/verifier-probes/2026-04-22-n26-owner-wave-reference/` | `N26 verifier PASS (completed packet)` |
| scratch reference scope guard | `N26 scope PASS` |
| `git diff --check` before launch | exit `0` |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-22_13-36-21-X1-wave-w6-n26-owner-recovery-repeat-2026-04-22/N26/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-22_13-36-21-X3-wave-w6-n26-owner-recovery-repeat-2026-04-22/N26/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-22_13-41-39-X2-wave-w6-n26-owner-recovery-repeat-2026-04-22/N26/` | `0` | `FAIL` | `PASS` | `0 / 1` |
| `X5 / gemini3.1pro` | `.scratch/v2-cohort-runs/2026-04-22_13-46-21-X5-wave-w6-n26-owner-recovery-repeat-2026-04-22/N26/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-22_13-41-38-X6-wave-w6-n26-owner-recovery-repeat-2026-04-22/N26/` | `0` | `FAIL` | `PASS` | `0 / 1` |

`X5` was admitted only after the second same-session smoke invocation used absolute paths and wrote
`.scratch/gemini-smoke-n26-2026-04-22/x5-output.txt` with `X5_SMOKE_OK`. The first X5 smoke attempt
failed before model classification because a relative `WorkspaceDir` was doubled under scratch; it
is an invocation footnote, not model evidence. `X2` and `X6` both produced scoreable verifier
failures under `wrapperExitCode=0`; X6 output also included known Gemini missing-tool noise, but the
summary/verifier source of truth is scoreable `FAIL` for this run.

### Rubric read

| Row | Binary | Scoreability | Rubric | Source/stale | Continuity | Routing | Cal/runtime | Citation/denom | Compact | Elapsed proxy | Output bytes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `X3 / opus 4.7max` | `PASS` | `scoreable` | `100 / 100` | `25` | `20` | `20` | `15` | `10` | `10` | `274.897s` | `2488` |
| `X5 / gemini3.1pro` | `PASS` | `scoreable` | `100 / 100` | `25` | `20` | `20` | `15` | `10` | `10` | `150.840s` | `766` |
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `92 / 100` | `25` | `20` | `20` | `15` | `10` | `2` | `137.357s` | `119280` |
| `X2 / gpt-5.3-codex-spark` | `FAIL` | `scoreable` | `70 / 100` | `25` | `20` | `9` | `15` | `8` | `2` | `46.786s` | `115864` |
| `X6 / gemini3.1flash-lite-preview` | `FAIL` | `scoreable` | `50 / 100` | `10` | `0` | `9` | `15` | `6` | `10` | `72.965s` | `2718` |

### N26 Verdict

`binary tie remains` for `X1` and `X3`, but N26 repeats the N23 owner recovery split: `X3` again
beats `X1` by rubric (`100 / 100` versus `92 / 100`) while both pass the verifier and scope guard.
Because owner recovery now has independent same-lane evidence (`N23` and `N26`), owner/orchestration
can move from `X3 provisional-primary` to `X3 primary` versus `X1` for compact recovery/routing
packets. `X5` also passes N26 and ties X3 at `100 / 100` after a healthy smoke-gated route, so it is
a serious owner-recovery contender; keep it behind `X3` until another owner-family pass confirms
the signal. `X2` and `X6` separate lower with scoreable verifier failures.

## 2026-04-22 Follow-Up: W7 / N27 Release Train Long-Horizon Repeat

`N27-release-train-governor-long-horizon-repeat-gauntlet` was added as diagnostic `E17` to repeat
the long-horizon integration signal from `N16` on a new `deploygrid` domain. The verifier checks
active profile precedence, request immutability, latest-wins semantic dedupe, dependency ordering,
cycle blocking, canary-before-prod policy, frozen-scope deferral, idempotent repeat, crash/resume
without replay, current-attempt rollback, source trace preservation, and report derivation from
ledger/audit rather than notifications.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for `oracle/deploygrid-contract.json` | `PASS` |
| `python Scenarios-v2/N27-release-train-governor-long-horizon-repeat-gauntlet/verifiers/check_release_train_governor.py --bundle-shape-only` | `N27 verifier PASS (bundle shape)` |
| `python Scenarios-v2/N27-release-train-governor-long-horizon-repeat-gauntlet/verifiers/check_release_train_governor.py --expect-start-state` | `N27 verifier PASS (start state)` |
| scratch reference at `.scratch/verifier-probes/2026-04-22-n27-deploygrid-reference/` | `N27 verifier PASS (completed run)` |
| scratch reference scope guard | `N27 scope PASS` |
| sidecar anti-hardcoding audit | `REVISE` accepted; `prohibited_candidate_terms` expanded from `4` to all `12` case IDs before launch |
| `python -m py_compile` for verifier, scope checker, and scorer | `PASS` |
| `git diff --check` before launch | exit `0` |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-22_22-52-11-X1-wave-w7-n27-release-train-repeat-2026-04-22/N27/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-22_22-52-11-X3-wave-w7-n27-release-train-repeat-2026-04-22/N27/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-22_23-06-21-X2-wave-w7-n27-release-train-repeat-2026-04-22/N27/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-22_23-06-20-X6-wave-w7-n27-release-train-repeat-2026-04-22/N27/` | `1` | `FAIL` | `PASS` | `ROUTE-FAIL` |
| `X5 / gemini3.1pro` | smoke only: `.scratch/gemini-smoke-n27-2026-04-22/x5-output.txt` | `1` | n/a | n/a | `REQUEUE` |

`X5` was not admitted to the semantic N27 run because the same-session smoke did not write
`X5_SMOKE_OK`; the Gemini Pro route returned quota exhaustion after retries. This is a
`REQUEUE/runtime-quota` event, not model-quality evidence. `X6` produced a partial bundle and
summary, but `wrapperExitCode=1` with Gemini quota/tool-loop/`AbortError` route noise; classify it
as `ROUTE-FAIL/runtime-route`, not scoreable model `FAIL`.

### Rubric read

| Row | Binary | Scoreability | Rubric | Correct | Stateful | Patch | Tests | Time | Cost | Elapsed proxy | Output bytes | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `X3 / opus 4.7max` | `PASS` | `scoreable` | `92 / 100` | `50` | `15` | `13` | `4` | `5` | `5` | `821.310s` | `3537` | tests unchanged; `361` added, `43` deleted |
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `88 / 100` | `50` | `15` | `13` | `4` | `5` | `1` | `438.414s` | `487950` | tests unchanged; `321` added, `37` deleted |
| `X2 / gpt-5.3-codex-spark` | `PASS` | `scoreable` | `88 / 100` | `50` | `15` | `13` | `4` | `5` | `1` | `125.729s` | `660126` | tests unchanged; `299` added, `30` deleted |
| `X6 / gemini3.1flash-lite-preview` | `ROUTE-FAIL` | `runtime-route` | `0 / 100` | `0` | `0` | `0` | `0` | `0` | `0` | `218.718s` | `3935` | route failure; partial candidate missed all verifier invariants |
| `X5 / gemini3.1pro` | `REQUEUE` | `runtime-quota` | n/a | n/a | n/a | n/a | n/a | n/a | n/a | smoke only | n/a | smoke failed with quota; semantic run not launched |

### N27 Verdict

`binary tie remains` for `X1` and `X3`; the long-horizon integration repeat again does not produce a
semantic correctness separator. The scored read still favors `X3` (`92 / 100`) over `X1` (`88 / 100`)
through output-size cost and compactness, matching the direction of `N16` (`X3 95 / 100`, `X1 89 /
100`). With `N16` and `N27` both favoring `X3` on independent long-horizon integration tasks, the
long-horizon integration routing read can move from `X3 provisional-primary` to `X3 primary` for
compact production integration patches, with `X1` retained when explicit self-added regression
tests or verbose trace are more valuable. `X2` is a useful calibration pass on N27 but is not
promoted because other implementation repeats still separate it lower. `X5` has no N27 semantic
evidence due quota-gated smoke failure, and `X6` remains a route-health caveat.

## 2026-04-22 Follow-Up: W8 / N28 Incident-Driven Integration Repair

`N28-incident-driven-integration-repair-gauntlet` was added as diagnostic `E18` to push beyond
ordinary implementation repeats. It extends the N27 deploygrid runtime with incident-source
arbitration, stale requirements, review feedback, a required reconciliation note, and the same
multi-file repair surface. The verifier now checks both runtime behavior and cross-role note
obligations: source arbitration, stale-source rejection, review-response coverage, and validation
evidence.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for `oracle/incident-repair-contract.json` | `PASS` |
| `python Scenarios-v2/N28-incident-driven-integration-repair-gauntlet/verifiers/check_incident_integration_repair.py --bundle-shape-only` | `N28 verifier PASS (bundle shape)` |
| `python Scenarios-v2/N28-incident-driven-integration-repair-gauntlet/verifiers/check_incident_integration_repair.py --expect-start-state` | `N28 verifier PASS (start state)` |
| scratch reference at `.scratch/verifier-probes/2026-04-22-n28-incident-reference/` | `N28 verifier PASS (completed run)` |
| scratch reference scope guard | `N28 scope PASS` |
| sidecar verifier/scorer audit | `PASS`; noted that reconciliation checks are substring-based and should not be treated as hidden semantic proof |
| `python -m py_compile` for verifier, scope checker, and scorer | `PASS` |
| `git diff --check` before launch | exit `0` |
| `mcp-free` after Gemini timeouts | `STATS kill: none`; active parent-owned MCP processes skipped |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-23_00-00-20-X1-wave-w8-n28-incident-repair-2026-04-22/N28/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-23_00-00-20-X3-wave-w8-n28-incident-repair-2026-04-22/N28/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-23_00-16-36-X2-wave-w8-n28-incident-repair-2026-04-22/N28/` | `0` | `FAIL` | `PASS` | `0 / 1` |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-23_00-16-36-X6-wave-w8-n28-incident-repair-2026-04-22/N28/` | `1` | `FAIL` | `PASS` | `ROUTE-FAIL` |
| `X5 / gemini3.1pro` | smoke only: `.scratch/gemini-smoke-n28-2026-04-22*/x5-smoke-output.txt` | timeout | n/a | n/a | `REQUEUE` |

`X2` is a scoreable fail: `wrapperExitCode=0`, no benchmark files changed, and the verifier failed
all runtime and reconciliation invariants. `X6` produced a partial patch and note, but
`wrapperExitCode=1` with Gemini quota/tool-loop/`AbortError` route evidence; classify it as
`ROUTE-FAIL/runtime-route`, not model-quality `FAIL`. `X5` was not admitted to semantic N28 because
two same-session smoke attempts timed out without writing `X5_SMOKE_OK`; classify it as
`REQUEUE/runtime-timeout`.

### Rubric read

| Row | Binary | Scoreability | Rubric | Correct | Stateful | Recon | Patch | Tests | Time | Cost | Elapsed proxy | Output bytes | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `X3 / opus 4.7max` | `PASS` | `scoreable` | `99 / 100` | `45` | `10` | `20` | `10` | `5` | `4` | `5` | `932.627s` | `3057` | tests changed; note changed; `481` added, `56` deleted |
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `93 / 100` | `45` | `10` | `20` | `10` | `2` | `5` | `1` | `419.507s` | `304834` | tests unchanged; note changed; `278` added, `43` deleted |
| `X2 / gpt-5.3-codex-spark` | `FAIL` | `scoreable` | `16 / 100` | `0` | `0` | `0` | `6` | `0` | `5` | `5` | `6.256s` | `903` | no candidate edits; failed all runtime and reconciliation invariants |
| `X6 / gemini3.1flash-lite-preview` | `ROUTE-FAIL` | `runtime-route` | `0 / 100` | `0` | `0` | `0` | `0` | `5` | `0` | `0` | `200.996s` | `4070` | Gemini quota/tool-loop/`AbortError`; partial patch failed runtime invariants |
| `X5 / gemini3.1pro` | `REQUEUE` | `runtime-timeout` | n/a | n/a | n/a | n/a | n/a | n/a | n/a | smoke only | n/a | two direct smoke attempts timed out with no `X5_SMOKE_OK` |

### N28 Verdict

`binary tie remains` for `X1` and `X3`; N28 still does not produce a semantic correctness separator
between the top pair. The scored read favors `X3` (`99 / 100`) over `X1` (`93 / 100`) because X3
changed tests and stayed compact while X1 generated a much larger worker output and left tests
unchanged. This strengthens the routing read that cross-role incident repair / long-horizon
integration should prefer `X3 primary` for compact production patches, with `X1` retained when
verbose trace is valued more than output cost. `X2` now separates lower scoreably on the same
cross-role surface, unlike its N27 pass.

## 2026-04-23 Follow-Up: W9 / N29 Ownership-Budget Incident Repair

`N29-ownership-budget-incident-repair-gauntlet` was added as diagnostic `E19` after N28 showed that
ordinary cross-role repair still tied the top pair by binary gate. N29 starts from a near-pass
DeployGrid baseline with localized retry/resume and report-source defects. The task requires a valid
runtime repair, tests, and a machine-readable `candidate/repair-ledger.json`. The scope verifier
compares actual changed paths against the ledger's patch budget, so a broad runtime-correct rewrite
is a binary failure.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for `oracle/ownership-budget-contract.json` and `candidate/repair-ledger.json` | `PASS` |
| `python Scenarios-v2/N29-ownership-budget-incident-repair-gauntlet/verifiers/check_ownership_budget_repair.py --bundle-shape-only` | `N29 verifier PASS (bundle shape)` |
| `python Scenarios-v2/N29-ownership-budget-incident-repair-gauntlet/verifiers/check_ownership_budget_repair.py --expect-start-state` | `N29 verifier PASS (start state)` |
| scratch reference at `.scratch/verifier-probes/2026-04-22-n29-ownership-budget-reference/` | `N29 verifier PASS (completed run)` |
| scratch reference scope guard with exact four changed paths | `N29 scope PASS` |
| `python -m py_compile` for verifier, scope checker, and scorer | `PASS` |
| `git diff --check` before launch | exit `0` |
| `mcp-free` during/after long provider runs | first pass `kill: none`; post-X6 cleanup killed `9` orphan `mcp-language-server.exe` helpers |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-23_00-47-52-X1-wave-w9-n29-ownership-budget-2026-04-22/N29/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-23_01-10-19-X3-wave-w9-n29-ownership-budget-rerun-2026-04-23/N29/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-23_01-22-52-X2-wave-w9-n29-ownership-budget-calibration-2026-04-23/N29/` | `0` | `FAIL` | `FAIL` | `0 / 1` |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-23_01-22-43-X6-wave-w9-n29-ownership-budget-calibration-2026-04-23/N29/` | timeout | no summary | n/a | `RUNTIME-FAIL` |
| `X5 / gemini3.1pro` | smoke only: `.scratch/gemini-smoke-n29-2026-04-23/x5-smoke-output.txt` | timeout | n/a | n/a | `REQUEUE` |

The first `X3` launch was interrupted by the user before worker output or summary existed; it is not
admitted as model evidence. The admitted `X3` result is the rerun root above. `X2` is a scoreable
fail: `wrapperExitCode=0`, no benchmark files changed, semantic verifier failed, and the patch
budget scope gate failed. `X6` timed out without `summary.json` or worker output, so it is
`runtime-no-summary`, not a model-quality fail. `X5` was not admitted to semantic N29 because the
same-session smoke timed out without `X5_SMOKE_OK`.

### Rubric read

| Row | Binary | Scoreability | Rubric | Correct | Stateful | Ledger | Patch | Budget | Tests | Time | Cost | Elapsed proxy | Output bytes | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `X3 / opus 4.7max` | `PASS` | `scoreable` | `100 / 100` | `35` | `10` | `20` | `10` | `10` | `5` | `5` | `5` | `694.629s` | `2325` | tests changed; ledger changed; exact four-path budget |
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `96 / 100` | `35` | `10` | `20` | `10` | `10` | `5` | `5` | `1` | `228.279s` | `155704` | tests changed; ledger changed; exact four-path budget |
| `X2 / gpt-5.3-codex-spark` | `FAIL` | `scoreable` | `42 / 100` | `23` | `2` | `4` | `3` | `0` | `0` | `5` | `5` | `43.644s` | `1212` | no edits; failed runtime, ledger, and budget gates |
| `X6 / gemini3.1flash-lite-preview` | `RUNTIME-FAIL` | `runtime-no-summary` | `0 / 100` | `0` | `0` | `0` | `0` | `0` | `0` | `0` | `0` | n/a | n/a | missing summary after launch timeout |
| `X5 / gemini3.1pro` | `REQUEUE` | `runtime-timeout` | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | smoke only | n/a | smoke timed out with no output |

### N29 Verdict

`binary tie remains` for `X1` and `X3` even after the stricter semantic ledger and exact four-path
patch-budget gate. This is useful negative evidence: near-pass ownership-budget repairs are not a
binary separator for the top pair. The role-fit read still favors `X3` (`100 / 100`) over `X1` (`96
/ 100`) by output cost only; both solved the runtime defect, updated tests, and matched the exact
patch budget. `X2` separates lower scoreably, and Gemini rows remain runtime-route/timeout caveats.

## 2026-04-23 Follow-Up: W10 / N30 Staged Delivery Re-Entry

`N30-staged-delivery-reentry-gauntlet` was added as diagnostic `E20` after N29 showed that
single-invocation synthetic patches were exhausted as top-pair binary separators. N30 changes the
execution shape: `run-v2-staged-cohort-batch.ps1` copies the bundle once, then launches four fresh
provider invocations against the same run root. The worker must persist plan, implementation,
review-response, and final closeout state in files, then pass a final verifier and exact cumulative
changed-path budget.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for `oracle/delivery-contract.json` and seeded candidate ledgers | `PASS` |
| `python verifiers/check_staged_delivery.py --bundle-shape-only` from N30 root | `N30 verifier PASS (bundle shape)` |
| `python verifiers/check_staged_delivery.py --expect-start-state` from N30 root | `N30 verifier PASS (start state)` |
| scratch reference at `.scratch/verifier-probes/2026-04-23-n30-staged-reference/` | tests `PASS`; completed verifier `PASS`; exact scope `PASS` |
| staged runner PowerShell parser check | `PASS` |
| `python -m py_compile` for verifier, scope checker, and scorer | `PASS` |
| `git diff --check` before launch | exit `0` |
| `mcp-free` between long provider runs | `STATS kill: none`; active parent-owned MCP processes skipped |

The first X1/X3 staged launch exposed an over-strict verifier field-name issue:
`phaseId`/`reviewId`/`ownerPath` were semantically valid but the verifier accepted only
`id`/`owner`, and `reportSource: ledger` was treated as failure even when the report ignored
notifications. The verifier and scorer were relaxed to semantic aliases before admission; the
admitted top-pair result is the rerun batch below.

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-staged-runs/2026-04-23_02-42-46-X1-wave-w10-n30-staged-delivery-rerun-2026-04-23/N30/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-staged-runs/2026-04-23_02-42-47-X3-wave-w10-n30-staged-delivery-rerun-2026-04-23/N30/` | `0` | `FAIL` | `PASS` | `0 / 1` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-staged-runs/2026-04-23_03-01-47-X2-wave-w10-n30-staged-delivery-calibration-2026-04-23/N30/` | `0` | `FAIL` | `PASS` | `0 / 1` |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-staged-runs/2026-04-23_03-01-46-X6-wave-w10-n30-staged-delivery-calibration-2026-04-23/N30/` | timeout | no final summary | n/a | `RUNTIME-FAIL` |
| `X5 / gemini3.1pro` | smoke only: `.scratch/gemini-smoke-n30-2026-04-23/x5-output.txt` | timeout | n/a | n/a | `REQUEUE` |

`X3` is a scoreable fail: all four phases exited `0`, the cumulative changed-path scope was exact,
runtime code/tests/review response were mostly correct, but the persisted `delivery-state.json`
omitted the `03-review-response` phase ledger, so the final staged re-entry verifier failed
`phase-ledger-complete`. `X2` is also a scoreable fail: all phases exited `0`, but it created a
forbidden top-level `.reports/` bundle entry, causing bundle-shape verification failure. `X6`
timed out after Gemini quota/tool-loop errors and no final `summary.json`; classify as
`runtime-no-summary`, not model-quality fail. `X5` was not admitted to semantic N30 because the
same-session smoke timed out without writing `X5_SMOKE_OK`.

### Rubric read

| Row | Binary | Scoreability | Rubric | Semantic | Phase | Resume | Review | Patch | Tests | Time | Output | Stale | Elapsed proxy | Output bytes | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `96 / 100` | `30` | `15` | `15` | `10` | `10` | `5` | `5` | `1` | `5` | `824.673s` | `429795` | passed staged re-entry and exact budget |
| `X3 / opus 4.7max` | `FAIL` | `scoreable` | `91 / 100` | `25` | `15` | `11` | `10` | `10` | `5` | `5` | `5` | `5` | `646.525s` | `6618` | omitted `03-review-response` from persisted phase ledger |
| `X2 / gpt-5.3-codex-spark` | `FAIL` | `scoreable` | `66 / 100` | `0` | `15` | `15` | `10` | `10` | `5` | `5` | `1` | `5` | `288.981s` | `612935` | forbidden `.reports/` top-level drift |
| `X6 / gemini3.1flash-lite-preview` | `RUNTIME-FAIL` | `runtime-no-summary` | `0 / 100` | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | Gemini quota/tool-loop timeout before final summary |
| `X5 / gemini3.1pro` | `REQUEUE` | `runtime-timeout` | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | smoke only | n/a | smoke timed out with no `X5_SMOKE_OK` |

### N30 Verdict

N30 is the first current hardened wave to produce a top-pair scoreable binary separator:
`X1 PASS`, `X3 FAIL`. The separator is not basic coding correctness; X3 kept the patch compact and
passed scope but failed the multi-session delivery contract by dropping one persisted phase ledger.
Routing impact: use `X1 primary` for staged/multi-session delivery, re-entry, and phase-ledger
accountability. Keep `X3 primary` for compact single-invocation implementation surfaces already
covered by N16/N19/N20/N23/N24/N25/N26/N27/N28/N29, and keep X3 as secondary for staged work when
output cost is critical but phase-ledger loss is acceptable risk.

## 2026-04-23 Follow-Up: W11 / N31 MoM Cylinder Analytical Oracle

`N31-mom-cylinder-analytic-oracle` was added as diagnostic `E21` for the
scientist/numerical reasoning lane after the earlier uncommitted textbook-potential draft was
rejected as too easy. The admitted N31 task is computational electromagnetics: repair a
pulse-basis Method of Moments solver for a TMz plane wave incident on a PEC circular cylinder.
The verifier uses a clear analytical oracle: the exact cylindrical-harmonic series for the same
cylinder. Passing requires a real MoM density, an independently rebuilt boundary residual, exterior
field samples against the analytical oracle, convergence from `64` to `96` panels, and a hidden
non-default radius/wavenumber/incidence-angle probe.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for `oracle/mom-contract.json` and starter report | `PASS` |
| `python verifiers/check_mom_cylinder_solver.py --bundle-shape-only` | `N31 verifier PASS (bundle shape)` |
| `python verifiers/check_mom_cylinder_solver.py --expect-start-state` | `N31 verifier PASS (start state)` |
| scratch reference at `.scratch/verifier-probes/2026-04-23-n31-mom-cylinder-reference/N31/` | local smoke `PASS`; completed verifier `PASS`; scope `PASS` |
| `python -m py_compile` for solver/verifier/scope/scorer | `PASS` |
| `git diff --check` before launch | exit `0` |
| `mcp-free` before provider launch | `STATS kill: none`; active parent-owned MCP processes skipped |

### Runs

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---:|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-23_04-54-06-X1-wave-w11-n31-mom-cylinder-2026-04-23/N31/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-23_04-54-04-X3-wave-w11-n31-mom-cylinder-2026-04-23/N31/` | `0` | `PASS` | `PASS` | `1 / 1` |

Per the updated calibration rule, `X5` and `X6` were not launched for this run. The earlier
uncommitted Poschl-Teller scratch runs are not admitted evidence for N31; they were superseded by
the MoM cylinder bundle before documentation and commit.

### Rubric read

| Row | Binary | Scoreability | Rubric | Correct | Report | Notes | Scope | Runtime | Output | Elapsed proxy | Output bytes | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `X3 / opus 4.7max` | `PASS` | `scoreable` | `94 / 100` | `50` | `15` | `10` | `10` | `4` | `5` | `311.085s` | `3353` | compact MoM solution; analytical-oracle gates pass |
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `92 / 100` | `50` | `15` | `10` | `10` | `5` | `2` | `188.341s` | `163289` | faster but much larger output; analytical-oracle gates pass |

Machine-readable rubric: `Work/next-upgraded-pack/Evidence/n31-mom-cylinder-rubric-2026-04-23.json`.

### N31 Verdict

`binary tie remains` for `X1` and `X3` on a real computational-electromagnetics task with a clear
analytical oracle. N31 is still useful: it upgrades the scientist/numerical lane from memo and
statistics constraints into a real numerical integral-equation solve. The routing read remains
co-primary for correctness; prefer `X3` when compactness/output cost matters and `X1` when faster
elapsed time or more verbose trace is desired. N31 is not a new binary separator.

## 2026-04-23 Follow-Up: W12 / N32 Dual Physics Analytical Oracle

`N32-dual-physics-analytic-oracle` was added as diagnostic `E22` after N31 showed that a single
MoM cylinder solve was real physics evidence but not a top-pair separator. N32 combines the
requested ideas into one task: computational electromagnetics plus hydrogenic radial Schrodinger,
both solved numerically and checked against analytical oracles. Runtime is scoreable from measured
solver wall time, not only from provider elapsed time.

### N32 hardening shape

| Domain | Numerical solve required | Analytical oracle | Runtime gate |
|---|---|---|---|
| CEM / MoM | pulse-basis TMz EFIE solve for PEC circular cylinder | cylindrical-harmonic exterior field plus surface-density Fourier coefficients | per-case `max_runtime_seconds`, including hidden `ka=8` case |
| Quantum radial solve | finite-difference tridiagonal Hamiltonian for hydrogenic bound states | exact hydrogenic energy and radial wavefunction | per-case `max_runtime_seconds`, including `1800` point high-grid case |

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for `oracle/dual-physics-contract.json` | `PASS` |
| `python verifiers/check_dual_physics_oracle.py --bundle-shape-only` | `N32 verifier PASS (bundle shape)` |
| `python verifiers/check_dual_physics_oracle.py --expect-start-state` | `N32 verifier PASS (start state)` |
| scratch reference at `.scratch/verifier-probes/2026-04-23-n32-dual-physics-reference/N32/` | completed verifier `PASS`; scope `PASS` |
| local smoke `candidate/workspace/tests/test_dual_physics.py` | `N32 dual physics local smoke PASS` |
| `git diff --check` before launch | exit `0` |

### Runs and calibration

| Row | Run root / smoke root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---|
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-23_05-32-15-X3-wave-w12-n32-dual-physics-2026-04-23/N32/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-23_05-43-09-X1-wave-w12-n32-dual-physics-2026-04-23/N32/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-23_05-50-58-X2-wave-w12-n32-dual-physics-calibration-2026-04-23/N32/` | `0` | `FAIL` | `PASS` | scoreable `FAIL` |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-23_05-50-58-X6-wave-w12-n32-dual-physics-calibration-2026-04-23/` | timeout | no summary | n/a | `NOT-RUN` runtime no-summary |
| `X5 / gemini3.1pro` | `.scratch/gemini-smoke-n32-2026-04-23/` | timeout | n/a | n/a | `REQUEUE`; smoke did not write `X5_SMOKE_OK` |

The first X1 launch attempt used bad `cmd`/`pwsh -File` quoting and failed before worker launch; it
is an invocation error and is not admitted as model evidence. The admitted X1 run is the later
`cmd /c 'pwsh ... < NUL'` root above.

### Rubric read

| Row | Binary | Scoreability | Rubric | Correct | EM | Hydrogen | Solver runtime | Solver seconds | Report | Notes | Scope | Output | Output bytes | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `X3 / opus 4.7max` | `PASS` | `scoreable` | `100 / 100` | `50` | `25` | `25` | `25` | `0.334s` | `5` | `5` | `10` | `5` | `2012` | compact exact output; analytical-oracle gates pass |
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `97 / 100` | `50` | `25` | `25` | `25` | `0.466s` | `5` | `5` | `10` | `2` | `345404` | analytical-oracle gates pass; much larger output |
| `X2 / gpt-5.3-codex-spark` | `FAIL` | `scoreable` | `33 / 100` | `1` | `0` | `1` | `25` | `0.090s` | `0` | `0` | `3` | `4` | `57206` | no benchmark edits; verifier saw starter defects |
| `X6 / gemini3.1flash-lite-preview` | `NOT-RUN` | `runtime-no-summary` | `0 / 100` | `0` | `0` | `0` | `0` | n/a | `0` | `0` | `0` | `0` | n/a | controller timeout without `summary.json` |
| `X5 / gemini3.1pro` | `REQUEUE` | `runtime-timeout` | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | smoke timeout, semantic run not admitted |

Machine-readable rubric: `Work/next-upgraded-pack/Evidence/n32-dual-physics-rubric-2026-04-23.json`.

### N32 Verdict

`binary tie remains` for `X1` and `X3` on the combined real-physics task. N32 is still stronger than
N31 as lane evidence because it forces two independent numerical physics solvers in one patch and
makes solver runtime scoreable. The top pair both solved it; `X3` keeps the output-compactness edge,
while both rows achieved full solver-runtime points under the current workload. `X2` separates lower
scoreably. Gemini rows remain route/runtime caveats.

If a true scientific runtime separator is required next, the follow-up should not be another
ordinary oracle; it should raise the workload into a high-load performance gauntlet, for example
higher `ka`/larger MoM panel counts and larger radial grids with stricter solver-runtime scoring.

## 2026-04-23 Follow-Up: W13 / N33 Interface Refactor Breakage Gauntlet

`N33-interface-refactor-breakage-gauntlet` was added as diagnostic `E23` after the user identified
interface refactoring as a likely failure mode. The task requires replacing three ambiguous public
interfaces with structured result objects, migrating hidden consumers, removing legacy wrappers,
preserving error/retry semantics, updating visible tests, and recording a migration ledger.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for `oracle/interface-refactor-contract.json` | `PASS` |
| `python verifiers/check_interface_refactor.py --bundle-shape-only` | `N33 verifier PASS (bundle shape)` |
| `python verifiers/check_interface_refactor.py --expect-start-state` | `N33 verifier PASS (expected start-state failures present)` |
| scratch reference at `.scratch/verifier-probes/2026-04-23-n33-interface-reference/N33/` | completed verifier `PASS` |
| `score-n33-interface-refactor-rubric.py --help` | `PASS` |
| `git diff --check` before launch | exit `0` |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-23_07-05-51-X1-wave-w13-n33-interface-refactor-2026-04-23/N33/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-23_07-19-58-X3-wave-w13-n33-interface-refactor-2026-04-23/N33/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-23_07-55-42-X2-wave-w13-n33-interface-refactor-calibration-2026-04-23/N33/` | `0` | `FAIL` | `PASS` | scoreable `FAIL` |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-23_07-56-42-X6-wave-w13-n33-interface-refactor-calibration-2026-04-23/N33/` | timeout | no `summary.json` | n/a | `NOT-RUN` runtime no-summary |
| `X5 / gemini3.1pro` | not launched | n/a | n/a | n/a | `REQUEUE` route caveat |

### Rubric read

| Row | Binary | Scoreability | Rubric | Interface | Hidden | Ledger | Tests | Patch | Output | Bytes | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `96 / 100` | `30` | `30` | `15` | `10` | `10` | `1` | `380247` | exact but high-output |
| `X3 / opus 4.7max` | `PASS` | `scoreable` | `100 / 100` | `30` | `30` | `15` | `10` | `10` | `5` | `2984` | compact exact |
| `X2 / gpt-5.3-codex-spark` | `FAIL` | `scoreable` | `5 / 100` | `0` | `0` | `0` | `0` | `0` | `5` | `1387` | no candidate edits; starter failures remain |
| `X6 / gemini3.1flash-lite-preview` | `NOT-RUN` | `runtime-no-summary` | `0 / 100` | `0` | `0` | `0` | `0` | `0` | `0` | n/a | controller timeout without `summary.json` |

Machine-readable rubric: `Work/next-upgraded-pack/Evidence/n33-interface-refactor-rubric-2026-04-23.json`.

### N33 Verdict

`binary tie remains` for `X1` and `X3`. The interface-refactor hypothesis is valid for separating
lower calibration rows (`X2` failed scoreably), but not for the current top pair under this bundle.
The top-pair split is again cost/compactness only: X3 solved the same contract with much smaller
worker output. N33 does not supersede N30 as the only current binary separator.

## 2026-04-23 Follow-Up: W14 / N34 High-Load Science Optimizer

`N34-high-load-science-optimizer-gauntlet` was added as diagnostic `E24`. It combines the N30
staged/re-entry artifact shape with the N32 dual-physics domain and a heavier performance workload:
larger MoM PEC-cylinder cases, higher hydrogenic radial grids, explicit phase state, performance
ledger, optimization report, and measured solver-runtime rubric.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for `oracle/optimizer-contract.json` | `PASS` |
| `python verifiers/check_science_optimizer.py --bundle-shape-only` | `N34 verifier PASS (bundle shape)` |
| `python verifiers/check_science_optimizer.py --expect-start-state` | `N34 verifier PASS (start state)` |
| scratch reference at `.scratch/verifier-probes/2026-04-23-n34-science-optimizer-reference/N34/` | completed verifier `PASS` |
| `score-n34-science-optimizer-rubric.py --help` | `PASS` |
| `git diff --check` before launch | exit `0` |

The first X1/N33 launch attempt in this session used bad shell quoting and failed before worker
launch; it is not admitted evidence. N34 runtime caps were also adjusted before launch to avoid
host-load flakes in the binary gate; actual speed separation is scored by verifier metrics.

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---|
| `X1 / gpt-5.4` | `.scratch/v2-cohort-runs/2026-04-23_07-30-16-X1-wave-w14-n34-science-optimizer-2026-04-23/N34/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-23_07-43-08-X3-wave-w14-n34-science-optimizer-2026-04-23/N34/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-23_07-56-13-X2-wave-w14-n34-science-optimizer-calibration-2026-04-23/N34/` | `0` | `FAIL` | `PASS` | scoreable `FAIL` |
| `X6 / gemini3.1flash-lite-preview` | not launched after N33 route timeout | n/a | n/a | n/a | `NOT-RUN` route caveat |
| `X5 / gemini3.1pro` | not launched | n/a | n/a | n/a | `REQUEUE` route caveat |

### Rubric read

| Row | Binary | Scoreability | Rubric | Correct | Runtime | Runtime seconds | Staged | Report | Notes | Scope | Output | Bytes | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `96 / 100` | `40` | `20` | `0.319s` | `15` | `5` | `5` | `10` | `1` | `540758` | fastest measured solver metrics, high output |
| `X3 / opus 4.7max` | `PASS` | `scoreable` | `96 / 100` | `40` | `16` | `3.448s` | `15` | `5` | `5` | `10` | `5` | `2411` | slower solver metrics, much smaller output |
| `X2 / gpt-5.3-codex-spark` | `FAIL` | `scoreable` | `27 / 100` | `2` | `20` | `1.089s` | `0` | `0` | `0` | `0` | `5` | `1382` | no candidate edits; starter defects remain |

Machine-readable rubric: `Work/next-upgraded-pack/Evidence/n34-science-optimizer-rubric-2026-04-23.json`.

### N34 Verdict

`binary tie remains` for `X1` and `X3`, but N34 gives a clearer non-binary lane tradeoff than N32:
X1 is materially faster on measured solver metrics, while X3 is materially more compact. Current
scientist/performance read should be `near-tie`: prefer X1 when measured runtime is the dominant
constraint; prefer X3 when output/cost compactness is dominant. This still does not beat N30's
staged delivery binary separator.

## 2026-04-23 Follow-Up: W15 / N35 Staged Interface Migration Re-entry

`N35-staged-interface-migration-reentry-gauntlet` was added as diagnostic `E25` after N33 showed
that a single-shot interface refactor did not split the top pair. N35 combines the interface
migration hypothesis with the N30 staged runner: four fresh invocations over one copied bundle,
requiring persisted migration plan, implementation, review response, and final closeout state.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for `oracle/staged-interface-contract.json` | `PASS` |
| `python verifiers/check_staged_interface_migration.py --bundle-shape-only` | `N35 verifier PASS (bundle shape)` |
| `python verifiers/check_staged_interface_migration.py --expect-start-state` | `N35 verifier PASS (expected start-state failures present)` |
| scratch reference at `.scratch/verifier-probes/2026-04-23-n35-staged-interface-reference/` | completed verifier `PASS`; scope `PASS` |
| `score-n35-staged-interface-rubric.py` | `py_compile PASS` |
| `git diff --check` before launch | exit `0` |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---|
| `X1 / gpt-5.4` | `.scratch/v2-staged-runs/2026-04-23_12-31-05-X1-wave-w15-n35-staged-interface-2026-04-23/N35/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-staged-runs/2026-04-23_12-31-05-X3-wave-w15-n35-staged-interface-2026-04-23/N35/` | `0` | `FAIL` | `PASS` | scoreable `FAIL` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-staged-runs/2026-04-23_12-47-58-X2-wave-w15-n35-staged-interface-2026-04-23-calibration/N35/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X5 / gemini3.1pro` | `.scratch/v2-staged-runs/2026-04-23_12-47-57-X5-wave-w15-n35-staged-interface-2026-04-23-calibration/N35/` | `1` | n/a | n/a | `ROUTE-FAIL`; Gemini capacity exhausted |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-staged-runs/2026-04-23_12-47-57-X6-wave-w15-n35-staged-interface-2026-04-23-calibration/N35/` | `1` | n/a | n/a | `ROUTE-FAIL`; Gemini quota/tool-loop/AbortError |

X3 is a scoreable model failure because `wrapperExitCode=0` and the verifier ran and failed. X5 and
X6 are runtime-route failures because the provider path hit quota/tool-loop/abort behavior before a
clean staged candidate could be admitted.

### Rubric read

| Row | Binary | Scoreability | Rubric | Interface | Hidden | Phase | Ledger | Review | Patch | Tests | Time | Output | Bytes | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `96 / 100` | `15` | `25` | `15` | `14` | `10` | `10` | `5` | `2` | `0` | `882122` | exact staged migration; high output |
| `X3 / opus 4.7max` | `FAIL` | `scoreable` | `71 / 100` | `15` | `0` | `15` | `12` | `10` | `10` | `5` | `2` | `2` | `8387` | missed hidden runtime semantics and several migration-ledger details |
| `X2 / gpt-5.3-codex-spark` | `PASS` | `scoreable` | `91 / 100` | `15` | `25` | `9` | `14` | `10` | `10` | `5` | `3` | `0` | `1237712` | final artifact passes, but implementation landed in review phase, so phase discipline loses points |
| `X5 / gemini3.1pro` | `ROUTE-FAIL` | `runtime-route` | `0 / 100` | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | `11016` | quota/capacity exhausted on every phase |
| `X6 / gemini3.1flash-lite-preview` | `ROUTE-FAIL` | `runtime-route` | `0 / 100` | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | `8971` | partial edits plus tool-loop/AbortError; not scoreable model fail |

Machine-readable rubric: `Work/next-upgraded-pack/Evidence/n35-staged-interface-rubric-2026-04-23.json`.

X3 failed verifier invariants:

| Invariant | Detail |
|---|---|
| `session-lookup-contract` | `active-admin.reason` was `ok` instead of `active` |
| `policy-contract` | policy decisions missed non-empty `source_ids` |
| `router-contract` | denied dispatch reason was `blocked` instead of `blocked-tenant` |
| `integration-contract` | blocked API result kept the same reason drift |
| `report-contract` | queued retryable summary count was absent |
| `phase-ledger-complete` | phase owner missing for `01-intake-plan` |
| `migration-callSites` | missing `orchestrator.process_request` call-site row |
| `migration-validation` | missing `check_staged_interface_migration.py` validation marker |
| `migration-patch-budget` | required changed-path budget mismatch |

### N35 Verdict

`X1 PASS` versus `X3 scoreable FAIL`: N35 is a second current hardened top-pair binary separator
and is stronger than N30 for the user's stated failure hypothesis because it combines interface
refactor breakage with staged re-entry. Current routing impact: keep `X1 primary` for staged
interface migrations, multi-session re-entry, and phase-ledger accountability. Keep `X3 primary`
for compact single-session implementation and ordinary interface migration only when a staged
ledger/re-entry contract is not part of the job.

## 2026-04-23 Follow-Up: W16 / N36 Real-Repo Staged API Migration

`N36-realrepo-staged-api-migration-gauntlet` was added as diagnostic `E26` as the real-repo repeat
of the N35 separator. The domain changed from abstract interface migration to BillingMesh-style API
migration across account lookup, entitlement decisioning, usage publishing, API/service/reporting
consumers, review response, and final re-entry closeout.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for `oracle/staged-api-contract.json` | `PASS` |
| `python verifiers/check_staged_api_migration.py --bundle-shape-only` | `N36 verifier PASS (bundle shape)` |
| `python verifiers/check_staged_api_migration.py --expect-start-state` | `N36 verifier PASS (expected start-state failures present)` |
| scratch reference at `.scratch/verifier-probes/2026-04-23-n36-realrepo-api-reference/` | visible tests `PASS`; verifier `PASS`; scope `PASS` |
| `score-n36-staged-api-rubric.py` | `py_compile PASS` |
| `git diff --check` before launch | exit `0` |
| `mcp-free` before launch | `STATS kill: none`; active parent-owned MCP processes skipped |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---|
| `X1 / gpt-5.4` | `.scratch/v2-staged-runs/2026-04-23_14-00-23-X1-wave-w16-n36-realrepo-api-2026-04-23/N36/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-staged-runs/2026-04-23_14-00-23-X3-wave-w16-n36-realrepo-api-2026-04-23/N36/` | `0` | `FAIL` | `PASS` | scoreable `FAIL` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-staged-runs/2026-04-23_14-19-15-X2-wave-w16-n36-realrepo-api-calibration-2026-04-23/N36/` | `0` | `FAIL` | `FAIL` | scoreable `FAIL` |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-staged-runs/2026-04-23_14-19-15-X6-wave-w16-n36-realrepo-api-calibration-2026-04-23/N36/` | no final summary | n/a | n/a | `NOT-RUN`; runtime no-summary after phase-2 quota/stall |
| `X5 / gemini3.1pro` | not launched | n/a | n/a | n/a | `REQUEUE`; Pro route remained smoke-gated |

X3 is a scoreable model failure because `wrapperExitCode=0` and the verifier ran and failed. X2 is
also scoreable because the wrapper completed and verifier/scope gates failed. X6 is not scoreable:
phase 1 completed, phase 2 hit Gemini capacity retry messages, then stalled without final
`summary.json`; the process tree was closed as runtime no-summary.

### Rubric read

| Row | Binary | Scoreability | Rubric | Interface | Hidden | Phase | Ledger | Review | Patch | Tests | Time | Output | Bytes | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `97 / 100` | `15` | `25` | `15` | `14` | `10` | `10` | `5` | `3` | `0` | `762929` | exact real-repo staged API migration; high output |
| `X3 / opus 4.7max` | `FAIL` | `scoreable` | `74 / 100` | `15` | `5` | `15` | `10` | `10` | `10` | `5` | `2` | `2` | `7995` | missed hidden API semantics and ledger details |
| `X2 / gpt-5.3-codex-spark` | `FAIL` | `scoreable` | `70 / 100` | `15` | `25` | `12` | `0` | `10` | `0` | `5` | `3` | `0` | `612512` | created forbidden `.reports`, missed closeout/API path budget |
| `X6 / gemini3.1flash-lite-preview` | `NOT-RUN` | `runtime-no-summary` | `0 / 100` | `0` | `0` | `0` | `0` | `0` | `0` | `0` | `0` | `0` | n/a | phase-2 quota/stall; no final summary |

Machine-readable rubric: `Work/next-upgraded-pack/Evidence/n36-staged-api-rubric-2026-04-23.json`.

X3 failed verifier invariants:

| Invariant | Detail |
|---|---|
| `account-lookup-contract` | `acct-pro.reason` was `None` instead of `active` |
| `entitlement-contract` | `acct-pro.source_ids` was missing or empty |
| `publisher-contract` | denied publish status was `denied` instead of `rejected` |
| `reporting-contract` | retryable summary count was absent |
| `phase-ledger-complete` | phase owner missing for `01-intake-plan` |
| `migration-interfaceMap` | missing `AccountDirectory.get_account -> AccountDirectory.lookup_account` |
| `migration-callSites` | missing `service.process_usage_request` |
| `migration-compatibilityCases` | missing `denied-event-no-publish` |
| `migration-validation` | missing `check_staged_api_migration.py` validation marker |

### N36 Verdict

`X1 PASS` versus `X3 scoreable FAIL`: N36 is the third current hardened top-pair binary separator
and confirms that the N35 split is not domain-specific to the original interfaceflow fixture. The
role-fit read is now stronger: staged API/interface migrations with fresh-session re-entry, hidden
consumer contracts, and phase-ledger accountability should route to `X1 primary`. `X3` remains
better suited to compact single-session implementation and ordinary interface refactors when staged
re-entry is not required.

## 2026-04-23 Follow-Up: W17 / N37 Staged Adversarial Review Gate

`N37-staged-adversarial-review-gate-gauntlet` was added as diagnostic `E27` to test whether the
staged/re-entry split also applies to advisory, architecture, and review-gate lanes. The bundle
requires four fresh sessions over one copied review target: source ledger, source-bound ADR,
exact finding/non-finding tuples, response-gate decisions, and final closure.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for `oracle/review-gate-contract.json` | `PASS` |
| `python verifiers/check_staged_review_gate.py --bundle-shape-only` | `N37 verifier PASS (bundle shape)` |
| `python verifiers/check_staged_review_gate.py --expect-start-state` | `N37 verifier PASS (expected start-state failures present)` |
| scratch reference at `.scratch/verifier-probes/2026-04-23-n37-staged-review-reference/` | verifier `PASS`; scope `PASS` |
| `score-n37-staged-review-rubric.py` | `py_compile PASS`; rubric normalized to `100` points before scoring |
| `git diff --check` before launch | exit `0` |
| `mcp-free` before and after runs | `STATS kill: none`; active parent-owned MCP processes skipped |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier | Scope guard | Binary read |
|---|---|---:|---|---|---|
| `X1 / gpt-5.4` | `.scratch/v2-staged-runs/2026-04-23_15-00-09-X1-wave-w17-n37-staged-review-2026-04-23/N37/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X3 / opus 4.7max` | `.scratch/v2-staged-runs/2026-04-23_15-00-09-X3-wave-w17-n37-staged-review-2026-04-23/N37/` | `0` | `FAIL` | `PASS` | scoreable `FAIL` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-staged-runs/2026-04-23_15-16-49-X2-wave-w17-n37-staged-review-calibration-2026-04-23/N37/` | `0` | `PASS` | `PASS` | `1 / 1` |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-staged-runs/2026-04-23_15-21-00-X6-wave-w17-n37-staged-review-calibration-2026-04-23/N37/` | `1` | `FAIL` | `PASS` | `ROUTE-FAIL`; quota/tool-loop/AbortError |
| `X5 / gemini3.1pro` | not launched semantically | n/a | n/a | n/a | `REQUEUE`; direct Pro smoke timed out after `180s` without output |

X3 is a scoreable model failure because `wrapperExitCode=0`, all required files changed, the scope
guard passed, and the verifier ran and failed. X6 is runtime-route, not model-quality: the Flash
route passed a direct smoke prompt, then the semantic run hit capacity retries, missing
`run_shell_command`, and `AbortError`.

### Rubric read

| Row | Binary | Scoreability | Rubric | Evidence | ADR | Findings | NonClaims | Response | Phase | Patch | Time | Output | Bytes | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `98 / 100` | `20` | `15` | `25` | `10` | `15` | `5` | `5` | `3` | `0` | `533776` | exact staged review gate; high output |
| `X3 / opus 4.7max` | `FAIL` | `scoreable` | `35 / 100` | `20` | `0` | `0` | `0` | `0` | `5` | `5` | `3` | `2` | `8655` | missed ADR source binding, exact findings, non-claims, response cues, and closure markers |
| `X2 / gpt-5.3-codex-spark` | `PASS` | `scoreable` | `97 / 100` | `20` | `15` | `25` | `10` | `15` | `4` | `5` | `3` | `0` | `970598` | passes final artifact; phase 04 also touched ADR, so phase discipline loses one point |
| `X6 / gemini3.1flash-lite-preview` | `ROUTE-FAIL` | `runtime-route` | `0 / 100` | `10` | `0` | `0` | `0` | `0` | `5` | `0` | `3` | `2` | `6045` | partial artifacts plus Gemini route/tool failure; not scoreable model fail |
| `X5 / gemini3.1pro` | `REQUEUE` | `runtime-smoke-timeout` | `0 / 100` | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | direct smoke timed out without writing output; semantic run skipped |

Machine-readable rubric: `Work/next-upgraded-pack/Evidence/n37-staged-review-rubric-2026-04-23.json`.

X3 failed verifier invariants:

| Invariant | Detail |
|---|---|
| `ledger-validationMarkers` | missing `python verifiers/check_staged_review_gate.py` / `check_review_scope.py` validation markers |
| `adr-source-bound` | plan fingerprint and required ADR markers missing |
| `finding-tuples` | F1 missing remediation cue; F2 severity/evidence cue mismatch; F3 owner/evidence cue mismatch |
| `finding-source-ids` | F1/F2/F3 lacked required non-empty `source_ids` |
| `non-finding-ledger` | required non-claim markers missing |
| `response-gate-complete` | response rows missed owner and/or visible return cue across A1..A6 |
| `closure-complete` | validation marker and closure markers incomplete |

### N37 Verdict

`X1 PASS` versus `X3 scoreable FAIL`: N37 is the fourth current hardened top-pair binary separator
and the first one on a staged adversarial review/advisory gate. It changes the lane read: review
and architecture tasks that are single-shot, compact, and ordinary can still route to `X3`, but
multi-session source arbitration, ADR traceability, exact finding/non-claim ledgers, and response
gate closure should route to `X1 primary`. `X2` is a credible calibration pass on this staged
review shape; Gemini rows remain route-caveated for this wave.

## 2026-04-23 Follow-Up: W18 / N38 Staged UI/Visual/State Integration

`N38-deterministic-ui-visual-state-integration-gauntlet` was added as diagnostic `E28` to test
whether the staged/re-entry split also applies to UI work when command state, dirty navigation,
ARIA/status cues, layout geometry, and raster pixels must stay coherent across fresh sessions.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for the staged UI contract/oracle | `PASS` |
| `python verifiers/check_deterministic_ui_visual_state.py --bundle-shape-only` | `PASS` |
| `python verifiers/check_deterministic_ui_visual_state.py --expect-start-state` | `PASS` |
| scratch reference verifier and scope simulation | `PASS` |
| scorer compile and `git diff --check` before launch | `PASS` |
| `mcp-free` before/after the batch | `STATS kill: none`; active parent-owned MCP processes skipped |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier / summary | Binary read |
|---|---|---:|---|---|
| `X1 / gpt-5.4` | `.scratch/v2-staged-runs/2026-04-23_16-57-40-X1-wave-w18-w21-staged-queued-2026-04-23/N38/` | `0` | final `summary.json` present; verifier `PASS` | `PASS` |
| `X3 / opus 4.7max` | `.scratch/v2-staged-runs/2026-04-23_17-56-36-X3-wave-w18-w21-staged-rerun-n38-2026-04-23/N38/` | no final summary | phase `01..03` completed; phase `04` stalled without worker output; original queued run also ended without final summary | `NOT-RUN`; repeated runtime no-summary |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-staged-runs/2026-04-23_18-28-55-X2-wave-w18-w21-staged-queued-2026-04-23/N38/` | `0` | final `summary.json` present; verifier `FAIL` | scoreable `FAIL` |
| `X5 / gemini3.1pro` | `.scratch/v2-staged-runs/2026-04-23_18-37-13-X5-wave-w18-w21-staged-queued-2026-04-23/N38/` | `1` | final `summary.json` present; repeated Gemini capacity exhaustion | `ROUTE-FAIL`; runtime-route |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-staged-runs/2026-04-23_18-57-00-X6-wave-w18-w21-staged-queued-2026-04-23/N38/` | `1` | final `summary.json` present; route/tool failure | `ROUTE-FAIL`; runtime-route |

X3 is not scoreable on N38. Both the original queued run and the bounded rerun reached late phases,
but neither produced a final `summary.json`. X5 and X6 are runtime-route caveats rather than model
quality failures.

### Rubric read

| Row | Binary | Scoreability | Rubric | Notes |
|---|---|---|---:|---|
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `94 / 100` | staged UI/visual/state packet completed cleanly |
| `X2 / gpt-5.3-codex-spark` | `FAIL` | `scoreable` | `78 / 100` | missed exact staged scope requirements |
| `X3 / opus 4.7max` | `NOT-RUN` | `runtime-no-summary` | `0 / 100` | repeated phase-4 stall without final summary |
| `X5 / gemini3.1pro` | `ROUTE-FAIL` | `runtime-route` | `0 / 100` | Gemini capacity exhaustion during staged run |
| `X6 / gemini3.1flash-lite-preview` | `ROUTE-FAIL` | `runtime-route` | `0 / 100` | route/tool failure, not scoreable |

Machine-readable rubric: `Work/next-upgraded-pack/Evidence/n38-ui-visual-state-rubric-2026-04-23.json`.

X2 failed scorer invariants:

| Invariant | Detail |
|---|---|
| `scope-contract` | staged packet failed the exact required change surface |
| `scope-missing-required-paths` | required candidate paths were not all present |

### N38 Verdict

`X1 PASS 94 / 100` is useful positive evidence that X1 handles the staged UI/visual/state packet,
but `X3` never produced a scoreable final result. This row therefore does not currently separate
`X1` versus `X3` semantically; the honest read is `X1 PASS`, `X3 NOT-RUN`, `X2 scoreable FAIL`,
and Gemini runtime-route caveats.

## 2026-04-23 Follow-Up: W19 / N39 Staged Systems/Toolchain Recovery Re-entry

`N39-staged-systems-toolchain-reentry-gauntlet` was added as diagnostic `E29` to test whether the
systems/toolchain `X3` edge from `N19` and `N24` survives fresh staged invocations, stale-source
recovery, runtime-status discipline, implementation ledger, closeout, and exact scope.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for the staged toolchain contract/oracle | `PASS` |
| `python verifiers/check_staged_toolchain_reentry.py --bundle-shape-only` | `PASS` |
| `python verifiers/check_staged_toolchain_reentry.py --expect-start-state` | `PASS` |
| scratch reference verifier and scope simulation | `PASS` |
| scorer compile and `git diff --check` before launch | `PASS` |
| `mcp-free` before/after the batch | `STATS kill: none`; active parent-owned MCP processes skipped |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier / summary | Binary read |
|---|---|---:|---|---|
| `X1 / gpt-5.4` | `.scratch/v2-staged-runs/2026-04-23_16-57-40-X1-wave-w18-w21-staged-queued-2026-04-23/N39/` | `0` | final `summary.json` present; verifier `FAIL` | scoreable `FAIL` |
| `X3 / opus 4.7max` | `.scratch/v2-staged-runs/2026-04-23_17-22-44-X3-wave-w18-w21-staged-queued-2026-04-23/N39/` | `0` | final `summary.json` present; verifier `FAIL` | scoreable `FAIL` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-staged-runs/2026-04-23_18-28-55-X2-wave-w18-w21-staged-queued-2026-04-23/N39/` | `0` | final `summary.json` present; verifier `FAIL` | scoreable `FAIL` |
| `X5 / gemini3.1pro` | `.scratch/v2-staged-runs/2026-04-23_18-37-13-X5-wave-w18-w21-staged-queued-2026-04-23/N39/` | `1` | final `summary.json` present; repeated Gemini capacity exhaustion | `ROUTE-FAIL`; runtime-route |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-staged-runs/2026-04-23_18-57-00-X6-wave-w18-w21-staged-queued-2026-04-23/N39/` | no final summary | no final `summary.json` | `NOT-RUN`; runtime no-summary |

### Rubric read

| Row | Binary | Scoreability | Rubric | Notes |
|---|---|---|---:|---|
| `X1 / gpt-5.4` | `FAIL` | `scoreable` | `78 / 100` | exact staged scope / changed-path budget miss |
| `X2 / gpt-5.3-codex-spark` | `FAIL` | `scoreable` | `78 / 100` | same exact staged scope failure class |
| `X3 / opus 4.7max` | `FAIL` | `scoreable` | `78 / 100` | same exact staged scope failure class |
| `X5 / gemini3.1pro` | `ROUTE-FAIL` | `runtime-route` | `0 / 100` | runtime-route / quota caveat |
| `X6 / gemini3.1flash-lite-preview` | `NOT-RUN` | `runtime-no-summary` | `0 / 100` | no final summary |

Machine-readable rubric: `Work/next-upgraded-pack/Evidence/n39-staged-toolchain-rubric-2026-04-23.json`.

Shared scoreable failure signature for `X1`, `X2`, and `X3`:

| Invariant | Detail |
|---|---|
| `scope-contract` | staged toolchain packet missed the exact admitted change surface |
| `scope-missing-required-paths` | one or more required candidate files were absent |

### N39 Verdict

N39 is not a usable separator. All three scoreable rows (`X1`, `X2`, `X3`) fail with the same
exact-scope / changed-path-budget signature at `78 / 100`, while Gemini rows remain runtime
caveats. The honest read is that N39 is currently over-tightened and should not be promoted as a
routing basis until the scope contract is relaxed or redesigned.

## 2026-04-23 Follow-Up: W20 / N40 Staged Owner Recovery Re-entry

`N40-staged-owner-recovery-reentry-gauntlet` was added as diagnostic `E30` to test whether the
owner-recovery `X3` edge from `N23` and `N26` survives four staged packets: source ledger, route
decision, runtime policy, and closeout.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for `oracle/staged-owner-recovery-contract.json` | `PASS` |
| `python verifiers/check_staged_owner_recovery.py --bundle-shape-only` | `PASS` |
| `python verifiers/check_staged_owner_recovery.py --expect-start-state` | `PASS` |
| scratch reference at `.scratch/verifier-probes/2026-04-23-n40-staged-owner-reference/` | verifier `PASS`; scope `PASS` |
| scorer compile and `git diff --check` before launch | `PASS` |
| `mcp-free` before/after the batch | `STATS kill: none`; active parent-owned MCP processes skipped |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier / summary | Binary read |
|---|---|---:|---|---|
| `X1 / gpt-5.4` | `.scratch/v2-staged-runs/2026-04-23_16-57-40-X1-wave-w18-w21-staged-queued-2026-04-23/N40/` | `0` | final `summary.json` present; verifier `PASS` | `PASS` |
| `X3 / opus 4.7max` | `.scratch/v2-staged-runs/2026-04-23_17-22-44-X3-wave-w18-w21-staged-queued-2026-04-23/N40/` | `0` | final `summary.json` present; verifier `FAIL` | scoreable `FAIL` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-staged-runs/2026-04-23_18-28-55-X2-wave-w18-w21-staged-queued-2026-04-23/N40/` | `0` | final `summary.json` present; verifier `FAIL` | scoreable `FAIL` |
| `X5 / gemini3.1pro` | `.scratch/v2-staged-runs/2026-04-23_18-37-13-X5-wave-w18-w21-staged-queued-2026-04-23/N40/` | `1` | final `summary.json` present; repeated Gemini capacity exhaustion | `ROUTE-FAIL`; runtime-route |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-staged-runs/2026-04-23_18-57-00-X6-wave-w18-w21-staged-queued-2026-04-23/N40/` | `0` | final `summary.json` present; verifier `FAIL` | scoreable `FAIL` |

### Rubric read

| Row | Binary | Scoreability | Rubric | Notes |
|---|---|---|---:|---|
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `98 / 100` | exact staged owner packet |
| `X2 / gpt-5.3-codex-spark` | `FAIL` | `scoreable` | `78 / 100` | exact packet incompleteness |
| `X3 / opus 4.7max` | `FAIL` | `scoreable` | `55 / 100` | missed core staged owner packet fields |
| `X5 / gemini3.1pro` | `ROUTE-FAIL` | `runtime-route` | `0 / 100` | quota / route caveat |
| `X6 / gemini3.1flash-lite-preview` | `FAIL` | `scoreable` | `40 / 100` | scoreable low-quality fail, not route-only |

Machine-readable rubric: `Work/next-upgraded-pack/Evidence/n40-staged-owner-rubric-2026-04-23.json`.

X3 failed scorer invariants:

| Invariant | Detail |
|---|---|
| `closure-complete` | closeout markers incomplete |
| `phase-ledger-complete` | staged owner phase ledger incomplete |
| `route-decision-complete` | route-decision packet incomplete |
| `runtime-policy-complete` | runtime-policy packet incomplete |

### N40 Verdict

`X1 PASS 98 / 100` versus `X3 scoreable FAIL 55 / 100` is an honest staged owner-recovery
separator. This flips the lane read by execution shape: compact single-session owner recovery still
favors `X3` from `N23` and `N26`, but staged owner recovery with explicit source ledger, route
decision, runtime-policy packet, and closeout now routes to `X1 primary`.

## 2026-04-23 Follow-Up: W21 / N41 Staged Incident-Budget Re-entry

`N41-staged-incident-budget-reentry-gauntlet` was added as diagnostic `E31` to test whether the
long-horizon / cross-role / ownership-budget `X3` edge from `N16`, `N27`, `N28`, and `N29`
survives staged runtime repair, repair ledger, reentry state, exact six-path budget, and closeout.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for `oracle/staged-incident-budget-contract.json` | `PASS` |
| `python verifiers/check_staged_incident_budget.py --bundle-shape-only` | `PASS` |
| `python verifiers/check_staged_incident_budget.py --expect-start-state` | `PASS` |
| scratch reference at `.scratch/verifier-probes/2026-04-23-n41-staged-incident-budget-reference/` | direct tests `PASS`; verifier `PASS`; scope `PASS` |
| scorer compile and `git diff --check` before launch | `PASS` |
| `mcp-free` before/after the batch | `STATS kill: none`; active parent-owned MCP processes skipped |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier / summary | Binary read |
|---|---|---:|---|---|
| `X1 / gpt-5.4` | `.scratch/v2-staged-runs/2026-04-23_16-57-40-X1-wave-w18-w21-staged-queued-2026-04-23/N41/` | `0` | final `summary.json` present; verifier `PASS` | `PASS` |
| `X3 / opus 4.7max` | `.scratch/v2-staged-runs/2026-04-23_17-22-44-X3-wave-w18-w21-staged-queued-2026-04-23/N41/` | `0` | final `summary.json` present; verifier `FAIL` | scoreable `FAIL` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-staged-runs/2026-04-23_18-28-55-X2-wave-w18-w21-staged-queued-2026-04-23/N41/` | `0` | final `summary.json` present; verifier `FAIL` | scoreable `FAIL` |
| `X5 / gemini3.1pro` | `.scratch/v2-staged-runs/2026-04-23_18-37-13-X5-wave-w18-w21-staged-queued-2026-04-23/N41/` | `1` | final `summary.json` present; repeated Gemini capacity exhaustion | `ROUTE-FAIL`; runtime-route |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-staged-runs/2026-04-23_18-57-00-X6-wave-w18-w21-staged-queued-2026-04-23/N41/` | no final summary | no final `summary.json` | `NOT-RUN`; runtime no-summary |

### Rubric read

| Row | Binary | Scoreability | Rubric | Notes |
|---|---|---|---:|---|
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `100 / 100` | exact staged incident-budget packet |
| `X2 / gpt-5.3-codex-spark` | `FAIL` | `scoreable` | `78 / 100` | partial staged incident packet |
| `X3 / opus 4.7max` | `FAIL` | `scoreable` | `78 / 100` | missed required staged repair / closeout ledgers |
| `X5 / gemini3.1pro` | `ROUTE-FAIL` | `runtime-route` | `0 / 100` | quota / route caveat |
| `X6 / gemini3.1flash-lite-preview` | `NOT-RUN` | `runtime-no-summary` | `0 / 100` | no final summary |

Machine-readable rubric: `Work/next-upgraded-pack/Evidence/n41-staged-incident-budget-rubric-2026-04-23.json`.

X3 failed scorer invariants:

| Invariant | Detail |
|---|---|
| `closeout-markers` | closeout markers incomplete |
| `reentry-phase-ledger` | reentry phase ledger incomplete |
| `reentry-runtime-classification` | runtime classification packet incomplete |
| `repair-ledger-schema` | repair ledger schema incomplete |
| `review-response-ledger` | review-response ledger incomplete |
| `source-decisions-ledger` | source-decisions ledger incomplete |

X2 failed scorer invariants:

| Invariant | Detail |
|---|---|
| `crash-resume-no-replay` | replay handling incomplete |
| `idempotent-repeat` | repeat/idempotency semantics incomplete |
| `report-from-ledger-audit` | closeout report did not match ledger audit requirements |
| `review-response-ledger` | review-response ledger incomplete |
| `semantic-dedupe-latest-wins` | stale-result dedupe semantics incomplete |
| `source-decisions-ledger` | source-decisions ledger incomplete |

### N41 Verdict

`X1 PASS 100 / 100` versus `X3 scoreable FAIL 78 / 100` is the strongest new staged separator in
this wave. It extends `X1 primary` beyond staged delivery/API/review into staged long-horizon,
cross-role, and ownership-budget incident repair when reentry state, repair ledger, exact patch
budget, and closeout must all survive fresh-session handoff.
