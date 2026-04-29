---
name: external-reviewer
description: Review approved Qwen work through an external provider when the routing decision selects the external adapter for an eligible reviewer or QA role. Use when Qwen Code needs a universal review or QA adapter with fail-fast handling and no role-internal fallback.
---

# External Reviewer

Use the shared Qwen dispatch contract in [../lead/external-dispatch.md](../lead/external-dispatch.md).

## Rules

- Review and QA-side only.
- No silent internal fallback.
- Respect the approved review surface.
- Preserve the replaced internal role as provenance.
- Use file-based prompt delivery for substantive task prompts: write the prompt to a temporary prompt file and feed it through stdin or the provider's supported file-input mechanism; direct prompt argv is only for tiny smoke checks or documented provider limitations.

## Qwen-line provider rules

- Read and normalize `.qwen/.agents-mode.yaml` to the current canonical format before trusting its flags.
- Read and normalize `.qwen/.agents-mode.yaml` to the current canonical format before trusting its flags. If local `.qwen/.agents-mode.yaml` is missing, read local legacy `.qwen/.agents-mode` as compatibility input only; if both local files are missing, fall back to global `~/.qwen/.agents-mode.yaml` and then global legacy `~/.qwen/.agents-mode`. Normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope and do not recreate any legacy file.
- Honor `.qwen/.agents-mode.yaml`, including `parallelMode`, `externalPriorityProfile`, `externalPriorityProfiles`, and `externalOpinionCounts`.
- `parallelMode` is the general helper fan-out rule across internal and external lanes; `externalOpinionCounts` governs distinct-provider opinions for one lane and does not cap how many same-provider review instances may run in parallel for different disjoint lanes or slices.
- `externalProvider: auto` resolves through the active named priority profile, not a Qwen-line default provider.
- `externalPriorityProfile` defaults to `balanced`; the shipped `balanced` profile keeps production `auto` routing on `codex | claude`.
- `externalProvider: codex` resolves to Codex CLI explicitly.
- `externalProvider: claude` resolves to Claude CLI explicitly.
- `externalProvider: gemini` and `externalProvider: qwen` are explicit example-only overrides; both are `WEAK MODEL / NOT RECOMMENDED`.
- Honor `externalModelMode` first when an external provider is selected: `runtime-default` keeps the resolved provider on its runtime default model/profile, while `pinned-top-pro` uses the strongest documented provider-native production path for that provider.
- If a review/QA profile order reaches `claude-secret`, honor `externalClaudeApiMode`: `auto` allows that supplemental candidate after primary `claude`/`codex`, and `force` keeps it available even when plain Claude is unavailable. Treat it as a weaker separate reviewer candidate, not a retry for primary Claude and not permission for the reviewer adapter to edit files or take implementation ownership.
- This adapter is a direct external launch contract. Do not spawn it as an internal Qwen agent/helper host for another provider.
- If a repository wants Qwen for a specific example review lane, express that through a scalar explicit provider override; do not place Qwen inside any `auto` profile.
- Same-provider Qwen routing must be explicit; ordinary `auto` must still avoid self-bounce.
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
