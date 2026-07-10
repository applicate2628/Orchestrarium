@AGENTS.md

# Claude Code Pack

Platform-specific rules for Claude Code. Shared governance (hygiene, publication safety, role index, core delegation) is imported from `AGENTS.md` above via `@import`.

## Bootstrap — verified premises plus edit/commit checkpoints

> **STOP. Universal premise rule first; two stricter trigger moments below.**
>
> Every decision, plan, review verdict, root-cause claim, fix, implementation action, or behavior-changing commit must rest on verified premises. The trigger moments below add mandatory edit/commit checkpoints; they do not limit the universal rule. Run the checklist at each trigger moment.
>
> **(a) Pre-fix trigger** — before the first code-mutating tool call (`Edit`, `Write`, `NotebookEdit`, or equivalent) in response to a bug report, runtime failure, error trace, regression, "does not work" claim, "не работает" claim, "broken" claim, or any user message naming a defect in behavior — or before changing behavior that already works, for speed, cleanup, or refactor with no defect reported (there, runtime diagnosis or profiling before the edit is mandatory) — **steps 1-3 must complete before the first edit lands**. The trigger fires regardless of whether the session invoked `/agents-bugfix` or any other flow — the discipline binds the session independent of the routing wrapper. Step 5 (Recovery readiness) does not apply at this moment; step 4 (Scope proportionality) and 4.5 (No-kostyl check) apply when you draft the planned edit.
>
> **(b) Pre-commit trigger** — before committing any change that fixes a bug, alters behavior, modifies a contract, or implements a feature, run **all 5 steps**. Step 5 is pre-commit-specific.
>
> This Bootstrap is the operational form of the shared `Hypothesis disclosure discipline` and `Pre-fix diagnostic gate` rules in `AGENTS.md`. It binds the main conversation and any role that authors code mutations or commits.
>
> 1. **Diagnostic data.** Name the concrete observed data points that drive this decision or change: `file:line` citation, command output captured this session, log line, user statement quoted verbatim, reproduction transcript. If you cannot name any — go investigate first; do not commit yet.
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
> 5. **Recovery readiness.** If a hypothesis later turns out wrong, what is the rollback path? For local-only commits, prefer `git reset --hard HEAD~N` over `git revert` because the hypothesis-bearing commit then disappears from history rather than being preserved as a partial truth. Do not `git push` hypothesis-bearing commits before user review; user review is the final hypothesis verification step. **Clean self-introduced churn before the first push:** the same logic extends beyond hypothesis failures — a broke-it-then-fixed-it sequence you authored (a bug introduced in one local commit, corrected in a later one) should not reach pushed history. While the commits are still local, squash or `git reset` the churn so the published history shows the correct fix directly, not your intermediate self-made error and its correction. Clean it BEFORE the first push; do not `git push --force` already-published history to hide it after the fact.
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

The pack ships six structural hooks: three blocking-enforcement (bugfix-discipline, passive-polling, work-items-archival) and three warn-only audits (machine-local-path, no-trash-in-repo, stale-relation-residue). They are backstops; they do not replace the text rules above. Separately, it ships two non-blocking `SessionStart` context hooks (both registered with no matcher, so they fire on startup/resume/clear/compact — plain stdout becomes added context on both Claude Code and Codex; both are generic and fail-open, emitting nothing and exiting 0 on any error). The first, `mcp-usage-reminder`, re-injects an MCP/tools-usage reminder into context at every session start AND after every compaction. It exists because agents keep forgetting the connected MCP servers, especially once a compaction summarizes working memory; it makes MCP/tool-discovery an explicit checkpoint for codebase, architecture, API/docs, search, browser, debugger, profiler, and repository-understanding tasks. Dispatched subagents inherit the runtime tool surface, but prompts should allow relevant MCP use within the assigned role, scope, and safety limits rather than hiding tool availability. It is generic by design — it names no specific server (a hardcoded machine-local list would be wrong to ship), so the agent discovers the actual connected servers via tool discovery. The second, `agents-mode-reminder`, re-injects the ACTIVE delegation posture: it reads the effective `delegationMode` from a self-contained first-match walk of the documented `.agents-mode.yaml` read-order and, ONLY when that mode is `force` or `auto`, emits an imperative directive telling the main conversation to adopt the `$lead` orchestration role in-session and route non-trivial tasks to the matching specialist subagents, and to maintain `work-items/` recovery state; it is SILENT on `manual` and on the no-file/unresolved state (fail-safe), so the block's presence is itself the signal and never becomes wallpaper. Because the shipped default is now `auto`, a default install surfaces the auto delegation directive automatically, without an `/agents-init-project` run. It exists because `delegationMode` is Orchestrator-pack governance the host never parses on its own — without this hook the main conversation never sees `force` and never applies it, which is exactly how a `force` config silently fails to route work and stops `work-items/` from being maintained.

