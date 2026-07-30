@AGENTS.md

# Claude Code Pack

Platform-specific rules for Claude Code. Shared governance (hygiene, publication safety, role index, core delegation) is imported from `AGENTS.md` above via `@import`.

## Bootstrap — verified premises plus edit/commit checkpoints

> **STOP. Universal premise rule first; three stricter trigger moments below.**
>
> Every decision, plan, review verdict, root-cause claim, fix, implementation action, or behavior-changing commit must rest on verified premises. The trigger moments below add mandatory edit/commit checkpoints; they do not limit the universal rule. Run the checklist at each trigger moment.
>
> **(a0) Pre-action orientation trigger** — before the first repository-local runner/build invocation or mutating tool call in an unfamiliar repo/subtree, complete step 0. This trigger is independent of whether the task is a bug fix; bug-fix steps 1-3 still apply at their existing trigger.
>
> **(a) Pre-fix trigger** — before the first code-mutating tool call (`Edit`, `Write`, `NotebookEdit`, or equivalent) in response to a bug report, runtime failure, error trace, regression, "does not work" claim, "не работает" claim, "broken" claim, or any user message naming a defect in behavior — or before changing behavior that already works, for speed, cleanup, or refactor with no defect reported (there, runtime diagnosis or profiling before the edit is mandatory) — **steps 1-3 must complete before the first edit lands**. The trigger fires regardless of whether the session invoked `/agents-bugfix` or any other flow — the discipline binds the session independent of the routing wrapper. Step 5 (Recovery readiness) does not apply at this moment; step 4 (Scope proportionality) and 4.5 (No-kostyl check) apply when you draft the planned edit.
>
> **(b) Pre-commit trigger** — before committing any change that fixes a bug, alters behavior, modifies a contract, or implements a feature, run **all 5 steps**. Step 5 is pre-commit-specific.
>
> This Bootstrap is the operational form of the shared `Hypothesis disclosure discipline` and `Pre-fix diagnostic gate` rules in `AGENTS.md`. It binds the main conversation and any role that authors code mutations or commits.
>
> 0. **Repository orientation.** Before the first repository-local run, build, or mutation in an unfamiliar repo/subtree, state `scope`, `status`, `workflow`, `protected`, and `evidence` from applicable governing docs; `evidence` carries `file:line` citations. Names, counts, recency, and layout do not prove liveness. Missing or conflicting authority means `status=conflict`: do not run/build/edit until the owning source or user resolves it.
>
>    ```text
>    REPOSITORY ORIENTATION: scope=<repo-relative path>; status=<live|mutable|frozen|archived|deprecated|superseded|conflict>; workflow=<repo-relative entry point(s)>; protected=<repo-relative path(s)|none>; evidence=<path:line[,path:line...]>
>    ```
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
> **Pre-action orientation triggers** (fire before the first repository-local run, build, or mutation in an unfamiliar repo/subtree):
>
> - "This has the most files, so it is the live/current suite," or any target choice based on name, count, recency, or layout without governing-doc evidence.
> - "I will fork/copy this runner/scorer" without first proving its status and inventorying the current owner/mechanism.
> - Running, building, or editing an archived/deprecated/superseded/frozen target without explicit user-approved historical scope.
> - Treating missing or conflicting orientation as permission to proceed.
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

The pack auto-installs fourteen hook entries into the user's `settings.json` (via `scripts/install-claude.sh`; opt out with `--no-hypothesis-hook` or `ORCHESTRARIUM_NO_HYPOTHESIS_HOOK=1`): ten structural hooks — four blocking-enforcement (bugfix-discipline, git-push-gate, passive-polling, work-items-archival) and six warn-only audits (machine-local-path, no-trash-in-repo, stale-relation-residue, repository-orientation, mcp-momentum, typed-routing) — plus four reminder/context hooks (`mcp-usage-reminder`, `agents-mode-reminder`, `check-scratch-valuables` on `SessionStart`; `turn-anchor-reminder` on `UserPromptSubmit`). They are backstops; they do not replace the text rules above. The operative invariants that bind behavior regardless of each hook's internals:

