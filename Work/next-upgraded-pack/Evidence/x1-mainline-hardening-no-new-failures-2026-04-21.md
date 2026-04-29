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
| `X3 / opus 4.7max` | `.scratch/v2-staged-runs/2026-04-23_21-17-20-X3-wave-w18-n38-x3-rerun-2026-04-23/N38/` | no final summary | phase `01..03` completed; phase `04` stalled without worker output; original queued run and prior bounded rerun also ended without final summary | `NOT-RUN`; repeated runtime no-summary |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-staged-runs/2026-04-23_18-28-55-X2-wave-w18-w21-staged-queued-2026-04-23/N38/` | `0` | final `summary.json` present; verifier `FAIL` | scoreable `FAIL` |
| `X5 / gemini3.1pro` | `.scratch/v2-staged-runs/2026-04-23_18-37-13-X5-wave-w18-w21-staged-queued-2026-04-23/N38/` | `1` | final `summary.json` present; repeated Gemini capacity exhaustion | `ROUTE-FAIL`; runtime-route |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-staged-runs/2026-04-23_18-57-00-X6-wave-w18-w21-staged-queued-2026-04-23/N38/` | `1` | final `summary.json` present; route/tool failure | `ROUTE-FAIL`; runtime-route |

X3 is not scoreable on N38. The original queued run, the bounded rerun, and the later solo rerun
all reached late phases, but none produced a final `summary.json`. X5 and X6 are runtime-route
caveats rather than model quality failures.

### Rubric read

| Row | Binary | Scoreability | Rubric | Notes |
|---|---|---|---:|---|
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `94 / 100` | staged UI/visual/state packet completed cleanly |
| `X2 / gpt-5.3-codex-spark` | `FAIL` | `scoreable` | `78 / 100` | missed exact staged scope requirements |
| `X3 / opus 4.7max` | `NOT-RUN` | `runtime-no-summary` | `0 / 100` | three phase-4 stalls without final summary |
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
but `X3` never produced a scoreable final result across three attempts. This row therefore does not
currently separate `X1` versus `X3` semantically; the honest read is `X1 PASS`, `X3 NOT-RUN`,
`X2 scoreable FAIL`, and Gemini runtime-route caveats.

## 2026-04-23 Follow-Up: W19 / N39 Staged Systems/Toolchain Recovery Re-entry

`N39-staged-systems-toolchain-reentry-gauntlet` was added as diagnostic `E29` to test whether the
systems/toolchain `X3` edge from `N19` and `N24` survives fresh staged invocations, stale-source
recovery, runtime-status discipline, implementation ledger, closeout, and bounded scope.

### Pre-run validation

| Check | Result |
|---|---|
| JSON parse for the staged toolchain contract/oracle | `PASS` |
| `python verifiers/check_staged_toolchain_reentry.py --bundle-shape-only` | `PASS` |
| `python verifiers/check_staged_toolchain_reentry.py --expect-start-state` | `PASS` |
| scratch reference verifier and scope simulation | `PASS` |
| scorer compile and `git diff --check` before launch | `PASS` |
| `mcp-free` before/after the batch | `STATS kill: none`; active parent-owned MCP processes skipped |
| bounded-scope redesign JSON, verifier compile, reference verifier, and scope probe | `PASS` |

### Runs and calibration

| Row | Run root | Wrapper exit | Verifier / summary | Binary read |
|---|---|---:|---|---|
| `X1 / gpt-5.4` | `.scratch/v2-staged-runs/2026-04-23_20-49-15-X1-wave-w19-n39-bounded-scope-rerun-2026-04-23/N39/` | `0` | final `summary.json` present; verifier `PASS` | `PASS` |
| `X3 / opus 4.7max` | `.scratch/v2-staged-runs/2026-04-23_20-22-31-X3-wave-w19-n39-bounded-scope-rerun-2026-04-23/N39/` | `0` | final `summary.json` present; scope `PASS`; stagegate verifier `FAIL` | scoreable `FAIL` |
| `X2 / gpt-5.3-codex-spark` | `.scratch/v2-staged-runs/2026-04-23_20-49-15-X2-wave-w19-n39-bounded-scope-rerun-2026-04-23/N39/` | `0` | final `summary.json` present; verifier `FAIL`; extra top-level `reports/` paths | scoreable `FAIL` |
| `X5 / gemini3.1pro` | `.scratch/v2-staged-runs/2026-04-23_20-22-31-X5-wave-w19-n39-bounded-scope-rerun-2026-04-23/N39/` | `1` | final `summary.json` present; repeated Gemini capacity exhaustion | `ROUTE-FAIL`; runtime-route |
| `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-staged-runs/2026-04-23_20-22-31-X6-wave-w19-n39-bounded-scope-rerun-2026-04-23/N39/` | `0` | final `summary.json` present; verifier `FAIL` | scoreable `FAIL` |

### Rubric read

| Row | Binary | Scoreability | Rubric | Notes |
|---|---|---|---:|---|
| `X1 / gpt-5.4` | `PASS` | `scoreable` | `94 / 100` | bounded staged systems/toolchain packet completed cleanly |
| `X2 / gpt-5.3-codex-spark` | `FAIL` | `scoreable` | `76 / 100` | bundle drift through top-level `reports/` paths and phase-path misses |
| `X3 / opus 4.7max` | `FAIL` | `scoreable` | `78 / 100` | semantic stagegate failures after scope passed |
| `X5 / gemini3.1pro` | `ROUTE-FAIL` | `runtime-route` | `0 / 100` | runtime-route / quota caveat |
| `X6 / gemini3.1flash-lite-preview` | `FAIL` | `scoreable` | `78 / 100` | omitted required test path and failed functional stagegate invariants |

Machine-readable rubric: `Work/next-upgraded-pack/Evidence/n39-staged-toolchain-rubric-2026-04-23.json`.

Main scoreable failure signatures after bounded-scope redesign:

| Invariant | Detail |
|---|---|
| `X3 stagegate` | selected stale recovery source, used `$product-manager` instead of `$lead`, classified quota as `FAIL`, missed cache restore source phrase, and left ledger/closure markers incomplete |
| `X2 scope-contract` | wrote top-level `reports/` paths and missed required staged phase path rules |
| `X6 scope-contract` | omitted `candidate/workspace/tests/test_stagegate.py` and also failed direct functional stagegate tests |

### N39 Verdict

The bounded-scope redesign removed the exact-scope artifact. N39 is now a usable staged
systems/toolchain separator: `X1 PASS 94 / 100` versus `X3 scoreable FAIL 78 / 100`.
This does not overturn the single-session systems/toolchain read from `N19` and `N24`, but it adds
an execution-shape split: use `X3 primary` for compact single-session systems/toolchain patches and
`X1 primary` for staged systems/toolchain recovery, source arbitration, runtime-status discipline,
and closeout.

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

## 2026-04-24 Follow-Up: X1 GPT-5.5 Full Rerun And Claude Hard-5 Probe

`X1` was switched to `gpt-5.5` and rerun across `S01..S33 + N01..N41`. The logical unique surface
is `74` scenarios. The run produced `75` top-level `summary.json` files because `S13` had an earlier
wrapper-nonzero summary and then a clean retry; the latest `S13` retry is the admitted row.

### X1 GPT-5.5 binary refresh

| Surface | Unique scenarios | Verifier PASS | Verifier FAIL | Runtime caveat |
|---|---:|---:|---:|---|
| `S01..S33 + N01..N41` | `74` | `74` | `0` | none in preferred latest summaries |

Wrapper caveats:

| Scenario | Preferred summary | Wrapper exit | Verifier | Classification |
|---|---|---:|---|---|
| `N30` | `.scratch/v2-staged-runs/2026-04-24_01-34-03-X1-x1-gpt55-full-rerun-2026-04-23-single/N30/meta/summary.json` | `1` | `PASS` | model `PASS`; wrapper caveat only |
| `S13` | `.scratch/v2-cohort-runs/2026-04-24_04-08-51-X1-x1-gpt55-full-rerun-2026-04-23-single/S13/meta/summary.json` | `0` | `PASS` | clean retry supersedes earlier wrapper-nonzero summary |

### Hard-5 comparative probe

The hard subset is `N35`, `N36`, `N37`, `N39`, and `N41`: staged interface migration, staged API
migration, staged review gate, staged systems/toolchain re-entry, and staged incident-budget
re-entry.

| Row / model | `N35` | `N36` | `N37` | `N39` | `N41` | PASS |
|---|---|---|---|---|---|---:|
| `X1 / gpt-5.5` | `PASS` | `PASS` | `PASS` | `PASS` | `PASS` | `5 / 5` |
| `X1 / gpt-5.4 xhigh` | `PASS` | `PASS` | `PASS` | `PASS` | `PASS` | `5 / 5` |
| `X3 / opus 4.7max` | `FAIL 71 / 100` | `FAIL 74 / 100` | `FAIL 35 / 100` | `FAIL 78 / 100` | `FAIL 78 / 100` | `0 / 5` |
| `X4 / Claude China opus max` | `FAIL` | `FAIL` | `FAIL` | `PASS` | `FAIL` | `1 / 5` |
| `official opus 4.5 max` | `FAIL` | `FAIL` | `FAIL` | `FAIL` | `FAIL` | `0 / 5` |
| `official opus 4.6 max` | `FAIL` | `FAIL` | `FAIL` | `FAIL` | `FAIL` | `0 / 5` |
| `official sonnet max` | `FAIL` | `FAIL` | `FAIL` | `NOT-RUN` | `NOT-RUN` | `0 / 3 scoreable` |
| `official haiku max` | `FAIL` | `FAIL` | `FAIL` | `FAIL` | `NOT-RUN` | `0 / 4 scoreable` |

Hard-5 failure signatures:

| Row / model | Main scoreable failure signature |
|---|---|
| `X3 / opus 4.7max` | staged interface/API migration ledger and hidden runtime semantics, exact review tuples/source binding, staged systems stagegate, incident repair/reentry closeout |
| `X4 / Claude China opus max` | same staged families as X3, but `N39` passes through the secret-backed opus route |
| `official opus 4.5 max` | scoreable failures on all five hard staged tests; `N35/N36/N39` also hit scope guards |
| `official opus 4.6 max` | scoreable failures on all five hard staged tests; `N35/N36` hit scope guards |
| `official sonnet max` | scoreable failures on `N35..N37`; `N39/N41` have no final summary and are runtime-route, not model FAIL |
| `official haiku max` | scoreable failures on `N35..N37` and `N39`; `N41` timed out without final summary and is runtime-route, not model FAIL |

### Tooling note

`Work/next-upgraded-pack/Tooling/run-v2-staged-cohort-batch.ps1` now honors
`BENCHMARK_CLAUDE_MODEL_OVERRIDE` and `BENCHMARK_MODEL_LABEL_OVERRIDE` for Claude rows. This was
used only to run official Claude model aliases through `claude.exe` on the same hard-5 staged
surface; it does not change default `X3` or `X4` routing.

`Work/next-upgraded-pack/Tooling/run-v2-cohort-batch.ps1` and
`Work/next-upgraded-pack/Tooling/run-v2-staged-cohort-batch.ps1` also honor
`BENCHMARK_CODEX_MODEL_OVERRIDE` plus optional `BENCHMARK_MODEL_LABEL_OVERRIDE` for Codex rows.
This is a comparison-only override used for explicit model refreshes such as `gpt-5.4` versus the
active `X1 / gpt-5.5` row.

### 2026-04-24 Verdict

The active `X1 / gpt-5.5` row is now cleanly refreshed on the live binary surface and preserves the
staged-separator pattern: `5 / 5` on hard-5 versus `0 / 5` for admitted `X3 / opus 4.7max` and
`1 / 5` for the secret-backed `X4` opus route. The staged integration/refactor/re-entry lane remains
`X1 primary`; compact single-session lanes keep their earlier rubric reads until separately
refreshed.

The explicit `X1 / gpt-5.4 xhigh` comparison rerun also passed `5 / 5` on the same hard-5 staged
subset (`wrapperExitCode=0`, verifier `PASS` for `N35`, `N36`, `N37`, `N39`, and `N41`). The staged
separator pattern is therefore not solely a `gpt-5.5` refresh artifact.

## 2026-04-24 Follow-Up: W22/W23 Immutable-Test Inverse-Separator Probes

`N42-systems-toolchain-immutable-ci-hotfix` and `N43-ui-dirty-state-immutable-test-hotfix` were
added to test whether the earlier single-session `X3` edge on systems/toolchain and UI could be
converted into an honest `X1 FAIL / X3 PASS` separator by protecting visible tests and requiring a
production-only patch. This avoids treating provider transcript size as a semantic model failure.

### Pre-run validation

| Check | Result |
|---|---|
| `N42` JSON parse, bundle-shape, and start-state verifier | `PASS` |
| `N42` production-only reference from prior `X3/N24` source patch | verifier `PASS`; scope `PASS`; tests untouched |
| `N43` JSON parse, bundle-shape, and start-state verifier | `PASS` |
| `N43` production-only reference from prior `X3/N25` source patch | verifier `PASS`; scope `PASS`; tests untouched |
| PowerShell parser checks for cohort/staged runners and `git diff --check` | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Changed production paths | Output bytes |
|---|---|---|---:|---|---:|---:|
| `N42` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-24_04-56-52-X1-wave-w20-n42-immutable-ci-2026-04-24/N42/` | `0` | `PASS` | `5` | `183114` |
| `N42` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-24_04-54-29-X3-wave-w20-n42-immutable-ci-2026-04-24/N42/` | `0` | `PASS` | `5` | `3289` |
| `N43` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-24_05-04-59-X1-wave-w21-n43-ui-immutable-test-2026-04-24/N43/` | `0` | `PASS` | `3` | `157951` |
| `N43` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-24_05-05-00-X3-wave-w21-n43-ui-immutable-test-2026-04-24/N43/` | `0` | `PASS` | `3` | `1956` |

### Verdict

`binary tie remains` on both inverse-separator probes. Explicit immutable-test constraints closed the
suspected X1 over-edit path: `X1 / gpt-5.5` changed only production files on both scenarios. The
remaining difference is output/runtime cost, not semantic correctness. Do not record raw
`worker-output.txt` size as a model-quality fail because the provider CLIs expose different transcript
surfaces; keep it as a cost/route signal in the lane-fit scorecard.

## 2026-04-24 Follow-Up: W24 Interface SourceId Hidden Consumer

`N44-interface-refactor-sourceid-hidden-consumer` extends the earlier `N33` interface-refactor line
with an immutable visible test and a hidden public-result consumer invariant. The visible test stays
outside the allowed change surface; the allowed production/ledger budget is exactly the nine
interfaceflow source and ledger paths.

### Pre-run validation

| Check | Result |
|---|---|
| `N44` JSON parse, bundle-shape, and start-state verifier | `PASS` |
| `N44` production-only reference from prior `X1/N33` source patch plus sourceId report extension | verifier `PASS`; scope `PASS`; visible test untouched |
| `score-n44-interface-sourceid-rubric.py` compile and scorer execution | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Rubric | Changed paths | Output bytes |
|---|---|---|---:|---|---:|---:|---:|
| `N44` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-24_05-48-04-X1-wave-w24-n44-interface-sourceid-2026-04-24/N44/` | `0` | `PASS` | `96 / 100` | `9` | `315371` |
| `N44` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-24_05-37-21-X3-wave-w24-n44-interface-sourceid-2026-04-24/N44/` | `0` | `FAIL` | `72 / 100` | `13` | `3524` |

### Verdict

No inverse `X1 FAIL / X3 PASS` separator was found. `N44` is an `X1`-over-`X3` patch-hygiene
separator, but not a hidden `sourceIds` semantic separator: X3 preserved the interface and hidden
sourceId/report invariants, then failed the exact patch/scope gate by leaving `.pytest_cache` files in
the changed-path set. Record this as scoreable because `wrapperExitCode=0` and the verifier failed,
but keep the failure reason precise.

## 2026-04-24 Follow-Up: W25 Ownership-Budget Immutable Report Consumer

`N45-ownership-budget-immutable-report-consumer` derives from `N29` and keeps the task single-session:
visible tests are protected by hash, the allowed budget is exactly `executor.py`, `report.py`, and
`repair-ledger.json`, and hidden checks cover double-run replay plus public report-consumer fields.

### Pre-run validation

| Check | Result |
|---|---|
| `N45` JSON parse, bundle-shape, and start-state verifier | `PASS` |
| `N45` reference candidate in `.scratch/verifier-probes/2026-04-24-n45-ownership-report-reference` | verifier `PASS`; scope `PASS` |
| `score-n45-ownership-report-rubric.py` compile and scorer execution | `PASS` |
| `git diff --check` before launch | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Rubric | Benchmark changed paths | Output bytes |
|---|---|---|---:|---|---:|---:|---:|
| `N45` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-24_06-32-50-X1-wave-w25-n45-ownership-report-2026-04-24/N45/` | `0` | `PASS` | `96 / 100` | `3` | `180549` |
| `N45` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-24_06-32-50-X3-wave-w25-n45-ownership-report-2026-04-24/N45/` | `0` | `PASS` | `100 / 100` | `3` | `2628` |

### Verdict

`binary tie remains`. The hidden replay and public report-consumer gates did not produce the requested
inverse `X1 FAIL / X3 PASS` separator: both rows preserved the frozen visible test, changed exactly the
three required benchmark paths, and passed verifier/scope with `wrapperExitCode=0`.

