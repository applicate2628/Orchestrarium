# Codex Platform Rules

Platform-specific rules for OpenAI Codex. Merged with shared governance (`AGENTS.shared.md`) into a single `AGENTS.md` at install time.

Treat `AGENTS.md` as the universal minimum contract for Codex work in a repository. Installed skills and custom-agent overrides provide the detailed role overlays: they narrow execution posture, scope, and prompting for a specific role, but they do not replace the base `AGENTS.md` rules.

## Bootstrap — verified premises plus edit/commit checkpoints

> **STOP. Universal premise rule first; two stricter trigger moments below.**
>
> Every decision, plan, review verdict, root-cause claim, fix, implementation action, or behavior-changing commit must rest on verified premises. The trigger moments below add mandatory edit/commit checkpoints; they do not limit the universal rule. Run the checklist at each trigger moment.
>
> **(a) Pre-fix trigger** — before the first code-mutating tool call (file write, patch, `apply_patch`, or equivalent) in response to a bug report, runtime failure, error trace, regression, "does not work" claim, "не работает" claim, "broken" claim, or any user message naming a defect in behavior, **steps 1-3 must complete before the first edit lands**. The trigger fires regardless of whether the session invoked the bugfix flow or any other routing — the discipline binds the session independent of the routing wrapper. Step 5 (Recovery readiness) does not apply at this moment; step 4 (Scope proportionality) and 4.5 (No-kostyl check) apply when you draft the planned edit.
>
> **(b) Pre-commit trigger** — before committing any change that fixes a bug, alters behavior, modifies a contract, or implements a feature, run **all 5 steps**. Step 5 is pre-commit-specific.
>
> This Bootstrap is the operational form of the shared `Hypothesis disclosure discipline` and `Pre-fix diagnostic gate` rules (above in this merged `AGENTS.md`). It binds the main Codex session and any installed skill that authors code mutations or commits.
>
> 1. **Diagnostic data.** Name the concrete observed data points that drive this decision or change: `file:line` citation, shell command output captured this session, log line, user statement quoted verbatim, reproduction transcript. If you cannot name any — go investigate first; do not commit yet.
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
> **4.5. Fix means correct logic, not workaround (no kostyl check).** Before committing, ask: does this implement the right behavior, or just hide the symptom? A fix names the root cause (a specific function, contract, invariant, or boundary that produced the wrong behavior) and corrects it; a workaround silences a visible failure mode without changing the underlying logic. Catch-and-swallow error handling, defensive checks without root-cause understanding, type assertions that silence the type contract, fallback values that mask missing-data bugs, hardcoding to dodge a configuration-resolution bug, `try/except: pass` around recurring failures, log filtering to hide real errors — all count as *kostyl*, not fix. Kostyl is allowed only as an explicit `WORKAROUND` commit that names the root cause separately, states scope/lifetime, and discloses that the underlying defect is unfixed. See the shared `Hypothesis disclosure discipline` rule clause "Fix means correct logic" for the full definition.
>
> 5. **Recovery readiness.** If a hypothesis later turns out wrong, what is the rollback path? For local-only commits, prefer `git reset --hard HEAD~N` over `git revert` because the hypothesis-bearing commit then disappears from history rather than being preserved as a partial truth. Do not `git push` hypothesis-bearing commits before user review; user review is the final hypothesis verification step. **Clean self-introduced churn before the first push:** the same logic extends beyond hypothesis failures — a broke-it-then-fixed-it sequence you authored (a bug introduced in one local commit, corrected in a later one) should not reach pushed history. While the commits are still local, squash or `git reset` the churn so the published history shows the correct fix directly, not your intermediate self-made error and its correction. Clean it BEFORE the first push; do not `git push --force` already-published history to hide it after the fact.
>
> **Violation triggers** — if you find yourself writing or thinking any of these as load-bearing reasoning for a fix *or* a fix-attempt code edit, that IS the trigger to invoke this Bootstrap:
>
> **Pre-fix triggers** (fire before the first file-write / patch / `apply_patch` tool call):
>
> - "I see the bug, let me edit X" without a captured `file:line` symptom citation or verbatim error output
> - "the fix is to add Y" or "let me just patch Z" without a verified hypothesis about what is broken and where
> - starting a file-write or `apply_patch` tool call in a bug-report context with no diagnostic data captured in this session's conversation (user's wording verbatim, error output verbatim, return code, log line, reproduction step, or `file:line` symptom anchor)
> - "I didn't touch that component's code, so my change can't have broken it" as a regression dismissal — behavior couples indirectly (timing, ordering, lifecycle, render/layout passes, shared state, viewport), so your change is the prime suspect until you revert it and reproduce the REAL symptom (the actual broken interaction, not a convenient proxy state); see `Indirect-regression discipline`
>
> **Pre-commit triggers** (fire before authoring the commit):
>
> - `most likely means`, `presumably`, `I believe it refers to`, `this should map to`, `based on training data`, `extrapolating from`, `in general X means Y`
> - `while I'm here let me also`, `since we're touching this anyway`
> - `I'll just commit this and we can fix it if wrong`
>
> These phrases and patterns are not banned in open exploration or hypothesis formation. They are banned **only** as the justification for a code edit (pre-fix triggers) or a commit (pre-commit triggers). When one appears in that position, name it, treat the underlying claim as a HYPOTHESIS, and apply the relevant steps (1-3 at pre-fix; 1-5 at pre-commit).

