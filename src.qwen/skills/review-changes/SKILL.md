---
name: review-changes
description: Run a full read-only repository impact review starting from recent local changes, a specified diff, branch, commit range, or PR. Use when Qwen Code needs to verify that recent fixes are complete, nothing important was forgotten, unchanged call sites or contracts were not broken, logic still holds across the wider repo, and regressions or missed edge cases are surfaced before commit.
---

# Review Changes

Run a repository-wide impact review triggered by recent changes. The changed files are only the starting point; the review target is the full affected behavior surface, including unchanged dependents, nearby contracts, tests, and likely regression paths.

## Core stance

- Stay read-only.
- Use the `review` template semantics from `src.codex/AGENTS.codex.md`: `$analyst` -> QA lane -> reviewer lane.
- Review the repo in light of the changes, not just the diff lines themselves.
- Findings come first, ordered by severity.
- Do NOT commit or modify files.

## Scope decision

1. Check `$ARGUMENTS`.
- If a PR URL, PR number, branch, commit range, or diff target is given, use that scope.
- Otherwise inspect current unstaged and staged changes with `git diff` and `git diff --cached`.
- If no changes are present, stop and tell the user there is nothing to review.
2. If the user mentions a bug, review thread, accepted plan, or expected fix list, use that as the completion baseline.
3. If no explicit baseline exists, review against the observed change impact and say that fix-completeness against an external checklist could not be verified.

## Review workflow

1. Run `$analyst` first.
- Goal: identify what changed, which contracts or behaviors moved, what unchanged code depends on those changes, and where logic may now be incomplete.
- Require the analyst to inspect callers, dependents, tests, config, schemas, and adjacent modules that may be affected even if they were not edited.
2. Run the QA lane.
- Use `$qa-engineer` by default.
- If external review is preferred for an eligible QA-side slot, `$external-reviewer` may stand in for that lane.
- Goal: verify regression risk, edge cases, test sufficiency, fix completeness, and whether untouched behavior is now inconsistent with the new logic.
3. Run the reviewer lane.
- Always invoke `$architecture-reviewer`.
- Add `$security-reviewer` if the change touches auth, trust boundaries, secrets, dangerous configuration, input validation, or vulnerability surfaces.
- Add `$performance-reviewer` if the change touches hot paths, query plans, rendering loops, budgets, throughput, or latency-sensitive behavior.
- Add `$ux-reviewer`, `$accessibility-reviewer`, or `$ui-test-engineer` when the affected surface is clearly user-facing and the risk is interaction quality rather than pure logic.
- If external review is preferred for an eligible review-side slot, `$external-reviewer` may stand in for the matching reviewer role.
4. Keep the chain sequential in Qwen unless the user explicitly approves a delegated team and the scopes are clearly independent.

## What to verify

- The requested fixes are actually present.
- The apparent root cause is covered, not just one symptom.
- Unchanged callers, consumers, configs, tests, or docs are still compatible with the new behavior.
- Nearby logic still makes sense after the change.
- Hidden regressions, stale assumptions, and missed edge cases are surfaced.
- Validation is strong enough for the touched behavior, or the exact gap is called out.
- The change did not leave partial rewires, stale branches, dead conditions, or forgotten follow-up adjustments in unchanged files.

## Output

Return one unified review with:

- scope reviewed
- findings ordered by severity
- impacted unchanged surfaces that were checked
- what could not be verified
- verdict: `PASS`, `REVISE`, or `BLOCKED`

If the user asked "did we fix everything?", answer that directly before the detailed findings.

## Persistence

- If the repository uses active work-items, persist the accepted review artifact there.
- Otherwise log the review under `.reports/YYYY-MM/` using the standard report naming convention.

## Rules

- Do not role-play specialist reviewers inline when delegation is available and permitted.
- Treat changed files as entry points, not as the review boundary.
- If a critical issue appears early, surface it immediately.
- If the impact surface is too large for a trustworthy single pass, say so and recommend splitting the review into smaller scopes.
