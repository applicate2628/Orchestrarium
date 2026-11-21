---
name: second-opinion
description: "Second opinion: request consultant advice or set its mode."
---

# Second Opinion

Get an independent advisory memo or manage the consultant toggle.

## Steps

0. **Check for toggle command.** If `$ARGUMENTS` is one of the toggle sub-commands, handle it directly:
   - Map `enable` / `internal` / `disable` to `external` / `internal` / `disabled`. Within explicit user-approved configuration scope, update only the local `consultantMode` key in `.agents/.agents-mode.yaml`; preserve unrelated existing local keys. Leave inherited keys inherited. If the canonical file does not exist, create only this one-key override; do not clone a lower layer, insert defaults, rewrite a global overlay, or recreate a legacy file. Read the effective setting back through the [existing dispatch owner](../lead/external-dispatch.md) and report the observed mode.
   - `status` → resolve the effective overlay in memory using the dispatch owner below, then display the consultant mode and applicable routing settings. Do not change configuration files when reporting status. Exit.
   - If `$ARGUMENTS` is not a toggle command, proceed to step 1.

   Resolve in memory through the existing dispatch owner: each key resolves to the highest-priority layer that defines it (local canonical `.agents/.agents-mode.yaml`, local legacy `.agents/.agents-mode`, provider-global canonical and legacy under `~/.codex/`, shared global `~/.agents-mode.yaml`, then built-in defaults). Normalize in memory before using the result. Inspection never rewrites, migrates, or creates files.

   Shipped `auto` stays on the Codex/Claude pair. Kimi is explicit-only via the canonical Windows wrapper for read-only, independently verified, nonauthorizing advice. Grok remains unavailable in 1.x.

1. **Check toggle state.** Read the effective Codex overlay first:
   - If `consultantMode: disabled`: print "Consultant is disabled. Run `/second-opinion enable` first." and exit.
   - If `consultantMode: external` / `consultantMode: internal`: proceed.

2. **Get the question.** Use `$ARGUMENTS` as the question or topic. If empty, ask the user what they want a second opinion on.

3. **Invoke consultant.** Use the consultant role:
   - Pass the question along with relevant context (current file, recent changes, or accepted artifacts).
   - The consultant follows its execution paths based on the current toggle mode.

4. **Present the memo.** Display the consultant's advisory memo:
   - Recommended direction
   - Alternatives considered
   - Major tradeoffs
   - Key risks
   - Confidence level
   - Continuation prompt — a ready-to-send second prompt that begins with a direct imperative to continue and names the next concrete action

5. **Save.** Follow the session persistence rule:
   - If the current task has `work-items/active/<slug>/`, persist only the memo there and return its concise result/provenance for the root ledger.
   - With no active work-item, a meaningful standalone memo MAY use one `.reports/YYYY-MM/report(consultant)-YYYY-MM-DD_HH-MM_topic.md` summary.

## Rules

- Consultant is advisory-only — do not treat the memo as a blocking gate.
- Do not modify any project files (toggle file excluded).
- If the memo identifies a real blocker, recommend the proper specialist role to handle it.
- `.agents/.agents-mode.yaml` is the project-local override surface for consultant mode. Read-only status and routing follow the layered resolution above whether or not this file exists.
