# Implement

Execute an approved plan from `work-items/active/` phase by phase.

## When to auto-invoke

Apply this command's flow automatically when:

- an accepted plan exists in `work-items/active/<slug>/plan.md` and the user asks to proceed, continue, or execute
- user explicitly says "implement plan X", "execute the plan for Y", "run phase N"
- user says "continue", "next phase", "go ahead" while a work-item is mid-implementation — if the session is FRESH (no in-context chain state), first apply `/agents-resume`'s load-and-validate steps (git-divergence + `Depends-on` checks), then continue
- user references a specific phase by slug or number

The user does not need to type `/agents-implement` for this flow to fire. Apply it transparently and announce the routing decision in your first response.

This command executes an approved plan. If its admitted route requires a plan and that input is missing, retain the exact missing input and return to its owner. A new feature without a plan does not automatically commission research/design/Plan. Select the existing route from actual admission; an authorized no-Plan route uses its own implementation entrypoint, not a fabricated plan or silent widening of this executor.

## Steps

1. **Find the plan.** Check `$ARGUMENTS`:
   - If a slug or path is given, load that work-item
   - If empty, check `work-items/active/` for items with a plan artifact. List them and ask the user to pick one.
   - If the accepted plan required by this command is unavailable, report that exact input, owner and resume condition; route only the actual missing decision, not a universal design/Plan stage.

2. **Read the plan.** Load the plan artifact (e.g., `plan.md`) and `status.md`. Identify:
   - Total phases and their order
   - Current phase (from status.md, or phase 1 if fresh)
   - Dependencies between phases
   - Acceptance criteria per phase

3. **Execute phase by phase.** For each phase:
   - **Implementer** (Agent tool, appropriate engineer `subagent_type`, or `external-worker` when external dispatch is preferred): implement the phase within the allowed change surface. Pass the phase spec, acceptance criteria, and any constraints from the plan.
   - **QA** (Agent tool, `subagent_type: qa-engineer`, or `external-reviewer` when external dispatch is preferred): verify the phase — run tests, check acceptance criteria, write bug files if defects found.
   - If QA returns `PASS`, Root receives the actual verdict for the current phase and source/configuration scope, settles the phase through its existing recovery owner, and applies the Between phases rule. PASS covers only its evidenced checks; it grants no next-phase authority or bypass of another required gate.
   - If QA returns `REVISE` — check the classification:
     - **regression**: loop back to implementer to fix code, then re-run QA
     - **contract-change**: loop back to the **same implementer** to update tests under the new contract (the implementer who changed the behavior owns the test adaptation), then re-run QA
     - **test-rot**: file low-severity bug, apply the Between phases rule
     - Present findings to user — user may override: fix now or defer to registry.
   - If QA returns `BLOCKED` — stop and present the blocker to the user.

4. **Between phases.** Root records the settled phase, evidence and next action in the existing status/handoff. Determine the next action's authority from the genuine user request and accepted scope, including amendments, explicit approval checkpoints and stop/pause restrictions. Whole-plan execution authority covers its admitted phases subject to required gates; a selected-phase request covers only selected work. Plan presence, phase number, PASS or review convergence grants no additional authority. Preserve the required plan, order, dependencies and phase criteria. Continue an already-authorized ready next phase without confirmation solely because a phase ended or review converged, only after Root receives current required QA/review evidence and verifies inputs, dependencies, integration and triggered-risk gates. The parallel semantic-conflict/interaction check below remains mandatory before dependent advance. Explicit user approval checkpoints, genuine missing authority/scope/input, unresolved mandatory checks, stop/pause and publication consent requirements hold their dependent action; record the missing condition, owner and resume condition. Resolve actual authority ambiguity with the user rather than infer whole-plan consent; no timeout, acknowledgement, plan or successful check counts as consent. Independent authorized ready work follows its own gates and the actual scope of the user's hold. When no authorized phase remains, report the bounded completed scope and required remainder, settle only already-authorized remaining work, and request precise genuinely missing authority for further execution. Never broaden a selected phase into whole-plan execution or declare a whole item complete from a slice. Human publication review, consent and leak gates remain mandatory; this rule grants no commit or publication authority.
   - **After parallel phases**: check for semantic conflicts and unintended interactions between the parallel agents' outputs (see parallel execution protocol in `operating-model.md`). Resolve conflicts before advancing.

5. **Completion.** Save the final implementation report only to `work-items/active/<slug>/implementation-report.md`; the root records the concise lane result/provenance in `agent-runs.jsonl`. Do not duplicate either in `.reports/` or `.plans/`. When all phases are done:
   - Run architecture reviewer (Agent tool, `subagent_type: architecture-reviewer`) on the full changeset
   - Present summary: phases completed, tests passed, open bugs, residual risk
   - Suggest `/agents-review` for final review before commit
   - **Close the work-item once it is delivered (the user commits/pushes) or parked.** Do not leave a delivered item in `work-items/active/` — apply the Recovery rule's close step through the installed lifecycle owner (write the required closure evidence, move the folder to `work-items/archive/<YYYY-MM>/<slug>/`, and regenerate the derived `work-items/README.md` read-model). Physical archive placement, not status or closure prose, makes the item terminal; `work-items/index.md` is compatibility-only. If the work-item declares an `Epic:`, refresh the parent epic's roll-up from physical child locations and archive the epic through the same lifecycle owner when this was its last open child and the epic goal is met (see the lead skill `## Epics`).

## Rules

- **Every stage MUST be invoked via the Agent tool** with the specified `subagent_type`. Do not role-play specialists inline.
- Choose the implementer subagent_type based on the phase domain (backend-engineer, frontend-engineer, etc.).
- Follow evidence-based completion: show fresh execution evidence per phase.
- Independent phases (no shared change surface) may be implemented in parallel.
- Never skip QA for any phase.
- **Do NOT commit automatically.** After all phases complete and the final review passes, present the full changeset to the user. The user decides when to commit.