**PreToolUse bugfix-discipline hook.** `check-bugfix-discipline.py` catches the most common pre-fix discipline violation: the model is about to make a code-mutating tool call (`Edit`/`Write`/`NotebookEdit`/`apply_patch`) in response to a user message that contains a bug-report or change-request signal (e.g. `fix`, `change`, `broken`, `не работает`, `исправь`, `пофикси`, `поменяй`, traceback, `Error:`), but it did NOT first invoke `/agents-bugfix` or otherwise capture diagnostic data. The hook reads the PreToolUse envelope's `transcript_path`, parses the recent transcript tail, and:

- If the envelope carries `agent_id` (a subagent context) → exit 0 (allow; the dispatching main conversation owns the diagnostic discipline at the dispatch decision, and a subagent must never be blocked).
- If the write target path is under `.reports/`, `.scratch/`, `.plans/`, `work-items/`, or `docs/` (matched as a `/`-bounded segment, so `src/mydocs/x.py` is NOT exempt) → exit 0 (allow; a doc/report/scratch/plan/task-memory write is never the CODE fix this guard targets — verified on a real transcript where the guard fired legitimately on a `.reports/` memo write under a bug-fix-review prompt with no prose marker).
- If the last user message contains no bug-trigger phrase → exit 0 (allow; not a bug context).
- If the last user message contains the override marker `[skip-bugfix-discipline]` → exit 0 (allow; user explicitly opted out).
- If the current turn (everything after the last user message) shows discipline signals (`/agents-bugfix` invocation, `agents-bugfix` skill load, text containing `diagnostic`/`hypothesis`/`reproducing`/`VERIFIED:`) → exit 0 (allow; model is following the flow).
- Otherwise → emit a structured `permissionDecision: "deny"` JSON payload telling the model exactly how to comply (invoke skill, capture diagnostic data, or use override marker).

**Stop passive-polling hook.** `check-passive-polling-stop.py` catches a different failure: the model is about to end its turn by saying it is waiting for an async external source (bot/review/CI/job/notification/reply) without a relevant current-turn state check. The hook reads `last_assistant_message` directly from the Stop envelope, exits immediately when `stop_hook_active=true`, and parses the transcript only after a passive-polling phrase is detected. It allows user handoffs such as `waiting for your response` / `жду твоего подтверждения`, allows the per-stop override marker `[acknowledge-passive-stop]`, and otherwise requires a relevant probe in the current turn: time/status commands (`date`, `Get-Date`, `gh pr view`, `gh run list`, `gh api`, `curl`), process/task output, or reads of output/log/task files. If no relevant probe is present, it emits top-level `{"decision":"block","reason":"..."}` telling the model to check state now, use the override for a real handoff, or invoke a concrete tool like `Bash: gh pr view`.

