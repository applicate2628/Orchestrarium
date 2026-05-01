# Gemini Skills

This directory is the stable Gemini expertise layer for the full shared role vocabulary.

## What lives here

- every shared specialist role from the common Orchestrarium model
- Gemini-line `$lead` as the orchestration skill
- Gemini-line `init-project` as the overlay review/update helper for the installed default
- Gemini-line `second-opinion`, `consultant`, and external adapter skills that honor the shared routing overlay, named priority profiles, and per-lane opinion counts
- Gemini-line `external-brigade` as the bounded parallel external-helper orchestration utility

## Why both `skills/` and `agents/` exist

Gemini now uses two official provider surfaces on purpose:

- `skills/` for stable on-demand expertise
- `agents/` for explicit preview specialist delegation

The common role principle depends on both:

- skills provide the full durable role catalog
- agents provide the explicit team members that the main Gemini session can delegate to

Orchestration remains in `skills/lead`, not in a recursive lead subagent. The lead skill also owns the overlay-aware external routing story so the Gemini line stays inspectable as an example pack while shipped production `auto` routing remains on `codex | claude`.
