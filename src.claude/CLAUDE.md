@AGENTS.md

# Claude Code Pack

Platform-specific rules for Claude Code. Shared governance (hygiene, publication safety, role index, core delegation) is imported from `AGENTS.md` above via `@import`.

## Bootstrap — before every fix or implementation (two trigger moments)

> **STOP. Two trigger moments fire this Bootstrap, and you must run the checklist at each.**
>
> **(a) Pre-fix trigger** — before the first code-mutating tool call (`Edit`, `Write`, `NotebookEdit`, or equivalent) in response to a bug report, runtime failure, error trace, regression, "does not work" claim, "не работает" claim, "broken" claim, or any user message naming a defect in behavior, **steps 1-3 must complete before the first edit lands**. The trigger fires regardless of whether the session invoked `/agents-bugfix` or any other flow — the discipline binds the session independent of the routing wrapper. Step 5 (Recovery readiness) does not apply at this moment; step 4 (Scope proportionality) and 4.5 (No-kostyl check) apply when you draft the planned edit.
>
> **(b) Pre-commit trigger** — before committing any change that fixes a bug, alters behavior, modifies a contract, or implements a feature, run **all 5 steps**. Step 5 is pre-commit-specific.
>
> This Bootstrap is the operational form of the shared `Hypothesis disclosure discipline` and `Pre-fix diagnostic gate` rules in `AGENTS.md`. It binds the main conversation and any role that authors code mutations or commits.
>
> 1. **Diagnostic data.** Name the concrete observed data points that drive this fix: `file:line` citation, command output captured this session, log line, user statement quoted verbatim, reproduction transcript. If you cannot name any — go investigate first; do not commit yet.
>
> 2. **Hypothesis inventory.** List every interpretive leap the fix depends on. Examples:
>    - "Word X in the user's message means Y."
>    - "Mechanism A is what is hiding behind label B in the user's vocabulary."
>    - "Flag `--foo` produces behavior C."
>    - "This fix touches three files because the contract spans them."
>    Each item is a HYPOTHESIS until verified. The chain typically has more than one node — list each one separately rather than collapsing them.
>
> 3. **For each hypothesis, decide one of two paths:**
>    - **Verify now** — run the empirical test (`Bash` / `PowerShell` shell-out, smoke run, file read), check the authoritative doc (`WebFetch` to versioned source), or ask the user directly via `AskUserQuestion`. Do not commit until verified.
>    - **Label `ASSUMPTION (UNVERIFIED)`** in the commit message body alongside the verification step that would resolve it. Only allowed when the cost of asking/verifying is genuinely higher than the cost of being wrong, AND the assumption is disclosed in the commit message — never silent. An unlabelled unverified claim driving a commit is a violation.
>
> 4. **Scope proportionality.** Is the change scope what the verified hypothesis actually requires? Minimal is the default — if the verified bug is a one-character typo, the fix is one character. Wider scope (refactor, multi-file edit, contract change, abstraction extraction) is allowed when the verified hypothesis itself names the wider scope (for example "wire-shape mismatch between producer and consumer requires updating both sides"); state that explicitly in the commit message. "While I'm here let me also..." additions and opportunistic cleanups without their own verified hypothesis are forbidden.
>
> **4.5. Fix means correct logic, not workaround (no kostyl check).** Before committing, ask: does this implement the right behavior, or just hide the symptom? A fix names the root cause (a specific function, contract, invariant, or boundary that produced the wrong behavior) and corrects it; a workaround silences a visible failure mode without changing the underlying logic. Catch-and-swallow error handling, defensive checks without root-cause understanding, type assertions that silence the type contract, fallback values that mask missing-data bugs, hardcoding to dodge a configuration-resolution bug, `try/except: pass` around recurring failures, log filtering to hide real errors — all count as *kostyl*, not fix. Kostyl is allowed only as an explicit `WORKAROUND` commit that names the root cause separately, states scope/lifetime, and discloses that the underlying defect is unfixed. See the shared `Hypothesis disclosure discipline` rule clause "Fix means correct logic" for the full definition.
>
> 5. **Recovery readiness.** If a hypothesis later turns out wrong, what is the rollback path? For local-only commits, prefer `git reset --hard HEAD~N` over `git revert` because the hypothesis-bearing commit then disappears from history rather than being preserved as a partial truth. Do not `git push` hypothesis-bearing commits before user review; user review is the final hypothesis verification step.
>
> **Violation triggers** — if you find yourself writing or thinking any of these as load-bearing reasoning for a fix *or* a fix-attempt code edit, that IS the trigger to invoke this Bootstrap:
>
> **Pre-fix triggers** (fire before the first `Edit` / `Write` / `NotebookEdit` tool call):
>
> - "I see the bug, let me edit X" without a captured `file:line` symptom citation or verbatim error output
> - "the fix is to add Y" or "let me just patch Z" without a verified hypothesis about what is broken and where
> - starting an `Edit` / `Write` tool call in a bug-report context with no diagnostic data captured in this session's conversation (user's wording verbatim, error output verbatim, return code, log line, reproduction step, or `file:line` symptom anchor)
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

