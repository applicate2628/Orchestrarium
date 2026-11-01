# Review Loop

Run the autonomous parallel-review-loop: dispatch three independent scope angles against one written fix-design artifact and converge autonomously under an anti-drift guard. Root receives the terminal outcome and continues already-authorized ready work under its existing gates; convergence itself adds no human approval step or execution authority. This command is THIN — it reads the installed contract at runtime and executes the loop; it does not restate the methodology.

## When to auto-invoke

Use the installed contract’s semantic admission triggers for complex decisions; these explicit user requests also mandate the loop:

- "review loop"
- "проводи review loop"
- "loop review"
- "автономная петля"

Do NOT auto-invoke on `review` / `let's review` (owned by `/agents-review`) or `second opinion` (owned by `/agents-second-opinion`). The loop is a deliberate, heavier surface (three angles, multi-round, autonomous convergence); it is not the default for an ordinary review or a single second opinion.

Do NOT auto-invoke for trivial changes (one-line typo, doc edit, single-file refactor with no behavior change) or when the bug's root is an unmeasured runtime value — capture the runtime root FIRST, then loop on the fix design.

## Steps

1. **Read the installed contract.** Read `.claude/agents/contracts/review-loop.md`. It owns the operative loop rules (the angles, the Claude dispatch mapping, autonomous-to-convergence, anti-drift, the cap, the hardening invariants, the convergence rule, and the `review-loop-state` ledger — its force, schema, and enforcement envelope), including hardening invariants 7-8 (failed-lane-is-unverified, fail-closed aggregation); do not re-derive any of that here — follow the contract.

2. **Confirm the verified premises (hard gate).** Apply installed contract invariant 1 to the artifact's exact claims before writing it; acquire the underlying primary evidence THIS session, never admit a secondhand root or pin `CONFIRMED — do not re-litigate`.

3. **Write the fix-design artifact.** Save it under `.scratch/reviews/fix-design-YYYY-MM-DD-<topic>.md` (gitignored). Include: the verified premises with claim-appropriate primary evidence and `file:line`/trace citations; candidate options with cost/risk; the recommended option; an implementation sketch (file paths, where the change lands); the validation plan; and what each scope angle should evaluate. Specifics in → specifics out.

4. **Use the state owner for the supported formal path.** Resolve the installed helper from project-local `.claude/agents/scripts/review_loop_state.py` first, then `~/.claude/agents/scripts/review_loop_state.py`. Invoke `review_loop_state.py begin` with state below `.scratch/reviews/<loop-id>/`, file inputs for objective/scope/runtime-root/diff, and the artifact file or verified Git revision. Parse the single JSON receipt and require `event=ORCHESTRARIUM_REVIEW_LOOP_STATE_V2`; a defective helper permits only declared owner-equivalent admission under the shared assistance contract, with actual canonical readback and no fabricated engine receipt; unmet invariants or host denial stop the action. This command is not an executable host gate. Claude's dispatch sentinel observes bounded same-role internal Agent depth, while the helper itself does not observe bypass and direct/ad-hoc launches outside that monitored surface remain outside its guarantees. The historical observer gap is fixed without expanding the helper's guarantees.

5. **Dispatch all three angles in parallel.** Carry the actual attempt IDs and `artifact_revision` from committed canonical admission, using a genuine helper receipt when the helper ran or independent state readback for declared manual-equivalent admission. Select and freeze each supported initial route per the installed contract before dispatch; its mapping below is a preference, not mandatory external realization. For host Agent lanes use `run_in_background: true` when compatible:
   - **Surgical verdict** → the selected nonauthoring review-side profession; `external-reviewer` only when the external route was selected.
   - **Deep verdict** → `subagent_type: architecture-reviewer` with a sufficient admitted profile; returns its own verdict directly.
   - **Mechanical scout** → `subagent_type: analyst` with a sufficient factual profile (factual `file:line`, NO verdict — it feeds the verdicts).
   Carry the ORIGINAL pinned objective verbatim into every angle. Same-vendor Agent subagents return their normal result; each external-provider lane follows the admitted launch/terminal guarantees in `agents/contracts/external-dispatch.md`, through the working approved thin wrapper or declared owner-equivalent launch/settlement when defective. Actual wrapper execution supplies the strict V2 parser, full external-nonauthorizing tuple, and untrusted/potentially-sensitive resultText contract. For a tracked run, apply that owner's terminal-ledger read-back before counting the angle. Notifications are collection hints only; independence remains scope/framing, never vendor.

6. **Converge autonomously through the state owner.** Use the preferred helper commands below or declared owner-equivalent transitions with the same state contract. Call `mark-running` before each launch; count a result/failure only after `record-result`/`record-failure` accepts the same round, attempt ID, and artifact revision. Reconcile failed lanes through `admit-retry`, finish each clean round through `complete-round`, and freeze every corrected artifact through `next-round` before re-dispatch. Use fresh operation IDs, replaying one only for an idempotent retry. Close through `close --outcome converged|drift|deadlock`.

7. **Receive the terminal outcome under existing authority.** Receive the terminal outcome through Root: on convergence, present the accepted design and short round history, verify both verdicts, reconciled scout findings and canonical closure/readback, then continue the next already-authorized ready action under its existing gates. A design-only request ends at its accepted handoff; an actual human, scope, pause or publication gate holds only its dependent action. Drift or deadlock stops the affected loop and escalates its unresolved decision/cap; independent admitted ready work may continue. No human gate is added per round or merely because convergence occurred.

8. **Implement under existing authority.** When Root receives the converged outcome and the next implementation action is already authorized with its required gates passed, the assigned implementer executes its accepted guarantees and invariants, preserving upstream claim identity and required safety corrections that discharge genuine vetoes. Optional reviewer HOW or telemetry suggestions remain advisory/nonblocking unless separately admitted into scope; run the validation plan and capture evidence before the root's verified local checkpoint. Read-only reviewer lanes gain no Source mutation authority.

## Disambiguation

Pick the loop when there is real design uncertainty (2+ candidate fix options, or prior verdicts were false-positive) and you want autonomous multi-angle convergence on ONE artifact before the change lands. Use `/agents-second-opinion` for a single advisory memo, `/agents-review` for a post-implementation specialist gate, and `/agents-external-brigade` for disjoint parallel lanes that each own a different artifact.

See also `/agents-design-panel` — the generation-side analog: it independently generates N candidate designs BEFORE a single artifact exists, converged through one mandatory synthesis, while this loop verifies ONE already-written artifact to convergence.

## Rules

- This is an operator command, not a new specialist role; the angles are dispatched via the Agent tool.
- The methodology lives in `.claude/agents/contracts/review-loop.md`; this command points at it and must not restate it.
- The mechanical scout is `analyst` and casts no verdict; never route it to `qa-engineer`.
- The deep angle is a direct-verdict `architecture-reviewer` using a sufficient current policy/host-admitted profile. Preserve genuinely admitted exact model/effort/corridor/family requirements and record actual runtime metadata distinctly from requested/resolved controls; no dated alias establishes availability. It is intentionally NOT `consultant` (external-mode consultant shells out — the role-confusion). `consultant.md` stays untouched.
- Do NOT commit, push, or install from this command. Return the accepted artifact to the root; verified local commit checkpoints remain the root's responsibility under shared governance. Human review remains required before push, release, or equivalent publication.