- **Subagent and main-conversation ownership.** The blocking hooks skip subagent contexts: a subagent must never be blocked by a main-conversation discipline guard. This exemption never transfers ownership: the dispatching main conversation still owns diagnostic discipline and publication authorization, and it must not delegate a push to dodge review.
- **Stop ownership.** Stop hooks do not replace the main conversation's current-turn status checks or work-item close/archive ownership; their subagent skip preserves that ownership boundary.
- **Delivery-drought sentinel.** SEN-2 is the stateless third `RESOLVE` sentinel for one exact opted-in Primary mutation action. Only a direct semantic exact-target mutation with a same-id explicit-success result earns credit; it blocks at most once per root user turn, skips child/re-entry contexts, and fails open on invalid input. It has no prose bypass.
- **Warn-only audits.** The six audit hooks run in AUDIT mode: they always allow the tool call and only warn; every hook is fail-open, so an internal error permits the operation rather than manufacturing a false block. The no-trash-in-repo audit warns on every confidently parsed `git worktree add` except one add whose command ends with the exact `# orchestrarium:requested-isolation-worktree` marker required by the installed parallel-isolation protocol; missing, near-match, quoted, reused, or batch markers do not suppress the audit.
- **Reminders and tooling.** Reminder hooks re-anchor Model Context Protocol (MCP) discovery/use after compaction, active delegation/recovery, scratch preservation, and every-turn continuity. The shared MCP policy also evaluates native `Grep` and `Bash|PowerShell|shell_command|exec_command` code-navigation calls, including default-recursive `rg`/`ag`/`ack` and explicit-recursive `grep`; only searches whose every explicit scope resolves from the raw envelope `cwd` to `work-items/`, `.reports/`, `.plans/`, or `.scratch/` at the nearest repository root are exempt, and a matching segment elsewhere is not. Root and `agent_id` envelopes are treated identically. The momentum advisory is model-visible, warn-only, fail-open, always exits 0, and cannot prove obedience. Runtime detail: [MCP continuity addendum](../references-claude/mcp-continuity.md). Dispatched prompts should allow relevant MCP use within the assigned role, scope, and safety limits.
- **Publication.** The git-push gate is a backstop, not a guarantee. Only the user's own last message can approve publication, and an instructed push requires the publication-safety scan in the current turn; the binding rule remains the governance text (human review + leak-check before any push).

**Bypass is by design.** `[skip-bugfix-discipline]` bypasses the PreToolUse guard for the next turn. `[approve-publication]` opens the git-push gate for one turn — honored ONLY when it appears in the user's own last message, never from assistant prose or tool output. `[acknowledge-passive-stop]` bypasses one passive-polling Stop decision when the assistant is intentionally handing off to the user. `[acknowledge-open-work-items]` bypasses one work-items-archival Stop decision when leaving a closed-marked item in `active/` is intentional this turn (SEN-0 only; never dual-state/drought). SEN-2 has no prose bypass: satisfy the declared mutation or use the canonical work-item `blocked`, `cancelled`, or closed transition. False discipline markers remain review territory; the Bootstrap text rule remains binding regardless of whether hooks are installed.

Full detail: [Claude Markdown structural-enforcement maintainer reference](../references-claude/claude-md-structural-enforcement.md).

## Delegation rule

If `## Project policies` is missing, or if no `.agents-mode.yaml` file exists at any layer for the current project, suggest running `/agents-init-project` before starting implementation work.

**Read-order precedence** (highest to lowest, per-key resolution): project-local `.claude/.agents-mode.yaml` > local legacy `.claude/.agents-mode` > pack-local global `~/.claude/.agents-mode.yaml` > pack-local global legacy `~/.claude/.agents-mode` > shared cross-pack global `~/.agents-mode.yaml` > built-in defaults. Each key resolves to the highest layer that defines it; layers compose, they do not replace each other wholesale. The shared cross-pack global (`~/.agents-mode.yaml`, alongside `~/.claude.json`) is created during default global install and serves as the single source of truth shared between Claude Code and Codex CLI; pack-local globals stay as Claude-specific overrides where needed. `scripts/resolve-agents-mode.py --provider claude --json` is the executable reference in the source repository.