The pack ships four structural hooks: two blocking-enforcement (bugfix-discipline, passive-polling) and two warn-only audits (machine-local-path, no-trash-in-repo). They are backstops; they do not replace the text rules above.

**PreToolUse bugfix-discipline hook.** `check-bugfix-discipline.py` catches the most common pre-fix discipline violation: the model is about to make a code-mutating tool call (`Edit`/`Write`/`NotebookEdit`/`apply_patch`) in response to a user message that contains a bug-report or change-request signal (e.g. `fix`, `change`, `broken`, `не работает`, `исправь`, `пофикси`, `поменяй`, traceback, `Error:`), but it did NOT first invoke `/agents-bugfix` or otherwise capture diagnostic data. The hook reads the PreToolUse envelope's `transcript_path`, parses the recent transcript tail, and:

- If the last user message contains no bug-trigger phrase → exit 0 (allow; not a bug context).
- If the last user message contains the override marker `[skip-bugfix-discipline]` → exit 0 (allow; user explicitly opted out).
- If the current turn (everything after the last user message) shows discipline signals (`/agents-bugfix` invocation, `agents-bugfix` skill load, text containing `diagnostic`/`hypothesis`/`reproducing`/`VERIFIED:`) → exit 0 (allow; model is following the flow).
- Otherwise → emit a structured `permissionDecision: "deny"` JSON payload telling the model exactly how to comply (invoke skill, capture diagnostic data, or use override marker).

**Stop passive-polling hook.** `check-passive-polling-stop.py` catches a different failure: the model is about to end its turn by saying it is waiting for an async external source (bot/review/CI/job/notification/reply) without a relevant current-turn state check. The hook reads `last_assistant_message` directly from the Stop envelope, exits immediately when `stop_hook_active=true`, and parses the transcript only after a passive-polling phrase is detected. It allows user handoffs such as `waiting for your response` / `жду твоего подтверждения`, allows the per-stop override marker `[acknowledge-passive-stop]`, and otherwise requires a relevant probe in the current turn: time/status commands (`date`, `Get-Date`, `gh pr view`, `gh run list`, `gh api`, `curl`), process/task output, or reads of output/log/task files. If no relevant probe is present, it emits top-level `{"decision":"block","reason":"..."}` telling the model to check state now, use the override for a real handoff, or invoke a concrete tool like `Bash: gh pr view`.

