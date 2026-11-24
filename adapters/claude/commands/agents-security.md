# Security Review

Run a security-focused review using the `security-sensitive` template roles.

## When to auto-invoke

Apply this command's flow automatically when the user's request matches any of:

- security or vulnerability concern raised: "is this secure?", "review X for vulnerabilities", "could this be exploited?"
- auth, authz, or credential surface touched: "review the login flow", "check how we handle tokens/secrets", "audit the permission checks"
- trust boundary or data-exposure question: "is this input validated?", "are we leaking data here?", "what's the attack surface of Y?"
- dependency or supply-chain risk: "is this library safe to add?", "check the new dependency for known CVEs"

The user does not need to type `/agents-security` for this flow to fire. Apply it transparently, announce the routing decision in your first response ("I'm routing this through the security flow because the request touches a trust boundary / credential surface"), and let the user redirect if the auto-routing was wrong.

**Do NOT auto-invoke** for a general code-quality or architecture review with no trust-boundary, auth, credential, or data-exposure dimension — that is `/agents-review` territory. When a bug or change involves auth, credentials, or a trust boundary, this security flow takes precedence over `/agents-bugfix` and `/agents-review` per the "pick the most specialized one" resolution rule in CLAUDE.md. This flow is read-only — it produces a threat model and findings, not fixes.

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
   - If security reviewer returns `REVISE` → route findings back to security engineer for updated threat model or constraints → re-run security reviewer under the shared spine's consecutive same-role/same-artifact `REVISE`-cycle cap, then escalate to the user when exhausted.
   - If security reviewer returns `BLOCKED` → present to user with classification

4. **Save.** Persist per artifact persistence protocol (`operating-model.md`):
   - If part of an active work-item → `work-items/active/<slug>/security-review.md`
   - With an active item, return concise result/provenance for the root ledger and do not create a `.reports/` duplicate. With no active item, a meaningful standalone review MAY use one `.reports/` summary.

5. **Report.** Present:
   - Threat model summary (trust boundaries, attack surfaces)
   - Findings (CRITICAL / HIGH / MEDIUM / LOW)
   - Required fixes before merge
   - Verdict: PASS / REVISE / BLOCKED

## Rules

- **Every stage MUST be invoked via the Agent tool** with the specified `subagent_type`. Do not role-play specialists inline.
- Pass the security engineer's threat model to the security reviewer.
- A CRITICAL finding always fails the gate: return `REVISE` with the finding marked must-fix-before-merge (`BLOCKED` only when a real external blocker prevents remediation). No exceptions to failing the gate.
- This is read-only — do not modify any files.