When subagent delegation is appropriate, classify the task and pick the matching team template from `.claude/agents/team-templates/`.

External adapter preferences live in `.claude/.agents-mode.yaml`, with `~/.claude/.agents-mode.yaml` as the global fallback when the project-local overlay is absent. The file keeps `consultantMode` for consultant behavior, adds `delegationMode`, `parallelMode`, and `mcpMode` for operator-level routing/tooling preference, keeps `preferExternalWorker` / `preferExternalReviewer` for eligible implement and review-side substitutions, and uses `externalProvider: auto | codex | claude | gemini | qwen` when the operator wants to steer provider-backed execution through the active named production priority profile without changing team template JSON. Shipped production `auto` routing stays on `codex | claude`; Gemini and Qwen are `WEAK MODEL / NOT RECOMMENDED`, and both remain explicit example-only paths rather than production recommendations. `parallelMode` is the general helper fan-out rule across internal and external lanes; external opinion counts and brigade routing stay overlays on top of it. Claude-line canonical config may also include the shared `externalModelMode` and `externalCodexProfile`, while `externalClaudeProfile` remains Codex-line only. On the Claude line, plain Claude CLI stays plain; `reserve` is a symbolic supplemental read-only candidate in `advisory.*` and `review.*` profile orders, after primary `claude`/`codex`, and is independent of the primary provider candidate. `reserveResolver` binds that symbolic candidate to `claude-sonnet`, `claude-wrapper`, `wrapper:<command>`, or `disabled`; `wrapper:<command>` must be a PATH-resolved command or repo-relative wrapper path. Worker, mutating implementation, code-generation, file-editing, installer, publication, or write-producing repository-hygiene routes must not use `reserve`. `externalProvider: auto` is lane-driven, not host-default-driven; Gemini or Qwen use must be a scalar explicit provider override such as `externalProvider: gemini` or `externalProvider: qwen`, never a provider entry inside `externalPriorityProfiles`.
If the effective Claude overlay exists but is stale, comment-free, or from an older pack version, decision-driving reads must normalize that file to the current canonical format before trusting its flags.

**External CLI transport (Claude line):** the pack prompt wrappers `invoke-codex-prompt.sh`/`.ps1` (Codex) and `invoke-claude-prompt.sh`/`.ps1` (Claude) are the canonical file-based-prompt path, the inline chain the fallback; `invoke-claude-api.sh`/`.ps1` is a separate secret-backed transport used only when `reserveResolver` resolves to `claude-wrapper`, not interchangeable with the prompt wrappers. Wrapper operating detail: `.claude/agents/consultant.md`.

**Decision tree:**

1. Does the task need parallel risk owners (security + performance + ...)? → `requiresLead: true` template
2. Does it need implementation? No → `research` or `review`
3. Satisfies the shared `quick-fix` predicate? → `quick-fix`
4. Otherwise → `full-delivery`

**Templates:**

| Template | When | Full lead pipeline? | Routing |
| --- | --- | --- | --- |
| `quick-fix` | Shared `quick-fix` predicate | No | Main conv → implementer → QA |
| `research` | Investigation, ADR, alternatives — no implementation | No | Main conv → analyst → architect → planner |
| `review` | Architecture/code quality gate, project audit, post-impl validation | No | Main conv → analyst → QA → reviewers |
| `full-delivery` | New feature, substantial change, multi-stage pipeline | Yes | Main conv (as Lead) coordinates full pipeline |
| `security-sensitive` | Auth, trust boundaries, credentials, vulnerability | Yes | Main conv (as Lead) coordinates, security-reviewer mandatory |
| `performance-sensitive` | Hard budgets, SLAs, latency targets | Yes | Main conv (as Lead) coordinates, performance-reviewer mandatory |
| `geometry-review` | Spatial computation, transforms, meshing | Yes | Main conv (as Lead) coordinates, computational-scientist + arch-reviewer |
| `combined-critical` | Multiple risk domains simultaneously | Yes | Main conv (as Lead) coordinates all risk owners |

`Quick-fix` follows the shared predicate; explicit `/lead` use and `delegationMode: auto|force` change coordination, not template admission or artifact requirements.

