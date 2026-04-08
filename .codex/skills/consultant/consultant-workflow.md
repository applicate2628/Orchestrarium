# Consultant Workflow

This file defines how the `$consultant` role is used in this repository.

## Identity

- `$consultant` is the repository's independent advisory team member.
- It is optional, advisory-only, and lead-invoked.
- It is not part of the mandatory delivery pipeline and it does not own gates.
- The role may be fulfilled by an external provider or by an internal independent subagent; the advisory-only contract stays the same either way.
- Provider-specific adapters may exist next to this file. Use them only when that execution method is actually selected for the current run.

## When to invoke

Use `$consultant` when the lead wants a second opinion for:

- hard planning
- complex workspace-modifying tasks
- cross-cutting tradeoffs
- ambiguity that spans multiple specialist roles
- comparing options before choosing a route

Usually do not invoke `$consultant` for:

- trivial or simple tasks
- routine git or admin work
- ordinary read-only investigation
- work already well covered by a current specialist role

## How to use it

The normal flow is:

1. Discuss the problem first instead of asking only for a plan.
2. Use the discussion to compare options, surface tradeoffs, and choose a direction.
3. Ask the consultant to save the selected plan if the task needs a plan file.
4. If the chosen execution method fails or stalls, record that in the plan file and continue with the fallback path.

## Execution paths

### External-provider path

- Use the currently configured consultant-provider command for your environment.
- Prefer `stdin` or a file for longer or multiline prompts.
- Keep direct command-line prompts short enough to avoid truncation.
- Do not use TTY when a non-interactive invocation is available.
- For hard tasks, prefer the strongest available reasoning mode or profile.

### Internal-subagent fallback

- If the external provider is unavailable, stalls, or returns quota, auth, or limit errors, fall back to an internal independent subagent consultant.
- Give the fallback subagent only the minimal accepted artifact or canonical brief needed for the advisory question.
- Keep the fallback consultant advisory-only: one memo, no routing authority, no gate decision, no implementation ownership.
- If independence matters, do not leak the failed external-provider reasoning into the fallback prompt; pass the task and accepted artifacts only.

## Provider adapters

- Keep this file as the provider-neutral source of truth for when and why `$consultant` is used.
- If a provider-specific adapter exists, read it only when that provider is installed and intentionally selected.
- For Claude-based invocation, use [claude-workflow.md](claude-workflow.md) as an optional adapter, not as the canonical workflow for every environment.

## Stalled-run rules

- Wait about 5 to 15 minutes after starting a run before assuming it is stalled.
- Do not start a new chat while the current run may still be alive.
- If needed, poll or nudge the same session instead of creating a second one.
- If the run returns quota, auth, or limit errors, record that in the plan file and continue locally through the internal-subagent fallback.

## Boundaries

- `$consultant` returns one advisory memo or second-opinion memo.
- `$consultant` does not route work, assign roles, accept artifacts, or block progress.
- The lead keeps routing authority and decides whether to adopt the advice.
