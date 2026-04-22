Date: 2026-04-21
Owner: `$lead`
Status: `DRAFT`

# N06 Authz Trust-Boundary — Tuple-Exact Hardening (Pilot)

## Scope

Harden `Scenarios-v2/N06-authz-trust-boundary-review/` in place as the pilot cell for tuple-exact
finding verification, with the goal of breaking the current `X1`/`X3` near-ceiling tie on the core
`12+1` baseline. No new scenario IDs are introduced. `N03`, `N11..N13`, `S30`, `N02`, and `S29` from
prior hardening waves are left untouched.

Out of scope: `S27`, `S28`, `S29`, `N05`, `N07` — these share the same answer-leak pattern
(`inputs/review-observations.md` enumerating findings) and will reuse the `N06` template in a second
wave if the pilot confirms the pattern works. They are not part of this change.

## Why N06

Evidence from the separator audit `Evidence/separator-audit-2026-04-21.md` (row N06, line 53):

- `inputs/review-observations.md:1-6` directly enumerates all three oracle findings.
- current verifier is `mixed` (substring plus structural sectioning) but still falls through
  to keyword-substring term matching at the finding level.
- a near-ceiling model passes by paraphrasing the three observation bullets, naming the four
  required terms per finding, adding the two required false-positive tokens, and ending with
  `REVISE`.
- the underlying code `candidate/review-target/access-surface/grant_console.js` genuinely
  contains three authz/trust-boundary defects whose specific `(file, line, category, severity)`
  tuples cannot be reconstructed from `task.md` alone — only from reading the code.

Removing the leak and tightening the verifier to tuple-exact matching preserves the scenario's
canonical slot in `N01..N07` (core routing lanes), keeps the `12+1` shape stable, and reuses an
existing multi-file code target.

## Hardening Delta

### Files to delete

| Path | Reason |
|---|---|
| `Scenarios-v2/N06-authz-trust-boundary-review/inputs/review-observations.md` | enumerates the three expected findings verbatim; retained `inputs/trust-boundary-notes.md` and `inputs/accepted-security-claims.md` keep the abstract framing rules visible to the reviewer |

### Files to modify

| Path | Change |
|---|---|
| `inputs/task.md` | rewrite from 3-line abstract framing to structured-table requirement (see Task Contract below). No answer enumeration. |
| `oracle/authz-trust-review-contract.json` | remove `inputs/review-observations.md` from `required_bundle_paths`; replace `required_findings` keyword-only shape with tuple shape `{id, title_keywords, file, acceptable_lines, category_terms, severity, required_evidence_terms}`; add `forbidden_findings[]` with `title_keywords + reason`; add `max_finding_count`; keep `required_false_positive_terms`, `prohibited_report_snippets`, `expected_gate_decision`; update `required_report_sections` to include `## Findings` as a table. |
| `oracle/expected-findings.md` | rewrite to the ground-truth tuple table mirroring the new contract shape. Retained as a human-readable oracle doc; not shown to the candidate. |
| `verifiers/check_authz_trust_review.py` | rewrite the finding-check routine: parse the `## Findings` markdown table in `candidate/review-report.md`; for each oracle tuple require at least one candidate row where `file` matches exactly, `line` is in `acceptable_lines`, `severity` matches, at least one `category_term` substring present in the `Category` cell, at least one `title_keyword` substring present in the `Title` cell, and every `required_evidence_terms` present in the `Evidence` cell; reject any candidate row whose `Title` matches any `forbidden_findings[*].title_keywords`; enforce `<= max_finding_count` total rows; preserve `--bundle-shape-only` fast path. |
| `candidate/review-report.md` | rewrite the placeholder template to match the new structured `## Findings` table layout; still marked `[fill in after run]`. |

### Files unchanged

| Path | Reason |
|---|---|
| `candidate/review-target/access-surface/grant_console.js` | the real code under review — preserving the defect positions keeps oracle lines stable |
| `candidate/review-target/access-surface/grant_console.html` | unchanged review target |
| `candidate/review-target/access-surface/policy.css` | unchanged; its cosmetic role is a false-positive trap |
| `inputs/trust-boundary-notes.md` | abstract trust-boundary rules — valid framing, not an answer |
| `inputs/accepted-security-claims.md` | abstract security invariants — valid framing, not an answer |
| `inputs/review-boundary.md` | scope rules — valid framing |
| `oracle/false-positive-traps.md` | documents trap intent; kept for human readability |
| `oracle/scoring-anchors.md` | qualitative anchors — unchanged |
| `oracle/severity-anchors.md` | calibration for candidate use — unchanged |
| `scenario.yaml` | metadata stable; `must_not_touch` + `allowed_change_surface` unchanged |