**Claude Code routing rules:**

- Every specialist invocation MUST use the Agent tool with the matching `subagent_type`. Do not simulate roles in the main conversation. **Narrow exception — curated inline role-skills:** exactly five roles carry a canonical contract under `.claude/skills/<role>/SKILL.md` and may be adopted inline instead of dispatched: `lead`, `product-manager`, `analyst`, `architect`, `planner`. Inline adoption has exactly two triggers: (a) the operator explicitly invokes the named skill (`/lead`, `/product-manager`, `/analyst`, `/architect`, `/planner` or an equivalent explicit `Skill` tool call), or (b) the model self-invokes `product-manager`, `analyst`, or `architect` for the ONE bounded decision the `quick-fix` route already makes inline — light intake, a trivial factual read, or a seam/blast-radius call — PROVIDED the adoption is announced in-chat before executing and stays scoped to that one decision. `planner` remains explicit-user-only until `quick-fix` admission fails and routing selects a Plan stage; it never upgrades an admitted `quick-fix` into a paper artifact. Unannounced inline adoption remains forbidden, and inline adoption is never a substitute for a template's dispatched stages or for an independent gate. Inline adoption preserves the current conversation's accumulated context and produces that role's one artifact; it does NOT claim isolation or independence, and it satisfies no independent gate. `lead` is a fail-closed stub with no valid dispatch; the other four stay valid fresh-context Agent targets (`subagent_type: product-manager | analyst | architect | planner`) whose wrapper loads the same skill inside an isolated subagent context. `product-manager` carries an additional separation caveat: inline adoption is for quick intake/scope framing only — a formal cross-initiative roadmap decision, or admitting work that will gate other work, still routes to the `product-manager` subagent. Every other role stays Agent-tool-only; this exception is not a general permission to simulate any role inline.
- If the template says `requiresLead: false`, the main conversation manages the chain directly — invoke specialists via Agent tool in order, pass each accepted artifact to the next.
- If the template says `requiresLead: true`, the main conversation holds the Lead role and runs the full lead pipeline directly (per the `/lead` skill) — coordinating work-items, risk owners, integration, and gates while dispatching each specialist via the Agent tool. `requiresLead` sets how heavy the orchestration is, not who is lead; Lead is never spawned as a subagent.
- Independent roles (e.g., security-engineer and performance-engineer) SHOULD be launched in parallel via multiple Agent tool calls in a single message when their scopes do not overlap.
- External adapter substitution is a routing decision, not a template change. When the preferences file favors external dispatch, eligible worker-side slots may route through `$external-worker` and eligible review/QA slots through `$external-reviewer`.
- Independent external adapters may also run in parallel when their scopes are disjoint and the selected provider runtimes support concurrent non-interactive execution. If native internal slot limits would otherwise block more independent eligible lanes, prefer available external adapters instead of silently serializing or dropping them.
- The built-in `general-purpose` subagent is not a substitute for a typed pack role: route specialist work (implementation, review, design, security, performance, toolchain) to the matching typed `subagent_type`. A warn-only `check-typed-routing` audit surfaces a `general-purpose` dispatch that carries a specialist-work signal.

**Recovery rule:**

