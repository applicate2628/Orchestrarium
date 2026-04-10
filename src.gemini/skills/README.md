# Gemini Skills

This directory is the canonical Gemini-native expertise layer for the provider pack.

Use `skills/<name>/SKILL.md` for workflow and role-like expertise that Gemini should activate on demand.

This pack intentionally stays minimal:

- Gemini skills are official and stable.
- Gemini `/init` and `.gemini/settings.json` remain the official bootstrap and runtime-state surfaces; skills are expertise, not configuration.
- `init-project` is the only current skill that touches configuration, and it only owns the Orchestrarium `.gemini/.agents-mode` overlay after the official `/init` step.
- Gemini extension sub-agents exist, but remain a preview feature in the official docs.
- The baseline pack surface should prefer the stable skills model and keep future preview-agent adoption optional.
- Only a minimal lead skill plus the overlay-bootstrap `init-project` helper are included until the Gemini line needs a fuller role catalog.
