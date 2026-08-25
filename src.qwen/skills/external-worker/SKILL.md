---
name: external-worker
description: "External worker: run eligible worker roles externally."
---

# External Worker

Use the shared Qwen dispatch contract in [../lead/external-dispatch.md](../lead/external-dispatch.md).

## Rules

- Worker-side only.
- No silent internal fallback.
- Respect the approved role contract and change surface.
- Preserve the replaced internal worker role as provenance.
- Use file-based prompt delivery for substantive task prompts through the approved thin wrapper: write the prompt to a temporary prompt file and feed it through stdin or the provider's supported file-input mechanism; direct prompt argv is only for a fixed synthetic non-substantive smoke token. If the wrapper is unavailable, fail or reroute honestly.

## Qwen-line provider rules

- Read and normalize `.qwen/.agents-mode.yaml` to the current canonical format before trusting its flags.
- Read and normalize `.qwen/.agents-mode.yaml` to the current canonical format before trusting its flags. If local `.qwen/.agents-mode.yaml` is missing, read local legacy `.qwen/.agents-mode` as compatibility input only; if both local files are missing, fall back through pack-local global `~/.qwen/.agents-mode.yaml`, pack-local global legacy `~/.qwen/.agents-mode`, then the shared cross-pack global `~/.agents-mode.yaml` (alongside `~/.claude.json`), before applying built-in defaults. Each key resolves to the highest layer that defines it; layers compose, they do not replace each other wholesale. Normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope and do not recreate any legacy file.
- Honor `.qwen/.agents-mode.yaml`, including `parallelMode`, `externalPriorityProfile`, `reserveResolver`, `externalPriorityProfiles`, and `externalOpinionCounts`.
- `parallelMode` is the general helper fan-out rule across internal and external lanes; `externalOpinionCounts` governs distinct-provider opinions for one lane and does not cap how many same-provider worker instances may run in parallel for different disjoint lanes or slices.
- `externalProvider: auto` resolves through the active named priority profile, not a Qwen-line default provider.
- `externalPriorityProfile` defaults to `balanced`; the shipped `balanced` profile keeps production `auto` routing on `codex | claude`.
- `externalProvider: codex` resolves to Codex CLI explicitly.
- `externalProvider: claude` resolves to Claude CLI explicitly.
- `externalProvider: gemini` and `externalProvider: qwen` are explicit example-only overrides; both are `WEAK MODEL / NOT RECOMMENDED`.
- Honor `externalModelMode` first when an external provider is selected: `runtime-default` keeps the resolved provider on its runtime default model/profile, while `pinned-top-pro` uses the strongest documented provider-native production path for that provider.
- When Codex is the resolved provider, honor `externalCodexProfile`: `default` inherits `externalModelMode`; `gpt-5.6-sol-max` requests model `gpt-5.6-sol` with `model_reasoning_effort = "max"` for higher-complexity/hard lanes; `gpt-5.6-terra` selects the balanced Codex model tier (a distinct model, `model_reasoning_effort = "high"`, not an effort downgrade) and must record unavailable or deviated if that model cannot be verified against the installed runtime; `gpt-5.6-sol-xhigh` (shipped as default in the Codex/Claude packs) pins model `gpt-5.6-sol` with `model_reasoning_effort = "xhigh"` regardless of `externalModelMode`, symmetric to Claude's `opus-xhigh`.
- Do not honor `reserve` for worker-side lanes. It is a supplemental read-only candidate only in `advisory.*` and `review.*` profile orders after primary `claude`/`codex`, and `reserveResolver` must not turn it into a worker transport, primary-Claude retry, or implementation/editing fallback.
- This adapter is a direct external launch contract. Do not spawn it as an internal Qwen agent/helper host for another provider.
- If a repository wants Qwen for a specific example worker lane, express that through a scalar explicit provider override; do not place Qwen inside any `auto` profile.
- Same-provider Qwen routing must be explicit; ordinary `auto` must still avoid self-bounce.
- If the active lane policy requests more than one external worker-side opinion, the lead may launch more than one eligible external worker in parallel and aggregate the returned worker artifacts fail closed.
- Multiple simultaneous instances of this adapter may target the same provider when each instance owns a different admitted artifact or disjoint slice and the provider runtime supports concurrent non-interactive execution.

## Return

Return one worker artifact with:

1. Summary
2. Changed surface
3. Verification evidence or blocked reason
4. Risks / unknowns
5. Gate: PASS | REVISE | BLOCKED:dependency

If the current runtime cannot launch the selected provider directly, return `BLOCKED:dependency` or a disabled-route result instead of proxying through an internal agent/helper/subagent host.
