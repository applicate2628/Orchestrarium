---
name: lead
description: "Lead: coordinate approved delivery, artifacts, and gates."
initialPrompt: /lead
---

# Lead — main-session activation and fail-closed stale dispatch

When Claude selects this definition as the main agent, its documented main-session-only `initialPrompt` runs `/lead`. The installed `/lead` skill at `.claude/skills/lead/SKILL.md` then owns the complete Lead contract. This definition intentionally does not duplicate that contract or rely on a `skills` preload.

## If you are reading this as a dispatched subagent

A stale `subagent_type: lead` dispatch is refused. Do NOT orchestrate, do NOT implement, do NOT spawn other agents, do NOT write files. Return exactly this and stop:

- Gate: `BLOCKED`
- Reason: lead-is-a-main-conversation-role — `$lead` is never spawned; the dispatching conversation must hold the Lead role itself (activate the `/lead` skill or adopt the Lead contract in-session) and route work to leaf specialist subagents directly.

## Why this file still exists

It is the host-selected main-agent definition and also preserves the refusal above so any stale `subagent_type: lead` dispatch fails CLOSED instead of silently spinning up a throwaway lead. `requiresLead: true` in a team template means "the main conversation runs the full lead pipeline" — heavier orchestration, same owner, never a dispatch; `/agents-external-brigade` remains the bounded external-helper route.
