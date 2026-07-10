# Design Panel

Run the design-panel technique: dispatch N independently-framed design lanes on one pinned problem, converge them through one mandatory synthesis, and gate the human only on the synthesized result. This command is THIN — it reads the installed contract at runtime and executes the panel; it does not restate the methodology.

## When to auto-invoke

Auto-invoke this flow ONLY on the narrow, explicit panel triggers:

- "design panel"
- "design-panel"
- "дизайн-панель"
- "панель дизайнов"
- "two architects" / "два архитектора"
- "parallel independent designs"

Do NOT auto-invoke on plain "design" / "спроектируй" (owned by `/agents-design`), on "review loop" / "автономная петля" (owned by `/agents-review-loop`), or on "second opinion" / "второе мнение" (owned by `/agents-second-opinion`). The panel is a deliberate, heavier surface (N strong-model design lanes plus mandatory synthesis); it is not the default for an ordinary design request.

Do NOT auto-invoke for single-module additive design, or when the design problem's premise is still unverified — verify the premise first, then consider the panel.

## Steps

1. **Read the installed contract.** Read `.claude/agents/contracts/design-panel.md`. It owns the operative panel rules (DP1–DP8, the Claude dispatch mapping, the skip-guards, and the candidate/synthesis artifact contracts). Do not re-derive any of that here — follow the contract.

2. **Pinned-input gate.** Confirm one admitted objective, scope, and evidence/constraint package exist (per `DP1`). If the problem statement is unverified, verify it first — a panel multiplies an unverified premise across every lane.

3. **Choose N and framings.** Default `N=2`. Pick a distinct, bounded framing per lane and pre-register them (lane id, framing, assigned role) in the work-item `status.md` `## Active agents` table BEFORE dispatch.

4. **Dispatch the candidate lanes in parallel**, per the contract's Claude dispatch mapping, via the Agent tool with `run_in_background: true`:
   - Internal lane → `subagent_type: architect` with an explicit `model:` override.
   - External lane (when used) → `subagent_type: external-worker` inheriting `architect`.
   - Optional comparison scout (after lanes return) → `subagent_type: analyst`, `model: sonnet` — factual set-diff, no verdict.
   Carry the identical pinned input to every lane; only the framing overlay differs. Each lane writes its candidate to `design-<lane>.md` — never `design.md`.

5. **Collect.** Verify each lane's captured OUTPUT (not its notification) before counting it. A died, timed-out, or empty lane is `UNVERIFIED` — re-run it with the same framing; never silently reduce quorum below `N=2`.

6. **Synthesize.** The main conversation, as Lead, performs the synthesis inline (default) — or, if pre-declared before dispatch, one non-candidate synthesis architect dispatch. NEVER a spawned "synthesizer" subagent acting as a stand-in lead, and never a candidate author. Produce the comparison/disposition matrix (`DP5`) and write the sole canonical `work-items/active/<slug>/design.md`, citing every candidate as evidence.

7. **Return exactly one public result:** the synthesized design and its gate (`PASS | REVISE | BLOCKED:dependency | BLOCKED:prerequisite`). Never present one candidate as "the design." Route `design.md` onward (architecture review, `/agents-review-loop`, or `$planner`) naming the synthesis comparison matrix as the claims source; candidate artifacts stay in the work-item as inputs and are never handed to the planner.

## Disambiguation

Pick the panel when the design problem is a high-surface-count sweep or an open architecture choice and you want independently-framed candidate generation BEFORE a design exists. Use `/agents-design` for an ordinary single-architect design chain, `/agents-review-loop` to converge multiple angles on ONE already-written artifact, and `/agents-second-opinion` for a single advisory memo.

## Rules

- This is an operator technique, not a new specialist role; lanes are dispatched via the Agent tool.
- The methodology lives in `.claude/agents/contracts/design-panel.md`; this command points at it and must not restate it.
- Only the synthesis step may write `design.md`; candidate lanes write `design-<lane>.md` and are never shown to each other's output.
- Do NOT commit, push, or install from this command. The synthesized design and any implementation stop at the human's commit gate.