The useful signal is cost/compactness, not semantic correctness. X3 wins the rubric only through the
cost bucket (`2628` output bytes versus `180549` for X1). If the next inverse wave tries to separate
this same single-session family, low-noise/cost budget must be an explicit hard requirement rather than
a post-hoc interpretation of raw provider transcript size.

## 2026-04-24 Follow-Up: W26 Operator-Budget Compact Hotfix

`N46-operator-budget-compact-hotfix` converts the strongest W25 signal into a first-class gate rather
than a post-hoc metric. The task remains the same compact DeployGrid repair family with protected
visible test, hidden double-run replay, public report-consumer checks, and exact three-path production
/ ledger budget, but it adds a visible operator budget: `../meta/worker-output.txt` must stay at or
below `40000` bytes.

### Pre-run validation

| Check | Result |
|---|---|
| `N46` JSON parse, bundle-shape, start-state verifier, and operator-budget bundle-shape | `PASS` |
| `N46` reference candidate in `.scratch/verifier-probes/2026-04-24-n46-operator-budget-reference` | ownership verifier `PASS`; operator-budget `PASS`; scope `PASS` |
| `score-n46-operator-budget-rubric.py` compile and scorer execution | `PASS` |
| `git diff --check` before launch | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Rubric | Benchmark changed paths | Output bytes |
|---|---|---|---:|---|---:|---:|---:|
| `N46` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-24_07-01-32-X1-wave-w26-n46-operator-budget-2026-04-24/N46/` | `0` | `FAIL` | `70 / 100` | `3` | `210369` |
| `N46` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-24_07-01-32-X3-wave-w26-n46-operator-budget-2026-04-24/N46/` | `0` | `PASS` | `100 / 100` | `3` | `2378` |

### Verdict

This is the first honest inverse separator found in the compact single-session family:
`X1 FAIL / X3 PASS`. It is scoreable because both wrappers exited `0`, X1 passed the hidden ownership
and exact-scope gates, and the only failed verifier was the visible operator-budget gate:
`210369 > 40000`. X3 passed the same semantic gates and stayed under budget: `2378 <= 40000`.

Record the lane meaning narrowly: `N46` separates low-noise compact-hotfix operator behavior, not
semantic repair correctness. For ordinary compact incident repair without a hard transcript/output
budget, `N45` still ties by binary and X3's edge remains cost/rubric only.

## 2026-04-24 Follow-Up: W27 UI Compact Operator-Budget Hotfix

`N47-ui-compact-operator-budget-hotfix` repeats the explicit low-noise/operator-budget gate on a
different pass/pass family. It derives from the `N43` UI dirty-state immutable-test probe rather than
from DeployGrid ownership repair: visible UI tests are protected by hash, only production UI files are
in scope, hidden dirty-state behavior remains the semantic gate, and `../meta/worker-output.txt` must
stay at or below `40000` bytes.

### Pre-run validation

| Check | Result |
|---|---|
| `N47` JSON parse, verifier compile, bundle-shape, start-state verifier, and operator-budget bundle-shape | `PASS` |
| `N47` reference candidate in `.scratch/verifier-probes/2026-04-24-n47-ui-operator-budget-reference` | UI dirty-state verifier `PASS`; operator-budget `PASS`; scope `PASS` |
| `score-n47-ui-operator-budget-rubric.py` compile and scorer execution | `PASS` |
| `git diff --check` before launch | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Rubric | Benchmark changed paths | Output bytes |
|---|---|---|---:|---|---:|---:|---:|
| `N47` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-24_07-34-56-X1-wave-w27-n47-ui-operator-budget-2026-04-24/N47/` | `0` | `FAIL` | `70 / 100` | `3` | `169913` |
| `N47` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-24_07-34-56-X3-wave-w27-n47-ui-operator-budget-2026-04-24/N47/` | `0` | `PASS` | `94 / 100` | `3` | `2467` |

### Verdict

`N47` is a second honest compact single-session inverse separator: `X1 FAIL / X3 PASS`.
It is scoreable because both wrappers exited `0`, both rows passed the hidden UI dirty-state
semantic verifier and exact-scope gate, and X1 failed only the visible operator-budget gate:
`169913 > 40000`. X3 passed the same semantic/scope gates and stayed under budget:
`2467 <= 40000`.

Record the lane meaning narrowly but more broadly than `N46`: low-noise/operator-budget behavior now
separates both compact DeployGrid repair and compact UI dirty-state repair. This supports `X3
primary` for compact UI hotfixes when operator-facing output budget is part of the task. It does not
mean X1 is worse at UI dirty-state semantics; both rows passed the semantic verifier.

## 2026-04-24 Follow-Up: W28 Visual Raster Compact Operator-Budget Hotfix

`N48-visual-compact-operator-budget-hotfix` repeats the low-noise/operator-budget gate on the visual
graphics raster line. It derives from `N21`, but tightens the task to a renderer-only patch:
`candidate/visual-owned/tests/test_renderer.py` is protected by hash, only
`candidate/visual-owned/src/visual_panel/renderer.py` is in the allowed change surface, the hidden
visual verifier checks exact raster semantics, and `../meta/worker-output.txt` must stay at or below
`40000` bytes.

### Pre-run validation

| Check | Result |
|---|---|
| `N48` JSON parse, verifier compile, bundle-shape, start-state verifier, and operator-budget bundle-shape | `PASS` |
| `N48` renderer-only reference in `.scratch/verifier-probes/2026-04-24-n48-visual-operator-budget-reference` | visual verifier `PASS`; scope `PASS`; operator-budget `PASS` |
| `score-n48-visual-operator-budget-rubric.py` compile and scorer execution | `PASS` |
| `git diff --check` before launch | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Rubric | Benchmark changed paths | Output bytes |
|---|---|---|---:|---|---:|---:|---:|
| `N48` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-24_07-58-51-X1-wave-w28-n48-visual-operator-budget-2026-04-24/N48/` | `0` | `FAIL` | `70 / 100` | `1` | `77825` |
| `N48` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-24_07-58-51-X3-wave-w28-n48-visual-operator-budget-2026-04-24/N48/` | `0` | `PASS` | `100 / 100` | `1` | `813` |

### Verdict

`N48` is the third compact single-session inverse separator: `X1 FAIL / X3 PASS`.
It is scoreable because both wrappers exited `0`, both rows passed exact visual raster semantics and
renderer-only scope, and X1 failed only the visible operator-budget gate: `77825 > 40000`. X3 passed
the same semantic/scope gates and stayed far under budget: `813 <= 40000`.

Record the lane meaning narrowly: this separates low-noise compact visual raster hotfix behavior,
not pixel correctness. Both top rows repaired the raster renderer correctly without changing the
visible test. Together with `N46` and `N47`, the operator-budget inverse pattern now repeats across
repair, UI, and visual graphics lines.

## 2026-04-24 Follow-Up: W29 Scientific Compact Operator-Budget Optimizer

`N49-science-compact-operator-budget-optimizer` tests whether the compact operator-budget separator
also holds on the real scientific optimizer lane. It derives from `N34`, preserving the Method of
Moments PEC cylinder oracle, the hydrogenic radial Schrodinger oracle, staged artifacts, solver
runtime budgets, and exact five-file allowed change surface. The only added hardening is the visible
`../meta/worker-output.txt <= 40000` operator-output gate.

### Pre-run validation

| Check | Result |
|---|---|
| `N49` JSON parse, verifier compile, bundle-shape, start-state verifier, and operator-budget bundle-shape | `PASS` |
| `N49` reference candidate in `.scratch/verifier-probes/2026-04-24-n49-science-operator-budget` | science optimizer verifier `PASS`; scope `PASS`; operator-budget `PASS` |
| `score-n49-science-operator-budget-rubric.py` compile and scorer execution | `PASS` |
| `git diff --check` before launch | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Rubric | Runtime s | Output bytes |
|---|---|---|---:|---|---:|---:|---:|
| `N49` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-24_08-24-09-X1-wave-w29-n49-science-operator-budget-2026-04-24/N49/` | `0` | `PASS` | `96 / 100` | `3.147` | `704` |
| `N49` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-24_08-24-09-X3-wave-w29-n49-science-operator-budget-2026-04-24/N49/` | `0` | `PASS` | `100 / 100` | `2.289` | `1306` |

### Verdict

`binary tie remains` for `N49`: this is negative inverse-separator evidence. Both wrappers exited
`0`, both rows passed the operator-budget gate, the full science optimizer verifier, and exact scope.
X3 wins the rubric by `4` points on measured solver runtime, but the explicit low-noise gate did not
separate the top pair on this scientific optimizer lane.

The practical read is narrower than `N46..N48`: when compactness is stated directly in a complex
scientific task, X1 can adapt and pass. Keep `X3 primary` for compact scientific optimizer work only
as a rubric/runtime preference, not as a binary separator, while `N34` and `N49` both support that
both top rows are viable for real computational-physics correctness.

## 2026-04-24 Follow-Up: W30 Systems Compact Operator-Budget Hotfix

`N50-systems-compact-operator-budget-hotfix` tests whether the explicit low-noise budget repeats on
the systems/toolchain immutable-CI line. It derives from `N42`, preserving the hidden stagegate
systems verifier, protected visible CI test hash, production-only scope, and exact changed-path gate.
The added hardening is the visible `../meta/worker-output.txt <= 40000` operator-output gate.

### Pre-run validation

| Check | Result |
|---|---|
| `N50` JSON parse, verifier compile, bundle-shape, start-state verifier, and operator-budget bundle-shape | `PASS` |
| `N50` reference candidate in `.scratch/verifier-probes/2026-04-24-n50-systems-operator-budget` | stagegate verifier `PASS`; scope `PASS`; operator-budget `PASS` |
| `score-n50-systems-operator-budget-rubric.py` compile and scorer execution | `PASS` |
| `git diff --check` before launch | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Rubric | Elapsed s | Output bytes |
|---|---|---|---:|---|---:|---:|---:|
| `N50` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-24_08-55-28-X1-wave-w30-n50-systems-operator-budget-2026-04-24/N50/` | `0` | `PASS` | `99 / 100` | `395.714` | `131` |
| `N50` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-24_08-55-28-X3-wave-w30-n50-systems-operator-budget-2026-04-24/N50/` | `0` | `PASS` | `99 / 100` | `260.449` | `1061` |

### Verdict

`binary tie remains` for `N50`: this is negative inverse-separator evidence. Both wrappers exited
`0`, both rows passed the operator-budget gate, hidden systems/toolchain verifier, protected visible
test hash, and exact scope. X1 also adapted to the explicit compact-output requirement.

The useful new signal is not output size but elapsed time: X1 needed `395.714s`, while X3 finished
in `260.449s`. If the systems/toolchain compact-hotfix role requires a hard turnaround budget, the
next honest separator attempt should make time a first-class verifier gate instead of using
post-hoc transcript size.

## 2026-04-24 Follow-Up: W31 Systems Turnaround-Budget Hotfix

`N51-systems-turnaround-budget-hotfix` tests the first-class elapsed-time hypothesis raised by
`N50`. It keeps the same hidden stagegate systems verifier, protected visible CI test hash,
production-only scope, and `../meta/worker-output.txt <= 40000` output budget, then adds a scoreable
`prompt.txt -> worker-output.txt <= 360s` turnaround gate.

### Pre-run validation

| Check | Result |
|---|---|
| `N51` JSON parse, verifier compile, bundle-shape, start-state verifier, operator-budget shape, and turnaround-budget shape | `PASS` |
| `N51` reference candidate in `.scratch/verifier-probes/2026-04-24-n51-turnaround-budget` | stagegate verifier `PASS`; scope `PASS`; operator-budget `PASS`; turnaround-budget `PASS` |
| `score-n51-systems-turnaround-budget-rubric.py` compile and scorer execution | `PASS` |
| `git diff --check` before launch | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Rubric | Turnaround s | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---:|---|
| `N51` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-24_09-24-07-X1-wave-w31-n51-turnaround-budget-2026-04-24/N51/` | `0` | `FAIL` | `70 / 100` | `356.406` | `987540` | output budget fail |
| `N51` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-24_09-24-06-X3-wave-w31-n51-turnaround-budget-2026-04-24/N51/` | `0` | `FAIL` | `55 / 100` | `177.885` | `1628` | hidden stagegate semantics fail |

### Verdict

`N51` is not an inverse `X1 FAIL / X3 PASS` separator. It is scoreable because both wrappers exited
`0`, both runs wrote final summaries, and both verifier failures are local benchmark failures rather
than runtime/quota issues.

The result is still useful role-fit evidence: X1 preserved the hidden systems/toolchain semantics,
exact scope, protected test hash, and the `360s` turnaround budget, but failed the visible output
budget badly (`987540 > 40000`). X3 preserved compactness and turnaround (`1628` bytes,
`177.885s`) but failed hidden stagegate invariants: portable fingerprint equality, signed/unsigned
mode conflict rejection, cache restore reason/source trace, and summary source trace. Record this as
`both scoreable FAIL`, not as a top-pair binary separator. For hard compact systems hotfixes, require
an explicit semantic gate plus an output budget; neither row is cleanly dominant under both
constraints.

## 2026-04-24 Follow-Up: W32 Interface Refactor Compact Operator-Budget

`N52-interface-refactor-compact-operator-budget` tests the strongest remaining pass/pass inverse
candidate from `N33`: both top rows passed the hidden interface-refactor semantics there, but X1's
visible output was much larger than X3's. `N52` keeps the N33 hidden consumer verifier, migration
ledger, required changed-path set, and scope gate, then adds `../meta/worker-output.txt <= 40000`.

### Pre-run validation

| Check | Result |
|---|---|
| `N52` JSON parse, verifier compile, bundle-shape, start-state verifier, and operator-budget bundle-shape | `PASS` |
| `N52` reference candidate in `.scratch/verifier-probes/2026-04-24-n52-interface-operator-budget` | interface-refactor verifier `PASS`; scope `PASS`; operator-budget `PASS` |
| `score-n52-interface-refactor-operator-budget-rubric.py` compile and scorer execution | `PASS` |
| `git diff --check` before launch | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Rubric | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---|
| `N52` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-24_09-56-10-X1-wave-w32-n52-interface-operator-budget-2026-04-24/N52/` | `0` | `FAIL` | `70 / 100` | `39316689` | output budget fail |
| `N52` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-24_09-56-10-X3-wave-w32-n52-interface-operator-budget-2026-04-24/N52/` | `0` | `FAIL` | `70 / 100` | `2573` | `.pytest_cache` scope/shape drift |

### Verdict

`N52` is not a clean inverse `X1 FAIL / X3 PASS` separator. Both rows are scoreable failures because
both wrappers exited `0` and final summaries/verifier logs exist.

The useful signal is split by failure type. X1 passed the hidden interface-refactor verifier and
exact required changed-path scope, but failed the visible operator budget massively
(`39316689 > 40000`). X3 stayed compact (`2573 <= 40000`) but created top-level `.pytest_cache`
files, which failed the runner changed-path gate, bundle-shape verifier, and scenario scope verifier.
This repeats the N44 patch-hygiene failure signature rather than proving an interface semantic miss.

If the next goal is to isolate only compact operator behavior for interface refactors, the honest
next wave is a new cache-ignored variant that explicitly treats `.pytest_cache/**` as auxiliary
test-run cache. Do not reinterpret this N52 result as `X3 PASS`.

## 2026-04-24 Follow-Up: W33 Interface Refactor Cache-Ignored Operator-Budget

`N53-interface-refactor-cache-ignored-operator-budget` isolates the question raised by `N52`.
It keeps the N33/N52 hidden interface-refactor semantics, migration ledger, required changed-path
set, and `../meta/worker-output.txt <= 40000`, but explicitly treats top-level `.pytest_cache/**`
as generated test cache rather than as semantic patch drift. Other changed-path drift remains
scoreable.

### Pre-run validation

| Check | Result |
|---|---|
| `N53` JSON parse, verifier compile, bundle-shape, start-state verifier, and operator-budget bundle-shape | `PASS` |
| `N53` reference probe in `.scratch/verifier-probes/2026-04-24-n53-interface-cache-ignored` | interface-refactor verifier `PASS`; scope `PASS` with `.pytest_cache/v/cache/nodeids`; operator-budget `PASS` |
| `score-n53-interface-refactor-cache-ignored-rubric.py` compile and scorer execution | `PASS` |
| `git diff --check` before launch | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Rubric | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---|
| `N53` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-24_10-18-35-X1-wave-w33-n53-interface-cache-ignored-2026-04-24/N53/` | `0` | `PASS` | `100 / 100` | `948` | none |
| `N53` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-24_10-18-34-X3-wave-w33-n53-interface-cache-ignored-2026-04-24/N53/` | `0` | `PASS` | `100 / 100` | `2922` | none |

### Verdict

`binary tie remains` for `N53`: this is negative inverse-separator evidence. Both wrappers exited
`0`, both rows passed the hidden interface-refactor verifier, the visible operator-budget gate,
and exact required-path scope after top-level `.pytest_cache/**` was explicitly ignored as generated
test cache.

This closes the N52 ambiguity. The N52 X3 failure was patch/cache hygiene, not hidden interface
semantics and not low-noise operator behavior. For ordinary compact single-session interface
refactors with generated cache isolated, both top rows are viable; keep the role-fit distinction at
execution shape: X3 for compact single-session refactor style, X1 for staged API/interface migration
and phase-ledger accountability.

## 2026-04-24 Follow-Up: W34 Release Train Compact Operator-Budget