## Task Contract (new `inputs/task.md`)

Required output section structure in `candidate/review-report.md`:

```
## Findings

| # | File | Line | Category | Severity | Title | Evidence |
|---|---|---|---|---|---|---|
| 1 | ... | ... | ... | ... | ... | ... |
...

## False Positives Avoided

- <one bullet per candidate false-positive trap, explaining why it is not a finding>

## Gate Decision

REVISE
```

Candidate-visible rules in `task.md`:

- File path must be bundle-relative and must exist under `candidate/review-target/`.
- Line must be the primary line where the defect is visible in the code.
- Category must be one of: `authz`, `trust-boundary`, `replay`, `session`.
- Severity must be one of: `high`, `medium`, `low`; use `oracle/severity-anchors.md` to calibrate.
- Title must name the defect class (not restate the code).
- Evidence must cite the specific variable, function, or header involved and explain the attack
  vector; bare line quotes are not evidence.
- Scope rules from `review-boundary.md` apply; do not invent issues, do not report cosmetic or
  stylistic problems, do not mix performance or accessibility commentary.
- End with one `## Gate Decision` line containing `PASS`, `REVISE`, or `BLOCK`.

## Oracle Tuple Shape

Expected `required_findings` in the hardened contract (target values):

| id | file | acceptable_lines | category_terms | severity | title_keywords | required_evidence_terms |
|---|---|---|---|---|---|---|
| F1 | `candidate/review-target/access-surface/grant_console.js` | `[2, 7, 8, 15, 19]` | `[authz, privilege, role]` | `high` | `[query, role, escalation, client, reviewerrole]` | `[reviewerRole, params, URLSearchParams]` |
| F2 | `candidate/review-target/access-surface/grant_console.js` | `[27, 28, 29, 30]` | `[trust, boundary, origin]` | `high` | `[parent, tenant, trust, boundary, message, postmessage]` | `[payload.trusted, effectiveTenant, origin]` |
| F3 | `candidate/review-target/access-surface/grant_console.js` | `[15, 18, 19]` | `[authz, replay, forward]` | `medium` | `[replay, authority, forwarded, client]` | `[X-Reviewer-Role, tenantId, server]` |

`forbidden_findings`:

| title_keywords | reason |
|---|---|
| `[policy.css, opacity, cosmetic]` | CSS cosmetic rule; no security impact |
| `[disabled button, approve-grant disabled]` | Client-side UI hint; not an authz boundary by itself |

`max_finding_count`: `5` (allows small over-report margin before failing).

`required_false_positive_terms`: `[disabled button, policy.css]` (unchanged; still require the
report to state the two traps are intentionally excluded).

`expected_gate_decision`: `REVISE` (unchanged).

## Why Compliance-Retelling Fails

1. The `review-observations.md` leak is gone; `task.md` only specifies the output schema, not the
   answers.
2. Required `(file, line)` tuples cannot be derived from `task.md` or from the abstract framing in
   `trust-boundary-notes.md` / `accepted-security-claims.md`. The model must read
   `grant_console.js` and locate the defect lines.
3. The verifier checks line membership in `acceptable_lines`; paraphrasing without reading code
   yields wrong lines or omitted line numbers.
4. `forbidden_findings` catches models that over-report (e.g. listing `policy.css` opacity as a
   security finding because it "looks suspicious").
5. `required_evidence_terms` in the `Evidence` cell require naming the specific variable or
   header involved — not just paraphrasing the finding title.

## Validation Plan (Pre-Run)

In order:

1. `python -c "import json; json.loads(open('Scenarios-v2/N06-authz-trust-boundary-review/oracle/authz-trust-review-contract.json').read())"` — JSON parse.
2. `python Scenarios-v2/N06-authz-trust-boundary-review/verifiers/check_authz_trust_review.py --bundle-shape-only` — bundle shape after `review-observations.md` removed.
3. `git diff --check` — whitespace/merge-marker sanity on staged changes.
4. Dry-run the new verifier against the current ground-truth table in `oracle/expected-findings.md`
   (synthesize a valid `candidate/review-report.md` matching the new schema) — confirm `PASS`.
