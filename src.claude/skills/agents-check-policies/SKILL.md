---
name: agents-check-policies
description: You are auditing the current codebase for compliance with configured project policies.
disable-model-invocation: true
---
# Audit Policy Compliance

You are auditing the current codebase for compliance with configured project policies.

## Steps

1. **Read policies.** Read the `## Project policies` section from `.claude/CLAUDE.md`.
   - If no policies exist, say "No project policies configured. Run `/agents-init-project` first." and stop.

2. **Run checks for each configured policy.** Only check policies that are actually set (skip any marked as "none" or absent).

### Testing methodology
- Look for test files (glob `**/*.test.*`, `**/*.spec.*`, `**/tests/**`, `**/__tests__/**`)
- If `tdd` or `test-after`: flag if no test files exist alongside source files
- Report: test file count, source-to-test ratio

### Coverage target
- Look for coverage configuration (jest.config, .nycrc, vitest.config, pytest.ini, etc.)
- Check if a coverage threshold is configured and matches the policy target
- Report: configured threshold vs policy target

### Commit format
- Run `git log --oneline -20` and check if recent commits match the configured format
- For `conventional`: check for `type(scope):` or `type:` prefix
- Report: compliant vs non-compliant commit count

### File size policy
- If `strict` or `moderate`: find source files exceeding the configured line threshold
- Report: list of files over limit with line counts

### PR review
- If `required`: check for branch protection or CI config that enforces reviews
- Report: whether enforcement mechanism was found

### Documentation
- If `public-api`: check exported functions/classes for doc comments
- Report: sample of undocumented exports (up to 10)

### Dependency policy
- Count total dependencies from package.json, requirements.txt, Cargo.toml, go.mod, etc.
- Report: dependency count and any that look unused or unmaintained

3. **Generate report.** Present results as a table:

| Policy | Status | Details |
| --- | --- | --- |
| Testing | PASS/WARN/FAIL | ... |
| ... | ... | ... |

Use:
- **PASS** — compliant
- **WARN** — partially compliant or unable to fully verify
- **FAIL** — clearly non-compliant

4. **Suggest fixes.** For any WARN or FAIL, provide a specific actionable recommendation.

## Rules

- This is a read-only audit — do not modify any files.
- Be pragmatic: WARN is better than a false FAIL.
- Skip checks that require running a build or test suite (just check configuration).
- If a policy area has no detectable artifacts (e.g., no package.json for deps), report as "N/A — no {artifact} found".