**Two PreToolUse audit hooks (warn-only).** `check-machine-local-path.py` warns when a machine-local absolute path (a concrete user home or workstation dev root; placeholders like `<you>`, `%USERPROFILE%`, `${CLAUDE_PROJECT_DIR}` are allowed) is written into a non-`.scratch/` file. `check-no-trash-in-repo.py` (the stray-artifact guard — filename and install-marker retained for install continuity; a rename to `check-stray-artifact` is a tracked follow-up) warns when a Bash command confidently runs `git worktree add` — the unrequested-worktree side effect. `git worktree list/remove/prune`, `git add` (not `git worktree add`), `git` inside a quoted string, and non-git commands never warn; the parser is shell-aware (shlex tokenization, command-position tracking across `&&`/`;`/`|`/`(`, env-assignment-prefix and git-global-option skipping) and fails open on any tokenizer error. This replaced a name-based version that warned only on new dirs named `kosyaks`/`mistake-log` — useless, because those are the *user's* personal-process vocabulary, not names the *agent* (the actor a PreToolUse hook guards) ever creates, so it never fired; the real reported problem was the agent creating stray artifacts, chiefly unrequested worktrees, so the guard now keys on the OPERATION, not a name. Deferred: the Claude `Agent` tool's `isolation: "worktree"` form (needs a captured PreToolUse envelope to confirm the field shape). Dropped: outside-repo writes (a static allow-list false-positive-floods on legitimate installs/temp/global-config/memory writes) and arbitrary in-repo trash (no reliable non-name signal — that stays governance). Both read their own call's `tool_input` (not session context), write a UTF-8 stderr warning, and ALWAYS allow — AUDIT mode; promotion to a blocking `deny` is a separate reviewed step once the false-positive rate is measured. Both fail open.

Hook entry points:

- `.claude/agents/scripts/check-bugfix-discipline.sh` / `.ps1`
- `.claude/agents/scripts/check-passive-polling-stop.sh` / `.ps1`
- `.claude/agents/hooks/check-machine-local-path.sh` / `.ps1` (audit; imports `hook_common` from the sibling `scripts/`)
- `.claude/agents/hooks/check-no-trash-in-repo.sh` / `.ps1` (audit; imports `hook_common` from the sibling `scripts/`)

Per the source-hygiene rule, the two audit hooks live in the typed `agents/hooks/` dir; the two grandfathered blocking hooks stay in `agents/scripts/`. All four wrappers are thin fail-open wrappers around their sibling Python brain. Shared JSON envelope and transcript helpers live in `.claude/agents/scripts/hook_common.py`.

**The installer auto-installs all four hook entries by default.** Both `scripts/install-claude.sh --global` and `scripts/install-claude.sh --target <project>` merge the `PreToolUse` (bugfix-discipline + machine-local-path + no-trash-in-repo, the last with a `Bash`-inclusive matcher so it sees the `git worktree add` command) and `Stop` entries into `settings.json` with an idempotent JSON merge that preserves other keys and hooks. Opt out at install time with `--no-hypothesis-hook` (legacy flag name kept for back-compat) or `ORCHESTRARIUM_NO_HYPOTHESIS_HOOK=1`. Remove entries independently:

```bash
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --hook-event Stop --script-marker check-passive-polling-stop --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-marker check-machine-local-path --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-marker check-no-trash-in-repo --script-path <ignored> --remove
```

