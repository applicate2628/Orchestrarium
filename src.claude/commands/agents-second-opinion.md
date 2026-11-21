# Second Opinion

Get an independent second opinion via the consultant agent.

## When to auto-invoke

Apply this flow when the user asks for one independent opinion on a decision or artifact:

- "second opinion", "второе мнение", "ask the consultant", "спроси консультанта"
- "what would another model say", "получи независимое мнение"

Do NOT auto-invoke on plain `review` / `let's review` (owned by `/agents-review`) or on "review loop" / "автономная петля" (owned by `/agents-review-loop`). Toggle sub-commands (`enable`/`internal`/`disable`/`status`) are explicit-only.

## Steps

0. **Check toggle mode.** Before invoking the consultant:
   - If `$ARGUMENTS` is one of the toggle sub-commands, handle it directly:
   - Map `enable` / `internal` / `disable` to `external` / `internal` / `disabled`. Within explicit user-approved configuration scope, update only the local `consultantMode` key in `.claude/.agents-mode.yaml`; preserve unrelated existing local keys. Leave inherited keys inherited. If the canonical file does not exist, create only this one-key override; do not clone a lower layer, insert defaults, rewrite a global overlay, or recreate a legacy file. Read the effective setting back through the [existing dispatch owner](../agents/contracts/external-dispatch.md) and report the observed mode.
   - `status` → resolve the effective overlay in memory using the dispatch owner below, then print the current consultant mode plus any `delegationMode`, `parallelMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, `externalProvider`, `externalPriorityProfile`, `reserveResolver`, `externalOpinionCounts`, `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, `externalModelMode`, and `externalCodexProfile` keys that are present. Do not change configuration files when reporting status. Exit.
   - If the effective `consultantMode` is `disabled` (including the default), print "Second opinion skipped — consultant disabled. Run `/agents-second-opinion enable` to activate." and exit.
   - Otherwise proceed to step 1.

   Resolve in memory through the existing dispatch owner: each key resolves to the highest-priority layer that defines it (local canonical `.claude/.agents-mode.yaml`, local legacy `.claude/.agents-mode`, provider-global canonical and legacy under `~/.claude/`, shared global `~/.agents-mode.yaml`, then built-in defaults). Normalize in memory before using the result. Inspection never rewrites, migrates, or creates files.

1. **Get the question.** Use `$ARGUMENTS` as the question or topic. If empty, ask the user what they want a second opinion on.

2. **Invoke the consultant by mode** (`consultantMode` governs how — see the consultant role's "Invocation by mode"):
   - **`internal` mode** → dispatch the consultant via the Agent tool (`subagent_type: consultant`); it returns a synchronous in-turn advisory.
   - **`external` mode** → the consultant is a runtime-launched external-CLI on a DIFFERENT-model provider than this orchestrator; THIS command's runtime launches the provider CLI/wrapper directly, awaits its terminal return, and consumes the single V2 `ORCHESTRARIUM_PROVIDER_RESULT_V2` envelope's complete untrusted/potentially-sensitive `resultText`, mandatory nonauthorizing tuple, combined outcome, cleanup status, and process exit. For a tracked run it reads the terminal ledger back separately. It does not read wrapper-private capture paths and is NOT a background `subagent_type: consultant` (that strands — see the spawn-and-wait trap). If the only available provider is this orchestrator's own model, return a "no independent (different-model) consultant available" memo.
   - Pass the question along with relevant context (current file, recent changes, or accepted artifacts)
  - The consultant uses the provider selected by the effective Claude overlay (`externalProvider: auto` resolves by the active named production priority profile and stays on the Codex/Claude pair; Kimi is an explicit read-only, independently verified and nonauthorizing route, Grok remains unavailable in 1.x, and `reserve` is a supplemental advisory candidate only when the profile order reaches it and is bound through `reserveResolver`). `consultantMode: external` stays external-only.

3. **Present the memo.** Display the consultant's advisory memo:
   - Recommended direction
   - Alternatives considered
   - Major tradeoffs
   - Key risks
   - Confidence level
   - Continuation prompt — a ready-to-send second prompt that begins with a direct imperative to continue and names the next concrete action

4. **Save.** Persist per artifact persistence protocol (`operating-model.md`):
   - If part of an active work-item → `work-items/active/<slug>/advisory.md`
   - With an active item, return concise result/provenance for the root ledger and do not create a `.reports/` duplicate. With no active item, a meaningful standalone advisory MAY use one `.reports/` summary.

## Rules

- **The consultant is invoked by mode:** `internal` via the Agent tool (`subagent_type: consultant`); `external` as a direct runtime-launched provider CLI on a different-model provider (NOT a background subagent — it would strand). Do not role-play the consultant inline.
- Consultant is advisory-only — do not treat the memo as a blocking gate.
- The toggle file is shared with the external dispatch contract, so never rewrite it into a mode-only shape.
- A status query and an advisory run do not modify configuration. Only the explicit mode-setting subcommands above may write the local toggle file.
- If the memo identifies a real blocker, recommend the proper specialist role to handle it.
