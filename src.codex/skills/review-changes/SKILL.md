---
name: review-changes
description: "Diff/PR/commit-range impact review beyond changed lines."
---

# Review Changes

Run a repository-wide impact review triggered by recent changes. The changed files are only the starting point; the review target is the full affected behavior surface, including unchanged dependents, nearby contracts, tests, and likely regression paths.

## Core stance

- Stay read-only.
- Use the `review` template semantics from the installed `AGENTS.md` (Template routing section): select the objective-named reviewer and admit only evidence-triggered helpers.
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

1. First identify the reviewer required by the review objective; this selection is the route's anchor, not the last stage of a fixed Analyst/QA/Architecture chain.
- A test, regression, or fix-completeness objective normally selects `$qa-engineer`.
- An architecture or maintainability objective selects `$architecture-reviewer`.
- A security, performance, user-experience, accessibility, or user-interface test objective selects the matching specialist reviewer.
2. Admit helpers only for evidence the selected reviewer actually needs.
- Add a factual or research helper only when required evidence is missing; use `$analyst` to inspect changed code plus callers, dependents, tests, configuration, schemas, and adjacent modules when that factual inventory is needed.
- Add a Quality Assurance (QA) helper only when the objective needs test, regression, or fix-completeness evidence that is not already the objective reviewer's lane.
- Add an Architecture Reviewer only when the objective is architectural or verified architecture or maintainability risk requires that gate.
- Add `$security-reviewer` if the change touches auth, trust boundaries, secrets, dangerous configuration, input validation, or vulnerability surfaces.
- Add `$performance-reviewer` if the change touches hot paths, query plans, rendering loops, budgets, throughput, or latency-sensitive behavior.
- Add `$ux-reviewer`, `$accessibility-reviewer`, or `$ui-test-engineer` when the affected surface is clearly user-facing and the risk is interaction quality rather than pure logic.
- If external review is preferred for an eligible QA or review-side slot, `$external-reviewer` may stand in for the matching role.
3. Execute every admitted lane in research -> QA -> review order and omit every lane without an evidence trigger. Keep the chain sequential in Codex unless the user explicitly approves a delegated team and the scopes are clearly independent.
4. Apply these routing scenarios as pressure tests:
- Narrow QA-only objective: select `$qa-engineer`; do not add Analyst or Architecture review without a separate evidence trigger.
- Architecture objective: the Architecture Reviewer is the objective reviewer; do not add Analyst or QA unless required evidence is missing.
- Research needed: when the selected reviewer cannot decide without a caller, dependency, or contract inventory, admit an Analyst to collect those facts before the downstream QA or review verdict.
5. When the existing multi-fix anti-layering trigger applies, its Architecture Reviewer lane and distinct-engine audit remain mandatory; a `PILED` verdict maps to `REVISE` and blocks push. Workflow economy does not waive this trigger.

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

- If the current task has `work-items/active/<slug>/`, persist only the accepted review artifact there and return its concise result/provenance for the root ledger.
- With no active work-item, a meaningful standalone review MAY use one `.reports/YYYY-MM/` summary using the standard report naming convention.

## Rules

- Do not role-play specialist reviewers inline when delegation is available and permitted.
- Treat changed files as entry points, not as the review boundary.
- If a critical issue appears early, surface it immediately.
- If the impact surface is too large for a trustworthy single pass, say so and recommend splitting the review into smaller scopes.
- Delegate authorized GitHub review-thread resolution to `$github-pr-review-bot`; this observational review skill does not resolve threads itself.
- The review entry point remains read-only; the delegated GitHub action is allowed only with explicit user authorization or existing standing authorization for that pull request.
- The bot owner must refresh the pull request's hosted `headRefOid`, verify the fix on that hosted head, re-read the exact thread, and resolve only that exact authorized thread. Local ancestry, a local diff, a user-interface badge, a notification, or stale prior bot evidence is insufficient.
- Thread resolution does not establish a clean bot result or `PASS`; it does not trigger a new review, start Continuous Integration (CI), or grant merge or publication authority. Those remain separate bot-state and human gates.