The auto-installed entries use this shape (Windows exec form using PowerShell; POSIX uses `bash` instead). The example shows the `check-bugfix-discipline` PreToolUse entry and the `check-passive-polling-stop` Stop entry; the other two auto-installed entries, `check-machine-local-path` and `check-no-trash-in-repo`, share the PreToolUse shape with their own markers and `-File` paths (`check-no-trash-in-repo` also adds `Bash` to its matcher so it sees the `git worktree add` command):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|NotebookEdit|apply_patch",
        "hooks": [
          {
            "type": "command",
            "command": "powershell",
            "args": [
              "-NoProfile",
              "-ExecutionPolicy",
              "Bypass",
              "-File",
              "C:\\Users\\<you>\\.claude\\agents\\scripts\\check-bugfix-discipline.ps1"
            ]
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "powershell",
            "args": [
              "-NoProfile",
              "-ExecutionPolicy",
              "Bypass",
              "-File",
              "C:\\Users\\<you>\\.claude\\agents\\scripts\\check-passive-polling-stop.ps1"
            ]
          }
        ]
      }
    ]
  }
}
```

Path resolution notes:

- The script-path in `args` is an absolute path; relative paths like `.claude/agents/scripts/...` are unreliable because the hook runs with the session's current working directory, not the directory of `settings.json` — see the [Hooks path placeholders](https://code.claude.com/docs/en/hooks.md#path-placeholders) docs.
- For project-local hooks (script lives at `<repo>/.claude/agents/scripts/...`), use `${CLAUDE_PROJECT_DIR}\.claude\agents\scripts\check-bugfix-discipline.ps1` instead.
- POSIX exec form uses `command: "bash", args: ["<abs-path>/check-bugfix-discipline.sh"]` and the equivalent `check-passive-polling-stop.sh` path for Stop.

The matcher `Edit|Write|NotebookEdit|apply_patch` (regex on tool name) covers Claude's code-mutating tools plus Codex's `apply_patch`. Stop ignores matcher; the installer omits it for the Stop entry.

**Bypass is by design.** `[skip-bugfix-discipline]` bypasses the PreToolUse guard for the next turn. `[acknowledge-passive-stop]` bypasses one Stop guard decision when the assistant is intentionally handing off to the user. False discipline markers remain review territory; the Bootstrap text rule remains binding regardless of whether hooks are installed.

## Delegation rule

If `## Project policies` is missing, or if no `.agents-mode.yaml` file exists at any layer for the current project, suggest running `/agents-init-project` before starting implementation work.

**Read-order precedence** (highest to lowest, per-key resolution): project-local `.claude/.agents-mode.yaml` > pack-local global `~/.claude/.agents-mode.yaml` > shared cross-pack global `~/.agents-mode.yaml` > built-in defaults. Each key resolves to the highest layer that defines it; layers compose, they do not replace each other wholesale. The shared cross-pack global (`~/.agents-mode.yaml`, alongside `~/.claude.json`) is created during default global install and serves as the single source of truth shared between Claude Code and Codex CLI; pack-local globals stay as Claude-specific overrides where needed.

When subagent delegation is appropriate, classify the task and pick the matching team template from `.claude/agents/team-templates/`.

External adapter preferences live in `.claude/.agents-mode.yaml`, with `~/.claude/.agents-mode.yaml` as the global fallback when the project-local overlay is absent. The file keeps `consultantMode` for consultant behavior, adds `delegationMode`, `parallelMode`, and `mcpMode` for operator-level routing/tooling preference, keeps `preferExternalWorker` / `preferExternalReviewer` for eligible implement and review-side substitutions, and uses `externalProvider: auto | codex | claude | gemini | qwen` when the operator wants to steer provider-backed execution through the active named production priority profile without changing team template JSON. Shipped production `auto` routing stays on `codex | claude`; Gemini and Qwen are `WEAK MODEL / NOT RECOMMENDED`, and both remain explicit example-only paths rather than production recommendations. `parallelMode` is the general helper fan-out rule across internal and external lanes; external opinion counts and brigade routing stay overlays on top of it. Claude-line canonical config may also include the shared `externalModelMode` and `externalCodexProfile`, while `externalClaudeProfile` remains Codex-line only. On the Claude line, plain Claude CLI stays plain; `reserve` is a symbolic supplemental read-only candidate in `advisory.*` and `review.*` profile orders, after primary `claude`/`codex`, and is independent of the primary provider candidate. `reserveResolver` binds that symbolic candidate to `claude-sonnet`, `claude-wrapper`, `wrapper:<command>`, or `disabled`; `wrapper:<command>` must be a PATH-resolved command or repo-relative wrapper path. Worker, mutating implementation, code-generation, file-editing, installer, publication, or write-producing repository-hygiene routes must not use `reserve`. `externalProvider: auto` is lane-driven, not host-default-driven; Gemini or Qwen use must be a scalar explicit provider override such as `externalProvider: gemini` or `externalProvider: qwen`, never a provider entry inside `externalPriorityProfiles`.
If the effective Claude overlay exists but is stale, comment-free, or from an older pack version, decision-driving reads must normalize that file to the current canonical format before trusting its flags.

