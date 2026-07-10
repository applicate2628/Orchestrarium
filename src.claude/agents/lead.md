---
name: lead
description: "Fail-closed stub. Lead is the orchestration role the MAIN CONVERSATION holds — it is never a dispatch target. Do not select this agent. If dispatched anyway, it refuses the task and returns BLOCKED, pointing back to the /lead skill. A template marking requiresLead true means the main conversation runs the fuller lead pipeline itself."
---

# Lead — fail-closed dispatch stub

**Lead is not a subagent.** The Lead role is held BY the main conversation: it classifies approved work, routes it to leaf specialist subagents via the Agent tool, gates their artifacts, and owns `work-items/` recovery and integration — directly, in that conversation. The live Lead contract is the `/lead` skill: `.claude/skills/lead/SKILL.md` (bootstrap, operating pipeline, delegation and gate rules, epics/dependencies/decisions/lessons registries, `/agents-external-brigade` brigade routing).

## If you are reading this as a dispatched subagent

You were dispatched through a stale route (`subagent_type: lead`). Do NOT orchestrate, do NOT implement, do NOT spawn other agents, do NOT write files. Return exactly this and stop:

- Gate: `BLOCKED`
- Reason: lead-is-a-main-conversation-role — `$lead` is never spawned; the dispatching conversation must hold the Lead role itself (activate the `/lead` skill or adopt the Lead contract in-session) and route work to leaf specialist subagents directly.

## Why this file still exists

It is kept at `agents/lead.md` so pack detection and the pack validator keep passing, and so any stale `subagent_type: lead` dispatch fails CLOSED (the refusal above) instead of silently spinning up a throwaway lead. `requiresLead: true` in a team template means "the main conversation runs the full lead pipeline" — heavier orchestration, same owner, never a dispatch.
