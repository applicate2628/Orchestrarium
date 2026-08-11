# Implementation — separate REVISE cycles from review-loop rounds

Gate: PASS

## Receiving echo

Accepted research, design, and plan define two independent contracts: the shared spine owns generic consecutive same-role/same-artifact correction cycles; `review_loop_state.py` owns autonomous multi-angle rounds. The p95 runner/installer surface is protected and excluded.

## Durable RED

The dedicated contract initially produced exactly three failures and one preservation pass (six subtests): duplicated generic numeric declarations, the unsupported `per stage` scope, and the ambiguous `DEFAULT_CAP` owner. An over-broad first preservation regex was corrected before any production edit because it mistook numbered steps for cap values.

## Implemented current truth

- `shared/AGENTS.shared.md` remains the only numeric owner of the generic Lead correction cap.
- Generic Claude/Codex/shared/reference consumers cite that owner without restating its number.
- `scripts/review_loop_state.py::REVIEW_LOOP_ROUND_CAP` owns the separate review-loop round default; the repository wrapper imports it instead of retyping `3`.
- Self-contained provider review-loop bindings retain `N = 3 rounds`; the dedicated drift guard binds every listed duplicate, including the Claude dispatch advisory, to the runtime value.
- The unsupported `per stage` interpretation and the ambiguous `DEFAULT_CAP` name are absent.
- Explicit `--cap` overrides, V1/V2 schema behavior, ledger transitions, and exit behavior are preserved.

## Verification

- Cap contract: 6 PASS, 6 subtests.
- Cap + review-loop state + dispatch sentinel: 57 PASS, 16 subtests.
- Review-loop validator self-test: PASS across good, redispatch, malformed, null, missing-lane, failure-reconciliation, attempt-ID cases.
- Codex pack: 530/530 PASS.
- Claude pack: 449/449 PASS.
- Shared spine: 111/111 PASS.
- Python compile and `git diff --check`: PASS.
- CodeGraph: fresh, 212 files / 6,725 nodes / 20,071 edges; final current owner/caller query completed.
- Staged audit: only the admitted cap surface is staged; the release-note index contains only the cap bullet, while the parked p95 bullet and its runner/installer/docs/tests remain unstaged.

## Adjacent prerequisite disclosure

The first full owner-suite run exposed a pre-existing stale lifecycle pointer to an already archived fixed observer-gap bug. It was corrected and committed separately as `4a3132b9`; the cap implementation then reran against the green baseline. No cap code was included in that prerequisite commit.

## Stable hashes

- `scripts/review_loop_state.py`: `8e56d0c0ded01e0e08fff5918b9291a97354a52d83a1e358e31f6f4769e2859f`
- `scripts/validate-review-loop-state.py`: `5bd5fcfa649632c7a80f21b23423c07eacacbbadca63149188f3baab01bdf1c7`
- `tests/test_revise_cap_contracts.py`: `053a04d84ecc800d6b788c91427cb9583cfd57bf0260780552a8436f0021c4cc`
- `src.claude/agents/hooks/dispatch_sentinels.py`: `9c96b027a977d51ac6917b67e21f368b933b48a608e7c4683e75854fe1d571e7`
- unchanged generic numeric owner `shared/AGENTS.shared.md`: `304ebf1cddb10ea5bf75d63dc179680f138a1a2a099cc8253f9106fcf90ae0ad`

## Rollback

Before publication, reset the isolated cap commit. This restores the old name/prose together; no migration or persisted-state rollback is required.

## Terms and Abbreviations

- **Cycle:** one completed correction/re-evaluation result for the same role and artifact.
- **Round:** one full autonomous multi-angle review iteration.
- **C1:** single-owner invariant.
- **C6:** superseding changes remove stale live relations.