### Structural enforcement (auto-installed)

Codex CLI exposes hook events that can intercept tool calls and turn completion. The Codex pack ships four structural hooks: two blocking-enforcement (bugfix-discipline, passive-polling) and two warn-only audits (machine-local-path, no-trash-in-repo). They are backstops; they do not replace the text rules above.

**PreToolUse bugfix-discipline hook.** `check-bugfix-discipline.py` catches the most common pre-fix discipline violation: the model is about to make a code-mutating tool call (`apply_patch`) in response to a user message that contains a bug-report or change-request signal (e.g. `fix`, `change`, `broken`, `не работает`, `исправь`, `пофикси`, `поменяй`, traceback, `Error:`), but it did NOT first invoke `/agents-bugfix` or otherwise capture diagnostic data. The hook reads the PreToolUse envelope's `transcript_path`, parses the recent transcript tail, and:

- If the last user message contains no bug-trigger phrase → exit 0 (allow; not a bug context).
- If the last user message contains the override marker `[skip-bugfix-discipline]` → exit 0 (allow; user explicitly opted out).
- If the current turn shows discipline signals (`/agents-bugfix` invocation, `agents-bugfix` skill load, text containing `diagnostic`/`hypothesis`/`reproducing`/`VERIFIED:`) → exit 0 (allow).
- Otherwise → emit a structured `permissionDecision: "deny"` payload telling the model how to comply.

**Stop passive-polling hook.** `check-passive-polling-stop.py` catches a different failure: the model is about to end its turn by saying it is waiting for an async external source (bot/review/CI/job/notification/reply) without a relevant current-turn state check. The hook reads `last_assistant_message` directly from the Stop envelope, exits immediately when `stop_hook_active=true`, and parses the transcript only after a passive-polling phrase is detected. It allows user handoffs such as `waiting for your response` / `жду твоего подтверждения`, allows the per-stop override marker `[acknowledge-passive-stop]`, and otherwise requires a relevant probe in the current turn: time/status commands (`date`, `Get-Date`, `gh pr view`, `gh run list`, `gh api`, `curl`), process/task output, or reads of output/log/task files. If no relevant probe is present, it emits top-level `{"decision":"block","reason":"..."}` telling the model to check state now, use the override for a real handoff, or invoke a concrete tool like `Bash: gh pr view`.

**Two PreToolUse audit hooks (warn-only).** `check-machine-local-path.py` warns when a machine-local absolute path (a concrete user home or workstation dev root; placeholders like `<you>`, `%USERPROFILE%`, `${CLAUDE_PROJECT_DIR}` are allowed) is written into a non-`.scratch/` file. `check-no-trash-in-repo.py` (the stray-artifact guard — filename and install-marker retained for install continuity; a rename to `check-stray-artifact` is a tracked follow-up) warns when a Bash command confidently runs `git worktree add` — the unrequested-worktree side effect. `git worktree list/remove/prune`, `git add` (not `git worktree add`), `git` inside a quoted string, and non-git commands never warn; the parser is shell-aware (shlex tokenization, command-position tracking across `&&`/`;`/`|`/`(`, env-assignment-prefix and git-global-option skipping) and fails open on any tokenizer error. This replaced a name-based version that warned only on new dirs named `kosyaks`/`mistake-log` — useless, because those are the *user's* personal-process vocabulary, not names the *agent* (the actor a PreToolUse hook guards) ever creates, so it never fired; the real reported problem was the agent creating stray artifacts, chiefly unrequested worktrees, so the guard now keys on the OPERATION, not a name. Deferred: the Claude `Agent` tool's `isolation: "worktree"` form (Codex CLI has no analogous Agent-isolation, so that branch is moot on this side anyway). Dropped: outside-repo writes (a static allow-list false-positive-floods on legitimate installs/temp/global-config/memory writes) and arbitrary in-repo trash (no reliable non-name signal — that stays governance). Both read their own call's `tool_input`, write a UTF-8 stderr warning, and ALWAYS allow — AUDIT mode; promotion to a blocking `deny` is a separate reviewed step once the false-positive rate is measured. Both fail open.

Hook entry points:

- `~/.codex/skills/lead/scripts/check-bugfix-discipline.sh` / `.ps1`
- `~/.codex/skills/lead/scripts/check-passive-polling-stop.sh` / `.ps1`
- `~/.codex/skills/lead/hooks/check-machine-local-path.sh` / `.ps1` (audit; imports `hook_common` from the sibling `scripts/`)
- `~/.codex/skills/lead/hooks/check-no-trash-in-repo.sh` / `.ps1` (audit; imports `hook_common` from the sibling `scripts/`)