`N54-release-train-compact-operator-budget-gauntlet` tests the same explicit low-noise requirement
on the long-horizon release-train line rather than on UI/visual/interface probes. It derives from
`N27`, preserving the hidden release-train governor verifier, exact deploygrid source scope, stateful
recovery invariants, and scoring rubric, then adds a visible `../meta/worker-output.txt <= 40000`
operator-output gate.

### Pre-run validation

| Check | Result |
|---|---|
| `N54` JSON parse, verifier compile, bundle-shape, start-state verifier, and operator-budget bundle-shape | `PASS` |
| `N54` reference probe in `.scratch/verifier-probes/2026-04-24-n54-release-train-operator-budget` | release-train verifier `PASS`; scope `PASS`; operator-budget `PASS` |
| `score-n54-release-train-operator-budget-rubric.py` compile and scorer execution | `PASS` |
| `git diff --check` before launch | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Rubric | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---|
| `N54` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-24_10-46-52-X1-wave-w34-n54-release-train-operator-budget-2026-04-24/N54/` | `0` | `FAIL` | `70 / 100` | `300873` | output budget fail |
| `N54` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-24_10-46-52-X3-wave-w34-n54-release-train-operator-budget-2026-04-24/N54/` | `0` | `PASS` | `92 / 100` | `2618` | none |

### Verdict

`N54` is the fourth honest compact single-session inverse separator: `X1 FAIL / X3 PASS`.
It is scoreable because both wrappers exited `0`, both rows produced final summaries, and the only
X1 failing verifier is the visible operator-output budget: `300873 > 40000`. X1 still passed the
hidden release-train semantic verifier and exact scope gate. X3 passed the same semantic/scope gates
and stayed compact: `2618 <= 40000`.

Record the lane meaning as compact long-horizon release-train work: this extends the low-noise
operator-budget inverse pattern beyond localized repair/UI/visual probes into a broader
long-horizon integration line. It does not mean X1 is worse at release-train correctness; both rows
preserved the hidden stateful integration semantics.

## 2026-04-24 Follow-Up: W35 Incident Compact Operator-Budget

`N55-incident-compact-operator-budget-gauntlet` repeats the explicit low-noise requirement on the
cross-role incident repair line. It derives from `N28`, preserving the hidden incident integration
verifier, source/review reconciliation note requirements, exact scope, and rubric, then adds a
visible `../meta/worker-output.txt <= 40000` operator-output gate.

### Pre-run validation

| Check | Result |
|---|---|
| `N55` JSON parse, verifier compile, bundle-shape, start-state verifier, and operator-budget bundle-shape | `PASS` |
| `N55` reference probe in `.scratch/verifier-probes/2026-04-24-n55-incident-operator-budget` | incident verifier `PASS`; scope `PASS`; operator-budget `PASS` |
| `score-n55-incident-operator-budget-rubric.py` compile and scorer execution | `PASS` |
| `git diff --check` before launch | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Rubric | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---|
| `N55` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-24_11-20-27-X1-wave-w35-n55-incident-operator-budget-2026-04-24/N55/` | `0` | `FAIL` | `70 / 100` | `352056` | output budget fail |
| `N55` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-24_11-20-27-X3-wave-w35-n55-incident-operator-budget-2026-04-24/N55/` | `0` | `PASS` | `97 / 100` | `1841` | none |

### Verdict

`N55` is the fifth honest compact single-session inverse separator: `X1 FAIL / X3 PASS`.
It is scoreable because both wrappers exited `0`, both rows produced final summaries, and the only
X1 failing verifier is the visible operator-output budget: `352056 > 40000`. X1 still passed the
hidden incident integration/reconciliation verifier and exact scope gate. X3 passed the same gates
and stayed compact: `1841 <= 40000`.

Record the lane meaning as compact cross-role incident repair. Together with `N46`, `N54`, and
`N55`, the long-horizon/incident family now has repeated low-noise inverse separators in favor of
X3 for single-session compact work, while `N41` remains the staged incident-budget separator in
favor of X1.

## 2026-04-24 Follow-Up: W36 Owner Recovery Compact Operator-Budget

`N56-owner-recovery-compact-operator-budget-gauntlet` repeats the explicit low-noise requirement
on the compact owner-recovery packet. It derives from `N26`, preserving the source/stale
classification, interruption continuity, lane-state, gate-order, and denominator-discipline
verifier, then adds a visible `../meta/worker-output.txt <= 40000` operator-output gate.

### Pre-run validation

| Check | Result |
|---|---|
| `N56` JSON parse, verifier compile, bundle-shape, start-state verifier, and operator-budget bundle-shape | `PASS` |
| `N56` reference probe in `.scratch/verifier-probes/2026-04-24-n56-owner-operator-budget` | owner verifier `PASS`; scope `PASS`; operator-budget `PASS` |
| `score-n56-owner-operator-budget-rubric.py` compile and scorer execution | `PASS` |
| `git diff --check` before launch | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Rubric | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---|
| `N56` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-24_12-04-25-X1-wave-w36-n56-owner-operator-budget-2026-04-24/N56/` | `0` | `FAIL` | `70 / 100` | `135621` | output budget fail |
| `N56` | `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-24_12-04-25-X2-wave-w36-n56-owner-operator-budget-2026-04-24/N56/` | `0` | `FAIL` | `10 / 100` | `1596` | semantic packet missing |
| `N56` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-24_12-04-25-X3-wave-w36-n56-owner-operator-budget-2026-04-24/N56/` | `0` | `PASS` | `100 / 100` | `1220` | none |
| `N56` | `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-24_12-04-25-X6-wave-w36-n56-owner-operator-budget-2026-04-24/N56/` | n/a | `NOT-RUN` | `0 / 100` | n/a | runtime no-summary timeout |

### Verdict

`N56` is the sixth honest compact single-session inverse separator: `X1 FAIL / X3 PASS`.
It is scoreable for the top pair because both wrappers exited `0`, both rows produced final
summaries, and the only X1 failing verifier is the visible operator-output budget:
`135621 > 40000`. X1 still passed the hidden owner-recovery packet verifier and exact scope gate.
X3 passed the same gates and stayed compact: `1220 <= 40000`.

Calibration rows do not change the top-pair conclusion. `X2` is a scoreable lower calibration fail:
it stayed compact but left the semantic packet unchanged/missing. `X6` is `runtime-no-summary`
after timeout and is not a model fail. `X5` remains quota-deferred; `X4` is reserved for the final
full closing run.

## 2026-04-24 Follow-Up: W37 Real-Repo Compact API Migration Operator-Budget

`N57-realrepo-compact-api-migration-operator-budget` moves the compact operator-budget test back
onto the interface/API migration lane, but with a real-repo BillingMesh-style domain rather than
the smaller InterfaceFlow fixture. It is a single-run compact task derived from `N36`: hidden API
runtime semantics, source-bound migration ledger, review-response decisions, closeout, exact patch
scope, generated-cache isolation, and a visible `../meta/worker-output.txt <= 40000` gate.

### Pre-run validation

| Check | Result |
|---|---|
| `N57` JSON parse, verifier compile, bundle-shape, start-state verifier, and operator-budget bundle-shape | `PASS` |
| `N57` reference probe in `.scratch/verifier-probes/2026-04-24-n57-compact-api` | compact API verifier `PASS`; scope `PASS`; operator-budget `PASS`; visible tests `PASS` |
| `score-n57-compact-api-migration-rubric.py` compile and scorer execution | `PASS` |
| `git diff --check` before launch | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Rubric | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---|
| `N57` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-24_13-42-06-X1-wave-w37-n57-compact-api-migration-2026-04-24/N57/` | `0` | `FAIL` | `70 / 100` | `3792275` | output budget fail |
| `N57` | `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-24_13-58-42-X2-wave-w37-n57-compact-api-migration-calibration-2026-04-24/N57/` | `0` | `FAIL` | `11 / 100` | `1112` | no migration patch |
| `N57` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-24_13-42-06-X3-wave-w37-n57-compact-api-migration-2026-04-24/N57/` | `0` | `PASS` | `100 / 100` | `2313` | none |
| `N57` | `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-24_13-58-42-X6-wave-w37-n57-compact-api-migration-calibration-2026-04-24/N57/` | n/a | `NOT-RUN` | `0 / 100` | n/a | runtime no-summary timeout |

### Verdict

`N57` is the seventh honest compact single-session inverse separator: `X1 FAIL / X3 PASS`.
It is scoreable because both wrappers exited `0`, both rows produced final summaries, and the only
X1 failing verifier is the visible operator-output budget: `3792275 > 40000`. X1 still passed the
hidden real-repo API migration verifier and exact scope gate. X3 passed the same hidden verifier,
scope gate, and operator budget with `2313 <= 40000`.

This changes the interface/API compact-lane read: after `N53` closed the small InterfaceFlow
fixture as `binary tie remains`, `N57` shows that the larger real-repo compact API migration shape
does separate by low-noise operator budget. Staged API/interface migrations remain `X1 primary`
after `N35` and `N36`; compact real-repo API migrations with explicit low-noise budget now read
`X3 primary`.

Calibration rows do not change the top-pair conclusion. `X2` is a scoreable lower calibration fail:
it stayed compact but made no migration patch and left legacy API, model, ledger, review, closure,
test, and scope invariants failing. `X6` is `runtime-no-summary` after timeout and is not a model
fail. `X5` remains quota-deferred; `X4` is reserved for the final full closing run.

## 2026-04-24 Follow-Up: W38 MoM Batch Runtime Analytical Oracle

`N58-mom-batch-runtime-analytic-oracle` replaces the earlier too-noisy science runtime probe with a
repeated-RHS Method-of-Moments cylinder-scattering task. It preserves the `N49` dual-physics
regression checks for PEC-cylinder MoM and hydrogenic radial Schrodinger, then adds
`solve_cylinder_batch_mom(...)`: one MoM matrix per geometry/frequency, LU/factorization reuse across
many incident-angle RHS vectors, Mie-series analytical validation, density Fourier checks, measured
batch runtime, exact five-file scope, and the visible `../meta/worker-output.txt <= 40000` gate.

### Pre-run validation

| Check | Result |
|---|---|
| `N58` JSON parse, verifier compile, bundle-shape, start-state science verifier, and start-state batch verifier | `PASS` |
| `N58` reference probe in `.scratch/verifier-probes/2026-04-24-n58-mom-batch-reference` | science regression verifier `PASS`; MoM batch runtime verifier `PASS`; reference total batch runtime about `0.663s` versus `13.0s` budget |
| `score-n58-mom-batch-runtime-rubric.py` compile and scorer execution | `PASS` |
| `mcp-free` before and after runs | no kills; parent-owned command helpers skipped |
| `git diff --check` before launch | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Rubric | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---|
| `N58` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-24_17-16-26-X1-wave-w38-n58-mom-batch-runtime-2026-04-24/N58/` | `0` | `FAIL` | `70 / 100` | `2530582` | output budget fail |
| `N58` | `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-24_17-33-10-X2-wave-w38-n58-mom-batch-runtime-2026-04-24-general/N58/` | `0` | `FAIL` | `25 / 100` | `1407` | no batch API / solver markers |
| `N58` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-24_17-16-26-X3-wave-w38-n58-mom-batch-runtime-2026-04-24/N58/` | `0` | `PASS` | `100 / 100` | `2818` | none |
| `N58` | `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-24_17-33-09-X6-wave-w38-n58-mom-batch-runtime-2026-04-24-general/N58/` | n/a | `NOT-RUN` | `0 / 100` | n/a | runtime no-summary timeout |

### Verdict

`N58` is the eighth honest compact single-session inverse separator: `X1 FAIL / X3 PASS`.
It is scoreable for the top pair because both wrappers exited `0`, both rows produced final
summaries, and both rows passed the science regression verifier, the new repeated-RHS MoM batch
runtime verifier, and exact scope. X1's only failing gate is the visible operator-output budget:
`2530582 > 40000`. X3 passed the same physics/runtime/scope gates and stayed compact:
`2818 <= 40000`.

This changes the science/runtime read. `N49` showed that explicit compactness alone did not split
the high-load science optimizer. `N58` shows that a real repeated-RHS CEM task with analytical oracle
and low-noise operator-budget requirement does split the compact science/runtime lane in favor of
X3. The split is still not a physics-correctness split: X1 solved the MoM batch and hydrogenic
regressions correctly, with runtime gates passing, but failed the operator-budget role requirement.

Calibration rows do not change the top-pair conclusion. `X2` is a scoreable lower calibration fail:
it stayed compact but left the starter mostly unchanged, including missing `solve_cylinder_batch_mom`,
missing factorization-reuse marker, missing hydrogen tridiagonal marker, and failing EM/hydrogen
regressions. `X6` is `runtime-no-summary` after a one-hour timeout and is not a model fail. `X5`
remains quota-deferred; `X4` is reserved for the final full closing run.

## 2026-04-24 Follow-Up: W39 Real-Repo Performance Cache Budget

`N59-realrepo-perf-cache-budget` adds a real-repo-style performance-sensitive implementation task.
The starter `QuoteEngine.quote_many(...)` is semantically correct for small cases but performs a full
rule scan per quote. The hardened bundle requires preserving pricing semantics while adding an
owning-boundary cache/index fast path that passes a hidden `6200` request / `5200` rule batch under
`0.70s`.

### Pre-run validation

| Check | Result |
|---|---|
| `N59` JSON parse, verifier compile, bundle-shape verifier, and scope bundle-shape verifier | `PASS` |
| `N59` start-state verifier | `PASS`; expected failures include `performance-budget`, incomplete state/ledger/closure evidence, and missing hot-path test |
| `N59` reference probe in `.scratch/verifier-probes/2026-04-24-n59-reference` | performance-cache verifier `PASS`; scope verifier `PASS`; reference runtime about `0.014s` versus `0.70s` budget |
| `score-n59-perf-cache-rubric.py` compile and scorer execution | `PASS` |
| `mcp-free` before/after provider runs | no kills; parent-owned command helpers skipped |
| `git diff --check` before launch | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Rubric | Runtime | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---:|---|
| `N59` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-24_19-02-57-X1-wave-w39-n59-perf-cache-2026-04-24/N59/` | `0` | `PASS` | `90 / 100` | `0.037078s` | `336382` | none; cost score `0` |
| `N59` | `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-24_19-11-22-X2-wave-w39-n59-perf-cache-2026-04-24-general/N59/` | `0` | `FAIL` | `50 / 100` | `2.921684s` | `1296` | runtime/evidence/scope |
| `N59` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-24_19-02-57-X3-wave-w39-n59-perf-cache-2026-04-24/N59/` | `0` | `PASS` | `100 / 100` | `0.009349s` | `2653` | none |
| `N59` | `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-24_19-11-21-X6-wave-w39-n59-perf-cache-2026-04-24-general/N59/` | n/a | `NOT-RUN` | `0 / 100` | n/a | n/a | runtime no-summary timeout |

### X5 quota probe

After the N59 runs, `X5 / gemini3.1pro` was checked with two minimal probes: the benchmark
`gemini-isolated-worker.ps1` wrapper and a direct `gemini -m gemini-3-pro-high-explicit -p ...`
call. Both timed out without producing worker output, JSON, or an explicit quota-exceeded message.
The direct probe left a Gemini node/cmd process pair, which was stopped by exact PID/command-line
match. Current X5 status is therefore `route/runtime unhealthy`, not `quota clear` and not a
scoreable model failure.

### Verdict

`N59` is a useful real-repo performance lane result, but it is not a binary X1/X3 separator:
`binary tie remains`. Both top rows preserve hidden correctness, pass the batch runtime budget,
update required evidence artifacts, and stay inside exact patch scope.

The routing signal is scored, not binary. X3 wins the role-fit rubric (`100 / 100` versus `90 / 100`)
because it stays compact (`2653` output bytes versus `336382`) and measures faster in scorer rechecks.
Use this as evidence for `X3 primary` on compact single-session real-repo performance hot-path work
when low-noise operation matters. Keep `X1` viable when verbose trace or self-explanatory evidence is
more important than operator cost.

## 2026-04-24 Follow-Up: W40 UI Visual-State Reentry Packet

`N60-ui-visual-state-reentry-packet` converts the unresolved staged `N38` UI/visual/state gauntlet
into a scoreable single-session reentry packet. It preserves the same hidden UI state, ARIA/status,
responsive layout, raster-pixel, PPM, stale-source, implementation-ledger, closure, and exact
changed-path semantics, but removes the four-provider-invocation staged runner boundary that made
`X3/N38` repeatedly end as runtime no-summary.

### Pre-run validation

| Check | Result |
|---|---|
| `N60` JSON parse, verifier compile, bundle-shape, and expected start-state verifier | `PASS` |
| `N60` reference probe in `.scratch/verifier-probes/2026-04-24-n60-reference` | hidden UI visual-state verifier `PASS`; direct Node test `PASS` |
| `score-n60-ui-reentry-rubric.py` compile and scorer execution | `PASS` |
| `mcp-free` before/after runs | pre-run killed none; post-calibration killed orphaned `mcp-language-server.exe` helpers and preserved parent-owned helpers |
| `git diff --check` before launch | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Rubric | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---|
| `N60` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-24_21-18-42-X1-wave-w40-n60-ui-reentry-2026-04-24/N60/` | `0` | `PASS` | `96 / 100` | `308696` | none; cost score `1 / 5` |
| `N60` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-24_21-30-45-X3-wave-w40-n60-ui-reentry-2026-04-24-rerun/N60/` | `0` | `PASS` | `100 / 100` | `3137` | none |
| `N60` | `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-24_21-46-30-X2-wave-w40-n60-ui-reentry-2026-04-24-calibration/N60/` | `0` | `FAIL` | `10 / 100` | `1116` | no patch; asked for next action |
| `N60` | `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-24_21-46-30-X6-wave-w40-n60-ui-reentry-2026-04-24-calibration/N60/` | n/a | `NOT-RUN` | `0 / 100` | n/a | runtime no-summary timeout |

