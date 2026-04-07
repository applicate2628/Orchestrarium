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

3. **Report.** Present:
   - Threat model summary (trust boundaries, attack surfaces)
   - Findings (CRITICAL / HIGH / MEDIUM / LOW)
   - Required fixes before merge
   - Verdict: PASS / REVISE / BLOCKED

## Rules

- Pass the security engineer's threat model to the security reviewer.
- CRITICAL findings = BLOCKED. No exceptions.
- This is read-only — do not modify any files.
