# Phase Plan

Status note:
- Keep publication-safe summaries only.
- Do not include raw logs, transcripts, or machine-specific paths.

Selected direction:
- Create a canonical periodic-control-matrix reference in `references/`.
- Distinguish periodic controls from existing stage-gated checks explicitly.
- Wire the new reference into repo-level docs so it is discoverable.
- Keep the solution minimal: no automation, CI jobs, or role redesign.

Checklist:
- [x] Inspect the current repository governance and identify the periodic-control gap.
  Acceptance criteria: the gap between stage gates and periodic controls is explicit and documented in the work-item brief.
- [x] Select the direction via Claude deep review and human approval.
  Acceptance criteria: a layered cadence matrix is the confirmed approach; the decision is recorded in the status log.
- [x] Draft the canonical periodic-control-matrix reference.
  Acceptance criteria: `references/periodic-control-matrix.md` exists with controls, owners, cadence, evidence, and fail actions; periodic controls are clearly distinguished from stage-gated checks.
- [x] Wire the reference into repo-level docs.
  Acceptance criteria: at least the main repo docs and the operating-model references link to the new matrix; the matrix is reachable within two clicks from the repo root.
- [x] Validate coherence and publication safety.
  Acceptance criteria: no secrets, machine-specific paths, or raw transcripts; all repo-relative links resolve; the work-item status is updated to reflect completion.
