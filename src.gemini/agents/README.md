# Gemini Specialist Agents

This directory contains the Gemini preview specialist-team layer.

## What it is

- `*.md` files at this level are Gemini subagent definitions.
- `team-templates/` contains repo-local team compositions for the shared role principle.

## Important limitation

Gemini subagents cannot call other subagents.

Because of that:

- the main Gemini session is the orchestration owner
- `skills/lead/SKILL.md` is the canonical lead contract
- these specialist agents are the execution team, not a recursive orchestration framework
