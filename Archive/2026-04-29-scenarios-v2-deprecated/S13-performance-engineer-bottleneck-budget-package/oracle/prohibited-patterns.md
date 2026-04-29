# Prohibited Patterns

The following failures should score poorly for `S13`.

- generic advice such as "parallelize it" or "cache more" without quantitative budgets
- bottleneck claims that are not tied to `E2` or `E3`
- reviewer-style findings severities, blame assignment, or regression triage
- implementation patch instructions or pseudocode as the main artifact
- rollout, rollback, incident response, or SLO policy writing
- proposals that win time by dropping redaction, hash-manifest coverage, or admitted cohort size
- web or browser assumptions in a pack that is explicitly non-web