The first `X3` launch at
`.scratch/v2-cohort-runs/2026-04-24_21-18-42-X3-wave-w40-n60-ui-reentry-2026-04-24/N60/`
returned `You've hit your limit - resets 9:30pm (Europe/Moscow)` with no changes. It is recorded as
`NOT-RUN/runtime-route`, not as a model failure. The admitted `X3` result is the post-reset rerun.

### Verdict

`binary tie remains` for `X1` and `X3` on N60: both rows pass hidden UI state, accessibility,
layout, raster, ledger, closure, test, and exact-scope gates. N60 therefore does not create a new
top-pair binary separator.

The role-fit read still favors X3 for compact single-session UI/visual-state reentry work:
`X3 100 / 100` versus `X1 96 / 100`, entirely from output/cost discipline (`3137` bytes versus
`308696`). This closes the N38 runtime ambiguity for the single-session branch: staged UI remains
only an X1 scoreable pass, but compact single-session UI/visual-state work remains X3-primary after
N20, N25, N47, and now N60.

## 2026-04-25 Follow-Up: E51 Visual Pixel-Localization Diagnostic

`N61-visual-pixel-localization-gauntlet` materializes the visual tiny-target localization hypothesis
as a real scenario bundle. The image is a `2200 x 1600` canvas with grid cues, six `13 x 13` solid
targets, same-color decoys, and a point-distance oracle. Passing requires all six target ids exactly
once, mean error `<= 5.0 px`, and max error `<= 8.0 px`, so the verifier allows a several-pixel
window rather than exact-center matching.

The first raw `X1`/`X3` runs were produced before the prompt/schema contract was tightened from a
`points` array into an object keyed by target id. Those raw runs remain useful as diagnostic evidence,
but the post-fix object-map rerun below is the current read.

### Pre-run validation

| Check | Result |
|---|---|
| `N61` oracle/schema JSON parse | `PASS` |
| `N61` bundle-shape verifier | `PASS` |
| `N61` exact reference answer in `.scratch/verifier-probes/2026-04-25-n61-visual/` | `PASS`, mean `0.0 px`, max `0.0 px`, score `100 / 100` |
| `N61` shifted tolerance answer in `.scratch/verifier-probes/2026-04-25-n61-visual/` | `PASS`, mean `4.472 px`, max `4.472 px`, score `99.2 / 100`; confirms the verifier allows a several-pixel window |
| `mcp-free` before runs | killed none |
| `git diff --check` before launch | `PASS` |

### Prompt/schema audit

| Finding | Result |
|---|---|
| Old response contract | Allowed array-style `points`, so a model could emit duplicate candidate points for the same color. |
| Observed impact | `X1` emitted duplicate `red`/`cyan` candidates and omitted four ids; strict first-occurrence mean overstated local pixel error. |
| Current fix | `points` is now an object keyed by `red/cyan/lime/magenta/amber/blue`, requiring exactly one coordinate per target. |
| Verifier diagnostic | Added `best_duplicate_*`, `matched_id_count`, and `within_window_ids` to separate local precision from coverage/format failures on legacy array outputs. |
| Score audit | `score_0_100` now keeps a soft gradient for FAIL cases: coverage `20`, format `20`, within-window count `20`, mean-error gradient `25`, max-error gradient `15`; binary PASS remains unchanged. |
| Post-fix status | Clean `X1`/`X3` rerun completed on the revised object-map prompt/schema. |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Score | Strict mean / max px | Coverage | Primary failure |
|---|---|---|---:|---|---:|---:|---|---|
| `N61` | `X1 / gpt-5.5` | `.scratch/visual-localization-runs/2026-04-25_02-30-14-n61-visual-pixel-localization-2026-04-25-postfix2-x1/` | `0` | `FAIL` | `65.1` | `77.065 / 106.231` | `6 / 6` ids; no target inside `8 px` window | object-map output fixed; all points are wrong-but-bounded, not decoy-level |
| `N61` | `X3 / opus 4.7max` | `.scratch/visual-localization-runs/2026-04-25_02-30-14-n61-visual-pixel-localization-2026-04-25-postfix2-x3/` | `0` | `FAIL` | `50.0` | `344.406 / 1981.709` | `6 / 6` ids; `lime/amber/blue` inside `8 px` window | selected a cyan decoy region; red/magenta exceed strict pass window |
| `N61` | `X5 / gemini3.1pro` | `.scratch/visual-localization-runs/2026-04-25_01-38-23-n61-visual-pixel-localization-2026-04-25-x5-nomcp-timeboxed2/` | `124` | `NOT-RUN` | n/a | n/a | n/a | `600s` timeout before JSON output |
| `N61` | `X6 / gemini3.1flash-lite-preview` | `.scratch/visual-localization-runs/2026-04-25_03-03-26-n61-visual-pixel-localization-2026-04-25-x6/` | `0` | `FAIL` | `40.0` | `363.604 / 1973.736` | `6 / 6` ids; no target inside `8 px` window | quota/route live; selected cyan decoy and missed strict window on all targets |

Superseded pre-revision raw runs:

| Row / model | Run root | Diagnostic read |
|---|---|---|
| `X1 / gpt-5.5` | `.scratch/visual-localization-runs/2026-04-25_01-48-52-n61-visual-pixel-localization-2026-04-25-x1-final/` | legacy array output duplicated `red/cyan`, missed four ids; best duplicate mean/max over attempted ids was `6.525 / 10.05 px` |
| `X3 / opus 4.7max` | `.scratch/visual-localization-runs/2026-04-25_01-23-24-n61-visual-pixel-localization-2026-04-25-x3-nomcp/` | all six ids present, but cyan decoy produced strict mean/max `341.301 / 1983.825 px` |

Fallback diagnostic `gemini-3-flash-preview` was also attempted at
`.scratch/visual-localization-runs/2026-04-25_01-55-59-n61-visual-pixel-localization-2026-04-25-gemini-flash-diagnostic/`.
It timed out after `240s` with only the Gemini wrapper banner and no JSON. This is route evidence
only and is not counted as official `X5`.

### Verdict

`N61` is diagnostic `E51`, not a `full-v2-hard` `/40` slot. It does not produce a binary top-pair
winner because both `X1` and `X3` remain scoreable failures under the strict `5 px` mean / `8 px`
max gate. It does produce a scored pure-localization edge after the prompt/schema fix: `X1` has
lower mean/max error and score `65.1 / 100`, while `X3` has three exact-window hits but one catastrophic
cyan decoy and score `50.0 / 100`. `X6` is quota/route-live but weaker on this visual diagnostic at
`40.0 / 100`. Official `X5` remains runtime-unhealthy for fresh semantic waves and is recorded as
`NOT-RUN`, not as a model-quality failure.

This changes the visual read by separating two surfaces that were previously conflated. Keep `X3`
primary for compact visual/raster code patches after N48/N60. Do not promote a Gemini-first pure
image-localization rule from official benchmark evidence until the Gemini Pro route produces
scoreable output, or until a separately labeled fallback Gemini diagnostic is admitted.

## 2026-04-25 Follow-Up: W41 Frame-Inversion Audit

`N62-frame-inversion-compact-staged-interface` and
`N63-frame-inversion-staged-compact-api-budget` test whether the current `X1`/`X3` split is merely
prompt-frame/style-coded. They intentionally invert the frame while preserving the hard verifier
class: compact wording over N35-class staged interface requirements, and staged wording over
N57-class compact API migration plus visible operator budget.

### Pre-run validation

| Check | Result |
|---|---|
| `N62/N63` JSON parse | `PASS` |
| `N62/N63` bundle-shape verifiers | `PASS` |
| `N62/N63` expected start-state verifier | `PASS`; starter bundles fail as expected under full verification |
| `git diff --check` on new bundles | `PASS` |
| `mcp-free` before model runs | first pass killed orphaned `mcp-language-server.exe`; second pass killed none |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---|
| `N62` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-25_03-48-55-X1-w41-frame-inversion-n62-2026-04-25/N62/` | `0` | `PASS` | n/a | none |
| `N62` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-25_03-48-55-X3-w41-frame-inversion-n62-2026-04-25/N62/` | `0` | `PASS` | n/a | none |
| `N62` | `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-25_04-07-45-X2-w41-frame-inversion-n62-2026-04-25/N62/` | `0` | `FAIL` | n/a | exact scope missed `candidate/workspace/src/interfaceflow/api.py` |
| `N62` | `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-25_04-07-45-X6-w41-frame-inversion-n62-2026-04-25/N62/` | `124` | `NOT-RUN` | n/a | shell timeout before `worker-output.txt` or `summary.json` |
| `N63` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-25_03-59-21-X1-w41-frame-inversion-n63-2026-04-25/N63/` | `0` | `FAIL` | `545831` | operator budget `545831 > 40000`; hidden API/scope checks pass |
| `N63` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-25_03-59-21-X3-w41-frame-inversion-n63-2026-04-25/N63/` | `0` | `PASS` | `3190` | none |
| `N63` | `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-25_04-07-45-X2-w41-frame-inversion-n63-2026-04-25/N63/` | `0` | `FAIL` | `125688` | operator budget `125688 > 40000`; hidden API/scope checks pass |
| `N63` | `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-25_04-07-45-X6-w41-frame-inversion-n63-2026-04-25/N63/` | `124` | `NOT-RUN` | n/a | shell timeout before `worker-output.txt` or `summary.json` |

### X5 quota probe

A short `X5 / gemini3.1pro` probe through `gemini-isolated-worker.ps1` with
`gemini-3-pro-high-explicit` timed out after `180s` without producing
`.scratch/x5-quota-check-2026-04-25_0440.txt` and without an explicit quota/reset message. Current
X5 status remains `route/runtime unhealthy`, not quota-clear and not scoreable model failure.

### Verdict

W41 confirms execution-shape routing rather than invalidating the split.

`N62` makes the N35-class interface migration compact and both top rows pass. Therefore the original
`N35/N36` failures should be read as staged re-entry / multi-session accountability failures, not as
evidence that X3 cannot perform the migration semantics.

`N63` makes the N57-class compact API migration staged in wording, and X1 still fails only the
visible operator-output budget while hidden API migration and exact scope pass. Therefore the compact
low-noise X3 separator is not merely a compact prompt artifact.

Routing remains: `X1 primary` for staged re-entry, multi-session accountability, and phase-ledger
closure; `X3 primary` for compact low-noise/operator-budget implementation.

## 2026-04-25 Follow-Up: W42 Security Depth Review Gauntlet

`N64-security-depth-review-gauntlet` targets unresolved `L10 review.security`. It is a multi-file
review-only bundle with nine exact vulnerability tuples across authz, tenant boundary, sessions,
webhooks, replay, secret exposure, and PII, plus three explicit false-positive traps:
`MASKED_EXAMPLE_TOKEN`, `rel="noopener"`, and `GET /health`.

### Pre-run validation

| Check | Result |
|---|---|
| `N64` JSON parse and bundle-shape verifier | `PASS` |
| `N64` starter full verifier | expected `FAIL`; missing report/gate/tuple content |
| `N64` reference probe in `.scratch/verifier-probes/2026-04-25-n64-reference` | completed report verifier `PASS` |
| `mcp-free` before model runs | `STATS kill: none` |
| `git diff --check` before launch | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---|
| `N64` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-25_04-56-04-X1-w42-security-depth-n64-2026-04-25/N64/` | `0` | `PASS` | `131863` | none |
| `N64` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-25_04-56-03-X3-w42-security-depth-n64-2026-04-25/N64/` | `0` | `PASS` | `1663` | none |
| `N64` | `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-25_05-06-43-X2-w42-security-depth-n64-2026-04-25/N64/` | `0` | `FAIL` | `1442` | did not edit the starter report |
| `N64` | `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-25_05-06-43-X6-w42-security-depth-n64-2026-04-25/N64/` | `1` | local `PASS` | `2463` | runtime caveat: capacity/tool-loop/AbortError produced non-zero wrapper exit |

### Verdict

`binary tie remains` for `X1` and `X3` on L10 security depth. Both top rows pass the exact
nine-finding tuple gate and avoid the false positives. N64 therefore does not assign a security
primary.

Role-fit read: keep ordinary security review as `X1 / X3 near-tie`. X3 has a strong operator-cost
advantage on this diagnostic (`1663` bytes versus `131863`), but that is not enough to promote a
semantic security primary. X2 is a clean lower-bound scoreable fail. X6 produced a locally passing
report, but because the Gemini wrapper returned non-zero after capacity/tool errors, it remains a
runtime-caveat result rather than a clean scoreable pass.

## 2026-04-25 Follow-Up: W43 Visual Correctness Review Gauntlet

`N65-visual-correctness-review-gauntlet` targets unresolved `L12 review.ui-visual-correctness`.
It is a review-only UI packet with DOM, CSS, state-matrix, and screenshot-probe evidence. The
contract requires eight exact visual defect tuples and three false-positive exclusions:
`aria-label`, `decorative-grid`, and `muted-meta`.

### Pre-run validation

| Check | Result |
|---|---|
| `N65` JSON parse and bundle-shape verifier | `PASS` |
| `N65` starter full verifier | expected `FAIL`; missing report/gate/tuple content |
| `N65` reference probe in `.scratch/verifier-probes/2026-04-25-n65-reference` | completed report verifier `PASS` |
| `mcp-free` before model runs | `STATS kill: none` |
| `git diff --check` on new bundle | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---|
| `N65` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-25_05-20-09-X1-w43-visual-correctness-n65-2026-04-25/N65/` | `0` | `PASS` | `94940` | none |
| `N65` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-25_05-20-08-X3-w43-visual-correctness-n65-2026-04-25/N65/` | `0` | `PASS` | `1666` | none |
| `N65` | `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-25_05-23-19-X2-w43-visual-correctness-n65-2026-04-25/N65/` | `0` | `FAIL` | `1094` | did not edit the starter report |
| `N65` | `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-25_05-23-18-X6-w43-visual-correctness-n65-2026-04-25/N65/` | `124` | `NOT-RUN` | n/a | shell timeout after `1800s`; only `prompt.txt` existed in `meta/` |

### Verdict

`binary tie remains` for `X1` and `X3` on L12 visual correctness review. Both top rows pass the
exact eight-finding tuple gate and avoid the false-positive traps. N65 therefore does not assign an
ordinary visual-review primary.

Role-fit read: keep single-shot visual correctness review as `X1 / X3 near-tie`. X3 again has a
large operator-cost advantage (`1666` bytes versus `94940`), but the semantic visual-review gate
does not separate the top pair. This preserves the existing split: use `X3` for compact visual/raster
implementation, treat pure pixel localization as separate diagnostic evidence, and use ordinary
visual review as near-tie until a stronger objective miss appears.

## 2026-04-25 Follow-Up: W44 Conflicting Evidence Fact Memo

`N66-conflicting-evidence-fact-memo-gauntlet` targets `L01 advisory.repo-understanding` with a
bounded repo snapshot containing current code/tests, accepted ADR-011, stale README text, draft
ADR-014, and a stale migration-status note. The memo contract requires source ranking, five conflict
ledger rows, four confirmed facts, four non-claims, and a bounded next action.

### Pre-run validation

| Check | Result |
|---|---|
| `N66` JSON parse and bundle-shape verifier | `PASS` |
| `N66` starter full verifier | expected `FAIL`; missing source ranking, conflict ledger, facts, non-claims, and next-action content |
| `N66` reference probe in `.scratch/verifier-probes/2026-04-25-n66-reference` | completed fact memo verifier `PASS` |
| `mcp-free` before model runs | `STATS kill: none` |
| `git diff --check` on new bundle | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---|
| `N66` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-25_06-07-53-X1-w44-conflicting-evidence-n66-2026-04-25/N66/` | `0` | `PASS` | `169439` | none |
| `N66` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-25_06-07-52-X3-w44-conflicting-evidence-n66-2026-04-25/N66/` | `0` | `PASS` | `1725` | none |
| `N66` | `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-25_06-13-31-X2-w44-conflicting-evidence-n66-2026-04-25/N66/` | `0` | `FAIL` | `76567` | missed source-ranking, conflict-ledger, fact/non-claim, and next-action requirements |
| `N66` | `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-25_06-13-31-X6-w44-conflicting-evidence-n66-2026-04-25/N66/` | `0` | `FAIL` | `3076` | missed source-ranking rows, all five conflict tuples, and multiple fact/non-claim requirements |

### X5 quota probe

A short `X5 / gemini3.1pro` probe through `gemini-isolated-worker.ps1` with
`gemini-3-pro-high-explicit` timed out after `240s` without producing
`.scratch/x5-quota-check-2026-04-25_0621.txt` and without an explicit quota/reset message. Current
X5 status remains `route/runtime unhealthy`, not quota-clear and not scoreable model failure.

### Verdict

`binary tie remains` for `X1` and `X3` on L01 conflicting-evidence repo-understanding. Both top rows
pass the exact source-ranking and conflict-ledger verifier, so N66 does not assign a repo-understanding
primary.

