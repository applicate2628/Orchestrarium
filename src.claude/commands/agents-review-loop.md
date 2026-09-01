# Review Loop

Run the autonomous parallel-review-loop: dispatch three independent scope angles against one written fix-design artifact, converge autonomously under an anti-drift guard, and gate the human only at the converged result. This command is THIN — it reads the installed contract at runtime and executes the loop; it does not restate the methodology.

## When to auto-invoke

Auto-invoke this flow ONLY on the narrow, explicit loop triggers:

- "review loop"
- "проводи review loop"
- "loop review"
- "автономная петля"

Do NOT auto-invoke on `review` / `let's review` (owned by `/agents-review`) or `second opinion` (owned by `/agents-second-opinion`). The loop is a deliberate, heavier surface (three angles, multi-round, autonomous convergence); it is not the default for an ordinary review or a single second opinion.

Do NOT auto-invoke for trivial changes (one-line typo, doc edit, single-file refactor with no behavior change) or when the bug's root is an unmeasured runtime value — capture the runtime root FIRST, then loop on the fix design.

## Steps

1. **Read the installed contract.** Read `.claude/agents/contracts/review-loop.md`. It owns the operative loop rules (the angles, the Claude dispatch mapping, autonomous-to-convergence, anti-drift, the cap, the hardening invariants, the convergence rule, and the `review-loop-state` ledger — its force, schema, and enforcement envelope), including hardening invariants 7-8 (failed-lane-is-unverified, fail-closed aggregation); do not re-derive any of that here — follow the contract.

2. **Confirm the runtime-verified root (hard gate).** Per invariant 1, the artifact's root must be runtime-captured THIS session. If the root is second-hand (commit message, prior plan, agent report), runtime-verify it yourself before writing the artifact. Never pin the root as `CONFIRMED — do not re-litigate`.

3. **Write the fix-design artifact.** Save it under `.scratch/reviews/fix-design-YYYY-MM-DD-<topic>.md` (gitignored). Include: the runtime-verified root with trace/`file:line` citations; candidate options with cost/risk; the recommended option; an implementation sketch (file paths, where the change lands); the validation plan; and what each scope angle should evaluate. Specifics in → specifics out.

4. **Use the state owner for the supported formal path.** Resolve the installed helper from project-local `.claude/agents/scripts/review_loop_state.py` first, then `~/.claude/agents/scripts/review_loop_state.py`. Invoke `review_loop_state.py begin` with state below `.scratch/reviews/<loop-id>/`, file inputs for objective/scope/runtime-root/diff, and the artifact file or verified Git revision. Parse the single JSON receipt and require `event=ORCHESTRARIUM_REVIEW_LOOP_STATE_V2`; any failure or missing/malformed receipt stops this supported procedure. This command is not an executable host gate. Claude's dispatch sentinel observes bounded same-role internal Agent depth, while the helper itself does not observe bypass and direct/ad-hoc launches outside that monitored surface remain outside its guarantees. The historical observer gap is fixed without expanding the helper's guarantees.

5. **Dispatch all three angles in parallel.** Carry the attempt IDs and `artifact_revision` from the committed receipt for this supported state path. Per the contract's Claude dispatch mapping, via the Agent tool with `run_in_background: true`:
   - **Surgical verdict** → `subagent_type: external-reviewer` (routes to the external provider).
   - **Deep verdict** → `subagent_type: architecture-reviewer`, `model: fable` (the flagship alias as of 2026-07; direct strategic verdict — NOT `consultant`).
   - **Mechanical scout** → `subagent_type: analyst`, `model: sonnet` (factual `file:line`, NO verdict — it feeds the verdicts).
   Carry the ORIGINAL pinned objective verbatim into every angle. Same-vendor Agent subagents return their normal result; each external-provider lane uses the approved thin wrapper owned by `agents/contracts/external-dispatch.md`, which supplies the strict V2 parser, full external-nonauthorizing tuple, and untrusted/potentially-sensitive resultText contract. For a tracked run, apply that owner's terminal-ledger read-back before counting the angle. Notifications are collection hints only; independence remains scope/framing, never vendor.

6. **Converge autonomously through the state owner.** Call `mark-running` before each launch; count a result/failure only after `record-result`/`record-failure` accepts the same round, attempt ID, and artifact revision. Reconcile failed lanes through `admit-retry`, finish each clean round through `complete-round`, and freeze every corrected artifact through `next-round` before re-dispatch. Use fresh operation IDs, replaying one only for an idempotent retry. Close through `close --outcome converged|drift|deadlock`.

7. **Human gate at convergence only.** Return to the human in exactly three cases — never per round: (a) converged (both verdict angles PASS + all scout findings reconciled) — present the final design plus a short round history; (b) drift — present what would have drifted off the pinned objective and why you stopped; (c) deadlock — cap N=3 reached without convergence — present the aspect that never converged.

8. **Implement after acceptance.** Once the human accepts the converged design, implement per the artifact with every guard/invariant/instrumentation the angles named, run the validation plan, capture evidence, and only then proceed to the commit gate.

## Disambiguation

Pick the loop when there is real design uncertainty (2+ candidate fix options, or prior verdicts were false-positive) and you want autonomous multi-angle convergence on ONE artifact before the change lands. Use `/agents-second-opinion` for a single advisory memo, `/agents-review` for a post-implementation specialist gate, and `/agents-external-brigade` for disjoint parallel lanes that each own a different artifact.

See also `/agents-design-panel` — the generation-side analog: it independently generates N candidate designs BEFORE a single artifact exists, converged through one mandatory synthesis, while this loop verifies ONE already-written artifact to convergence.

## Rules

- This is an operator command, not a new specialist role; the angles are dispatched via the Agent tool.
- The methodology lives in `.claude/agents/contracts/review-loop.md`; this command points at it and must not restate it.
- The mechanical scout is `analyst` and casts no verdict; never route it to `qa-engineer`.
- The deep angle is a direct-verdict `architecture-reviewer` at `model: fable` (the flagship alias as of 2026-07); it is intentionally NOT `consultant` (external-mode consultant shells out — the role-confusion). `consultant.md` stays untouched.
- Do NOT commit, push, or install from this command. The converged design and any implementation stop at the human's commit gate.
