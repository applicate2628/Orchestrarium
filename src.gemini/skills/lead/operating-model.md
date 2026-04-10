# Gemini Lead Operating Model

This file is the Gemini-line orchestration reference for the common role principle.

## Structural truth

- Gemini `skills/` are the stable expertise layer.
- Gemini `agents/` are the preview specialist-team layer.
- Gemini subagents cannot call other subagents, so recursive orchestration does not live inside a Gemini subagent.
- The main Gemini session, with `$lead` active, is the orchestration owner for team-template execution.

## Routing model

| Template type | Owner | Specialist execution |
|---|---|---|
| `requiresLead: false` | main Gemini session | main session invokes the matching specialist subagents directly |
| `requiresLead: true` | main Gemini session under `$lead` | main session reads the team template, invokes the needed specialist subagents, and owns integration |

## Team-template source

Use:

- `../../agents/team-templates/quick-fix.json`
- `../../agents/team-templates/research.json`
- `../../agents/team-templates/review.json`
- `../../agents/team-templates/full-delivery.json`
- `../../agents/team-templates/security-sensitive.json`
- `../../agents/team-templates/performance-sensitive.json`
- `../../agents/team-templates/geometry-review.json`
- `../../agents/team-templates/combined-critical.json`

These templates are repo-local orchestration metadata, not a Gemini-native settings surface.

## Parallel execution

Parallel specialist runs are allowed only when:

- scopes are independent
- allowed change surfaces are disjoint
- one integration owner is explicit before QA or review

The main Gemini session launches the parallel specialist subagents. A Gemini subagent does not launch peers.

## Primary-task lock

- Keep exactly one primary in-progress task.
- Side requests may pause it, but do not replace it unless the user explicitly reprioritizes.
- After any side request, resume the primary task and state the next concrete step.
- Do not begin closeout work while a primary review or verification pass is still open.

## Execution continuity

- `PASS` advances immediately.
- `REVISE` stays in the same role for bounded correction.
- Escalate after 3 consecutive `REVISE` cycles on the same role and artifact.
- Do not stop at a partial batch when admitted-scope next work is already known.

## External adapters

Gemini-line external adapters use `.gemini/.agents-mode`.

Canonical provider semantics:

| Key | Meaning |
|---|---|
| `externalProvider: auto` | Gemini-line external dispatch stays explicit until a repository or operator selects a concrete target |
| `externalProvider: codex` | explicit Codex CLI path |
| `externalProvider: claude` | explicit Claude CLI path |
| `externalClaudeSecretMode` | valid only when the resolved provider is Claude |

Gemini does not write `externalProvider: gemini` into the Gemini-line overlay because that would collapse into the current provider.
