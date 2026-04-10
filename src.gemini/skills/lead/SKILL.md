---
name: lead
description: >
  Use when Gemini-line work needs one lightweight orchestration skill to route
  work through the shared governance model without inventing a Gemini-only role
  system.
---

# Lead

Use `$lead` as the minimal orchestration skill in the Gemini pack.

Responsibilities:

- classify the task before execution
- keep shared governance rules in scope
- route specialized work through Gemini-native skills or commands as the Gemini line grows
- keep Gemini-native runtime surfaces official-first: use `/init` for `GEMINI.md`, `.gemini/settings.json` for Gemini runtime config, and reserve `.gemini/.agents-mode` for Orchestrarium's shared routing overlay only
- avoid inventing a custom `agents/` tree for Gemini when `GEMINI.md`, skills, and commands already cover the official runtime model

This skill stays intentionally short in the pack. In the source branch, maintainer-side governance references live in the repo-level `references-gemini/` tree; installed targets keep only the lean Gemini runtime surfaces.
