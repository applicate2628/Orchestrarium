---
description: Review or update the installed Orchestrarium Qwen routing overlay after the official Qwen `/init` step.
---

Read `QWEN.md` and `skills/init-project/SKILL.md`.

Then guide the user through Qwen project bootstrap in this order:

- verify that `QWEN.md` exists
- if `QWEN.md` is missing, stop and tell the user to run `Qwen Code /init` first
- review or update the installed default `.qwen/.agents-mode.yaml` according to `skills/init-project/SKILL.md`
- keep the overlay aligned with the example-provider contract: production auto routing stays on `codex/claude`, while explicit `qwen` and `gemini` routes remain manual `WEAK MODEL / NOT RECOMMENDED` example-only paths
- keep `.qwen/settings.json` untouched because it remains the official Qwen runtime config
