# Inputs

The inputs define the immutable triage packet for `N04`.

## Included files

- `task.md` defines the candidate instructions and report shape
- `accepted-triage-boundary.md` records the admitted behavior and nearby must-not-break surfaces
- `recent-changes.md` summarizes the recent code changes under review
- `executed-checks.md` captures targeted test outcomes
- `smoke-results.md` records manual repro and nearby stable observations
- `operator-signals.md` captures field reports tied to the recent changes
- `stable-signals.md` lists nearby stable surfaces and pre-existing noise
- `review-target/` contains the read-only changed files

The candidate should cite these files directly and keep the result triage-only.
