# Codex Platform Rules

Platform-specific rules for OpenAI Codex. Merged with shared governance (`AGENTS.shared.md`) into a single `AGENTS.md` at install time.

Treat `AGENTS.md` as the universal minimum contract for Codex work in a repository. Installed skills and custom-agent overrides provide the detailed role overlays: they narrow execution posture, scope, and prompting for a specific role, but they do not replace the base `AGENTS.md` rules.

## Bootstrap — before every fix or implementation commit

> **STOP. Before committing any change that fixes a bug, alters behavior, modifies a contract, or implements a feature, run this 5-step checklist. This Bootstrap is the operational form of the shared `Hypothesis disclosure discipline` rule (above in this merged `AGENTS.md`). It binds the main Codex session and any installed skill that authors commits.**
>
> 1. **Diagnostic data.** Name the concrete observed data points that drive this fix: `file:line` citation, shell command output captured this session, log line, user statement quoted verbatim, reproduction transcript. If you cannot name any — go investigate first; do not commit yet.
>
> 2. **Hypothesis inventory.** List every interpretive leap the fix depends on. Examples:
>    - "Word X in the user's message means Y."
>    - "Mechanism A is what is hiding behind label B in the user's vocabulary."
>    - "Flag `--foo` produces behavior C."
>    - "This fix touches three files because the contract spans them."
>    Each item is a HYPOTHESIS until verified. The chain typically has more than one node — list each one separately rather than collapsing them.
>
> 3. **For each hypothesis, decide one of two paths:**
>    - **Verify now** — run the empirical test via the shell (`command -v`, `which`, smoke run, file read), check the authoritative documentation source, or ask the user directly. Do not commit until verified.
>    - **Label `ASSUMPTION (UNVERIFIED)`** in the commit message body alongside the verification step that would resolve it. Only allowed when the cost of asking/verifying is genuinely higher than the cost of being wrong, AND the assumption is disclosed in the commit message — never silent. An unlabelled unverified claim driving a commit is a violation.
>
> 4. **Scope proportionality.** Is the change scope what the verified hypothesis actually requires? Minimal is the default — if the verified bug is a one-character typo, the fix is one character. Wider scope (refactor, multi-file edit, contract change, abstraction extraction) is allowed when the verified hypothesis itself names the wider scope (for example "wire-shape mismatch between producer and consumer requires updating both sides"); state that explicitly in the commit message. "While I'm here let me also..." additions and opportunistic cleanups without their own verified hypothesis are forbidden.
>
> 5. **Recovery readiness.** If a hypothesis later turns out wrong, what is the rollback path? For local-only commits, prefer `git reset --hard HEAD~N` over `git revert` because the hypothesis-bearing commit then disappears from history rather than being preserved as a partial truth. Do not `git push` hypothesis-bearing commits before user review; user review is the final hypothesis verification step.
>
> **Violation triggers** — if you find yourself writing or thinking any of these as load-bearing reasoning for a fix, that IS the trigger to invoke this Bootstrap:
>
> - `most likely means`, `presumably`, `I believe it refers to`, `this should map to`, `based on training data`, `extrapolating from`, `in general X means Y`
> - `while I'm here let me also`, `since we're touching this anyway`
> - `I'll just commit this and we can fix it if wrong`
>
> These phrases are not banned in open exploration or hypothesis formation. They are banned **only** as the justification for a commit. When one appears in that position, name it, treat the underlying claim as a HYPOTHESIS, and apply steps 1-5.

### Optional structural enforcement

Codex CLI exposes a `PreToolUse` hook surface (stable feature `hooks`, default-on) that can intercept `Bash` tool calls and block them by returning a structured deny decision. The Codex pack ships an opt-in hook script at `~/.codex/skills/lead/scripts/check-hypothesis-disclosure.sh` (and `.ps1`) that machine-checks the HEAD commit message before a `git push`: behavior-changing commit types (`feat`/`fix`/`refactor`) must carry `VERIFIED:` or `ASSUMPTION (UNVERIFIED)` markers in the commit body; whitelisted types (`docs`/`chore`/`style`/`merge`/`ci`/`build`/`perf`/`test`/`revert`) pass through unchecked.