Role-fit read: keep `L01` as `X1 / X3 near-tie` for correctness. X3 has a very large operator-cost
advantage on this diagnostic (`1725` bytes versus `169439`), and both lower calibration rows fail
scoreably, so the scenario is useful for lower-bound separation but not for top-pair primary selection.

## 2026-04-25 Follow-Up: W45 Cross-Phase Integration Owner

`N67-cross-phase-integration-owner-gauntlet` targets staged owner/QA gating. Three accepted upstream
artifacts disagree on the pagination continuation field: backend uses `cursor_token`, frontend uses
`nextCursor`, and QA uses `page_token`. The staged worker must detect the incompatibility before QA,
assign `integration-owner`, stop QA with `REVISE_BEFORE_QA`, and preserve repair/re-entry closure.

### Pre-run validation

| Check | Result |
|---|---|
| `N67` JSON parse and bundle-shape verifier | `PASS` |
| `N67` starter full verifier | expected `FAIL`; missing ledger, report, QA gate, and closure content |
| `N67` reference probe in `.scratch/verifier-probes/2026-04-25-n67-reference` | completed staged packet verifier `PASS` |
| `mcp-free` before and after runs | `STATS kill: none` |
| `git diff --check` on new bundle | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---|
| `N67` | `X1 / gpt-5.5` | `.scratch/v2-staged-runs/2026-04-25_06-31-53-X1-w45-cross-phase-integration-n67-2026-04-25/N67/` | `0` | `PASS` | `260381` | none |
| `N67` | `X3 / opus 4.7max` | `.scratch/v2-staged-runs/2026-04-25_06-31-53-X3-w45-cross-phase-integration-n67-2026-04-25/N67/` | `0` | `FAIL` | `7238` | missed pre-QA compatibility, QA-stop, gate, repair/re-entry, and closure markers |
| `N67` | `X2 / gpt-5.3-codex-spark` | `.scratch/v2-staged-runs/2026-04-25_06-41-40-X2-w45-cross-phase-integration-n67-2026-04-25/N67/` | `0` | `FAIL` | `249910` | did not change `candidate/integration-ledger.json`; exact changed-path contract failed |
| `N67` | `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-staged-runs/2026-04-25_06-41-40-X6-w45-cross-phase-integration-n67-2026-04-25/N67/` | `1` | `NOT-RUN` | `10397` | runtime-caveat non-zero wrapper plus verifier failures on owners, QA gate, repair/re-entry, and closure |

### Verdict

This is an honest top-pair separator: `X1 PASS`, `X3 scoreable FAIL` with `wrapperExitCode=0` and
all four expected candidate paths changed. X3 stayed compact but failed the cross-phase integration
owner semantics that matter: source-ranking/pre-QA compatibility, `REVISE_BEFORE_QA`, `do-not-run-qa`,
repair/re-entry, and closure.

Role-fit read: use `X1` for staged integration-owner packets, cross-phase compatibility checks,
QA-stop decisions, repair/re-entry ledgers, and closure. Use `X3` only for compact single-session
slices where those staged governance semantics are not the work product.

## 2026-04-25 Follow-Up: W46 Actual Screenshot Visual Review

`N68-actual-screenshot-visual-review-gauntlet` targets actual screenshot grounding, not DOM/CSS
retelling. It uses one `1280 x 900` PNG dashboard screenshot with eight seeded visual defects, three
false-positive traps, exact component/defect terms, and coordinate windows. The design follows
GUI/web grounding benchmark patterns: element grounding, screenshot-only visual evidence, coordinate
quality, and false-positive discipline.

### Pre-run validation

| Check | Result |
|---|---|
| `N68` JSON parse and bundle-shape verifier | `PASS` |
| `N68` starter full verifier | expected `FAIL`; empty finding set |
| `N68` reference answer in `.scratch/verifier-probes/2026-04-25-n68-reference-answer.json` | verifier `PASS`; score `100 / 100` |
| `mcp-free` before and after runs | `STATS kill: none` |
| `git diff --check` on new bundle/tooling | `PASS` |

Initial `X1` probes were invalidated by strict output-schema issues, not model quality. The final
run below used the fixed schema and verifier.

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Score | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---|
| `N68` | `X1 / gpt-5.5` | `.scratch/visual-localization-runs/2026-04-25_07-09-07-w46-actual-screenshot-n68-final2-2026-04-25/X1/` | `0` | `FAIL` | `70` | `2742` | missed search-input defect, release-timeline grounding, and required non-finding ledger |
| `N68` | `X3 / opus 4.7max` | `.scratch/visual-localization-runs/2026-04-25_07-09-07-w46-actual-screenshot-n68-final2-2026-04-25/X3/` | `0` | `FAIL` | `80` | `2072` | missed search-input defect and risk-score coordinate grounding |
| `N68` | `X6 / gemini3.1flash-lite-preview` | `.scratch/visual-localization-runs/2026-04-25_07-16-57-w46-actual-screenshot-n68-calibration-final-2026-04-25/X6/` | `0` | `FAIL` | `20` | `2945` | coordinates were scaled/misaligned; no seeded tuple matched |
| `N68` | `X2 / gpt-5.3-codex-spark` | n/a | n/a | `NOT-RUN` | n/a | n/a | current visual runner supports `X1/X3/X5/X6` vision routes only |
| `N68` | `X5 / gemini3.1pro` | n/a | n/a | `NOT-RUN` | n/a | n/a | smoke timed out after `264s` with no output file and no explicit quota/reset message |

### Verdict

N68 is not a binary top-pair separator because both `X1` and `X3` fail. It is still useful visual
grounding evidence: `X3` scores higher (`80 / 100` versus `70 / 100`) on the actual screenshot
review, while `X6` separates lower at `20 / 100`.

Role-fit read: keep ordinary visual correctness review as `X1 / X3 near-tie` after N65. For actual
screenshot coordinate grounding, use `X3` provisionally when the task is screenshot-first and
coordinate/scored-review quality is the deciding factor, but verify because neither top row passed
the strict eight-finding binary gate.

## 2026-04-25 Follow-Up: W47 Real-Repo Patch Quality Scorecard

`N69-realrepo-patch-quality-scorecard` targets compact real-repo implementation with hidden
correctness, runtime, patch-quality, and output-cost scoring. The starter package exposes a visible
charge/refund ledger test while hidden consumers require duplicate replacement by highest `sequence`,
void handling through `voids_event_id`, refund subtraction, currency partitioning, deterministic
evidence ids, no input mutation, and a fast indexed path over `60000` generated events.

### Pre-run validation

| Check | Result |
|---|---|
| `N69` JSON parse and bundle-shape verifier | `PASS` |
| `N69` starter full verifier | expected `FAIL`; hidden semantics, ledger, and patch fields missing |
| `N69` reference probe in `.scratch/verifier-probes/2026-04-25-n69-reference` | verifier `PASS`; runtime `0.032s` under `1.2s` limit |
| `git diff --check` on new bundle/tooling | `PASS` |
| `mcp-free` after runs | `STATS kill: none` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Score | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---|
| `N69` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-25_11-36-07-X1-w47-patch-quality-n69-2026-04-25/N69/` | `0` | `PASS` | `85 / 100` | `149015` | no semantic failure; output-cost score `0` |
| `N69` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-25_11-36-07-X3-w47-patch-quality-n69-2026-04-25/N69/` | `0` | `PASS` | `90 / 100` | `2037` | auxiliary `.pytest_cache` / `__pycache__` churn lowers patch-quality score |
| `N69` | `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-25_11-42-07-X2-w47-patch-quality-n69-2026-04-25/N69/` | `0` | `FAIL` | `35 / 100` | `1087` | made no patch; missed hidden semantics and ledger fields |
| `N69` | `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-25_11-42-07-X6-w47-patch-quality-n69-2026-04-25/N69/` | `0` | `FAIL` | `35 / 100` | `3501` | order-independence hidden semantics and ledger fields failed |

### X5 quota probe

A short `X5 / gemini3.1pro` probe through `gemini-isolated-worker.ps1` with
`gemini-3-pro-high-explicit` timed out after `244s` without producing
`.scratch/x5-quota-check-2026-04-25_1146.txt` and without an explicit quota/reset message. Current
X5 status remains `route/runtime unhealthy`, not quota-clear and not a scoreable model failure.

### Verdict

`binary tie remains` for `X1` and `X3` on the hidden ledger implementation: both pass semantic,
runtime, and required-path gates. The scored role fit separates tradeoffs instead of assigning a
binary primary. `X3` wins total rubric (`90` versus `85`) because it is much cheaper and faster at
the operator-output layer. `X1` wins patch hygiene because it changes only the two required files,
while X3 leaves generated cache artifacts that are counted as auxiliary churn by the W47 scorer.

Role-fit read: use W47 as patch-quality/cost evidence, not a `/40` slot. For compact real-repo
patches where low output cost matters, X3 remains preferred if generated cache/churn is controlled.
For exact patch hygiene and clean workspace discipline, X1 has the safer tendency.

## 2026-04-25 Follow-Up: W48 Entitlement Event Migration Scorecard

`N70-entitlement-event-migration-scorecard` targets a multi-file real-repo-style event schema
migration. The patch surface is parser, engine, reporting, and migration ledger. Hidden consumers
exercise schema-v2 nested identifiers, legacy compatibility, replacement/removal semantics, duplicate
highest-sequence selection, `hold` / `release` state, summary counters, and `50000` generated-event
runtime.

### Pre-run validation

| Check | Result |
|---|---|
| `N70` JSON parse and bundle-shape verifier | `PASS` |
| `N70` visible legacy unittest | `PASS`; `1` visible test |
| `N70` starter full verifier | expected `FAIL`; schema-v2 parser and ledger missing |
| `N70` reference probe in `.scratch/verifier-probes/2026-04-25-n70-reference` | verifier `PASS`; runtime about `1.0s` under final `2.0s` limit |
| `git diff --check` on new bundle/tooling | `PASS` |
| `mcp-free` after runs | `STATS kill: none` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Score | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---|
| `N70` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-25_12-04-30-X1-w48-entitlement-migration-n70-2026-04-25/N70/` | `0` | `PASS` | `85 / 100` | `229032` | no semantic failure; output-cost score `0` |
| `N70` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-25_12-04-30-X3-w48-entitlement-migration-n70-2026-04-25/N70/` | `0` | `PASS` | `90 / 100` | `2395` | auxiliary `__pycache__` churn lowers patch-quality score |
| `N70` | `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-25_12-11-28-X2-w48-entitlement-migration-n70-2026-04-25/N70/` | `0` | `FAIL` | `15 / 100` | `1307` | made no patch; schema-v2 parser exception and ledger failures |
| `N70` | `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-25_12-11-28-X6-w48-entitlement-migration-n70-2026-04-25/N70/` | `1` | `NOT-RUN` | `0 / 100` | `3702` | runtime/tool-loop wrapper failure; local verifier also showed hidden state and ledger misses |

### Verdict

`binary tie remains` for `X1` and `X3` on the multi-file hidden-consumer migration. This is important
negative evidence: simply making the patch multi-file and adding schema-v2 hidden consumers did not
break X3 or create an X1 semantic edge.

The scored split repeats W47: `X3` wins total rubric (`90` versus `85`) through very low output cost;
`X1` wins patch hygiene by changing only required files and leaving no auxiliary cache artifacts.
Promote this as execution-style evidence only, not a binary role separator and not a `/40` slot.

## 2026-04-25 Follow-Up: W49 Test-Led Rate Limit Regression

`N71-test-led-rate-limit-regression-scorecard` targets test-led implementation. The starter
`FixedWindowLimiter` passes a visible single-user test but leaks rate-limit state across users in the
same tenant/route and returns a full-window `retry_after`. The contract requires a production fix,
a meaningful regression test in `tests/test_window_regression.py`, and a `test-ledger.json` packet.

### Pre-run validation

| Check | Result |
|---|---|
| `N71` JSON parse and bundle-shape verifier | `PASS` |
| `N71` visible unittest | `PASS`; `1` visible test |
| `N71` starter full verifier | expected `FAIL`; hidden behavior, regression test, and ledger missing |
| `N71` reference probe in `.scratch/verifier-probes/2026-04-25-n71-reference` | verifier `PASS`; visible tests `PASS` with `2` tests |
| `git diff --check` on new bundle/tooling | `PASS` |
| `mcp-free` after runs | `STATS kill: none` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Score | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---|
| `N71` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-25_12-23-57-X1-w49-test-led-rate-limit-n71-2026-04-25/N71/` | `0` | `PASS` | `83 / 100` | `135535` | auxiliary `.pytest_cache` / `__pycache__` churn; output-cost partial |
| `N71` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-25_12-23-57-X3-w49-test-led-rate-limit-n71-2026-04-25/N71/` | `0` | `PASS` | `90 / 100` | `2410` | auxiliary `__pycache__` churn |
| `N71` | `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-25_12-28-47-X2-w49-test-led-rate-limit-n71-2026-04-25/N71/` | `0` | `FAIL` | `15 / 100` | `1587` | no patch; hidden behavior, regression test, and ledger failed |
| `N71` | `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-25_12-28-45-X6-w49-test-led-rate-limit-n71-2026-04-25/N71/` | `0` | `FAIL` | `15 / 100` | `3748` | visible tests / regression-test artifact / ledger failed |

### Verdict

`binary tie remains` for `X1` and `X3`. The hypothesis that this small test-led patch would create an
X1-over-X3 binary edge did not hold: both rows fixed behavior and supplied an accepted regression
test artifact. X3 wins the scored rubric (`90` versus `83`) through output cost and lower auxiliary
churn. X1 remains safe on semantic correctness, but this N71 construction should not be used as a
hard X1-primary proof for test-led implementation.

## 2026-04-25 Follow-Up: W50 Caller-Spanning API Refactor

`N72-caller-spanning-api-refactor-scorecard` changes the W47-W49 axis from internal patch semantics
to interface breakage across multiple callers. The starter `billinglink` package only supports legacy
`customer_id` payloads. The hidden contract requires schema-v2 `AccountRef` payloads, legacy
compatibility, service/API/CLI/report propagation, payload immutability, exact five-file scope, and a
complete `refactor-ledger.json`.

### Pre-run validation

| Check | Result |
|---|---|
| `N72` JSON parse and bundle-shape verifier | `PASS` |
| `N72` visible legacy unittest | `PASS`; `2` visible tests |
| `N72` starter full verifier | expected `FAIL`; hidden caller contracts and ledger missing |
| `N72` reference probe in `.scratch/verifier-probes/2026-04-25-n72-reference` | verifier `PASS`; exact changed paths accepted |
| `git diff --check` on new bundle/tooling | `PASS` |
| `mcp-free` after runs | `STATS kill: none` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Score | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---|
| `N72` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-25_14-22-54-X1-w50-caller-spanning-api-n72-2026-04-25/N72/` | `0` | `PASS` | `83 / 100` | `146983` | hidden callers pass; auxiliary `__pycache__` churn; output-cost partial |
| `N72` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-25_14-22-54-X3-w50-caller-spanning-api-n72-2026-04-25/N72/` | `0` | `PASS` | `90 / 100` | `2599` | hidden callers pass; auxiliary `__pycache__` churn |
| `N72` | `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-25_14-28-30-X2-w50-caller-spanning-api-n72-2026-04-25/N72/` | `0` | `FAIL` | `15 / 100` | `1467` | no patch; hidden API/service/CLI/report caller contracts and ledger failed |
| `N72` | `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-25_14-28-29-X6-w50-caller-spanning-api-n72-2026-04-25/N72/` | n/a | `NOT-RUN` | `0 / 100` | n/a | shell timeout after `1800s`, no `summary.json`; local probe of partial run root also failed visible and hidden contracts |

### X5 quota probe

A short `X5 / gemini3.1pro` probe through `gemini-isolated-worker.ps1` with
`gemini-3-pro-high-explicit` timed out after `244s` without producing
`.scratch/x5-quota-check-2026-04-25_1459.txt` and without an explicit quota/reset message. Current
X5 status remains `route/runtime unhealthy`, not quota-clear and not a scoreable model failure.

### Verdict

`binary tie remains` for `X1` and `X3`. This is negative evidence against the hypothesis that a
single-session caller-spanning API refactor is enough to produce an X1 semantic edge: both top rows
preserved legacy compatibility and satisfied hidden API, service, CLI, and report callers. X3 again
wins scored fit through output cost; X1 remains semantically safe but not binary-superior on this
single-session refactor surface.

Role-fit read: keep staged API/interface migration as `X1 primary` after N35/N36. Keep ordinary
single-session caller-spanning refactors as `X1 / X3 binary near-tie`; choose X3 when cost/compactness
matters and enforce cache/scope hygiene explicitly.

## 2026-04-25 Follow-Up: W51 DOM Event Runtime UI

`N73-dom-event-runtime-ui-scorecard` targets runtime UI behavior rather than static markup. The
bundle uses a dependency-free Node DOM/event harness that imports the candidate UI modules, mounts
the board, dispatches filter clicks, keyboard dirty toggles, and save clicks, then checks DOM state,
`aria-pressed`, `data-visible`, dirty status, save disabled state, and source payload immutability.

### Pre-run validation

