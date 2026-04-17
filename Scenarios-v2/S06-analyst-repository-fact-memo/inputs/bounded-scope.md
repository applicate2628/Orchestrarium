# Bounded Scope

The repository evidence in this bundle is intentionally incomplete.

## Included

- bundle-local scenario metadata under `candidate/repo-snapshot/benchmarks/Scenarios-v2/`
- scenario collection code
- metadata normalization and score-profile lookup code
- result-row writing code
- a legacy archive index and export helpers
- tests and two internal docs with conflicting age and authority

## Not included

- the outer CLI or scheduler that chooses the requested surface ID before the collector runs
- any production database, SaaS publication target, or external service integration
- full repository history, `git blame`, or runtime logs

If the evidence slice does not prove a claim, mark it as unknown instead of inferring.