5. Dry-run the new verifier against a deliberately wrong table (bad line, wrong category, missing
   finding, extra false-positive trap) — confirm each expected `FAIL` message surfaces.

## Execution Plan (X1 / X3 Runs)

- Launch `X1 / gpt-5.4` on hardened `N06`, writing to `.scratch/v2-cohort-runs/2026-04-21_<HH-MM-SS>-X1-x1-n06-authz-tuple-hardening-2026-04-21/`.
- Launch `X3 / opus 4.7max` on hardened `N06`, writing to `.scratch/v2-cohort-runs/2026-04-21_<HH-MM-SS>-X3-x3-n06-authz-tuple-hardening-2026-04-21/`.
- Do not launch X2/X5/X6 in this wave; hardening goal is top-pair separation, not calibration.
- Do not rerun X4; secret-backed Claude route still returns `502 unknown provider` as of latest
  checkpoint.

## Evidence and Surface Updates (In Place)

After both runs complete:

| Surface | Update |
|---|---|
| `Evidence/x1-mainline-hardening-no-new-failures-2026-04-21.md` | append a section documenting the N06 tuple-exact hardening + the X1/X3 binary result. Do not create a new dated evidence file. |
| `Results-drafts/short-results-current-2026-04-18.md` | insert a new compact note row describing the N06 hardened result; mark pre-hardening N06 as ceiling artefact for this cell only. |
| `Checkpoints/status-2026-04-16.md` | update `## Current state` row "next concrete action" and "current caveat" to reflect the N06 hardening result; update "latest v2 execution evidence" list if a new evidence subsection was added. |
| `Work/next-upgraded-pack/Evidence/separator-audit-2026-04-21.md` | leave the row read unchanged; it remains the pre-hardening audit snapshot. Do not rewrite. |

If `X1` and `X3` both pass: record `binary tie remains on N06 tuple-exact hardening` verbatim.

If `X1` and `X3` diverge: record the specific cell, tuple mismatch, and which tuple was missed.

## Risk and Rollback

| Risk | Mitigation |
|---|---|
| new verifier has a parsing bug and fails both X1/X3 on a syntactic nit | step 4 (dry-run against synthesized valid candidate) catches this before the X-runs |
| oracle tuple line numbers are too strict and a valid finding at a different line gets rejected | `acceptable_lines` is a set of 3-5 lines per finding; covers primary and adjacent defect locations; step 4 calibrates |
| `max_finding_count` too low and valid extra findings fail | initial cap `5` leaves room for one or two legitimate add-ons over the 3 required findings |
| prior X1/X3 N06 results become non-comparable | acknowledged; pre-v3 N06 cell is marked as ceiling artefact in the short-results note row; the full-v2 baseline is already labeled pre-v3 ceiling-effect in `short-results-current-2026-04-18.md` |
| if both X1 and X3 still tie | that is a valid experimental outcome; record `binary tie remains` and open wave 2 (S27 / N05 with same template) |

Rollback: if the hardening destabilizes the bundle beyond repair, `git checkout -- Scenarios-v2/N06-authz-trust-boundary-review/` restores pre-hardening state. Scratch runs are disposable.

## Acceptance Criteria

The pilot is complete when all of:

1. `--bundle-shape-only` passes on the hardened bundle.
2. Dry-run of the new verifier against a synthesized valid candidate yields `PASS` and against
   synthesized invalid candidates yields `FAIL` for each failure class above.
3. Both X1 and X3 runs complete without wrapper-level timeout.
4. Binary verifier result is recorded for each model (`PASS` or `FAIL` with tuple mismatch listed).
5. Live surfaces (`short-results-current-2026-04-18.md`, `x1-mainline-hardening-no-new-failures-2026-04-21.md`, `status-2026-04-16.md`) are updated in place with the new N06 read.
6. If the result is still a tie, the phrase `binary tie remains` appears verbatim in the evidence
   update section.

## Post-Pilot Decision (Not Part of This Change)

If N06 produces a clean X1/X3 separator:
- Wave 2 reuses the template on `S27`, `N05`, and optionally `N07` / `S28` / `S29`.

If N06 still ties after tuple-exact hardening:
- The pilot was structurally sound but insufficient; next wave introduces trap code inside
  `grant_console.js` itself (plausible-looking patterns that are not actually defects).
- Alternatively, the authz task class is too compliance-friendly and the wave-2 target shifts to
  `S06` analyst-repository-fact-memo (audit row: high leak, high separation potential, different
  reasoning surface).