| Check | Result |
|---|---|
| `N73` JSON parse and bundle-shape verifier | `PASS` |
| `N73` visible render check | `PASS` |
| `N73` starter hidden verifier | expected `FAIL`; filter, keyboard dirty, save, and ledger gaps |
| `N73` reference probe in `.scratch/verifier-probes/2026-04-25-n73-reference` | verifier `PASS`; exact changed paths accepted |
| `git diff --check` on new bundle/tooling | `PASS` |
| `mcp-free` after runs | `STATS kill: none` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Score | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---|
| `N73` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-25_15-28-28-X1-w51-dom-event-runtime-ui-n73-2026-04-25/N73/` | `0` | `PASS` | `93 / 100` | `138818` | none; exact five-path patch and DOM runtime pass |
| `N73` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-25_15-28-28-X3-w51-dom-event-runtime-ui-n73-2026-04-25/N73/` | `0` | `PASS` | `93 / 100` | `2467` | none; exact five-path patch and DOM runtime pass; elapsed proxy pushed cost bucket to partial |
| `N73` | `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-25_15-37-59-X2-w51-dom-event-runtime-ui-n73-2026-04-25/N73/` | `0` | `FAIL` | `15 / 100` | `1034` | no patch; filter, keyboard, save, and ledger failed |
| `N73` | `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-25_15-37-57-X6-w51-dom-event-runtime-ui-n73-2026-04-25/N73/` | `0` | `FAIL` | `15 / 100` | `3840` | dirty status and ledger completeness failed; changed only three of five required paths |

### Verdict

`binary tie remains` for `X1` and `X3`. Runtime DOM/event execution did not create a top-pair
semantic separator: both rows handled filtering, keyboard dirty toggles, save behavior, exact scope,
and immutability. X1 was faster by prompt-to-output proxy (`238.595s` versus `500.130s`), X3 was much
more compact (`2467` bytes versus `138818`), and the current rubric gives both the same `93 / 100`.

Role-fit read: keep compact UI implementation as X3-leaning only when low-noise/output budget is a
hard gate (N47/N60 evidence). For DOM event runtime correctness without a strict output budget, use
`X1 / X3` as binary near-tie and verify the actual UI behavior.

## 2026-04-25 Follow-Up: W52 DOM Runtime Output Budget

`N74-dom-runtime-output-budget-scorecard` repeats the N73 deterministic DOM/event runtime harness and
adds a visible operator-output budget verifier. The runtime contract still checks filter clicks,
keyboard dirty toggles, save behavior, exact five-path scope, payload immutability, and the
`ui-runtime-ledger.json`. The added budget contract reads the runner-owned `meta/worker-output.txt`
and fails if visible operator output exceeds `50000` bytes.

### Pre-run validation

| Check | Result |
|---|---|
| `N74` JSON parse and DOM/runtime bundle-shape verifier | `PASS` |
| `N74` operator-budget bundle-shape verifier | `PASS` |
| `N74` visible render check | `PASS` |
| `N74` starter hidden verifier | expected `FAIL`; runtime/ledger gaps remain in starter |
| `N74` reference probe in `.scratch/verifier-probes/2026-04-25-n74-reference` | DOM/runtime verifier `PASS`; operator-budget verifier `PASS` with synthetic meta output |
| `git diff --check` on new bundle/tooling | pending post-documentation rerun |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Score | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---|
| `N74` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-25_16-05-25-X1-w52-dom-runtime-output-budget-n74-2026-04-25/N74/` | `0` | `FAIL` | `80 / 100` | `241980` | DOM runtime and exact scope pass; visible operator-output budget fails |
| `N74` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-25_16-05-25-X3-w52-dom-runtime-output-budget-n74-2026-04-25/N74/` | `0` | `PASS` | `100 / 100` | `2085` | none; DOM runtime, exact scope, and output budget pass |

Calibration rows were not launched in W52. W51 had just run `X2` and `X6` on the same DOM runtime
base, and N74 changes only the top-pair visible output-budget gate. Keep lower-row calibration for
the next completed semantic task or final comparison sweep.

### Verdict

This is an honest compact inverse separator: `X1 / gpt-5.5` preserved runtime UI semantics and exact
scope but scoreably failed the visible operator-budget contract (`241980 > 50000`), while
`X3 / opus 4.7max` passed all runtime and budget gates (`2085 <= 50000`).

Role-fit read: for DOM event runtime correctness without strict output budget, N73 remains
`X1 / X3` near-tie. For compact UI implementation where low visible operator output is a first-class
contract, N74 reinforces `X3 primary`.

## 2026-04-25 Follow-Up: W53 Persisted-State Replay Migration

`N75-persisted-state-replay-migration-scorecard` changes the W50-W52 axis to persisted state. The
bundle requires v1/v2 event normalization, source immutability, idempotent replay by `dedupe_key`,
checkpoint rollback, schema-v2 persist/load envelopes, exact six-path scope, a visible regression
test, and `migration-ledger.json` coverage.

### Pre-run validation

| Check | Result |
|---|---|
| `N75` JSON parse and bundle-shape verifier | `PASS` |
| `N75` visible legacy replay unittest | `PASS`; `1` visible test |
| `N75` starter hidden verifier | expected `FAIL`; immutability, schema, dedupe, rollback, persistence, and ledger gaps |
| `N75` reference probe in `.scratch/verifier-probes/2026-04-25-n75-reference/N75` | verifier `PASS`; exact changed paths accepted |
| `git diff --check` on new bundle/tooling before launch | `PASS` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Score | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---|
| `N75` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-25_16-38-26-X1-w53-persisted-state-replay-n75-2026-04-25/N75/` | `0` | `PASS` | `83 / 100` | `148703` | none semantically; auxiliary `__pycache__` churn and partial cost |
| `N75` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-25_16-38-26-X3-w53-persisted-state-replay-n75-2026-04-25/N75/` | `0` | `PASS` | `83 / 100` | `2577` | none semantically; auxiliary `__pycache__` churn; elapsed cost bucket partial |
| `N75` | `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-25_16-47-04-X2-w53-persisted-state-replay-n75-2026-04-25/N75/` | `0` | `PASS` | `75 / 100` | `182431` | none semantically; auxiliary session-log churn and output-cost zero |
| `N75` | `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-25_16-47-03-X6-w53-persisted-state-replay-n75-2026-04-25/N75/` | n/a | `NOT-RUN` | `0 / 100` | n/a | shell timeout after `1800s`; no `summary.json` |

### Verdict

`binary tie remains` for `X1` and `X3`. The hidden persisted-state replay/rollback oracle is not
enough by itself to separate the top pair in a single-session implementation frame: both pass
schema migration, source immutability, idempotent replay, rollback, persistence, exact scope, and
visible regression gates. X2 also passes semantically, which marks N75 as a poor top-pair separator
but useful lower-bound evidence for this fixture shape.

Role-fit read: ordinary single-session persisted-state migration joins caller-spanning refactor and
small test-led regression as `X1 / X3` near-tie. To separate this lane further, the next attempt must
add staged re-entry, real repo integration, or stricter runtime/operability constraints rather than
only more hidden replay cases.

## 2026-04-25 Follow-Up: W54 Staged Persisted-State Reentry

`N76-staged-persisted-state-reentry-gauntlet` is the staged version of N75. It keeps the same hidden
runtime state oracle, but spreads the task across four fresh invocations: source ledger, migration
implementation, re-entry validation, and closeout. The verifier requires the runtime migration gates
plus exact staged artifacts: `source-ledger.json`, `migration-ledger.json`, `reentry-state.json`, and
`closeout.json`.

### Pre-run validation

| Check | Result |
|---|---|
| `N76` JSON parse and bundle-shape verifier | `PASS` |
| `N76` starter hidden verifier | expected `FAIL`; staged ledgers and runtime migration gaps |
| `N76` reference probe in `.scratch/verifier-probes/2026-04-25-n76-reference/N76` | verifier `PASS`; exact changed paths accepted |
| `git diff --check` before launch | `PASS` |
| `mcp-free` before calibration | `STATS kill: none` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Score | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---|
| `N76` | `X1 / gpt-5.5` | `.scratch/v2-staged-runs/2026-04-25_19-34-56-X1-w54-staged-persisted-state-n76-2026-04-25/N76/` | `0` | `PASS` | `85 / 100` | `870319` | none semantically; output cost zero and auxiliary cache churn |
| `N76` | `X3 / opus 4.7max` | `.scratch/v2-staged-runs/2026-04-25_19-34-55-X3-w54-staged-persisted-state-n76-2026-04-25/N76/` | `0` | `FAIL` | `15 / 100` | `7852` | missing `migrator.py` changed path, schema version, persist envelope, source/migration/reentry/closeout ledger contracts |
| `N76` | `X2 / gpt-5.3-codex-spark` | `.scratch/v2-staged-runs/2026-04-25_19-55-46-X2-w54-staged-persisted-state-n76-2026-04-25/N76/` | `0` | `FAIL` | `70 / 100` | `503532` | semantic behavior passes, but exact staged scope fails because `migrator.py` was not changed |
| `N76` | `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-staged-runs/2026-04-25_19-55-45-X6-w54-staged-persisted-state-n76-2026-04-25/N76/` | n/a | `NOT-RUN` | `0 / 100` | n/a | shell timeout during phase 2 after Gemini capacity/registry errors; no final `summary.json` |

### Verdict

This is a scoreable X1-over-X3 staged persisted-state separator. N75 proved that a single-session
persisted-state replay migration is too easy; N76 adds staged source arbitration, implementation,
re-entry validation, and closeout, and the top pair splits cleanly. X3 stays compact but loses
required runtime and artifact contracts. X2 passes most semantics but misses exact staged scope.

Role-fit read: persisted-state/interface migration should be `X1 primary` when staged re-entry,
source-ledger accountability, validation status, and closeout are part of the job. Compact
single-session persisted-state migration remains near-tie after N75.

## 2026-04-25 Follow-Up: W55 Security Capability Runtime Patch

`N77-security-capability-runtime-scorecard` targets the unresolved security implementation branch
instead of another security review memo. The bundle requires a dependency-free capability-token
repair with HMAC-SHA256 signing, tenant/user/resource/expiry/nonce binding, replay rejection, exact
redirect validation, audit redaction, a focused regression test, exact five-path scope, and a
`security-ledger.json` artifact. Hidden verifier checks are runtime exploit attempts, not textual
claims.

### Pre-run validation

| Check | Result |
|---|---|
| `N77` JSON parse and bundle-shape verifier | `PASS` |
| `N77` starter verifier | expected `FAIL`; unsigned token, weak binding, redirect, audit, test, and ledger gaps |
| `N77` reference probe in `.scratch/verifier-probes/2026-04-25-n77-reference/N77` | verifier `PASS`; exact changed paths accepted |
| `git diff --check` before launch | `PASS` |
| `mcp-free` after calibration | `STATS kill: none`; parent-owned MCP helpers skipped |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Score | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---|
| `N77` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-25_21-13-11-X1-w55-security-capability-n77-2026-04-25/N77/` | `0` | `PASS` | `85 / 100` | `404044` | none semantically; output-cost score `0` |
| `N77` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-25_21-13-11-X3-w55-security-capability-n77-2026-04-25/N77/` | `0` | `PASS` | `93 / 100` | `2598` | none semantically; auxiliary `__pycache__` churn lowers artifact score |
| `N77` | `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-25_21-22-42-X2-w55-security-capability-n77-2026-04-25/N77/` | `0` | `FAIL` | `15 / 100` | `1231` | no patch; runtime exploit, static, test, and ledger gates fail |
| `N77` | `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-25_21-22-41-X6-w55-security-capability-n77-2026-04-25/N77/` | n/a | `NOT-RUN` | `0 / 100` | n/a | shell timeout after `2400s`; no `summary.json` |

### Verdict

`binary tie remains` for `X1` and `X3` on single-session security implementation. Both top rows
closed the hidden runtime exploit oracle and preserved exact scope. X3 has the better operator-cost
profile (`93 / 100` versus `85 / 100`); X1 has no auxiliary cache churn but emits much larger output.
X2 is a scoreable lower-row no-op fail. X6 remains a runtime no-summary caveat.

Role-fit read: ordinary single-session security patching should stay `X1 / X3 near-tie`, with X3
preferred when compact output is a first-class operator metric and X1 preferred when trace-heavy
security reasoning or workspace hygiene is valued. The next useful security separator should be a
staged security re-entry variant, not more exploit cases in the same single-session frame.

## 2026-04-25 Follow-Up: W56 Staged Security Reentry

`N78-staged-security-reentry-gauntlet` is the staged version of N77. It keeps the same hidden runtime
exploit oracle, but spreads the work across four fresh invocations: threat ledger, implementation,
exploit validation/re-entry, and closeout. The verifier requires the runtime security gates plus
exact staged artifacts: `threat-ledger.json`, `security-ledger.json`, `exploit-validation.json`,
`reentry-state.json`, and `closeout.json`.

### Pre-run validation

| Check | Result |
|---|---|
| `N78` JSON parse and bundle-shape verifier | `PASS` |
| `N78` starter verifier | expected `FAIL`; runtime exploit and staged artifact gaps |
| `N78` reference probe in `.scratch/verifier-probes/2026-04-25-n78-reference/N78` | verifier `PASS`; exact changed paths accepted |
| `git diff --check` before launch | `PASS` |
| `mcp-free` after calibration | `STATS kill: none`; parent-owned MCP helpers skipped |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Score | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---|
| `N78` | `X1 / gpt-5.5` | `.scratch/v2-staged-runs/2026-04-25_22-21-21-X1-w56-staged-security-reentry-n78-2026-04-25/N78/` | `0` | `PASS` | `85 / 100` | `613332` | none semantically; output-cost score `0` |
| `N78` | `X3 / opus 4.7max` | `.scratch/v2-staged-runs/2026-04-25_22-21-20-X3-w56-staged-security-reentry-n78-2026-04-25/N78/` | `0` | `FAIL` | `23 / 100` | `8299` | percent-encoded CRLF redirect trap, missing structured-url marker, staged ledger/validation/closeout contract gaps |
| `N78` | `X2 / gpt-5.3-codex-spark` | `.scratch/v2-staged-runs/2026-04-25_22-45-22-X2-w56-staged-security-reentry-n78-2026-04-25/N78/` | `0` | `FAIL` | `45 / 100` | `1011624` | runtime exploit patch passes, but exact scope and staged artifact gates fail |
| `N78` | `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-staged-runs/2026-04-25_22-45-22-X6-w56-staged-security-reentry-n78-2026-04-25/N78/` | n/a | `NOT-RUN` | `0 / 100` | n/a | shell timeout after `2400s`; no `summary.json` |

### Verdict

This is a scoreable X1-over-X3 staged security separator. N77 proved that a single-session security
implementation with hidden exploit tests ties the top pair; N78 adds staged threat modeling,
implementation accountability, exploit validation, re-entry state, and closeout, and the top pair
splits cleanly. X3 remains compact but misses both a hidden redirect exploit and staged artifact
contracts. X2 can fix the runtime exploit but fails the staged scope/artifact layer.

Role-fit read: security implementation should now follow the same execution-shape rule as API,
systems, owner, review, and persisted-state lanes. Use `X1 primary` for staged security re-entry,
threat-ledger accountability, validation status, and closeout. Keep compact single-session security
patching as `X1 / X3 near-tie`, with X3 only preferred when output compactness is first-class.

## 2026-04-28 Follow-Up: W57 Staged UI Visual-State Reentry V2

`N79-staged-ui-visual-state-reentry-v2` replaces the brittle `N38` staged UI branch with a bounded
four-phase UI/visual-state packet: source/state ledger, state/render implementation,
layout/raster validation, and reentry closeout. It keeps the hidden N60 UI state, accessibility,
layout, raster-pixel, ledger, closure, test, and exact-scope oracle, but makes the staged evidence
scoreable for the top pair.

### Pre-run validation

| Check | Result |
|---|---|
| `N79` JSON parse and bundle-shape verifier | `PASS` |
| `N79` starter verifier | expected `FAIL`; state/render/layout/raster/ledger/closure gaps |
| `N79` synthesized reference probe in `.scratch/verifier-probes/2026-04-28-n79-staged-ui-valid` | verifier `PASS`; exact changed paths accepted |
| `git diff --check` before launch | `PASS` |
| `mcp-free` before launch | `STATS kill: none`; parent-owned helpers skipped |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Score | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---|
| `N79` | `X1 / gpt-5.5` | `.scratch/v2-staged-runs/2026-04-28_16-23-10-X1-w57-n79-staged-ui-reentry-2026-04-28/N79/` | `0` | `PASS` | `96 / 100` | `1296881` | none semantically; output-cost score `1` |
| `N79` | `X3 / opus 4.7max` | `.scratch/v2-staged-runs/2026-04-28_16-23-10-X3-w57-n79-staged-ui-reentry-2026-04-28/N79/` | `0` | `FAIL` | `63 / 100` | `9604` | visible blocked cue, focus return id, active descendant/accessibility, compact layout containment, raster overlay order, ledger/closure markers |

### Verdict

This is a scoreable X1-over-X3 staged UI/visual-state separator. It is not a quota, timeout, or
no-summary result: both wrappers exited `0`, both produced four phase summaries, and X3 passed exact
changed-path scope plus phase-path discipline before failing the hidden UI/visual-state verifier.

Role-fit read: compact single-session UI remains X3-primary when low-noise/output budget is explicit
after N47/N60/N74. Staged UI/visual-state reentry is now X1-primary after N79 because X1 preserves
state, accessibility, layout, raster, ledger, closeout, and exact scope across fresh invocations.

## 2026-04-28 Follow-Up: W58 Screenshot Grounding Review V2

