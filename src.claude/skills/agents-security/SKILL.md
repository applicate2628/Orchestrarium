---
name: agents-security
description: Run a security-focused review using the `security-sensitive` template roles.
disable-model-invocation: true
---
# Security Review

Run a security-focused review using the `security-sensitive` template roles.

## Steps

1. **Determine scope.** Check `$ARGUMENTS`:
   - If a file, module, or feature is specified, focus on that
   - Otherwise, review recent changes (`git diff`)
   - If no changes found, ask the user what to review

2. **Run the security chain:**
   - **Security engineer** (`subagent_type: security-engineer`): threat model the target — identify trust boundaries, attack surfaces, data flows, and required security controls
   - **Security reviewer** (`subagent_type: security-reviewer`): review the code against the threat model — check auth/authz, secret handling, input validation, dependency risk, data exposure

3. **Handle reviewer verdict:**
   - If security reviewer returns `PASS` → proceed to report
   - If security reviewer returns `REVISE` → route findings back to security engineer for updated threat model or constraints → re-run security reviewer. Max 3 iterations (see REVISE iteration cap in `operating-model.md`), then escalate to user.
   - If security reviewer returns `BLOCKED` → present to user with classification

4. **Save.** Persist per artifact persistence protocol (`operating-model.md`):
   - If part of an active work-item → `work-items/active/<slug>/security-review.md`
   - Log to `.reports/YYYY-MM/report(<role>)-YYYY-MM-DD_HH-MM_topic.md`

5. **Report.** Present:
   - Threat model summary (trust boundaries, attack surfaces)
   - Findings (CRITICAL / HIGH / MEDIUM / LOW)
   - Required fixes before merge
   - Verdict: PASS / REVISE / BLOCKED

## Rules

- **Every stage MUST be invoked via the Agent tool** with the specified `subagent_type`. Do not role-play specialists inline.
- Pass the security engineer's threat model to the security reviewer.
- CRITICAL findings = BLOCKED. No exceptions.
- This is read-only — do not modify any files.