**Decision tree:**

1. Does the task need parallel risk owners (security + performance + ...)? → `requiresLead: true` template
2. Does it need implementation? No → `research` or `review`
3. One module, contracts unchanged? → `quick-fix`
4. Otherwise → `full-delivery`

**Templates:**

| Template | When | Lead needed? | Routing |
| --- | --- | --- | --- |
| `quick-fix` | Local additive change, one module, no new risk | No | Main conv → implementer → QA |
| `research` | Investigation, ADR, alternatives — no implementation | No | Main conv → analyst → architect → planner |
| `review` | Architecture/code quality gate, project audit, post-impl validation | No | Main conv → analyst → QA → reviewers |
| `full-delivery` | New feature, substantial change, multi-stage pipeline | Yes | `$lead` coordinates full pipeline |
| `security-sensitive` | Auth, trust boundaries, credentials, vulnerability | Yes | `$lead` coordinates, security-reviewer mandatory |
| `performance-sensitive` | Hard budgets, SLAs, latency targets | Yes | `$lead` coordinates, performance-reviewer mandatory |
| `geometry-review` | Spatial computation, transforms, meshing | Yes | `$lead` coordinates, computational-scientist + arch-reviewer |
| `combined-critical` | Multiple risk domains simultaneously | Yes | `$lead` coordinates all risk owners |

**Claude Code routing rules:**

- Every specialist invocation MUST use the Agent tool with the matching `subagent_type`. Do not simulate roles in the main conversation.
- If the template says `requiresLead: false`, the main conversation manages the chain directly — invoke specialists via Agent tool in order, pass each accepted artifact to the next.
- If the template says `requiresLead: true`, invoke `$lead` via Agent tool who coordinates work-items, risk owners, integration, and gates.
- Independent roles (e.g., security-engineer and performance-engineer) SHOULD be launched in parallel via multiple Agent tool calls in a single message when their scopes do not overlap.
- External adapter substitution is a routing decision, not a template change. When the preferences file favors external dispatch, eligible worker-side slots may route through `$external-worker` and eligible review/QA slots through `$external-reviewer`.
- Independent external adapters may also run in parallel when their scopes are disjoint and the selected provider runtimes support concurrent non-interactive execution. If native internal slot limits would otherwise block more independent eligible lanes, prefer available external adapters instead of silently serializing or dropping them.

**Recovery rule:**

- For `requiresLead: true` chains, `$lead` manages recovery through `work-items/` (roadmap.md, brief.md, status.md).
- For `requiresLead: false` chains with 2+ stages, the main conversation must save recovery state in `work-items/active/<date>-<slug>/` after each stage transition: `status.md` (format defined in `subagent-contracts.md` — includes template, orchestrator role, active/completed agents, next action) and the accepted artifact itself (e.g. `research.md`, `design.md`, `plan.md`). This allows any future session to resume from the last accepted artifact without replaying the chain.
- For single-specialist invocations (user names a role directly), no recovery file is needed.

## Slash command auto-invocation

The pack ships entry-point slash commands in `.claude/commands/` (`/agents-bugfix`, `/agents-implement`, `/agents-design`, `/agents-research`, `/agents-review`, `/agents-refactor`, and others). Each command file owns its own `## When to auto-invoke` block listing the trigger phrases and intent patterns that should activate its flow.

