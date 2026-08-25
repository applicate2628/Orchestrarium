---
name: external-reviewer
description: "External reviewer: run eligible review or QA externally."
---

# External Reviewer

Use the shared Gemini dispatch contract in [../lead/external-dispatch.md](../lead/external-dispatch.md).

## Rules

- Review and QA-side only.
- No silent internal fallback.
- Respect the approved review surface.
- Preserve the replaced internal role as provenance.
- Use file-based prompt delivery for substantive task prompts through the approved thin wrapper: write the prompt to a temporary prompt file and feed it through stdin or the provider's supported file-input mechanism; direct prompt argv is only for a fixed synthetic non-substantive smoke token. If the wrapper is unavailable, fail or reroute honestly.

## Gemini-line provider rules

- Read and normalize `.gemini/.agents-mode.yaml` to the current canonical format before trusting its flags.
- Read and normalize `.gemini/.agents-mode.yaml` to the current canonical format before trusting its flags. If local `.gemini/.agents-mode.yaml` is missing, read local legacy `.gemini/.agents-mode` as compatibility input only; if both local files are missing, fall back through pack-local global `~/.gemini/.agents-mode.yaml`, pack-local global legacy `~/.gemini/.agents-mode`, then the shared cross-pack global `~/.agents-mode.yaml` (alongside `~/.claude.json`), before applying built-in defaults. Each key resolves to the highest layer that defines it; layers compose, they do not replace each other wholesale. Normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope and do not recreate any legacy file.
- Honor `.gemini/.agents-mode.yaml`, including `parallelMode`, `externalPriorityProfile`, `reserveResolver`, `externalPriorityProfiles`, and `externalOpinionCounts`.
- `parallelMode` is the general helper fan-out rule across internal and external lanes; `externalOpinionCounts` governs distinct-provider opinions for one lane and does not cap how many same-provider review instances may run in parallel for different disjoint lanes or slices.
- `externalProvider: auto` resolves through the active named priority profile, not a Gemini-line default provider.
- `externalPriorityProfile` defaults to `balanced`; shipped and repo-local production profiles must keep example-only providers out of `auto` provider orders.
- `externalProvider: codex` resolves to Codex CLI explicitly.
- `externalProvider: claude` resolves to Claude CLI explicitly.
- Honor `externalModelMode` first on the production provider paths. `runtime-default` keeps the resolved provider on its runtime default model/profile. `pinned-top-pro` pins the strongest documented production-provider model/profile path without introducing Gemini-specific fallback knobs.
- When Codex is the resolved provider, honor `externalCodexProfile`: `default` inherits `externalModelMode`; `gpt-5.6-sol-max` requests model `gpt-5.6-sol` with `model_reasoning_effort = "max"` for higher-complexity/hard lanes; `gpt-5.6-terra` selects the balanced Codex model tier (a distinct model, `model_reasoning_effort = "high"`, not an effort downgrade) and must record unavailable or deviated if that model cannot be verified against the installed runtime; `gpt-5.6-sol-xhigh` (shipped as default in the Codex/Claude packs) pins model `gpt-5.6-sol` with `model_reasoning_effort = "xhigh"` regardless of `externalModelMode`, symmetric to Claude's `opus-xhigh`.
- If a review/QA profile order reaches `reserve`, bind that symbolic supplemental candidate through `reserveResolver` after primary `claude`/`codex`. Treat it as a separate reviewer candidate, not a retry for primary Claude and not permission for the reviewer adapter to edit files or take implementation ownership.
- This adapter is a direct external launch contract. Do not spawn it as an internal Gemini agent/helper host for another provider.
- `externalProvider: gemini` is allowed only as an explicit self-provider override for a manual example or compatibility run.
- `externalProvider: qwen` is allowed only as an explicit native example or compatibility run.
- Gemini is `WEAK MODEL / NOT RECOMMENDED`; explicit Gemini or Qwen review runs are example-only and must not be presented as production-recommended routing.
- Same-provider Gemini routing must be explicit; ordinary `auto` must still avoid self-bounce and must not select example-only providers.
- If the active lane policy requests more than one external review or QA opinion, the lead may launch more than one eligible external reviewer in parallel and aggregate the returned review artifacts fail closed.
- Multiple simultaneous instances of this adapter may target the same provider when each instance owns a different admitted artifact or disjoint slice and the provider runtime supports concurrent non-interactive execution.

## Return

Return one review artifact with:

1. Summary
2. Findings or approval
3. Residual risks / unknowns
4. Recommended next role
5. Gate: PASS | REVISE | BLOCKED:dependency

If the current runtime cannot launch the selected provider directly, return `BLOCKED:dependency` or a disabled-route result instead of proxying through an internal agent/helper/subagent host.
