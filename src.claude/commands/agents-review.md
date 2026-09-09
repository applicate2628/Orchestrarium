# Code Review

Run a full read-only repository impact review starting from current changes or a specified review target. Changed files are only the entry point; the review must cover the wider affected surface, including unchanged dependents, contracts, tests, config, and nearby logic.

## When to auto-invoke

Apply this command's flow automatically when:

- user asks for review of completed work: "review what I built", "audit module X", "check the diff"
- user wants pre-merge gate: "is this ready to commit?", "can I push?"
- user asks for post-implementation validation: "verify the X feature works correctly"
- user requests architecture audit: "review the architecture of Y"

The user does not need to type `/agents-review` for this flow to fire. Apply it transparently and announce the routing decision.

This is read-only review — do not re-implement. If review uncovers required changes, surface them and let the user decide whether to route to `/agents-bugfix` or `/agents-refactor`.

## Steps

1. **Determine scope.** Check `$ARGUMENTS`:
   - If a PR number, branch, commit range, or other review target is given, use that
   - Otherwise, review unstaged/staged changes (`git diff` + `git diff --cached`)
   - If no changes found, tell the user and stop
   - If the user mentions a bug, review thread, accepted plan, or expected fix list, use that as the completion baseline

2. **Select the review route.** Follow the `review` template from CLAUDE.md:
   - First identify the reviewer required by the review objective; this selection is the route's anchor, not the last stage of a fixed Analyst/QA/Architecture chain
   - A test, regression, or fix-completeness objective normally selects Quality Assurance (`subagent_type: qa-engineer`); an architecture or maintainability objective selects Architecture Reviewer (`subagent_type: architecture-reviewer`); other objective-named specialist reviews select their matching reviewer
   - Add a factual or research helper only when required evidence is missing; use Analyst (`subagent_type: analyst`) to inspect changed code plus callers, dependents, tests, configuration, schemas, and adjacent modules when that factual inventory is needed
   - Add a Quality Assurance (QA) helper only when the objective needs test, regression, or fix-completeness evidence that is not already the objective reviewer's lane
   - Add an Architecture Reviewer only when the objective is architectural or verified architecture or maintainability risk requires that gate
   - Add **Security reviewer** (`subagent_type: security-reviewer`) if the change touches auth, trust boundaries, secrets, dangerous config, input validation, or vulnerability surfaces
   - Add **Performance reviewer** (`subagent_type: performance-reviewer`) if the change touches hot paths, query plans, rendering loops, budgets, throughput, or latency-sensitive behavior
   - Add **UX / accessibility / UI test reviewers** (`subagent_type: ux-reviewer`, `accessibility-reviewer`, or `ui-test-engineer`) when the affected surface is user-facing and the risk is interaction quality rather than pure logic
   - An eligible QA or review-side slot may use `external-reviewer` when external dispatch is preferred and policy allows it
   - Execute every admitted lane in research -> QA -> review order and omit every lane without an evidence trigger
   - **Narrow QA-only objective:** select `qa-engineer`; do not add Analyst or Architecture review without a separate evidence trigger
   - **Architecture objective:** the Architecture Reviewer is the objective reviewer; do not add Analyst or QA unless required evidence is missing
   - **Research needed:** when the selected reviewer cannot decide without a caller, dependency, or contract inventory, admit an Analyst to collect those facts before the downstream QA or review verdict
   - When the existing multi-fix anti-layering trigger applies, its Architecture Reviewer lane and distinct-engine audit remain mandatory; a `PILED` verdict maps to `REVISE` and blocks push. Workflow economy does not waive this trigger

3. **Save.** Persist per artifact persistence protocol (`operating-model.md`):
   - If part of an active work-item → `work-items/active/<slug>/review.md`
   - With an active item, return concise result/provenance for the root ledger and do not create a `.reports/` duplicate. With no active item, a meaningful standalone review MAY use one `.reports/` summary.

4. **Compile results.** Present a unified review with:
   - Scope reviewed
   - Issues found (CRITICAL / HIGH / MEDIUM / LOW)
   - Impacted unchanged surfaces that were checked
   - What could not be verified
   - Recommendations
   - Verdict: PASS / REVISE / BLOCKED

If the user asked "did we fix everything?", answer that directly before the detailed findings.

## Rules

- **Every admitted stage MUST be invoked via the Agent tool** with its selected `subagent_type`. Do not role-play specialists inline.
- Independent admitted stages may be launched in parallel. Sequential admitted stages must wait for the previous agent's artifact.
- Pass accepted artifacts between admitted stages in research -> QA -> review order.
- If any stage finds a CRITICAL issue, flag it immediately without waiting for later stages.
- Treat changed files as entry points, not the review boundary.
- Delegate authorized GitHub review-thread resolution to `$github-pr-review-bot`; this observational review command does not resolve threads itself.
- The review entry point remains read-only; the delegated GitHub action is allowed only with explicit user authorization or existing standing authorization for that pull request.
- The bot owner must refresh the pull request's hosted `headRefOid`, verify the fix on that hosted head, re-read the exact thread, and resolve only that exact authorized thread. Local ancestry, a local diff, a user-interface badge, a notification, or stale prior bot evidence is insufficient.
- Thread resolution does not establish a clean bot result or `PASS`; it does not trigger a new review, start Continuous Integration (CI), or grant merge or publication authority. Those remain separate bot-state and human gates.
- Do not modify any files — this is read-only.
