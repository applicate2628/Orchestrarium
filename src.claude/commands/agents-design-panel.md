# Design Panel

Run the admitted design-panel technique: independently framed candidates on one pinned problem, mandatory comparison and sole synthesis. Root receives that synthesis under existing authority and required gates: continue only an already-authorized ready next stage, end at the requested design-only handoff, or hold the action for a genuine scope/user/pause/publication condition. This thin command follows its installed operative contract; synthesis adds no permission or unconditional human stop.

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

3. **Choose N and framings.** Default `N=2`. Pick a distinct, bounded framing per lane and pre-register them through existing carriers BEFORE dispatch: `Current step` names panel preparation, `Last result` records the accepted pinned-input gate, `Next action` names candidate dispatch, and root-owned `agent-runs.jsonl` receives one running launch event per lane whose existing run identity, role/assigned-role, and scope carry the lane id, assigned role, and framing. Do not add a status table or ledger field.

4. **Dispatch every candidate through the existing direct `$external-worker` boundary**, inheriting the admitted design profession according to the operative sealed external mapping:
   - Use file-based prompts and inspect resolved provider argv against the no-session-reuse contract. No native Agent candidate, internal architect candidate or Agent relay to an external candidate is admitted.
   - Run compatible independent external lanes concurrently when supported; otherwise sequentially in fresh sealed external contexts, without reducing quorum or changing framing/authority.
   - Optional comparison scout (after lanes return) → `subagent_type: analyst`, `model: sonnet` — factual set-diff, no verdict.
   Carry the identical pinned input to every candidate; only the framing overlay differs. Each writes `design-<lane>.md`, never `design.md`. Every candidate uses a fresh sealed external context that has not seen a sibling's input/output; sequential execution changes concurrency only, not quorum or independence.

5. **Collect.** Receive every candidate through the approved thin wrapper or declared owner-equivalent execution preserving the same external guarantees under `agents/contracts/external-dispatch.md`: strict V2 parser, full external-nonauthorizing tuple, untrusted/potentially-sensitive resultText and actual terminal/privacy/provenance/ledger/custody checks, never a notification or private capture. A died, timed-out, cleanup-failed, ledger-unsettled or empty lane is `UNVERIFIED`; retry only under its existing same-framing lineage and budget, never reduce quorum below `N=2` or use internal fallback.

6. **Synthesize.** The main conversation, as Lead, performs the synthesis inline (default) — or, if pre-declared before dispatch, one non-candidate synthesis architect dispatch. NEVER a spawned "synthesizer" subagent acting as a stand-in lead, and never a candidate author. Produce the comparison/disposition matrix (`DP5`) and write the sole canonical `work-items/active/<slug>/design.md`, citing every candidate as evidence.

7. **Return exactly one public result:** the sole synthesized design and its gate (`PASS | REVISE | BLOCKED:dependency | BLOCKED:prerequisite`), never a candidate as "the design." Root receives the synthesis, comparison matrix and unchanged accepted owner claims, then selects only its next already-authorized stage after required gates. Reassess mandatory review-loop triggers; selected remaining review/Plan requirements remain binding, but the panel alone mandates neither. Candidates remain INPUT_ONLY work-item inputs and are never handed to Planner.

## Disambiguation

Use a panel only when expressly requested or Root separately admits it for a concrete generation need/benefit, such as a high-surface-count sweep or open architecture choice. Eligibility alone does not dispatch it. Use `/agents-design` for ordinary single-architect design, `/agents-review-loop` for admitted verification of one existing artifact, and `/agents-second-opinion` for advisory input. After synthesis, continue only authorized ready work; design-only, pause/publication or missing mandatory cases keep their actual holds.

## Rules

- This is an operator technique, not a new specialist role. Candidate dispatch follows the operative sealed direct external-worker contract; the optional factual scout and sole synthesis retain their separately defined owners and routes.
- The methodology lives in `.claude/agents/contracts/design-panel.md`; this command points at it and must not restate it.
- Only the synthesis step may write `design.md`; candidate lanes write `design-<lane>.md` and are never shown to each other's output.
- Do NOT commit, push, or install from this command. Return the accepted artifact to the root; verified local commit checkpoints remain the root's responsibility under shared governance. Human review remains required before push, release, or equivalent publication.