Per the source-hygiene rule, the two audit hooks live in the typed `skills/lead/hooks/` dir; the two grandfathered blocking hooks stay in `skills/lead/scripts/`. All four wrappers are thin fail-open wrappers around their sibling Python brain. Shared JSON envelope and transcript helpers live in `~/.codex/skills/lead/scripts/hook_common.py`.

**The installer auto-installs all four hook entries by default on all platforms** into `~/.codex/hooks.json` (`--global`) or `<project>/.codex/hooks.json` (`--target`). The JSON merge is idempotent and preserves all other user keys and hooks. Opt out with `--no-hypothesis-hook` (legacy flag kept for back-compat) or `ORCHESTRARIUM_NO_HYPOTHESIS_HOOK=1` in the environment.

**Manual trust step required (Codex security model).** Unlike Claude Code, Codex marks every newly-installed or modified hook as **untrusted** by design — all four entries are written to `hooks.json` but do **not fire** until the user reviews and trusts them via the interactive `codex` TUI. After install (or any pack upgrade that changes any hook script or hooks.json command), run `codex` once interactively, open the hook browser (per the on-screen prompt — typically the keystroke shown next to "Trust to view hooks; to trust; to toggle"), and trust all four entries. Until this step is done the hooks stay visible-but-inactive and `codex exec` skips them silently.

**Windows hook command shape.** On Windows, entries use `powershell.exe -NoProfile -ExecutionPolicy Bypass -File '<abs-path>\<script>.ps1'` — explicit `powershell.exe` avoids the Windows PATH gotcha where `bash` may resolve to the WSL launcher (`C:\Windows\System32\bash.exe`) instead of Git Bash. WSL bash cannot resolve `C:\Users\...` paths, so a `bash 'C:\...'` form silently failed on default Windows installs that have WSL installed alongside Git Bash. POSIX hosts use `bash <abs-path>/<script>.sh`.

To remove already-installed entries independently:

```bash
python scripts/install-hypothesis-hook.py --target <hooks.json path> --platform codex --host-os posix --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target <hooks.json path> --platform codex --host-os posix --hook-event Stop --script-marker check-passive-polling-stop --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target <hooks.json path> --platform codex --host-os posix --script-marker check-machine-local-path --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target <hooks.json path> --platform codex --host-os posix --script-marker check-no-trash-in-repo --script-path <ignored> --remove
```

The auto-installed entries on Windows have this shape (showing the `check-bugfix-discipline` PreToolUse entry and the `check-passive-polling-stop` Stop entry; the other two auto-installed entries, `check-machine-local-path` and `check-no-trash-in-repo`, share the PreToolUse shape with their own markers and `-File` paths, and `check-no-trash-in-repo` adds `Bash` to its matcher so it sees the `git worktree add` command):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|NotebookEdit|apply_patch",
        "hooks": [
          {
            "type": "command",
            "command": "powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\\Users\\<you>\\.codex\\skills\\lead\\scripts\\check-bugfix-discipline.ps1'"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\\Users\\<you>\\.codex\\skills\\lead\\scripts\\check-passive-polling-stop.ps1'"
          }
        ]
      }
    ]
  }
}
```

Codex's `matcher` field is regex on tool name only (no `if`-style argument filter like Claude Code has); the bugfix-discipline PreToolUse script self-filters on transcript-derived bug-context, while the two audit PreToolUse hooks (machine-local-path, no-trash-in-repo) self-filter on their own `tool_input`. Stop ignores matcher, so the installer omits it for the Stop entry. Both `~/.codex/hooks.json` and inline `[hooks]` tables in `~/.codex/config.toml` are supported; project-local `<repo>/.codex/hooks.json` is also supported but requires the project to be trusted.

**Bypass is by design.** `[skip-bugfix-discipline]` bypasses the PreToolUse guard for the next turn. `[acknowledge-passive-stop]` bypasses one Stop guard decision when the assistant is intentionally handing off to the user. False discipline markers remain review territory; the Bootstrap text rule remains binding regardless of whether hooks are installed or trusted.

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

If the project root `AGENTS.md` lacks `## Project policies`, or if no `.agents-mode.yaml` exists at any layer for the current project, suggest `$init-project` before substantial implementation work so the project policy surface and operator mode file are explicit instead of inferred.

**Read-order precedence** (highest to lowest, per-key resolution): project-local `.agents/.agents-mode.yaml` > pack-local global `~/.codex/.agents-mode.yaml` > shared cross-pack global `~/.agents-mode.yaml` > built-in defaults. Each key resolves to the highest layer that defines it; layers compose, they do not replace each other wholesale. The shared cross-pack global (`~/.agents-mode.yaml`, alongside `~/.claude.json`) is created during default global install and serves as the single source of truth shared between Claude Code and Codex CLI; pack-local globals stay as Codex-specific overrides where needed.

## Publication safety scan

For repo-local installs, run `bash .agents/skills/lead/scripts/check-publication-safety.sh` (Git Bash / macOS / Linux) or `powershell -ExecutionPolicy Bypass -File .agents/skills/lead/scripts/check-publication-safety.ps1` (Windows PowerShell). For global installs, run the same commands from `~/.codex/skills/lead/scripts/`.
