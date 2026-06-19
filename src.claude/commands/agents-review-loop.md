# Review Loop

Run the autonomous parallel-review-loop: dispatch three independent scope angles against one written fix-design artifact, converge autonomously under an anti-drift guard, and gate the human only at the converged result. This command is THIN — it reads the installed contract at runtime and executes the loop; it does not restate the methodology.

## When to auto-invoke

Auto-invoke this flow ONLY on the narrow, explicit loop triggers:

- "review loop"
- "проводи review loop"
- "loop review"
- "автономная петля"

Do NOT auto-invoke on `review`, `second opinion`, or `let's review` — those own `/agents-review` and `/agents-second-opinion` respectively. The loop is a deliberate, heavier surface (three angles, multi-round, autonomous convergence); it is not the default for an ordinary review or a single second opinion.

Do NOT auto-invoke for trivial changes (one-line typo, doc edit, single-file refactor with no behavior change) or when the bug's root is an unmeasured runtime value — capture the runtime root FIRST, then loop on the fix design.

## Steps

1. **Read the installed contract.** Read `.claude/agents/contracts/review-loop.md`. It owns the operative loop rules (the angles, the Claude dispatch mapping, autonomous-to-convergence, anti-drift, the cap, the six hardening invariants, the convergence rule, and the `review-loop-state` ledger schema). Do not re-derive any of that here — follow the contract.

2. **Confirm the runtime-verified root (hard gate).** Per invariant 1, the artifact's root must be runtime-captured THIS session. If the root is second-hand (commit message, prior plan, agent report), runtime-verify it yourself before writing the artifact. Never pin the root as `CONFIRMED — do not re-litigate`.

3. **Write the fix-design artifact.** Save it under `.scratch/reviews/fix-design-YYYY-MM-DD-<topic>.md` (gitignored). Include: the runtime-verified root with trace/`file:line` citations; candidate options with cost/risk; the recommended option; an implementation sketch (file paths, where the change lands); the validation plan; and what each scope angle should evaluate. Specifics in → specifics out.

4. **Dispatch the three scope angles in parallel.** Per the contract's Claude dispatch mapping, via the Agent tool with `run_in_background: true`:
   - **Surgical verdict** → `subagent_type: external-reviewer` (routes to the external provider).
   - **Deep verdict** → `subagent_type: architecture-reviewer`, `model: opus` (direct strategic verdict — NOT `consultant`).
   - **Mechanical scout** → `subagent_type: analyst`, `model: sonnet` (factual `file:line`, NO verdict — it feeds the verdicts).
   Carry the ORIGINAL pinned objective verbatim into every angle. Collection is split by lane: same-vendor Agent subagents fire a reliable notification (wait for it); an external-provider shell-out lane (its notification is not always delivered) is verified by actively reading its captured `.out`/`.err` + process status. Read each angle's captured OUTPUT (not its notification) before counting it.

5. **Converge autonomously, persisting `review-loop-state` per round.** No human gate per round. Each round: revise the artifact to fold in every open blocker and unreconciled scout finding; run the mandatory anti-drift check; re-dispatch all angles on the revised artifact. Persist one `review-loop-state` record per round under `.scratch/reviews/` in the contract's schema (pinned objective/scope/runtime_root identical across rounds, per-round diff, both verdict angles + scout, no bare PASS, round ≤ cap). The persisted ledger is the runtime trace; its schema is checked by `scripts/validate-review-loop-state.* --self-test` in the repo (development/CI), not a shipped runtime tool.

6. **Human gate at convergence only.** Return to the human in exactly three cases — never per round: (a) converged (both verdict angles PASS + all scout findings reconciled) — present the final design plus a short round history; (b) drift — present what would have drifted off the pinned objective and why you stopped; (c) deadlock — cap N=3 reached without convergence — present the aspect that never converged.

7. **Implement after acceptance.** Once the human accepts the converged design, implement per the artifact with every guard/invariant/instrumentation the angles named, run the validation plan, capture evidence, and only then proceed to the commit gate.

## Disambiguation

Pick the loop when there is real design uncertainty (2+ candidate fix options, or prior verdicts were false-positive) and you want autonomous multi-angle convergence on ONE artifact before the change lands. Use `/agents-second-opinion` for a single advisory memo, `/agents-review` for a post-implementation specialist gate, and `/agents-external-brigade` for disjoint parallel lanes that each own a different artifact.

## Rules

- This is an operator command, not a new specialist role; the angles are dispatched via the Agent tool.
- The methodology lives in `.claude/agents/contracts/review-loop.md`; this command points at it and must not restate it.
- The mechanical scout is `analyst` and casts no verdict; never route it to `qa-engineer`.
- The deep angle is a direct-verdict `architecture-reviewer` at `model: opus`; it is intentionally NOT `consultant` (external-mode consultant shells out — the role-confusion). `consultant.md` stays untouched.
- Do NOT commit, push, or install from this command. The converged design and any implementation stop at the human's commit gate.
