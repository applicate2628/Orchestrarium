# Qwen Skills

This directory is the stable Qwen expertise layer for the full shared role vocabulary.

## What lives here

- every shared specialist role from the common Orchestrarium model
- Qwen-line `$lead` as the orchestration skill
- Qwen-line `init-project` as the overlay review/update helper for the installed default
- Qwen-line `second-opinion`, `consultant`, and external adapter skills that honor the shared routing overlay, named priority profiles, and per-lane opinion counts
- Qwen-line `external-brigade` as the bounded parallel external-helper orchestration utility

## Why everything lives in `skills/`

`skills/` is the universal cross-tool agent-skill surface, so the common role principle ships as one universal skill per role:

- skills provide the full durable role catalog
- the main Qwen session activates the matching role skill to delegate work to a specialist

Orchestration remains in `skills/lead`, not in a recursive lead subagent. The lead skill also owns the overlay-aware external routing story so the Qwen line stays inspectable as an example pack while shipped production `auto` routing remains on `codex | claude`.