Recommended `~/.codex/hooks.json` snippet (opt-in — the installer does not modify this file):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash $HOME/.codex/skills/lead/scripts/check-hypothesis-disclosure.sh"
          }
        ]
      }
    ]
  }
}
```

Codex's `matcher` field is regex on the tool name only (no `if`-style argument filter like Claude Code has); the script self-filters by parsing `tool_input.command` from the stdin JSON envelope and exits 0 immediately on any command that is not `git push`. Both `~/.codex/hooks.json` and inline `[hooks]` tables in `~/.codex/config.toml` are supported; project-local `<repo>/.codex/hooks.json` is also supported but requires the project to be trusted. The Bootstrap text rule above remains binding regardless of whether the hook is installed.

## Default delegation entry point

If approved delivery work needs delegation and no narrower delegated role is already named, use `$lead` from `$CODEX_HOME/skills/lead` as the default coordinator. If the task is about roadmap ownership, prioritization, milestone shaping, or admission into discovery or delivery, use `$product-manager` instead.

## Template routing

Classify the task, choose the narrowest matching workflow shape, and re-classify if scope widens. Simple chains do not require `$lead`. Native Codex skill execution is sequential, but independent external adapters may still run in parallel when the routing contract and provider runtimes allow it.

**Decision tree:**

1. User explicitly names a role: invoke it directly.
2. Roadmap, prioritization, or milestone shaping: route to `$product-manager`.
3. Investigation, ADR, or alternatives exploration with no implementation: use **research**.
4. PR review, quality gate, or post-implementation validation with no new code: use **review**.
5. Local additive change in one module, no new risk owner, contracts unchanged: use **quick-fix**.
6. Auth, trust boundaries, credentials, or vulnerability work: use **security-sensitive**.
7. Hard performance budgets, SLAs, or latency targets: use **performance-sensitive**.
8. Spatial computation, transforms, meshing, or geometry: use **geometry-review**.
9. Multiple risk domains at once: use **combined-critical**.
10. Otherwise: use **full-delivery**.

| Template | Lead needed? | Chain |
|---|---|---|
| `quick-fix` | No | Main conv picks implementer, then `$qa-engineer` |
| `research` | No | Main conv chains `$analyst` then `$architect`, optionally `$planner` |
| `review` | No | Main conv chains `$analyst` then `$qa-engineer` then reviewer(s) |
| `full-delivery` | Yes | `$lead` coordinates full pipeline |
| `security-sensitive` | Yes | `$lead` coordinates; `$security-engineer` and `$security-reviewer` mandatory |
| `performance-sensitive` | Yes | `$lead` coordinates; `$performance-engineer` and `$performance-reviewer` mandatory |
| `geometry-review` | Yes | `$lead` coordinates; `$computational-scientist` and `$architecture-reviewer` mandatory |
| `combined-critical` | Yes | `$lead` coordinates all risk owners and reviewers |

When the template says "No" for lead, the main conversation runs the chain directly: invoke the listed specialists in order and pass each accepted artifact downstream. Re-classify immediately if scope widens beyond the current template.

For a direct full repository impact review of recent changes, use `$review-changes`. It starts from the current local diff or a specified review target, but checks the wider affected surface, including unchanged dependents and adjacent logic. A bugfix with a known file or function stays on `quick-fix` by default; log adjacent issues in the configured bug registry instead of widening the current plan.

## Recovery rule

- For lead-managed chains (`full-delivery`, `security-sensitive`, `performance-sensitive`, `geometry-review`, `combined-critical`), `$lead` manages recovery through the configured task-memory directory.
- For main-conversation-managed chains with 2+ stages (`research`, `review`), save recovery state after each accepted stage as `status.md` (template name, current stage, next role) plus the accepted artifact.
- For direct single-specialist invocations, no recovery file is needed.

## Role resolution paths

Role definitions live in the installed skills tree: `.agents/skills/<role>/SKILL.md` for repo-local installs, or `$CODEX_HOME/skills/<role>/SKILL.md` / `~/.codex/skills/<role>/SKILL.md` for global installs.

Use the skill or custom-agent overlay that matches the assigned role. Utility skills live in the same installed skills tree and may be invoked directly when their workflow fits. In particular, use `$init-project` to initialize project policies in the root `AGENTS.md` and bootstrap `.agents/.agents-mode.yaml` for a new Codex project, and use `$external-brigade` when a bounded set of independent external helpers should launch together instead of being orchestrated ad hoc.

Use these global anchor roles:

- `$lead`: default delivery coordination, routing, artifact acceptance, and gate decisions for approved work
- `$product-manager`: roadmap ownership, initiative prioritization, and admission into discovery or delivery
- `$consultant`: optional non-blocking independent advisor; usage rules, toggle check, and execution paths are in `$CODEX_HOME/skills/consultant/SKILL.md`

External dispatch roles also exist in the installed skills tree as bidirectional adapters:

- `$external-worker`: external worker-side adapter for eligible non-owner, non-review roles; dispatches through the shared provider universe `auto | codex | claude | gemini | qwen`, where shipped production `auto` profiles use `codex | claude` only and `gemini` / `qwen` stay explicit example-only overrides
- `$external-reviewer`: external review/QA adapter for eligible review-side roles; dispatches through the shared provider universe `auto | codex | claude | gemini | qwen`, where shipped production `auto` profiles use `codex | claude` only and `gemini` / `qwen` stay explicit example-only overrides

These roles are adapters, not aliases for `$consultant`.

For all other work, use the narrowest matching installed specialist. The shared role index names the canonical core team, but installed specialists outside that core team and repo-local specialists may still be the better fit. Repository-specific `AGENTS.md` files should add local priorities, canonical paths, build/test rules, and source-of-truth references instead of restating the full global role catalog.

## Project bootstrap

If the project root `AGENTS.md` lacks `## Project policies`, or if neither `.agents/.agents-mode.yaml` nor the matching global fallback `~/.codex/.agents-mode.yaml` exists, suggest `$init-project` before substantial implementation work so the project policy surface and operator mode file are explicit instead of inferred. If the project-local overlay is missing but the global overlay exists, read the global file honestly until the user wants a project-local override.

## Publication safety scan

For repo-local installs, run `bash .agents/skills/lead/scripts/check-publication-safety.sh` (Git Bash / macOS / Linux) or `powershell -ExecutionPolicy Bypass -File .agents/skills/lead/scripts/check-publication-safety.ps1` (Windows PowerShell). For global installs, run the same commands from `~/.codex/skills/lead/scripts/`.
