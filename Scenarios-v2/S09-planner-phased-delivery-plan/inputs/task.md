Role: `$planner`
Goal: Produce one phased delivery plan for adding machine-readable JSON output and a `--dry-run`
preview mode to the bundle-local status snapshot tool.

Approved inputs:
- `inputs/accepted-brief.md`
- `inputs/accepted-design-package.md`
- `inputs/accepted-constraints.md`

Allowed tools:
- read the approved inputs
- edit only `candidate/phase-plan.md`

Scope:
- convert the accepted brief, design, and constraints into ordered delivery phases
- assign explicit file scope for each phase
- record dependencies, tests and checks, rollback notes, and downstream gates
- keep deferred work visible without widening the admitted change

Out of scope:
- new repository research or source-code investigation
- redesigning the implementation seam or choosing a new architecture
- writing implementation code, diffs, or command transcripts
- editing `inputs/`, `oracle/`, or `verifiers/`

Must-not-break surfaces:
- the owner seam in `tools/status_snapshot.py`
- the direct verification seam in `tests/test_status_snapshot.py`
- the output filename contract `status.snapshot.json`
- the existing `--text-summary` behavior
- the no-write guarantee for `--dry-run`

Expected artifact:
- one phase plan in `candidate/phase-plan.md`

Acceptance criteria:
- the artifact is role-correct for `$planner`
- phases are ordered and implementation-ready without containing implementation code
- each phase names file scope, dependencies, tests and checks, and rollback notes
- the plan stays inside the accepted delivery boundary and does not reopen research or design

Gate to next stage:
- an implementer can start `Phase 1` without reinterpreting the brief or design package