`N80-screenshot-grounding-review-v2` converts the earlier `N68` actual-screenshot review into a
calibrated visual-grounding diagnostic: one deterministic `1600 x 1100` dashboard screenshot, ten
seeded visual defects, nonzero `22 px` coordinate tolerance, false-positive traps, exact JSON shape,
and a score threshold (`>= 8 / 10` matched and `>= 80 / 100`) instead of brittle `0 px` matching.

### Pre-run validation

| Check | Result |
|---|---|
| `N80` JSON parse for oracle/schema | `PASS` |
| `N80` bundle-shape verifier | `PASS` |
| `N80` starter verifier | expected `FAIL`; no findings |
| `N80` synthesized reference probe in `.scratch/verifier-probes/2026-04-28-n80-recalibrated-valid-answer.json` | verifier `PASS`; `10 / 10`, `100 / 100` |
| `git diff --check` before launch | `PASS` |
| `mcp-free` before launch | `STATS kill: none`; parent-owned helpers skipped |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Score | Matched | Mean / max px | Output bytes | Primary failure |
|---|---|---|---:|---|---:|---:|---:|---:|---|
| `N80` | `X1 / gpt-5.5` | `.scratch/visual-localization-runs/2026-04-28_17-14-34-w58-n80-screenshot-grounding-2026-04-28-rerun/X1/` | `0` | `PASS` | `82 / 100` | `8 / 10` | `2.855 / 7.071` | `26503` | none; clean PASS threshold |
| `N80` | `X3 / opus 4.7max` | `.scratch/visual-localization-runs/2026-04-28_17-14-34-w58-n80-screenshot-grounding-2026-04-28-rerun/X3/` | `0` | `FAIL` | `63 / 100` | `7 / 10` | `8.067 / 17.117` | `2755` | missed run-button, heatmap legend, toast/button artifacts; false-positive on header ornament |

### Verdict

This is a scoreable X1-over-X3 screenshot-grounding separator. It is not route/runtime noise: both
wrappers exited `0`, both produced parseable JSON, and both were scored by the same calibrated oracle.
X1 passes the visual grounding threshold with lower coordinate error and no false positives. X3 stays
compact, but misses the match threshold and flags an intentional header/skeleton ornament as a defect.

Role-fit read: actual screenshot grounding is no longer just the earlier non-binary N68 X3-scored edge.
When calibrated pixel windows, semantic defect tuples, and false-positive traps are first-class, X1 is
the current primary for screenshot grounding. Compact visual/raster code patches remain X3-primary only
when low-noise/operator budget is the hard gate.

## 2026-04-28 Follow-Up: W59 Evidence Conflict Repo Action Plan

`N81-evidence-conflict-repo-action-plan` tests whether a repo-understanding advisory task can split
the top pair when the candidate must reconcile current code/tests, command output, an accepted ADR,
stale docs, a mixed migration note, and a draft rollback ADR into a bounded action plan.

### Pre-run validation

| Check | Result |
|---|---|
| `N81` JSON parse for oracle/schema | `PASS` |
| `N81` bundle-shape verifier | `PASS` |
| `N81` starter verifier | expected `FAIL`; no required action-plan sections |
| `N81` synthesized reference probe in `.scratch/verifier-probes/2026-04-28-n81-evidence-action/valid-action-plan.md` | verifier `PASS`; `24 / 24`, `100 / 100` |
| `git diff --check` before launch | `PASS` |
| `mcp-free` before launch | `STATS kill: none`; parent-owned helpers skipped |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Score | Matched | Changed paths | Primary failure |
|---|---|---|---:|---|---:|---:|---|---|
| `N81` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-28_17-33-47-X1-w59-n81-evidence-action-2026-04-28/N81/run` | `0` | `PASS` | `100 / 100` | `24 / 24` | `candidate/action-plan.md` | none |
| `N81` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-28_17-33-47-X3-w59-n81-evidence-action-2026-04-28/N81/run` | `0` | `PASS` | `100 / 100` | `24 / 24` | `candidate/action-plan.md` | none |

### Verdict

`binary tie remains` for `X1` and `X3` on the N81 repo-understanding/action-plan task. Both rows
produce the exact source-authority, conflict-ledger, command-evidence, action-plan, non-claim, and
re-intake structure. N81 is retained as negative separator evidence for `advisory.repo-understanding`;
it does not assign a primary.

Verifier note: the X3 worker output explicitly observed that forbidden literal snippets can be
gamed with inserted tokens. Future evidence-conflict scenarios should prefer decision-context checks
and table-specific stale-claim assertions over broad literal substring traps.

## 2026-04-28 Follow-Up: W60 UX Runtime State Spec

`N82-ux-structure-runtime-state-spec` converts the UX-structure lane from a prose brief into a
valid-JSON runtime-state contract with five states, three breakpoint invariants, six affordance rules,
five copy-ledger entries, three handoff contracts, and five non-goals.

### Pre-run validation

| Check | Result |
|---|---|
| `N82` JSON parse for oracle and input faults | `PASS` |
| `N82` bundle-shape verifier | `PASS` |
| `N82` starter verifier | expected `FAIL`; placeholder JSON only |
| `N82` synthesized reference probe in `.scratch/verifier-probes/2026-04-28-n82-ux-state/valid-ux-state-spec.json` | verifier `PASS`; `27 / 27`, `100 / 100` |
| `git diff --check` before launch | `PASS` |
| `mcp-free` before launch | `STATS kill: none`; parent-owned helpers skipped |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Score | Matched | Changed paths | Primary failure |
|---|---|---|---:|---|---:|---:|---|---|
| `N82` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-28_17-53-25-X1-w60-n82-ux-state-2026-04-28/N82/run` | `0` | `PASS` | `100 / 100` | `27 / 27` | `candidate/ux-state-spec.json` | none |
| `N82` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-28_17-53-25-X3-w60-n82-ux-state-2026-04-28/N82/run` | `0` | `PASS` | `100 / 100` | `27 / 27` | `candidate/ux-state-spec.json` | none |

### Verdict

`binary tie remains` for `X1` and `X3` on the N82 objective UX state-spec task. This is negative
separator evidence for `design.ui-ux-structure`: single-shot JSON anchors are not enough to split the
top pair. Future UX/design separation should use runtime simulation, staged UX review, or calibrated
visual grounding rather than term-matched JSON anchors.

## 2026-04-28 Follow-Up: W61 Interface Refactor Breakage Hunt

`N83-interface-refactor-breakage-hunt` retests interface-refactor quality without making visible
operator-output budget the decisive gate. The hidden oracle requires structured result dataclasses,
removal of the legacy `get/evaluate/dispatch` public methods, `handle_event_batch` order and
duplicate-state behavior, rejected-request non-dispatch, structured-report compatibility, exact
ten-path scope, visible regression markers, and a migration ledger.

### Pre-run validation

| Check | Result |
|---|---|
| `N83` JSON parse and bundle-shape verifier | `PASS` |
| `N83` starter verifier | expected `FAIL`; legacy methods, missing dataclasses, batch API, structured report, and ledger gaps |
| `N83` synthesized reference probe in `.scratch/verifier-probes/2026-04-28-n83-interface-valid` | verifier `PASS`; exact changed paths accepted |
| `git diff --check` before launch | `PASS` |
| `mcp-free` before launch | `STATS kill: none`; parent-owned helpers skipped |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Changed paths | Primary failure |
|---|---|---|---:|---|---|---|
| `N83` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-28_18-32-26-X1-wave61-n83-interface-refactor-breakage-final-2026-04-28/N83/run` | `0` | `PASS` | ten required candidate paths; generated cache auxiliary | none |
| `N83` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-28_18-32-26-X3-wave61-n83-interface-refactor-breakage-final-2026-04-28/N83/run` | `0` | `PASS` | ten required candidate paths; generated cache auxiliary | none |

### Verdict

`binary tie remains` for `X1` and `X3` on N83. The batch hidden-consumer and structured-report
runtime checks did not split the top pair. Interface-refactor routing remains execution-shape based:
staged API/interface migration is X1-primary after N35/N36; compact operator-budget API migration is
X3-primary after N57; ordinary single-session hidden-consumer interface refactor remains near-tie
when generated cache is treated as auxiliary.

Runner note: this wave fixed the v2 runner's generated-artifact split so top-level `.pytest_cache/`
is classified as auxiliary cache, matching the existing nested cache behavior. Earlier N83 raw runs
that failed only on top-level `.pytest_cache/` scope were harness false positives, not model failures.

## 2026-04-28 Follow-Up: W62 Security Review Reproduction Gauntlet

`N84-security-review-repro-gauntlet` hardens ordinary single-session security review beyond N64's
tuple-retelling shape. The editable artifact is a single JSON report. PASS requires nine exact
security findings, `R1..R9` exploit reproduction binding, source evidence, violated invariant,
fix-boundary ownership, `B1..B3` false-positive suppression, exact `REVISE` gate decision, and exact
changed-path scope.

### Pre-run validation

| Check | Result |
|---|---|
| `N84` JSON parse and bundle-shape verifier | `PASS` |
| `N84` starter verifier | expected `FAIL`; empty findings and missing gate decision |
| `N84` synthesized reference probe in `.scratch/verifier-probes/2026-04-28-n84-security-repro-valid` | verifier `PASS`; exact changed path accepted |
| stale N64/markdown split-brain scan | `PASS`; no stale `review-report.md` / old verifier references |
| `git diff --check` before launch | `PASS` |
| `mcp-free` before launch | `STATS kill: none`; parent-owned helpers skipped |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Changed paths | Worker output | Primary failure |
|---|---|---|---:|---|---|---:|---|
| `N84` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-28_19-05-21-X1-wave62-n84-security-repro-2026-04-28/N84/run` | `0` | `PASS` | `candidate/review-report.json` | `247446` bytes | none |
| `N84` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-28_19-05-21-X3-wave62-n84-security-repro-2026-04-28/N84/run` | `0` | `PASS` | `candidate/review-report.json` | `1628` bytes | none |

### Verdict

`binary tie remains` for `X1` and `X3` on N84. Exploit reproduction binding and false-positive
suppression strengthen ordinary security review versus N64, but both top rows still satisfy the
complete JSON oracle. Routing impact: ordinary single-session security review stays `X1 / X3
near-tie`; choose `X3` when compact review output is first-class, choose `X1` when verbose
traceability is preferred. Staged security implementation/re-entry remains `X1 primary` after N78.

## 2026-04-28 Follow-Up: W63 Performance Runtime Budget

`N85-performance-review-runtime-budget` replaces the weaker N59 performance-cache slot for the
canonical `full-v2-hard /40` surface. It keeps N59's hidden quote-pricing correctness, measured
batch runtime, evidence JSON, and exact patch-scope checks, then adds a visible hard
`worker-output.txt <= 40000` budget. In this lane, output cost is part of the performance operator
contract rather than a secondary style preference.

### Pre-run validation

| Check | Result |
|---|---|
| `N85` JSON parse and bundle-shape verifiers | `PASS` |
| `N85` starter verifier | expected `FAIL`; slow hot path and missing evidence |
| `N85` synthesized valid probe in `.scratch/verifier-probes/2026-04-28-n85-performance-valid/N85/run` | verifier `PASS`; runtime `0.009939s <= 0.7s`; operator output `89 <= 40000` |
| stale `N59` / `E49` scan inside N85 | `PASS` |
| `git diff --check` before launch | `PASS` |
| `mcp-free` before launch | `STATS kill: none`; parent-owned helpers skipped |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Runtime | Output budget | Changed paths | Classification |
|---|---|---|---:|---|---:|---:|---|---|
| `N85` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-28_19-27-57-X1-wave63-n85-performance-runtime-2026-04-28/N85/run` | `0` | `FAIL` only `check_operator_budget.py` | `0.015369s <= 0.7s` | `266051 > 40000` | five required benchmark paths | scoreable `FAIL` |
| `N85` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-28_19-27-57-X3-wave63-n85-performance-runtime-2026-04-28/N85/run` | `0` | `PASS` | `0.014301s <= 0.7s` | `1827 <= 40000` | six accepted benchmark paths | `PASS` |
| `N85` | `X2 / gpt-spark` | `.scratch/v2-cohort-runs/2026-04-28_19-36-19-X2-wave63-n85-performance-runtime-fill-2026-04-28/N85/run` | `0` | `FAIL` runtime/evidence/scope | `3.508s > 0.7s` | `1217 <= 40000` | none | scoreable `FAIL` |
| `N85` | `X6 / flash-lite` | `.scratch/v2-cohort-runs/2026-04-28_19-36-19-X6-wave63-n85-performance-runtime-fill-2026-04-28/N85/run` | `1` | route/auth before model work | n/a | n/a | none | `NOT-RUN`; Gemini `UNSUPPORTED_LOCATION` |

### Verdict

N85 is the first promoted `full-v2-hard /40` replacement after the N79+ diagnostic series. It
replaces N59 in `L06 systems/performance-worker`: X1 passes the hidden performance/correctness/scope
work but scoreably fails the hard operator-output budget; X3 passes all gates compactly. Current
top-pair canonical score becomes `X1 34 / 40` versus `X3 35 / 40`.

## 2026-04-28 Follow-Up: W65 Real Interface Downstream Migration

`N86-real-interface-downstream-migration` removes the N57-style operator-output budget and tests a
BillingMesh API migration through hidden repo consumers plus a hidden downstream app that imports
only the public `billingmesh` package exports. PASS requires structured dataclass result models,
legacy method removal, public root exports, downstream `dataclasses.asdict` compatibility,
denied-without-publish, retryable timeout, duplicate non-republish behavior, structured reporting,
source-bound ledgers, review response, closeout, and exact changed-path scope.

### Pre-run validation

| Check | Result |
|---|---|
| `N86` JSON parse and verifier compile | `PASS` |
| `N86` bundle-shape verifier | `PASS` |
| `N86` starter verifier | expected `FAIL`; legacy APIs, missing result models, ledger gaps, and downstream public-app failure present |
| synthesized valid probe in `.scratch/verifier-probes/2026-04-28-n86-interface-valid/N86` | verifier `PASS`; scope `PASS` |
| stale N57/operator-budget scan inside N86 | `PASS`; no `operator`, `low-noise`, `check_operator`, or `compact-api-contract` references |
| `git diff --check` before launch | `PASS` |
| `mcp-free` before launch | `STATS kill: none`; parent-owned helpers skipped |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Interface/downstream verifier | Scope | Worker output | Classification |
|---|---|---|---:|---|---|---:|---|
| `N86` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-28_20-34-35-X1-wave65-n86-interface-downstream-2026-04-28/N86/run` | `0` | `PASS` | `PASS`; all 12 required paths changed | `462449` bytes | `PASS` |
| `N86` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-28_20-34-35-X3-wave65-n86-interface-downstream-2026-04-28/N86/run` | `0` | `PASS` | `FAIL`; missing `candidate/workspace/src/billingmesh/api.py` | `2764` bytes | scoreable `FAIL` |

### Verdict

N86 is an honest X1-over-X3 diagnostic separator for real interface migration when exact migration
surface completeness is part of the contract. The split is not a runtime/quota issue and not an
output-budget issue: X3 passed the hidden interface/downstream semantic verifier, then failed the
exact changed-path migration surface by leaving `api.py` unchanged. Do not promote N86 into
`full-v2-hard /40` without a later named slot-replacement decision.

## 2026-04-28 Follow-Up: W66 Performance Review Gate

`N87-performance-review-gate` tests a read-only performance architecture review without any
operator-output budget. PASS requires rejecting warm-cache-only speedup evidence, diagnosing cache
key context loss, diagnosing global cache lifetime growth, rejecting false-positive hot-path claims,
classifying author responses, returning `REVISE`, and keeping exact five-artifact review scope.

### Pre-run validation

| Check | Result |
|---|---|
| `N87` JSON parse and verifier compile | `PASS` |
| `N87` bundle-shape verifier | `PASS` |
| `N87` starter verifier | expected `FAIL`; source ledger, findings, response gate, closure, and gate decision incomplete |
| synthesized valid probe in `.scratch/verifier-probes/2026-04-28-n87-performance-review-valid/N87` | verifier `PASS`; scope `PASS` |
| stale N37/security-review scan inside N87 | `PASS` |
| `git diff --check` before launch | `PASS` |
| `mcp-free` before launch | `STATS kill: none`; parent-owned helpers skipped |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Scope | Worker output | Classification |
|---|---|---|---:|---|---|---:|---|
| `N87` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-28_21-05-51-X1-wave66-n87-performance-review-2026-04-28/N87/run` | `0` | `PASS` | `PASS`; exact five review artifacts | `154170` bytes | `PASS` |
| `N87` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-28_21-05-50-X3-wave66-n87-performance-review-2026-04-28/N87/run` | `0` | `PASS` | `PASS`; exact five review artifacts | `2466` bytes | `PASS` |

### Verdict

`binary tie remains` for X1 and X3 on N87. Benchmark admissibility, cache-boundary review,
memory-lifetime diagnosis, false-positive restraint, and exact `REVISE` gate discipline are not
enough to split the top pair in this read-only performance-review frame. Keep N87 diagnostic-only;
do not replace N07 in `full-v2-hard /40` from this result.

## 2026-04-28 Follow-Up: W67 UX Runtime Event-Policy Simulator

`N88-ux-runtime-event-policy-simulator` tests whether UX structure can split through hidden runtime
event-policy simulation rather than term-matched JSON anchors. The bundle is design-only: candidates
must update runtime, breakpoint, and re-entry policy JSON, with no implementation/UI/CSS edits.
The hidden simulator checks stale remote source handling, owner-required publishing, regression-proof
requirements, priority ordering when failures combine, auditor-export scope, post-publish follow-up
diff handling, ready-state publishing, breakpoint ordering, and re-entry persistence.

