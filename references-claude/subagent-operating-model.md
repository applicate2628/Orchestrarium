# Subagent Operating Model — Claude Addendum

> **Note**: this document keeps the Claude-specific addendum to the shared blueprint. Canonical routing and operator semantics live in the shared core and the current Claude operator reference surfaces.

Canonical shared core: [shared/references/subagent-operating-model.md](../shared/references/subagent-operating-model.md)

Visual companion: [operating-model-diagram.md](operating-model-diagram.md)

This file keeps only Claude-specific runtime and repository concretization for the shared subagent operating model. Use the shared core for canonical blueprint, routing, role, and governance-model text.

### Optional source-mode Claude SDK integration

The separate direct Claude SDK adapter retains the native Claude preset and adds
current common/provider instructions through the existing owned-file mechanism.
Tool-restricted review is not an operating-system sandbox. Selected model aliases
are not silently guessed into canonical IDs; source qualification limits and
non-authorizing receiving remain explicit in [SDK execution](../docs/sdk-execution.md).
Existing Claude provider execution and installed agent entrypoints remain unchanged.
Both host packs receive installer-managed SDK helpers; that does not activate the
Claude adapter. A Claude-hosted, policy-admitted Codex external-reviewer invocation
may explicitly select `--sdk-review-binding` under the same Host authority, without
starting an Agents coordinator or changing billing. This repository-local opt-in
is Windows-only with empty MCP scope; other roles/providers remain on legacy
routes. Diagnostic recovery is implemented but not yet native-qualified;
installed-bridge qualification remains pending, and older native observations
do not qualify this candidate.

## Claude-specific runtime notes

- Claude runtime uses the Agent tool and the current Claude operator reference surfaces. Treat this file as a local runtime addendum to the shared blueprint, not as the canonical full methodology copy.
- Claude native Agent lanes use the shared rolling lane-ready-set contract. Current host capacity is authoritative when exposed; otherwise admission probes one ranked candidate at a time and does not cache a numeric cap.
- Claude internal Agent model and effort are host-selected; role definitions declare no fixed model, effort, or floor. Unless returned actual runtime metadata proves the effective values, record `unspecified by runtime`.
- Consultant config lives in `.claude/.agents-mode.yaml`; routing reads normalize effective values in memory, with persistence limited to authorized install/configuration writes under the [external dispatch owner](../src.claude/agents/contracts/external-dispatch.md#shared-config-file).
- Claude-line canonical config does not include `externalClaudeProfile`; Claude-side `externalProvider: auto` resolves by lane type through the active named production priority profile and shipped production `auto` uses `codex | claude` only. Explicit Kimi selection is limited to policy-admitted read-only work or engineering whose task eligibility and assigned profession map to `external-worker`. A selected capability file supplies only caller-scoped tools under that existing mutation class and role mapping; it grants neither authority nor a sandbox. Grok remains unavailable, and removed Gemini/Qwen scalar values fail closed with `E_EXTERNAL_PROVIDER_REMOVED`.
- `$external-worker` and `$external-reviewer` dispatch from Claude Code to the provider selected by `.claude/.agents-mode.yaml`.

## Claude-side repository concretization

- Admitted adjacent-defect proposals use `work-items/bugs/` under `qa-engineer`'s bug-admission contract. Typed holds retain their actual cause, required remainder, owner and next action under the shared core.
- Human recovery starts at generated `work-items/README.md`; state resolves from physical `work-items/backlog/`, `work-items/active/<date>-<slug>/`, and `work-items/archive/YYYY-MM/<date>-<slug>/` locations plus owning artifacts. `work-items/index.md` is compatibility-only. Accepted terminal results consume the [Lead work-cycle owner](../src.claude/skills/lead/SKILL.md#work-cycle-ownership-recipe) for strict selected-item `--obligations-json` receipt/status acknowledgment and actual continuation/close and original-target readiness. This includes logical-phase versus supported-host release/accounting and retention of actual runner identities/state before formatting/truncation; this addendum owns no second completion or teardown algorithm.
- Bug preservation and separate fixed-bug administration use the [shared lifecycle owner contract](../shared/references/work-items-root-contract.md) and its operator runbook; no provider-specific status or parent-location rule is added.
- Periodic controls stay pack-local in [periodic-control-matrix.md](periodic-control-matrix.md).
- Claude-side examples use `Gate: PASS | REVISE | BLOCKED:<class> | RETURN(role)`.
- Claude runtime docs also keep the explicit `Artifact invalidation protocol` and `Parallel execution protocol`; use them together with the shared core.

## Shared core now owns

- Main rule, core management rules, delivery loops, routing patterns, role map, prompts, gates, and team composition
- Shared review/gate semantics, periodic-controls model, rolling lane-ready admission, parallel-work guidance, and generic task-memory expectations
- The generic lead memo and final wording

## Terms and Abbreviations

- SDK: Software Development Kit.
- MCP: Model Context Protocol.
- Host: the existing invoking orchestration session, not a new coordinator.
- API: Application Programming Interface.