**Auto-invocation contract:** when a user's request matches one of the trigger patterns and the user did not explicitly type the slash command, apply that command's flow as if the user had typed it. Announce the routing decision in your first response (for example: *"I'm routing this through the bugfix flow because the report names a defect without a proposed fix"*) and let the user redirect if the auto-routing was wrong.

**Dispatch index** — short pointer table from user intent to command file. The owning content (full trigger list, edge cases, do-not-auto-invoke exceptions) lives in each command's `## When to auto-invoke` block; this index is just the lookup surface:

| Intent signal | Command flow to apply |
| --- | --- |
| Bug report, error trace, "fix this", "broken", "не работает", regression, registry bug slug | `.claude/commands/agents-bugfix.md` |
| New feature without accepted plan: "build X", "add Y", "design Z", unclear creative work | `.claude/commands/agents-design.md` |
| Accepted plan in `work-items/active/`, user says "proceed", "continue", "next phase" | `.claude/commands/agents-implement.md` |
| Investigation question, "how does X work", ADR exploration, code-surface understanding | `.claude/commands/agents-research.md` |
| Review of completed work, pre-merge gate, post-implementation validation | `.claude/commands/agents-review.md` |
| Refactor request without functional change, deduplication, readability improvement | `.claude/commands/agents-refactor.md` |
| Performance budget breach, SLA, latency, throughput | `.claude/commands/agents-perf.md` |
| Security, auth, credentials, trust boundary, vulnerability | `.claude/commands/agents-security.md` |
| Interactive testing session, "let's test X together" | `.claude/commands/agents-qa-session.md` |
| Test writing request, "add tests for X", "what's the coverage of Y" | `.claude/commands/agents-test.md` |

**Resolution rules:**

- If multiple commands could match (e.g., a bug whose fix requires substantial architecture review): pick the most specialized one (`agents-security` or `agents-perf` over `agents-bugfix`), or ask the user to confirm before proceeding.
- If the user's request does not match any auto-invoke trigger, fall back to the decision tree in `## Delegation rule` above and select a template (`quick-fix`, `research`, `review`, `full-delivery`, etc.) directly.
- Auto-invocation is a routing convenience, not a forcing function. The user can always override with explicit `/agents-<name>` typing or with a direct instruction such as "skip the bugfix flow, just answer".

## Coexistence with the superpowers plugin

When the Claude Code superpowers plugin is installed alongside this pack, the two systems compose; they do not compete. **superpowers skills shape main conv's process discipline** (HOW to think and work) — brainstorming, systematic-debugging, verification-before-completion, writing-plans, test-driven-development, subagent-driven-development. **Orchestrator templates shape delegation routing** (WHO does what and through which gate) — `quick-fix`, `research`, `review`, `full-delivery`, `security-sensitive`, `performance-sensitive`, `geometry-review`, `combined-critical`.

**Standard composition order:**

1. If a superpowers process skill applies to the incoming request, invoke it via the `Skill` tool **before** picking an Orchestrator template — brainstorming for new or unclear creative work, systematic-debugging for runtime bugs whose cause is not obvious, writing-plans for multi-step work that lacks a plan, requesting-code-review before merge.
2. After the process skill yields a clear admitted scope (accepted design, logged root cause, written plan), pick an Orchestrator template per the decision tree above and delegate specialists via the Agent tool.
3. Subagents themselves may invoke common-skills (`$bug-hunting`, `$analyzing-video-bugs`, `$windows-gui-manual-testing`, `$mathtype-book-page`) via the `Skill` tool inside their own context. Subagents typically cannot spawn other subagents — common-skills are the canonical way roles share methodology across the delegation tree.

**Resolving apparent overlaps:**

