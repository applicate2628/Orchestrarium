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
    - `enable` → write `consultantMode: external` to `.claude/.agents-mode.yaml`, preserving or initializing `delegationMode: auto`, `parallelMode: auto`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalPriorityProfile: balanced`, `reserveResolver: claude-sonnet`, shipped `externalPriorityProfiles`, `externalOpinionCounts` defaulting each documented lane to `1`, `externalCodexWorkdirMode: neutral`, `externalClaudeWorkdirMode: neutral`, `externalModelMode: runtime-default`, and `externalCodexProfile: default`. If the local file does not yet exist, inherit the effective known values from global `~/.claude/.agents-mode.yaml` (or global legacy `~/.claude/.agents-mode`) when available; otherwise initialize those defaults directly. Keep `externalProvider` lane-driven through the active named production priority profile; shipped `auto` stays on the Codex/Claude pair, Kimi is explicit-only policy-admitted read-only exploration, research, planning, or review through fixed `kimi-code/k3` with no tools or subagents, independently verified and nonauthorizing, and Grok remains unavailable in 1.x. Print "Consultant enabled (external-first)." and exit.
    - `internal` → write `consultantMode: internal` to `.claude/.agents-mode.yaml`, preserving `delegationMode`, `parallelMode`, `mcpMode`, the preference flags, `externalProvider`, `externalPriorityProfile`, `reserveResolver`, `externalPriorityProfiles`, `externalOpinionCounts`, `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, `externalModelMode`, and `externalCodexProfile`. If the local file does not yet exist, inherit the effective known values from global `~/.claude/.agents-mode.yaml` (or global legacy `~/.claude/.agents-mode`) when available; otherwise initialize `delegationMode: auto`, `parallelMode: auto`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalPriorityProfile: balanced`, `reserveResolver: claude-sonnet`, shipped `externalPriorityProfiles`, `externalOpinionCounts` defaulting each documented lane to `1`, `externalCodexWorkdirMode: neutral`, `externalClaudeWorkdirMode: neutral`, `externalModelMode: runtime-default`, and `externalCodexProfile: default`. Keep `externalProvider` lane-driven through the active named production priority profile; shipped `auto` stays on the Codex/Claude pair, Kimi is explicit-only policy-admitted read-only exploration, research, planning, or review through fixed `kimi-code/k3` with no tools or subagents, independently verified and nonauthorizing, and Grok remains unavailable in 1.x. Print "Consultant set to internal-only." and exit.
    - `disable` → write `consultantMode: disabled` to `.claude/.agents-mode.yaml`, preserving `delegationMode`, `parallelMode`, `mcpMode`, the preference flags, `externalProvider`, `externalPriorityProfile`, `reserveResolver`, `externalPriorityProfiles`, `externalOpinionCounts`, `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, `externalModelMode`, and `externalCodexProfile`. If the local file does not yet exist, inherit the effective known values from global `~/.claude/.agents-mode.yaml` (or global legacy `~/.claude/.agents-mode`) when available; otherwise initialize `delegationMode: auto`, `parallelMode: auto`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalPriorityProfile: balanced`, `reserveResolver: claude-sonnet`, shipped `externalPriorityProfiles`, `externalOpinionCounts` defaulting each documented lane to `1`, `externalCodexWorkdirMode: neutral`, `externalClaudeWorkdirMode: neutral`, `externalModelMode: runtime-default`, and `externalCodexProfile: default`. Keep `externalProvider` lane-driven through the active named production priority profile; shipped `auto` stays on the Codex/Claude pair, Kimi is explicit-only policy-admitted read-only exploration, research, planning, or review through fixed `kimi-code/k3` with no tools or subagents, independently verified and nonauthorizing, and Grok remains unavailable in 1.x. Print "Consultant disabled." and exit.
    - `status` → read and normalize `.claude/.agents-mode.yaml`. If local `.claude/.agents-mode.yaml` is absent, continue with local legacy `.claude/.agents-mode`, global `~/.claude/.agents-mode.yaml`, then global legacy `~/.claude/.agents-mode`. If neither local nor global file exists: print "disabled (no file — run `/agents-second-opinion enable` to activate)". Otherwise rewrite the effective file into the current canonical format in the same scope, then print the current consultant mode plus any `delegationMode`, `parallelMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, `externalProvider`, `externalPriorityProfile`, `reserveResolver`, `externalOpinionCounts`, `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, `externalModelMode`, and `externalCodexProfile` keys that are present. Exit.
  - If neither local nor global Claude overlay exists: print "Second opinion skipped — consultant disabled. Run `/agents-second-opinion enable` to activate." and exit.
   - If the file contains `consultantMode: disabled`: same notification and exit.
   - Otherwise proceed to step 1.

   When reading, creating, or rewriting `.claude/.agents-mode.yaml`, normalize it to the current canonical format: keep one key per line, restore inline YAML allowed-value comments, refresh the shipped profile/count blocks, preserve effective known values and unknown keys, and drop retired canonical keys. Legacy `.claude/.agents-mode` is compatibility input only and must not be recreated.

1. **Get the question.** Use `$ARGUMENTS` as the question or topic. If empty, ask the user what they want a second opinion on.

2. **Invoke the consultant by mode** (`consultantMode` governs how — see the consultant role's "Invocation by mode"):
   - **`internal` mode** → dispatch the consultant via the Agent tool (`subagent_type: consultant`); it returns a synchronous in-turn advisory.
   - **`external` mode** → the consultant is a runtime-launched external-CLI on a DIFFERENT-model provider than this orchestrator; THIS command's runtime launches the provider CLI/wrapper directly, awaits its terminal return, and consumes the single V2 `ORCHESTRARIUM_PROVIDER_RESULT_V2` envelope's complete untrusted/potentially-sensitive `resultText`, mandatory nonauthorizing tuple, combined outcome, cleanup status, and process exit. For a tracked run it reads the terminal ledger back separately. It does not read wrapper-private capture paths and is NOT a background `subagent_type: consultant` (that strands — see the spawn-and-wait trap). If the only available provider is this orchestrator's own model, return a "no independent (different-model) consultant available" memo.
   - Pass the question along with relevant context (current file, recent changes, or accepted artifacts)
  - Normalize the effective Claude overlay to the current canonical format before trusting its flags.
  - Resolve in this order: local `.claude/.agents-mode.yaml`, local legacy `.claude/.agents-mode`, global `~/.claude/.agents-mode.yaml`, then global legacy `~/.claude/.agents-mode`.
  - The consultant uses the provider selected by the effective Claude overlay (`externalProvider: auto` resolves by the active named production priority profile and stays on the Codex/Claude pair; Kimi is an explicit read-only/nonauthorizing route, Grok remains unavailable in 1.x, and `reserve` is a supplemental advisory candidate only when the profile order reaches it and is bound through `reserveResolver`). `consultantMode: external` stays external-only.

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
- Do not modify any files.
- If the memo identifies a real blocker, recommend the proper specialist role to handle it.
