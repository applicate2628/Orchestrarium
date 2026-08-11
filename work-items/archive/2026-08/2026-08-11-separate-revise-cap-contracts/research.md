# Research — REVISE cap contracts

## Files & symbols

- `static-read` — the shared spine defines a cap of 3 **consecutive cycles for the same role and artifact** at `shared/AGENTS.shared.md:39`; the shared operating-model reference repeats that scope at `shared/references/subagent-operating-model.md:178`.
- `static-read` — the autonomous review-loop state engine owns `DEFAULT_CAP = 3` at `scripts/review_loop_state.py:26` and enforces it as a count of `rounds` at `scripts/review_loop_state.py:124-150` and `scripts/review_loop_state.py:207-258`.
- `static-read` — review-loop prose names the same unit as rounds at `shared/references/review-loop-methodology.md:30-37`, `src.claude/agents/contracts/review-loop.md:38-45`, and `src.codex/skills/review-loop/SKILL.md:43-48`.
- `static-read` — Claude's general operating model instead says `3 iterations per stage` at `src.claude/agents/contracts/operating-model.md:219-229`; Codex says same role and artifact at `src.codex/skills/lead/operating-model.md:18-24`.

## Flows

- `static-read` — `scripts/validate-review-loop-state.py:12-16` imports the engine and passes a caller-supplied/default cap into `validate_record`; the engine rejects excess round count.
- `static-read` — generic Lead correction is instruction-driven through the shared spine and provider Lead bindings; no runtime counter owner was found in the searched production Python surfaces.
- `static-inference; ASSUMPTION (UNVERIFIED)` — human/agent adherence to the generic prose cap is not mechanically observable. Resolving probe: a future execution ledger schema with an explicit correction-cycle record; this task can only enforce source agreement.

## Contracts

- `static-read` — the generic contract's identity includes role, artifact, consecutive `REVISE` result, and escalation after 3 (`shared/AGENTS.shared.md:39`; `src.codex/skills/lead/SKILL.md:274`).
- `static-read` — the autonomous review-loop contract's identity is the number of full multi-angle rounds in one loop (`scripts/review_loop_state.py:124-150`; `shared/references/review-loop-methodology.md:30-37`).
- `static-read` — `shared/references/cross-pack-reconciliation.md:26` currently claims Claude and Codex have identical cap semantics even though the cited provider texts use `per stage` versus `same role and artifact`.

## Tests & coverage

- `runtime-verified` — CodeGraph freshness was current after the preceding hook fix; current source queries resolved `validate_v1`, `validate_v2`, and `validator_main` call paths.
- `static-read` — `tests/test_review_loop_state_v2.py` covers the state owner broadly but contains no explicit prose-consumer inventory or cross-pack scope assertion.
- `runtime-verified` — a current exact text inventory found the two scopes across shared, Claude, Codex, Russian, and reconciliation surfaces; no dedicated cap-contract test exists.

## Similar implementations

- `static-read` — `scripts/skill_pack_validator_runtime.py:338-343` already uses normalized fingerprint gates where duplicated cross-pack prose cannot share one runtime object.
- `static-read` — `shared/references/cross-pack-reconciliation.md:20-29` is the existing maintainer inventory for semantically paired Claude/Codex sections.

## Constraints

- `static-read` — installed provider bindings cannot import one shared Markdown object at runtime; a generated-from-one-source or drift-gated duplicate is the permitted C1 exception.
- `static-read` — the review-loop engine accepts explicit `--cap` overrides (`scripts/review_loop_state.py:1379-1384`), so the default owner must remain distinct from per-run configuration.
- `runtime-verified` — parked p95 changes occupy `RELEASE_NOTES.md` and several installer/docs surfaces; this item must stage its release hunk separately and avoid those implementation files.

## Change risks

- `static-read` — collapsing both caps into one semantic rule would be incorrect because a round contains multiple lanes while a generic correction cycle identifies one role and artifact.
- `static-read` — retaining `per stage` would preserve a third unit with no owner or trace schema.
- `static-read` — recent history on the state owner includes `cfbfe3d7` and `1ac19a3f`; changing validation behavior rather than naming/default ownership could reopen hardened review-loop contracts.

## Unresolved questions

- `ASSUMPTION (UNVERIFIED)` — whether the generic cap should later become ledger-enforced. Resolving probe: approve a separate agent-run schema change; absent that, source drift is the only enforceable property.
- `ASSUMPTION (UNVERIFIED)` — whether both values will remain numerically equal after future policy changes. Resolving probe: an explicit policy revision; current design must not couple them merely because both equal 3 today.

## Searched and excluded

- Publication hooks, provider prompt launchers, installers, and p95 runner files do not consume either cap and are excluded.
- Upstream Codex skill-description shortening and Claude early-return bugs are separate host-runtime constraints and are excluded.

## Research admission gates

- **Regression risk:** PASS — naming and drift-gating can preserve the engine's existing default/override behavior and generic escalation behavior.
- **Metric alignment:** PASS — success is exact owner/consumer agreement, not runtime performance.
- **Known limits:** PASS — generic adherence remains instruction-enforced and is explicitly unmeasured.
- **Bounded falsification:** PASS — mutate each owner value/scope independently and require the dedicated contract test to fail.

## Adjacent findings

None beyond the already-recorded upstream and RU-parity bugs.

## Gate decision

PASS.

## Terms and Abbreviations

- **C1:** architecture law requiring one owner per invariant, with drift-gated duplication across hard boundaries.
- **PASS:** the next role can proceed without reopening broad discovery.