| superpowers skill | Orchestrator counterpart | How they compose |
| --- | --- | --- |
| `brainstorming` | `research` / `full-delivery` template | Brainstorming clarifies user intent and design direction; `$analyst` / `$architect` / `$planner` then turn the accepted direction into a delivery plan with evidence and gates. |
| `systematic-debugging` | `quick-fix` template + `$bug-hunting` common-skill | systematic-debugging is main conv's diagnostic frame; `$bug-hunting` is the loaded discipline inside the implementer's context; `quick-fix` is the delegation shape after the cause is known. |
| `writing-plans` | `$planner` role | Use `writing-plans` for ad-hoc plans **outside** a tracked delivery flow; for delivery, delegate to `$planner` so the plan becomes a recovery-tracked artifact in `work-items/`. |
| `verification-before-completion` | `$qa-engineer` role | verification-before-completion is main conv's pre-claim discipline; `$qa-engineer` is the dedicated phase-gate specialist. Both apply at different layers — the skill for main conv's own claims, the role for the formal phase gate. |
| `test-driven-development` | `$backend-engineer` / `$frontend-engineer` / `$qt-ui-engineer` execution | TDD shapes how the implementer writes code; the Orchestrator implementer role follows that discipline inside its own execution. |
| `subagent-driven-development` | This pack's templates and routing | The skill provides procedural guidance for multi-subagent runs; this pack provides the role catalog, team templates, and acceptance gates. Use both: the skill says "spawn parallel independent subagents"; the templates say which `subagent_type` is correct for each lane. |
| `requesting-code-review` / `receiving-code-review` | `$architecture-reviewer` / `$security-reviewer` / `$performance-reviewer` | superpowers procedures shape how main conv frames the request and processes the feedback; the Orchestrator reviewers are the specialists who actually produce the review artifact. |

**Quick rubric — when do I invoke which?**

- New feature, exploration, or unclear request → invoke `brainstorming` first, then pick a template.
- Bug whose cause is not obvious from code → invoke `systematic-debugging` (and optionally load `$bug-hunting` via Skill) first, then `quick-fix` or `full-delivery` once the cause is known.
- Code change with clear scope, one module, no new risk owner → pick `quick-fix` directly, no superpowers prelude needed.
- Research question or ADR exploration → pick `research` template directly.
- Review-only or audit → pick `review` template directly.
- Already in mid-flow with admitted scope → continue delegation along the active template; do not re-invoke a process skill unless the task type changes.

**Precedence when superpowers and this pack appear to conflict on the same step:** per superpowers' own `using-superpowers` rule, the priority order is user instructions → superpowers skills → default system prompt. This pack is installed through the user-instruction tier (via `@AGENTS.md` import in this file), so its delegation rules are not subordinate to superpowers; they apply at the **delegation layer** while superpowers applies at the **process layer**. Most apparent conflicts are compositions at different stages; if a genuine same-step contradiction appears, surface it to the user before silently picking one side.

## Role definitions

Role definitions live in `.claude/agents/<role>.md`.

## Publication safety scan

Pre-publication scan: run `/agents-check-safety`, or manually: `bash .claude/agents/scripts/check-publication-safety.sh` (Windows PowerShell: `powershell -ExecutionPolicy Bypass -File .claude/agents/scripts/check-publication-safety.ps1`).

Claude secret-backed wrapper: `bash .claude/agents/scripts/invoke-claude-api.sh [args...]` or `powershell -ExecutionPolicy Bypass -File .claude/agents/scripts/invoke-claude-api.ps1 --% [args...]`. The wrapper prefers repo-local `.claude/SECRET.md` and then falls back to `~/.claude/SECRET.md`, exports the declared `ANTHROPIC_*` environment, and runs plain `claude`. Use the PowerShell wrapper from PowerShell and the bash wrapper from Bash or Git Bash; the PowerShell wrapper accepts both `-PrintSecretPath` and `--print-secret-path`, requires `--%` before forwarded Claude flags, and the bash wrapper honors `CLAUDE_BIN` when the active shell PATH cannot see `claude`.