### Pre-run validation

| Check | Result |
|---|---|
| `N88` JSON parse and verifier compile | `PASS` |
| `N88` bundle-shape verifier | `PASS` |
| `N88` starter verifier | expected `FAIL`; runtime, breakpoint, and re-entry policy files are placeholders |
| synthesized valid probe in `.scratch/verifier-probes/2026-04-28-n88-ux-runtime-policy-valid/N88` | verifier `PASS`; `100.0 / 100` |
| stale N82/E72 scan inside N88 | `PASS` |
| `git diff --check` before launch | `PASS` |
| `mcp-free` before launch | `STATS kill: none`; parent-owned helpers skipped |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Changed paths | Worker output | Classification |
|---|---|---|---:|---|---|---:|---|
| `N88` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-28_21-26-25-X1-wave67-n88-ux-runtime-policy-2026-04-28/N88/run` | `0` | `PASS`; `100.0 / 100` | `candidate/breakpoint-policy.json`, `candidate/reentry-policy.json`, `candidate/runtime-policy.json` | `151375` bytes | `PASS` |
| `N88` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-28_21-26-23-X3-wave67-n88-ux-runtime-policy-2026-04-28/N88/run` | `0` | `PASS`; `100.0 / 100` | `candidate/breakpoint-policy.json`, `candidate/reentry-policy.json`, `candidate/runtime-policy.json` | `2758` bytes | `PASS` |

### Verdict

`binary tie remains` for X1 and X3 on N88. Hidden event-policy simulation is stronger than the N82
runtime-state JSON contract, but both top rows satisfy it. X3 is much more compact; compactness is
not a binary winner here because no output budget is part of N88. Keep N88 diagnostic-only; do not
replace N02 or any canonical `/40` UX slot from this result.

## 2026-04-28 Follow-Up: W68 Security Runtime Witness Review

`N89-security-review-runtime-witness-gauntlet` tests whether ordinary single-session security review
can split through executable witness binding while remaining review-only. It keeps the N84 envelope
of one mutable `candidate/review-report.json`, then adds verifier-owned runtime probes over the
admin, session, webhook, audit, and export target. Admission is v3 only: earlier v1/v2 debug runs
were discarded after review found answer-key leakage and weak witness exactness.

### Pre-run validation

| Check | Result |
|---|---|
| `N89` JSON parse and verifier compile | `PASS` |
| `N89` bundle-shape verifier | `PASS` |
| `N89` starter verifier | expected `FAIL`; report scaffold lacks findings, false positives, witness matrix, and gate decision |
| synthesized valid probe in `.scratch/verifier-probes/2026-04-28-n89-security-runtime-witness-v3-valid/N89` | verifier `PASS`; `100.0 / 100` |
| answer-leakage review | `PASS`; oracle JSON hides exact findings/witness rows; verifier uses opaque tuple digests plus dynamic runtime execution |
| protected-target tamper probe | `PASS`; default/bundle-shape verifier fails on changed `candidate/review-target/security-depth/admin_api.py` |
| false-positive cardinality probe | `PASS`; extra `B4` row fails exact `falsePositiveAvoided` count |
| stale N84/E74 scan inside N89 | `PASS` |
| `git diff --check` before launch | `PASS` |
| `mcp-free` before launch | `STATS kill: none`; parent-owned helpers skipped |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Changed paths | Worker output | Classification |
|---|---|---|---:|---|---|---:|---|
| `N89` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-28_22-29-33-X1-wave68-n89-security-runtime-witness-v3-2026-04-28/N89/run` | `0` | `PASS`; `100.0 / 100` | `candidate/review-report.json`; verifier-created `__pycache__` classified auxiliary | `158078` bytes | `PASS` |
| `N89` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-28_22-29-32-X3-wave68-n89-security-runtime-witness-v3-2026-04-28/N89/run` | `0` | `PASS`; `100.0 / 100` | `candidate/review-report.json`; verifier-created `__pycache__` classified auxiliary | `1951` bytes | `PASS` |

### Verdict

`binary tie remains` for X1 and X3 on N89. Executable runtime witness binding, exact structured
`witnessMatrix` rows, false-positive cardinality, protected target hashes, and review-only scope
still do not split ordinary single-session security review. X3 is much more compact, but compactness
is not a binary winner because N89 has no output budget. Keep N89 diagnostic-only; staged security
implementation/re-entry remains X1-primary after N78.

## 2026-04-28 Follow-Up: W69 Staged UX Review Reentry Gate

`N90-staged-ux-review-reentry-gate` tests the unresolved staged UX-review axis after N82 and N88
proved that single-shot UX policy/spec tasks still tie. The bundle is review-only: candidates must
produce staged source/state, ADR, findings, response-gate, and closeout artifacts while the
publish-console review target remains immutable. The verifier uses protected target hashes,
runtime witness execution, opaque exact finding-tuple digests, hidden response-decision digests,
false-positive controls, and exact five-artifact changed-path scope.

### Pre-run validation

| Check | Result |
|---|---|
| `N90` JSON parse and verifier compile | `PASS` |
| `N90` bundle-shape verifier | `PASS` |
| `N90` starter verifier | expected `FAIL`; state, ADR, findings, response gate, and closure are placeholders |
| synthesized valid probe in `.scratch/verifier-probes/2026-04-28-n90-staged-ux-review-valid/N90` | verifier `PASS`; `100.0 / 100` |
| exact changed-path positive probe | `PASS`; five required review artifacts accepted |
| exact changed-path negative probe | `PASS`; single-path run rejected |
| answer-leakage review | `PASS`; oracle JSON exposes shape/count/enums, while exact findings and response decisions are verifier-owned opaque checks |
| `git diff --check` before launch | `PASS` |
| `mcp-free` before launch | `STATS kill: none`; parent-owned helpers skipped |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Changed paths | Worker output | Classification |
|---|---|---|---:|---|---|---:|---|
| `N90` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-28_23-10-15-X1-wave69-n90-staged-ux-review-2026-04-28/N90/run` | `0` | `PASS`; `100.0 / 100` | exact five review artifacts | `396503` bytes | `PASS` |
| `N90` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-28_23-10-15-X3-wave69-n90-staged-ux-review-2026-04-28/N90/run` | `0` | `PASS`; `100.0 / 100` | exact five review artifacts; target `__pycache__` classified auxiliary | `1539` bytes | `PASS` |

### Verdict

`binary tie remains` for X1 and X3 on N90. Staged UX review/reentry with runtime witness binding,
opaque exact tuples, hidden response decisions, protected target hashes, and exact changed-path scope
still does not split the top pair. X3 is much more compact, but compactness is not a binary winner
because N90 has no output budget. Keep N90 diagnostic-only; do not replace N02, S30, or any
canonical `/40` UX review slot from this result. Next work should change axis rather than further
tighten staged UX review.

## 2026-04-29 Follow-Up: W70 Real-Repo Staged Security Incident Reentry

`N91-realrepo-staged-security-incident-reentry` repeats the staged security idea in a real-repo-style
repair bundle instead of another review-only report. Candidates must repair tenant-bound export
authorization, HMAC-bound download tokens, redirect allowlisting, and audit redaction while also
updating incident, repair, exploit-validation, reentry, and closeout ledgers. The verifier owns
hidden runtime exploit checks for cross-tenant support access, break-glass support flow, owner/admin
authorization, token tamper, replay, expiry, resource/user binding, redirect traps, audit redaction,
protected starter hashes, and exact ten-path changed scope.

### Pre-run validation

| Check | Result |
|---|---|
| `N91` JSON parse and verifier compile | `PASS` |
| `N91` bundle-shape verifier | `PASS` |
| `N91` starter verifier | expected `FAIL`; starter has the tenant/support/token/redirect/audit defects |
| synthesized valid probe in `.scratch/verifier-probes/2026-04-29-n91-security-incident-valid/N91` | verifier `PASS`; `100.0 / 100` |
| exact changed-path positive probe | `PASS`; ten required artifacts accepted |
| exact changed-path negative probe | `PASS`; single-path run rejected |
| `git diff --check` before launch | `PASS` |
| `mcp-free` before launch | `STATS kill: none`; parent-owned helpers skipped |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Changed paths | Worker output | Classification |
|---|---|---|---:|---|---|---:|---|
| `N91` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-29_00-02-54-X1-wave70-n91-security-incident-2026-04-29/N91/run` | `0` | `PASS`; `100.0 / 100` | exact ten security/ledger artifacts | `867547` bytes | `PASS` |
| `N91` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-29_00-02-54-X3-wave70-n91-security-incident-2026-04-29/N91/run` | `0` | `PASS`; `100.0 / 100` | exact ten security/ledger artifacts | `2752` bytes | `PASS` |

### Verdict

`binary tie remains` for X1 and X3 on N91. Real-repo staged security incident repair with hidden
runtime exploit checks, exact changed-path scope, protected starter hashes, regression tests, and
reentry/closeout ledgers is solved by both top rows. X3 is much more compact, but compactness is not
a binary winner because N91 has no output budget. Keep N91 diagnostic-only; do not replace N78 or
any canonical `/40` slot from this result. The next useful top-pair separator should move to a
different implementation axis, preferably real-repo staged interface/downstream reentry rather than
more security/review-only hardening.

## 2026-04-29 Follow-Up: W71 Staged Interface Downstream Reentry

`N92-staged-interface-downstream-reentry-gauntlet` switches away from security/review-only hardening
and tests a new SubscriptionMesh interface migration. It combines staged source/reentry artifacts,
public package facade migration, a legacy-event adapter, hidden downstream SDK clean-room import,
dataclass wire contracts, denied-without-webhook, timeout retryability, duplicate suppression, mixed
structured reporting, protected input hashes, and exact fifteen-path changed scope.

### Pre-run validation

| Check | Result |
|---|---|
| `N92` JSON parse and verifier compile | `PASS` |
| `N92` bundle-shape verifier | `PASS` |
| `N92` starter verifier | expected `FAIL`; starter has legacy APIs, no dataclasses, incomplete public facade, and empty ledgers |
| synthesized valid probe in `.scratch/verifier-probes/2026-04-29-n92-staged-interface-valid/N92` | verifier `PASS`; `100.0 / 100` |
| exact changed-path positive probe | `PASS`; fifteen required artifacts accepted |
| exact changed-path negative probe | `PASS`; omission of `candidate/workspace/src/subscriptionmesh/api.py` rejected |
| cache auxiliary probe | `PASS`; subscriptionmesh `__pycache__` path ignored as generated cache |
| public facade mutation probe | expected `FAIL`; missing root `handle_subscription_event` breaks clean-room import |
| legacy wrapper mutation probe | expected `FAIL`; reintroduced `get_customer` fails static/runtime/test gates |
| `git diff --check` before launch | `PASS` |
| `mcp-free` before launch | first pass killed 2 orphan `uvx.exe`; second pass `STATS kill: none` |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Changed paths | Worker output | Classification |
|---|---|---|---:|---|---|---:|---|
| `N92` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-29_13-37-12-X1-wave71-n92-x1-retry-2026-04-29/N92/run` | `0` | `PASS`; `100.0 / 100` | exact fifteen benchmark artifacts | `454833` bytes | `PASS` |
| `N92` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-29_00-38-09-X3-wave71-n92-staged-interface-2026-04-29/N92/run` | `0` | `PASS`; `100.0 / 100` | exact fifteen benchmark artifacts; subscriptionmesh `__pycache__` auxiliary | `3189` bytes | `PASS` |

### Verdict

`binary tie remains` for X1 and X3 on N92. The earlier X1 quota row is superseded by the
`2026-04-29_13-37-12` retry: wrapper exit `0`, verifier PASS, and exact fifteen benchmark changed
paths. X3 also passed with exact benchmark scope. N92 is diagnostic-only and does not change the
canonical `full-v2-hard /40` surface without a separate slot-replacement decision.

## 2026-04-29 Follow-Up: W72 Multipackage Protocol SDK Reentry

`N93-multipackage-protocol-sdk-reentry` was prepared and then run as the next interface-breakage
separator axis. It extends the N92 idea into a multi-package ProtocolMesh SDK/CLI/plugin migration:
core routing, SDK v2 wire serialization, legacy envelope migration, plugin delivery, CLI structured
return, staged source/migration/sdk-compat/reentry ledgers, protected input hashes, clean-room
public package imports, and exact nineteen-path scope. Top-pair runs used `X1` and `X3`; calibration
then ran `X2` and `X6`. `X4` remained final-only and `X5` remained parked.

### Preparation validation

| Check | Result |
|---|---|
| `N93` verifier py_compile | `PASS` |
| `N93` oracle JSON parse | `PASS` |
| `N93` bundle-shape verifier | `PASS` |
| `N93` starter verifier | expected `FAIL`; starter has legacy wrappers, no dataclasses, incomplete package-root exports, weak CLI, and empty ledgers |
| synthesized valid probe in `.scratch/verifier-probes/2026-04-29-n93-protocol-valid/N93` | verifier `PASS`; `100.0 / 100` |
| exact changed-path negative probe | expected `FAIL`; omission of `candidate/workspace/src/protocolmesh_sdk/serializer.py` rejected |
| cache auxiliary probe | `PASS`; protocolmesh SDK `__pycache__` changed path ignored as generated cache |
| public export mutation probe | expected `FAIL`; missing `protocolmesh_sdk.migrate_legacy_envelope` root export breaks visible/import/runtime gates |
| legacy wrapper mutation probe | expected `FAIL`; reintroduced `send_event` fails static legacy-wrapper gate |

### Runs

| Scenario | Row / model | Run root | Wrapper exit | Verifier | Changed paths | Worker output | Classification |
|---|---|---|---:|---|---|---:|---|
| `N93` | `X1 / gpt-5.5` | `.scratch/v2-cohort-runs/2026-04-29_13-48-35-X1-wave72-n93-protocol-sdk-2026-04-29/N93/run` | `1` | `FAIL`; starter verifier failures after no edits | none | `161555` | scoreable `FAIL`; no-op, not quota/timeout |
| `N93` | `X3 / opus 4.7max` | `.scratch/v2-cohort-runs/2026-04-29_13-48-35-X3-wave72-n93-protocol-sdk-2026-04-29/N93/run` | `0` | `PASS`; `100 / 100` | exact 19 benchmark artifacts; pycache auxiliary only | `4251` | `PASS` |
| `N93` | `X2 / gpt-5.3-codex-spark` | `.scratch/v2-cohort-runs/2026-04-29_14-01-51-X2-wave72-n93-protocol-sdk-calibration-2026-04-29/N93/run` | `0` | `FAIL`; starter verifier failures after no edits | none | `45077` | scoreable `FAIL`; no-op |
| `N93` | `X6 / gemini3.1flash-lite-preview` | `.scratch/v2-cohort-runs/2026-04-29_14-01-51-X6-wave72-n93-protocol-sdk-calibration-2026-04-29/N93/run` | `0` | `FAIL`; scope/runtime/ledger failures | 18 benchmark artifacts; missing `registry.py`; cache auxiliary | `20276` | scoreable `FAIL`; Gemini `AttachConsole` post-run noise is not the failure reason |

### Verdict

`X3 PASS over X1 scoreable FAIL` on N93. X1 did not hit quota or timeout; it produced no candidate
changes and failed against the starter contract. X3 passed the exact multipackage migration contract
compactly. X2 failed as a no-op and X6 failed semantic/scope gates with wrapper exit `0`. N93 remains
diagnostic-only and must not change the canonical `full-v2-hard /40` surface unless a named
slot-replacement decision is admitted later.

## 2026-04-29 Follow-Up: W73 Staged Multipackage Protocol Reentry Prep

`N94-staged-multipackage-protocol-reentry` is prepared as the paired hardening task for N93. It keeps
the same ProtocolMesh core/SDK/plugin/CLI migration surface, v2 wire dataclasses, legacy-envelope
migration, plugin delivery, structured CLI return, clean-room public imports, and exact nineteen-path
scope. The added separator axis is staged accountability: phaseBindings, exact phaseOrder,
compatibility-case ownership, final fresh-session replay, review visible-return cues, and closeout
readiness are now first-class JSON verifier inputs.

### Preparation validation

| Check | Result |
|---|---|
| `N94` oracle JSON parse | `PASS` |
| `N94` bundle-shape verifier | `PASS` |
| `N94` starter verifier | expected `FAIL`; starter exposes legacy APIs, incomplete public exports, weak runtime contracts, and empty staged ledgers |
| synthesized valid probe in `.scratch/verifier-probes/2026-04-29-n94-staged-valid/N94` | verifier `PASS`; `100.0 / 100` |

### Runs

| Scenario | Row / model | Classification |
|---|---|---|
| `N94` | `X1 / gpt-5.5` | `NOT-RUN`; prep-only, no launch |
| `N94` | `X3 / opus 4.7max` | `NOT-RUN`; prep-only, no launch |
| `N94` | `X2 / gpt-5.3-codex-spark` | `NOT-RUN` |
| `N94` | `X4 / Claude China` | `NOT-RUN` |
| `N94` | `X5 / gemini3.1pro` | `NOT-RUN` |
| `N94` | `X6 / gemini3.1flash-lite-preview` | `NOT-RUN` |

### Verdict

No model verdict yet. N94 is admission-ready as a diagnostic candidate and does not change the
canonical `full-v2-hard /40` surface. Resume point: launch N94 only after an explicit run decision;
keep `X1` parked until the user authorizes model runs.