- Every admitted `quick-fix` creates a minimal `work-items/active/<slug>/status.md` before its first repository mutation. That file contains only ordinary lifecycle fields plus task, current step, last result, and next action; no `roadmap.md`, `brief.md`, Research, Design, Plan, consultant, pre-implementation review, or report is required before that mutation. Re-classification enriches the same work-item instead of creating a late unrelated item, and delivery applies the normal immediate closure/archive rule.
- The main conversation owns `work-items/` recovery after routing selects recovery-tracked or heavier orchestration. For `requiresLead: true` (heavier-orchestration) chains it runs the full lead pipeline in the `/lead` skill, maintaining `roadmap.md`, `brief.md`, `status.md` (and `plan.md`) throughout.
- For recovery-tracked `requiresLead: false` chains with 2+ stages (`research`, `review`), the main conversation must save recovery state in `work-items/active/<date>-<slug>/` after each stage transition: `status.md` (format defined in `subagent-contracts.md` — includes template, orchestration weight, active/completed agents, next action) and the accepted artifact itself (e.g. `research.md`, `design.md`, `plan.md`). This allows any future session to resume from the last accepted artifact without replaying the chain.
- **Closing a recovery-tracked `requiresLead: false` item is the main conversation's job, and the close step is as mandatory as the create step above.** When the item is delivered (its changes committed or pushed) or the user parks, cancels, or reprioritizes it, the main conversation must close it — a delivered item left in `work-items/active/` is an orphan. Close = (1) DECIDE the close and write `closure.md` (outcome, residual risk, archive location) — the main conversation (as Lead) owns this decision and content; it MAY include a `## Retrospective` (what went well / what didn't / lessons, proportionate to the item) and MUST carry a `Closed: <YYYY-MM-DD>` line; (2) apply the close MECHANICS — move the folder to `work-items/archive/<YYYY-MM>/<date>-<slug>/` and move its row in `work-items/index.md` from Active to Archived. The mechanics contract (index sync, archive movement, active/archive reconciliation after every work-item state change) is OWNED by `$knowledge-archivist` (periodic controls: Index sync; Closure and archive hygiene): for a routine single-item close the main conversation applies it directly in the same step; multi-item, drifted, or complex archive/index states route to `$knowledge-archivist` instead of being hand-fixed. This is the main-conversation counterpart to the `$lead` close step in the lead skill (`closure.md` mandatory before `work-items/archive/`). If the session ends before the item is closed, the work-items archival Stop-hook flags the still-open delivered item on the next session. A keep-worthy delivery lesson goes in the `work-items/lessons/` registry (consulted by `$product-manager`/`$lead` on admission; full rules: the lead skill `## Lessons` + `docs/lessons.md`, the latter a maintainer reference not installed at runtime).
- **Epics (grouping multiple work-items).** When several work-items serve one initiative, group them as an **epic**. An active epic is the flat file `work-items/epics/<date>-<slug>.md`; after all children close and the goal is met, `$lead` writes `status: closed`, `## Closure`, and `Closed: <YYYY-MM-DD>`, then `$knowledge-archivist` moves that same file to `work-items/epics/archive/<YYYY-MM>/<slug>.md` and reconciles the local index. Each child work-item declares a single bare `Epic: <slug>` line in its `status.md`; child progress is derived live across work-item `active/` + `archive/`. Reopening moves the epic back to the active root and sets `status: active` in the same operation. Epic lookup has one owner and distinguishes unique active, unique archived, missing, and duplicate state; duplicates fail closed rather than selecting a copy. The archival Stop hook flags ready active epics, closed-in-root residue, stale archived epics, and duplicates; it does not verify the `## Goal` is met. `$product-manager` admits the epic; `$lead` links, rolls up, and decides closure/reopening; `$knowledge-archivist` owns location mechanics. Full rules: the lead skill (`skills/lead/SKILL.md`) `## Epics`.
- **Dependencies & decisions.** A work-item that needs prior work declares `Depends-on: <slug>, <slug>` (work-item slugs) in its `status.md` — a standing, planned inter-work-item dependency edge (distinct from the runtime `BLOCKED:*` gate verdicts); `/agents-status` derives `blocked-by` (open targets) and the ready-set from these lines. Durable cross-cutting architecture decisions go in the `work-items/decisions/` registry (a flat `<date>-<slug>.md`, `status: proposed | accepted | dropped | superseded | reverted`), referenced from a work-item's `design.md` rather than buried in it. Full rules: the lead skill `## Dependencies` + `## Decisions` + `docs/decisions.md` + `docs/dependencies.md` (the two `docs/` files are maintainer references; not installed at runtime).
- For a direct single-specialist invocation (the user names a role directly), no recovery file is needed unless that invocation is itself admitted as `quick-fix`; this exception does not broaden recovery to trivial questions.

## Slash command auto-invocation

The pack ships entry-point slash commands in `.claude/commands/` (`/agents-bugfix`, `/agents-implement`, `/agents-design`, `/agents-research`, `/agents-review`, `/agents-refactor`, and others). Each command file owns its own `## When to auto-invoke` block listing the trigger phrases and intent patterns that should activate its flow.

