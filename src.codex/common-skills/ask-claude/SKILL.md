---
name: ask-claude
description: "Invoke Claude CLI for independent second opinions when a task needs large-context consultation: hard planning, complex multi-step or multi-file changes, broad tradeoffs, or synthesis over too much context for a quick local pass. Use when you need a reusable Claude consultation launcher rather than the repository's consultant role."
---

# Ask Claude

## Overview

Use this skill to launch Claude CLI as an external second opinion. Treat it as an invocation procedure, not a persona or routing role.

## When to use

- Need an independent Claude consultation before hard planning or a complex multi-step or multi-file task.
- Need help comparing routes or tradeoffs that depend on a large amount of gathered context.
- Read-only investigation has turned into a broad edit package and you want a second opinion before committing to the route.
- Need a repeatable way to run Claude without re-learning the command each time.

## When not to use

- Trivial tasks, routine git or admin work, or ordinary read-only investigation.
- Small isolated edits, narrow bug fixes, or straightforward tasks that fit comfortably in the current local context.
- As a gate, blocker, or routing authority.
- As a replacement for `$consultant` or repo-specific consultant policy.

## What to do

- Read [invocation.md](invocation.md) for the canonical command and stalled-run rules.
- Launch Claude with the safe command path there.
- Ask Claude to compare options, surface tradeoffs, and choose the best route.
- For hard complex tasks, prefer the strongest available Claude profile that the installed client supports.
- If the task needs a plan file, ask Claude to save the selected plan according to the local rules.

## Output

- Return the Claude consultation result, plus any selected plan path or stalled-run note.