**Stop work-items-archival hook.** `check-work-items-archival-stop.py` catches the systemic create-but-never-close failure: a delivered or closed work-item is left in `work-items/active/` instead of being archived. It fires at turn end and reads the Stop envelope; it exits immediately when the envelope carries `agent_id` (a subagent context — work-item lifecycle is the MAIN conversation's job, so a subagent is never blocked by this guard) or when `stop_hook_active=true`. Otherwise it walks up from the session cwd to the nearest `work-items/active/`, and an active item counts as an orphan when it contains a `closure.md` (closure was written but the folder was never moved), or its `status.md` has a state/status/stage/outcome line whose value begins with a done/closed word (`closed`/`done`/`complete`/`archived`). Anchoring detection to the state-key line — not a free substring anywhere in the file — is deliberate and false-positive-critical: chatty active-item prose like `nothing pending on our side` or `phase 1 shipped + pushed` must NOT be read as a whole-item-done declaration. A merely-active or parked item never triggers. It also scans the sibling `work-items/epics/` and flags an epic that is ready-to-close (all children done but still `status: active`) or stale-closed (`status: closed` with a child not done), reading the epic status from its `---` frontmatter only and requiring the documented `(active|closed)` child marker so a prose bullet or sub-heading under `## Children` cannot false-block. On an orphan it emits top-level `{"decision":"block","reason":"..."}` telling the model to close the item (write `closure.md`, move to `work-items/archive/<YYYY-MM>/<slug>/`, update `index.md`) or use the per-stop override `[acknowledge-open-work-items]`. It is registered ONLY on the `Stop` event (never `SubagentStop`) and fails open on any error. The same `agent_id` subagent-safety skip is retrofitted onto the passive-polling Stop hook, so neither blocking Stop guard can ever interfere with a subagent doing its work.

**Three PreToolUse audit hooks (warn-only).** `check-machine-local-path.py` warns when a machine-local absolute path (a concrete user home or workstation dev root; placeholders like `<you>`, `%USERPROFILE%`, `${CLAUDE_PROJECT_DIR}` are allowed) is written into a non-`.scratch/` file. `check-no-trash-in-repo.py` (the stray-artifact guard — filename and install-marker retained for install continuity; a rename to `check-stray-artifact` is a tracked follow-up) warns when a Bash command confidently runs `git worktree add` — the unrequested-worktree side effect. `git worktree list/remove/prune`, `git add` (not `git worktree add`), `git` inside a quoted string, and non-git commands never warn; the parser is shell-aware (shlex tokenization, command-position tracking across `&&`/`;`/`|`/`(`, env-assignment-prefix and git-global-option skipping) and fails open on any tokenizer error. This replaced a name-based version that warned only on new dirs named `kosyaks`/`mistake-log` — useless, because those are the *user's* personal-process vocabulary, not names the *agent* (the actor a PreToolUse hook guards) ever creates, so it never fired; the real reported problem was the agent creating stray artifacts, chiefly unrequested worktrees, so the guard now keys on the OPERATION, not a name. Deferred: the Claude `Agent` tool's `isolation: "worktree"` form (needs a captured PreToolUse envelope to confirm the field shape). Dropped: outside-repo writes (a static allow-list false-positive-floods on legitimate installs/temp/global-config/memory writes) and arbitrary in-repo trash (no reliable non-name signal — that stays governance). Both read their own call's `tool_input` (not session context), write a UTF-8 stderr warning, and ALWAYS allow — AUDIT mode; promotion to a blocking `deny` is a separate reviewed step once the false-positive rate is measured. Both fail open. `check-stale-relation-residue.py` is the structural backstop for architecture law C6 ("a superseding change leaves only the correct current state; stale-relation residue is erased"): it warns when an `Edit`/`Write` ADDS a stale-relation residue phrase — fixed-vocabulary markers that almost always assert an OBSOLETE relationship a completed rename / merge / deprecation / move / fix should have erased (`deprecated alias`, `former alias` / `former name`, `now-retired ... kept as a historical example`, `(was X)` / `(formerly X)` / `(previously X)` parentheticals, `misregistered as`, `X -> Y alias`, `this is wrong, the correct is Y`) — into a LIVE-tree file. It cannot run C6's full change-specific old-name grep (the hook does not know the old name), so it keys on those operation-independent residue phrases instead. The STALE-vs-LIVE discriminator is review-bound — a real dependency, a deliberate split, or a current `X vs Y` comparison uses some of the same words — so this is WARN-only; it exempts the targets where recording a superseded relation IS legitimate provenance: decision/closure/task-memory registries (`work-items/`), changelogs / release notes (`RELEASE_NOTES`, `CHANGELOG`, `HISTORY`), archival trees (`/archive/`, `/legacy/`, `_archive`), the local scratch area (`.scratch/`), and git internals (`.git/`). It reads its own call's `tool_input`, writes a UTF-8 stderr warning, ALWAYS allows, and fails open — same AUDIT contract as the other two.

Hook entry points:

- `.claude/agents/scripts/check-bugfix-discipline.sh` / `.ps1`
- `.claude/agents/scripts/check-passive-polling-stop.sh` / `.ps1`
- `.claude/agents/scripts/check-work-items-archival-stop.sh` / `.ps1`
- `.claude/agents/hooks/check-machine-local-path.sh` / `.ps1` (audit; imports `hook_common` from the sibling `scripts/`)
- `.claude/agents/hooks/check-no-trash-in-repo.sh` / `.ps1` (audit; imports `hook_common` from the sibling `scripts/`)
- `.claude/agents/hooks/check-stale-relation-residue.sh` / `.ps1` (audit; imports `hook_common` from the sibling `scripts/`)

Per the source-hygiene rule, the three audit hooks live in the typed `agents/hooks/` dir; the three blocking hooks (bugfix-discipline, passive-polling, work-items-archival) stay in `agents/scripts/` next to the shared `hook_common.py` they import directly. All six wrappers are thin fail-open wrappers around their sibling Python brain. Shared JSON envelope and transcript helpers live in `.claude/agents/scripts/hook_common.py`.

**The installer auto-installs all eight hook entries by default.** Both `scripts/install-claude.sh --global` and `scripts/install-claude.sh --target <project>` merge the `PreToolUse` (bugfix-discipline + machine-local-path + no-trash-in-repo, the last with a `Bash`-inclusive matcher so it sees the `git worktree add` command, + stale-relation-residue), the two `Stop` (passive-polling + work-items-archival), and the two informational `SessionStart` entries (`mcp-usage-reminder` + `agents-mode-reminder`, both no-matcher) into `settings.json` with an idempotent JSON merge that preserves other keys and hooks. Opt out at install time with `--no-hypothesis-hook` (legacy flag name kept for back-compat) or `ORCHESTRARIUM_NO_HYPOTHESIS_HOOK=1`. Remove entries independently:

```bash
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --hook-event Stop --script-marker check-passive-polling-stop --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --hook-event Stop --script-marker check-work-items-archival-stop --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-marker check-machine-local-path --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-marker check-no-trash-in-repo --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-marker check-stale-relation-residue --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --hook-event SessionStart --script-marker mcp-usage-reminder --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --hook-event SessionStart --script-marker agents-mode-reminder --script-path <ignored> --remove
```

The auto-installed entries use this shape (Windows exec form using PowerShell; POSIX uses `bash` instead). The example shows the `check-bugfix-discipline` PreToolUse entry and the `check-passive-polling-stop` Stop entry; the other four auto-installed entries — `check-work-items-archival-stop` (a second `Stop` entry, same Stop shape with its own marker and `-File` path) plus the `check-machine-local-path`, `check-no-trash-in-repo`, and `check-stale-relation-residue` PreToolUse audits — share these shapes with their own markers and `-File` paths (`check-no-trash-in-repo` also adds `Bash` to its matcher so it sees the `git worktree add` command; the other two use the default `Edit|Write|NotebookEdit|apply_patch` matcher):

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

**Bypass is by design.** `[skip-bugfix-discipline]` bypasses the PreToolUse guard for the next turn. `[acknowledge-passive-stop]` bypasses one passive-polling Stop decision when the assistant is intentionally handing off to the user. `[acknowledge-open-work-items]` bypasses one work-items-archival Stop decision when leaving a closed-marked item in `active/` is intentional this turn. False discipline markers remain review territory; the Bootstrap text rule remains binding regardless of whether hooks are installed.

## Delegation rule

If `## Project policies` is missing, or if no `.agents-mode.yaml` file exists at any layer for the current project, suggest running `/agents-init-project` before starting implementation work.

**Read-order precedence** (highest to lowest, per-key resolution): project-local `.claude/.agents-mode.yaml` > local legacy `.claude/.agents-mode` > pack-local global `~/.claude/.agents-mode.yaml` > pack-local global legacy `~/.claude/.agents-mode` > shared cross-pack global `~/.agents-mode.yaml` > built-in defaults. Each key resolves to the highest layer that defines it; layers compose, they do not replace each other wholesale. The shared cross-pack global (`~/.agents-mode.yaml`, alongside `~/.claude.json`) is created during default global install and serves as the single source of truth shared between Claude Code and Codex CLI; pack-local globals stay as Claude-specific overrides where needed. `scripts/resolve-agents-mode.py --provider claude --json` is the executable reference in the source repository.

When subagent delegation is appropriate, classify the task and pick the matching team template from `.claude/agents/team-templates/`.

External adapter preferences live in `.claude/.agents-mode.yaml`, with `~/.claude/.agents-mode.yaml` as the global fallback when the project-local overlay is absent. The file keeps `consultantMode` for consultant behavior, adds `delegationMode`, `parallelMode`, and `mcpMode` for operator-level routing/tooling preference, keeps `preferExternalWorker` / `preferExternalReviewer` for eligible implement and review-side substitutions, and uses `externalProvider: auto | codex | claude | gemini | qwen` when the operator wants to steer provider-backed execution through the active named production priority profile without changing team template JSON. Shipped production `auto` routing stays on `codex | claude`; Gemini and Qwen are `WEAK MODEL / NOT RECOMMENDED`, and both remain explicit example-only paths rather than production recommendations. `parallelMode` is the general helper fan-out rule across internal and external lanes; external opinion counts and brigade routing stay overlays on top of it. Claude-line canonical config may also include the shared `externalModelMode` and `externalCodexProfile`, while `externalClaudeProfile` remains Codex-line only. On the Claude line, plain Claude CLI stays plain; `reserve` is a symbolic supplemental read-only candidate in `advisory.*` and `review.*` profile orders, after primary `claude`/`codex`, and is independent of the primary provider candidate. `reserveResolver` binds that symbolic candidate to `claude-sonnet`, `claude-wrapper`, `wrapper:<command>`, or `disabled`; `wrapper:<command>` must be a PATH-resolved command or repo-relative wrapper path. Worker, mutating implementation, code-generation, file-editing, installer, publication, or write-producing repository-hygiene routes must not use `reserve`. `externalProvider: auto` is lane-driven, not host-default-driven; Gemini or Qwen use must be a scalar explicit provider override such as `externalProvider: gemini` or `externalProvider: qwen`, never a provider entry inside `externalPriorityProfiles`.
If the effective Claude overlay exists but is stale, comment-free, or from an older pack version, decision-driving reads must normalize that file to the current canonical format before trusting its flags.

**Decision tree:**

1. Does the task need parallel risk owners (security + performance + ...)? → `requiresLead: true` template
2. Does it need implementation? No → `research` or `review`
3. One module, contracts unchanged? → `quick-fix`
4. Otherwise → `full-delivery`

**Templates:**

| Template | When | Full lead pipeline? | Routing |
| --- | --- | --- | --- |
| `quick-fix` | Local additive change, one module, no new risk | No | Main conv → implementer → QA |
| `research` | Investigation, ADR, alternatives — no implementation | No | Main conv → analyst → architect → planner |
| `review` | Architecture/code quality gate, project audit, post-impl validation | No | Main conv → analyst → QA → reviewers |
| `full-delivery` | New feature, substantial change, multi-stage pipeline | Yes | Main conv (as Lead) coordinates full pipeline |
| `security-sensitive` | Auth, trust boundaries, credentials, vulnerability | Yes | Main conv (as Lead) coordinates, security-reviewer mandatory |
| `performance-sensitive` | Hard budgets, SLAs, latency targets | Yes | Main conv (as Lead) coordinates, performance-reviewer mandatory |
| `geometry-review` | Spatial computation, transforms, meshing | Yes | Main conv (as Lead) coordinates, computational-scientist + arch-reviewer |
| `combined-critical` | Multiple risk domains simultaneously | Yes | Main conv (as Lead) coordinates all risk owners |

**Claude Code routing rules:**

- Every specialist invocation MUST use the Agent tool with the matching `subagent_type`. Do not simulate roles in the main conversation.
- If the template says `requiresLead: false`, the main conversation manages the chain directly — invoke specialists via Agent tool in order, pass each accepted artifact to the next.
- If the template says `requiresLead: true`, the main conversation holds the Lead role and runs the full lead pipeline directly (per the `/lead` skill) — coordinating work-items, risk owners, integration, and gates while dispatching each specialist via the Agent tool. `requiresLead` sets how heavy the orchestration is, not who is lead; Lead is never spawned as a subagent.
- Independent roles (e.g., security-engineer and performance-engineer) SHOULD be launched in parallel via multiple Agent tool calls in a single message when their scopes do not overlap.
- External adapter substitution is a routing decision, not a template change. When the preferences file favors external dispatch, eligible worker-side slots may route through `$external-worker` and eligible review/QA slots through `$external-reviewer`.
- Independent external adapters may also run in parallel when their scopes are disjoint and the selected provider runtimes support concurrent non-interactive execution. If native internal slot limits would otherwise block more independent eligible lanes, prefer available external adapters instead of silently serializing or dropping them.

**Recovery rule:**

- The main conversation owns `work-items/` recovery for every chain — it holds the Lead role. For `requiresLead: true` (heavier-orchestration) chains it runs the full lead pipeline in the `/lead` skill, maintaining `roadmap.md`, `brief.md`, `status.md` (and `plan.md`) throughout.
- For `requiresLead: false` chains with 2+ stages, the main conversation must save recovery state in `work-items/active/<date>-<slug>/` after each stage transition: `status.md` (format defined in `subagent-contracts.md` — includes template, orchestration weight, active/completed agents, next action) and the accepted artifact itself (e.g. `research.md`, `design.md`, `plan.md`). This allows any future session to resume from the last accepted artifact without replaying the chain.
- **Closing a `requiresLead: false` item is the main conversation's job, and the close step is as mandatory as the create step above.** When the item is delivered (its changes committed or pushed) or the user parks, cancels, or reprioritizes it, the main conversation must close it — a delivered item left in `work-items/active/` is an orphan. Close = (1) DECIDE the close and write `closure.md` (outcome, residual risk, archive location) — the main conversation (as Lead) owns this decision and content; it MAY include a `## Retrospective` (what went well / what didn't / lessons, proportionate to the item) and MUST carry a `Closed: <YYYY-MM-DD>` line; (2) apply the close MECHANICS — move the folder to `work-items/archive/<YYYY-MM>/<date>-<slug>/` and move its row in `work-items/index.md` from Active to Archived. The mechanics contract (index sync, archive movement, active/archive reconciliation after every work-item state change) is OWNED by `$knowledge-archivist` (periodic controls: Index sync; Closure and archive hygiene): for a routine single-item close the main conversation applies it directly in the same step; multi-item, drifted, or complex archive/index states route to `$knowledge-archivist` instead of being hand-fixed. This is the main-conversation counterpart to the `$lead` close step in the lead skill (`closure.md` mandatory before `work-items/archive/`). If the session ends before the item is closed, the work-items archival Stop-hook flags the still-open delivered item on the next session. A keep-worthy delivery lesson goes in the `work-items/lessons/` registry (consulted by `$product-manager`/`$lead` on admission; full rules: the lead skill `## Lessons` + `docs/lessons.md`).
- **Epics (grouping multiple work-items).** When several work-items serve one initiative, group them as an **epic** — a flat file `work-items/epics/<date>-<slug>.md` (`status: active | closed` frontmatter, `## Goal` / `## Children` slug list), the same flat shape as `work-items/bugs/`. Each child work-item declares a single bare `Epic: <slug>` line in its `status.md`. Epic progress is DERIVED live from the children (a child counts as done by the same predicate the work-items-archival hook uses, resolving each slug across `active/` + `archive/`); `/agents-status` shows it. Close the epic (`status: closed` + `## Closure`) only when ALL children are closed AND the goal is met — epic closure is backstopped by the archival Stop-hook, which scans `work-items/epics/` and flags a ready-to-close or stale-closed epic (it does not verify the `## Goal` is met). `$product-manager` admits the epic; `$lead` links, rolls up, and closes it. Full rules: the lead skill (`skills/lead/SKILL.md`) `## Epics`.
- **Dependencies & decisions.** A work-item that needs prior work declares `Depends-on: <slug>, <slug>` (work-item slugs) in its `status.md` — a standing, planned inter-work-item dependency edge (distinct from the runtime `BLOCKED:*` gate verdicts); `/agents-status` derives `blocked-by` (open targets) and the ready-set from these lines. Durable cross-cutting architecture decisions go in the `work-items/decisions/` registry (a flat `<date>-<slug>.md`, `status: proposed | accepted | dropped | superseded | reverted`), referenced from a work-item's `design.md` rather than buried in it. Full rules: the lead skill `## Dependencies` + `## Decisions` + `docs/decisions.md` + `docs/dependencies.md`.
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
| Autonomous multi-angle convergence on one fix-design: "review loop", "проводи review loop", "loop review", "автономная петля" (NOT plain "review"/"second opinion") | `.claude/commands/agents-review-loop.md` |
| One independent opinion on a decision/artifact: "second opinion", "второе мнение", "ask the consultant" (NOT plain "review", NOT "review loop") | `.claude/commands/agents-second-opinion.md` |
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
3. Subagents themselves may invoke common-skills (`$bug-hunting`, `$analyzing-video-bugs`, `$windows-gui-manual-testing`, `$mathtype-book-page`, `$explain-simply`, `$vak-dissertation-review`) via the `Skill` tool inside their own context. Subagents typically cannot spawn other subagents — common-skills are the canonical way roles share methodology across the delegation tree.

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

