---
name: consultant
description: Provide an independent advisory memo for the lead without becoming a reviewer, approver, or delivery owner. Use when Qwen Code needs a non-blocking second opinion on tradeoffs, ambiguity, or cross-cutting concerns before choosing a route.
---

# Consultant

## Core stance

- Advisory-only.
- One memo per invocation, then stop.
- No routing authority, no gate authority, no hidden fallback.
- **The consultant MUST run on a DIFFERENT model than the orchestrator — that is the entire point.** A
  same-model consultant is the orchestrator echoing itself and adds no second signal. The external
  consultant must resolve to a provider whose model differs from the orchestrating runtime's own; if only
  the orchestrator's own model is available, return a "no independent (different-model) consultant
  available" memo rather than a same-model echo. The explicit self-provider override in the provider rules
  below is for NON-consultant lanes.

## Toggle state

Read and normalize `.qwen/.agents-mode.yaml` before routing. Comment-free, partial, or older-layout files are legacy input that must be rewritten to the current canonical format before the flags are trusted.
Read and normalize `.qwen/.agents-mode.yaml` before routing. If local `.qwen/.agents-mode.yaml` is missing, read local legacy `.qwen/.agents-mode` as compatibility input only; if both local files are missing, fall back through pack-local global `~/.qwen/.agents-mode.yaml`, pack-local global legacy `~/.qwen/.agents-mode`, then the shared cross-pack global `~/.agents-mode.yaml` (alongside `~/.claude.json`), before applying built-in defaults. Each key resolves to the highest layer that defines it; layers compose, they do not replace each other wholesale. Normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope and do not recreate any legacy file.

Relevant keys:

- `consultantMode`
- `parallelMode`
- `externalProvider`
- `externalPriorityProfile`
- `reserveResolver`
- `externalPriorityProfiles`
- `externalOpinionCounts`
- `externalModelMode`
- `externalCodexProfile`

Qwen-line provider rules:

- `externalProvider: auto` resolves through the active named priority profile, not a Qwen-line default provider
- `externalPriorityProfile` defaults to `balanced`
- `reserveResolver` binds symbolic `reserve` to `claude-sonnet`, `claude-wrapper`, `wrapper:<command>`, or `disabled`
- the shipped `balanced` profile is production-only and keeps `auto` routing on `codex | claude`
- `externalProvider: codex` means Codex CLI explicitly
- `externalProvider: claude` means Claude CLI explicitly
- `externalProvider: gemini` and `externalProvider: qwen` are explicit example-only overrides; both are `WEAK MODEL / NOT RECOMMENDED`
- `externalModelMode` is the shared cross-provider model policy: `runtime-default` leaves the resolved provider on its runtime default model/profile, while `pinned-top-pro` starts on the strongest documented provider-native production path for the resolved provider
- `externalCodexProfile: default` inherits `externalModelMode` when Codex is selected or auto-resolved; `gpt-5.5-fast` selects the fast Codex model tier (model variant only — reasoning_effort still stays `xhigh`, this is not an effort downgrade) and must be verified against the installed Codex runtime; `gpt-5.5-xhigh` (shipped as default in the Codex/Claude packs) pins model `gpt-5.5` with `model_reasoning_effort = "xhigh"` regardless of `externalModelMode`, symmetric to Claude's `opus-max`
- the consultant lane always runs at best effort regardless of the operator-set `externalModelMode` or `externalCodexProfile`: when Codex resolves, model `gpt-5.5` with `model_reasoning_effort = "xhigh"`; when Claude resolves, `--model opus --effort max`. Do not downgrade consultant memos to `gpt-5.3-codex-spark`, to runtime-default, or to `gpt-5.5-fast` between attempts on the same consultant lane
- `reserve` is a symbolic supplemental read-only candidate inside eligible advisory/review profile orders
- `reserve` appears only after primary `claude`/`codex` when an advisory/review order reaches it; it is bound through `reserveResolver`, independent of primary `claude`, and not a retry, fallback, or worker transport
- `parallelMode` is the general helper fan-out rule across internal and external lanes
- if a repository wants Qwen participation in an advisory lane, express that through a scalar explicit provider override rather than any `auto` profile entry
- same-provider Qwen routing must be explicit; ordinary `auto` must still avoid self-bounce
- when the active lane policy asks for more than one external opinion, the lead may invoke this skill more than once and aggregate the returned memos on top of `parallelMode`

## Return

Return one advisory memo with:

1. Summary
2. Recommended direction
3. Alternatives considered
4. Risks / unknowns
5. Advisory status: NON-BLOCKING
6. Continuation prompt: one ready-to-send prompt that begins with a direct imperative to continue and names the next concrete action

## Working rules

- Distinguish confirmed facts, assumptions, and judgment.
- Use file-based prompt delivery for substantive external CLI prompts: write the prompt to a temporary prompt file and feed it through stdin or the provider's supported file-input mechanism; direct prompt argv is only for tiny smoke checks or documented provider limitations.
- If the lead or repo-local lane policy explicitly requests a closeout consultant sweep, follow the configured consultant mode honestly and do not silently downgrade to a different path.
- If the selected consultant path is unavailable for that requested closeout sweep, say so explicitly and keep the batch open for escalation.
- If the active lane policy requests more than one consultant-check, each invocation still returns one memo; the lead aggregates the memos and fails closed when the requested count cannot be satisfied.