**Auto-invocation contract:** when a user's request matches one of the trigger patterns and the user did not explicitly type the slash command, apply that command's flow as if the user had typed it. Announce the routing decision in your first response (for example: *"I'm routing this through the bugfix flow because the report names a defect without a proposed fix"*) and let the user redirect if the auto-routing was wrong.

**Dispatch index** — short pointer table from user intent to command file. The owning content (full trigger list, edge cases, do-not-auto-invoke exceptions) lives in each command's `## When to auto-invoke` block; this index is just the lookup surface:

| Intent signal | Command flow to apply |
| --- | --- |
| Bug report, error trace, "fix this", "broken", "не работает", regression, registry bug slug | `.claude/commands/agents-bugfix.md` |
| New feature without accepted plan: "build X", "add Y", "design Z", unclear creative work | `.claude/commands/agents-design.md` |
| N independently-framed design lanes on one pinned problem + mandatory synthesis: "design panel", "дизайн-панель", "two architects" (NOT plain "design") | `.claude/commands/agents-design-panel.md` |
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

1. Evaluate the shared `quick-fix` predicate before invoking a process skill. If it passes, select `quick-fix` directly; no brainstorming, writing-plan, consultant, or review prelude is admitted.
2. Only after `quick-fix` admission fails, invoke an applicable process skill — brainstorming for new or unclear creative work, systematic-debugging when a runtime cause is unknown, writing-plans when the selected route needs a plan, requesting-code-review before merge — then select the heavier template.
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
- Work satisfying the shared `quick-fix` predicate → pick `quick-fix` directly, no superpowers prelude.
- Research question or ADR exploration → pick `research` template directly.
- Review-only or audit → pick `review` template directly.
- Already in mid-flow with admitted scope → continue delegation along the active template; do not re-invoke a process skill unless the task type changes.

**Precedence when superpowers and this pack appear to conflict on the same step:** per superpowers' own `using-superpowers` rule, the priority order is user instructions → superpowers skills → default system prompt. This pack is installed through the user-instruction tier (via `@AGENTS.md` import in this file), so its delegation rules are not subordinate to superpowers; they apply at the **delegation layer** while superpowers applies at the **process layer**. Most apparent conflicts are compositions at different stages; if a genuine same-step contradiction appears, surface it to the user before silently picking one side.

## Role definitions

Role definitions live in `.claude/agents/<role>.md`. Exception — the curated inline role-skills (see the narrow exception above): `lead`, `product-manager`, `analyst`, `architect`, and `planner` keep their canonical contracts under `.claude/skills/<role>/SKILL.md` instead. `lead`'s `.claude/agents/lead.md` is a fail-closed dispatch stub (an in-session role activated as `/lead`, never dispatched). The other four (`product-manager`, `analyst`, `architect`, `planner`) are duals: `.claude/agents/<role>.md` is a thin fresh-context delegate wrapper whose required first step loads the same-named skill. Every other core role's canonical contract stays in `.claude/agents/<role>.md` as before.

## Publication safety scan

Pre-publication scan: run `/agents-check-safety`, or manually: `bash .claude/agents/scripts/check-publication-safety.sh` (Windows PowerShell: `powershell -ExecutionPolicy Bypass -File .claude/agents/scripts/check-publication-safety.ps1`).

Claude secret-backed wrapper: `bash .claude/agents/scripts/invoke-claude-api.sh [args...]` or `powershell -ExecutionPolicy Bypass -File .claude/agents/scripts/invoke-claude-api.ps1 --% [args...]`. The wrapper prefers repo-local `.claude/SECRET.md` and then falls back to `~/.claude/SECRET.md`, exports the declared `ANTHROPIC_*` environment, and runs plain `claude`. Use the PowerShell wrapper from PowerShell and the bash wrapper from Bash or Git Bash; the PowerShell wrapper accepts both `-PrintSecretPath` and `--print-secret-path`, requires `--%` before forwarded Claude flags, and the bash wrapper honors `CLAUDE_BIN` when the active shell PATH cannot see `claude`.