Role definitions live in `.claude/agents/<role>.md`. Exception: the Lead contract lives in `.claude/skills/lead/SKILL.md` — an in-session role activated as `/lead`, never dispatched; `.claude/agents/lead.md` is its fail-closed dispatch stub.

## Publication safety scan

Pre-publication scan: run `/agents-check-safety`, or manually: `bash .claude/agents/scripts/check-publication-safety.sh` (Windows PowerShell: `powershell -ExecutionPolicy Bypass -File .claude/agents/scripts/check-publication-safety.ps1`).

Claude secret-backed wrapper: `bash .claude/agents/scripts/invoke-claude-api.sh [args...]` or `powershell -ExecutionPolicy Bypass -File .claude/agents/scripts/invoke-claude-api.ps1 --% [args...]`. The wrapper prefers repo-local `.claude/SECRET.md` and then falls back to `~/.claude/SECRET.md`, exports the declared `ANTHROPIC_*` environment, and runs plain `claude`. Use the PowerShell wrapper from PowerShell and the bash wrapper from Bash or Git Bash; the PowerShell wrapper accepts both `-PrintSecretPath` and `--print-secret-path`, requires `--%` before forwarded Claude flags, and the bash wrapper honors `CLAUDE_BIN` when the active shell PATH cannot see `claude`.
