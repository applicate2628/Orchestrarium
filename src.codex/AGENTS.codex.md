# Codex Platform Rules

Apply the shared **Assistance and owner-equivalent execution (binding)** contract. Working helpers remain preferred; a defective helper permits declared owner-equivalent execution with the same actual data, ownership, serialization, preimages, rollback, truthful provenance, independent readback and resource guarantees. No fabricated helper receipts or host-denial bypass.

Platform-specific rules for OpenAI Codex. Merged with shared governance (`AGENTS.shared.md`) into a single `AGENTS.md` at install time.

Treat `AGENTS.md` as the universal minimum contract for Codex work in a repository. Installed skills and custom-agent overrides provide the detailed role overlays: they narrow execution posture, scope, and prompting for a specific role, but they do not replace the base `AGENTS.md` rules.

## Bootstrap — verified premises plus edit/commit checkpoints

**STOP. Universal premise rule first; three stricter trigger moments below.** Every decision, plan, verdict, root-cause claim, fix, implementation action or behavior-changing commit requires verified premises under the shared **Verification-and-evidence core**, **Evidence-citation discipline** and **Hypothesis disclosure discipline**. Checkpoints supplement, never limit, that rule. This binds the main Codex session and every mutation/commit author, including direct, nested, non-Lead and skill-only callers, at the applicable triggers; another routing flow does not waive it.

- **(a0) Pre-action orientation trigger**: before the first repository-local runner/build or mutation in an unfamiliar repo/subtree, complete step 0, even outside a bug fix.
- **(a) Pre-fix trigger**: before the first code mutation for a bug report, runtime failure, error trace, regression, "does not work", "не работает", "broken" or any reported behavioral defect, **steps 1-3 must complete before the first edit lands**. The same applies before changing working behavior for speed, cleanup or refactoring: runtime diagnosis or profiling before editing is mandatory. Steps 4 and 4.5 apply while drafting the edit; step 5 does not apply at this moment.
- **(b) Pre-commit trigger**: before a bug-fix, behavior, contract or feature commit, run **all 5 steps** (1-5), including the 4.5 no-kostyl check; step 0 retains its (a0) trigger. Step 5 is pre-commit-specific.

0. **Repository orientation.** Apply shared **Repository orientation; Mechanism inventory before new paths**, including its exact `REPOSITORY ORIENTATION:` record and `file:line` evidence. Missing/conflicting authority is `status=conflict`: no run/build/edit until the owner or user resolves it. Names/counts/recency/layout prove no liveness; archived/deprecated/superseded/frozen targets need explicit user-approved historical scope. Prove status and inventory the existing owner before copying/forking a runner or scorer.
1. **Diagnostic data.** Name concrete observed decision-driving data captured in this session's conversation: `file:line`, this-session command output, log, verbatim user statement or reproduction. If none, investigate before editing/committing. Apply the shared **Pre-fix diagnostic gate** independently of `/agents-bugfix`.
2. **Hypothesis inventory.** List every interpretive leap separately, including user-intent interpretation, mechanism/flag behavior and the reason for the affected scope. Each remains a hypothesis until verified; do not collapse the chain.
3. **Verify or disclose.** Apply shared evidence/availability rules and verify every hypothesis empirically, from authoritative documentation, or directly with the user before committing. Only when asking/verifying genuinely costs more than being wrong may the commit instead disclose `ASSUMPTION (UNVERIFIED)` plus its resolving verification step. No silent unverified premise.
4. **Scope proportionality.** Limit the change to what the verified hypothesis requires. A wider refactor, multi-file/contract change or extraction must be justified by that hypothesis and stated in the commit; unrelated opportunistic cleanup is forbidden.
4.5. **No-kostyl check.** Apply shared **Fix means correct logic, not workaround or hiding (no kostyl)**: name/correct the producing root cause, not symptom suppression. Only an explicit `WORKAROUND` commit may retain a workaround, with separate root cause, scope/lifetime and disclosure that the defect remains unfixed.
5. **Recovery readiness.** State the rollback path. Shared **Hypothesis disclosure discipline** governs destructive history rewrite: explicit user authority, fresh dirty/index census, preservation of every unrelated working-tree byte and staged change, local commits and no other work depends on them; otherwise use a nondestructive reversible route and re-verify from the contradicted node. Under those preconditions prefer `git reset --hard HEAD~N` to `git revert`. Before first push, also clean your own introduced-then-fixed local commit churn under the same conditions, by squash/reset; never `git push --force` already-published history to hide it. Do not push hypothesis-bearing commits before user review; it is the final hypothesis verification step, separate from required publication/leak gates.

**Violation triggers.** Load-bearing fix/edit/commit reasoning that violates the shared orientation, pre-fix, evidence, scope or no-kostyl rules invokes these checkpoints before the dependent action. This includes editing from "I see the bug"/"add Y" without captured diagnostic evidence and a verified causal hypothesis; dismissing indirect regression because the component was untouched; every banned reasoning phrase in shared **Hypothesis disclosure discipline**; and "I'll just commit this and we can fix it if wrong". Shared **Indirect-regression discipline** requires reverting and reproducing the REAL symptom before clearing non-involvement. These phrases are allowed in open exploration/hypothesis formation, never as the load-bearing justification for an edit or commit; name the hypothesis and apply steps 1-3 before the fix and all steps before the commit.

Apply shared **Context handoff economy** at handoff/interruption/compaction/resume: restore missing applicable obligations and current authority before the next dependent decision or action, including interpreting/accepting outstanding results; reuse unchanged actual context. A catalog entry, path, prior-read marker or summary alone is not proof that the required rules are present; a trusted handoff may carry their actual content. Named shared rules mean the governing text in the already selected Source/project/global context, not an uninstalled reference or a guessed global substitute for missing project rules. Restore missing selected content before reliance; no new lookup when it is already present and no permission reset. These checkpoints neither activate Lead nor admit a new workflow, Goal, scope or authority.

### Codex hook requirements and mandatory procedure

Codex hooks are structural backstops; they do not replace text rules, owning guarantees, or authorized human decisions. Blocking backstops remain fail-closed for their named required conditions; warn-only audits and reminder/context hooks remain fail-open and confer no authority. Host refusals and fallback limits still apply. Human publication approval and the staged leak check remain separate. Helpers remain assistance: a failed helper permits only the same owner's declared equivalent with the same guarantees.

Changed Codex hooks may be untrusted or inactive. Rely on them only after the required explicit interactive trust review and supported health receiving. Root remains the workflow owner; hook handling must preserve leaf/subagent identity and event-specific scope.

**Mandatory read:** Any actor, regardless of profession, who installs, upgrades, removes, or changes Codex hooks; handles hook trust or health; or diagnoses behavior based on hook contracts MUST read the Codex hook procedure in the existing Lead operating-model. Resolve Source or installed Lead paths through existing role-path and installation contracts; do not guess machine paths. Unrelated work does not require this procedure.

## Default delegation entry point

## Native dispatch kernel

Before selecting or resolving an ordinary native or skill-only Codex role or a named mechanical route, submitting its native attempt, or receiving or interpreting its outcome, every already-authorized caller (Root/Lead, direct, nested, or non-Lead) MUST read the applicable **Native Astra task-dependent route** or **Native Luna mechanical corridor** procedure in the existing Lead `operating-model.md`. Before changing or diagnosing native role installation, registration, policy/manifest migration or configured controls, read both procedures. Read the applicable named sections only: this is not an eager import, activation of Lead, or permission to delegate. These procedures govern Codex native routes, not Claude Agent dispatch or external adapters.

Resolve the procedure within the already selected Source/project/global layout: Source `src.codex/skills/lead/operating-model.md`; project `<project>/.agents/skills/lead/operating-model.md`; global `$HOME/.agents/skills/lead/operating-model.md`. Use global only when existing layout selection chooses global. Keep resolver and native TOML roots matched to that selection. Do not search current/parent directories or substitute a global owner for a missing selected project owner. Missing or ambiguous layout/content holds only its dependent operation; it grants no installation or fallback authority.

The shared **Task-first dispatch economics (binding)** rule remains always binding: conscious exact task/role/model/effort choice, floors and eligible membership; every Astra attempt at any effort and every model Max needs genuine individual user agreement for that exact task, role, scope, provider route, model, effort and one attempt. Astra Max uses one combined agreement. Low is excluded on every model. Metadata, a selector result, copied approval flag or prior attempt never creates consent. Current user configuration and parent permissions remain binding.

Ordinary roles use `describe_ordinary_native_role_options` then `resolve_ordinary_native_dispatch`; named `mechanical-scout`/`mechanical-worker` use only their existing `RoleDispatchPolicyV1` owner and exact contract, never ordinary-role substitution. Selectors launch nothing. Denied, unavailable, unknown required controls, conflicting pins, host rejection or returned control drift do not authorize a launch or fallback. Record requested/resolved controls separately from actual runtime metadata; missing actual metadata is `unspecified by runtime`. Named mechanical roles have no decision authority, no generic shell/code execution, no external realization or provider/default-role substitution; their native outcome is nonauthorizing and cannot authorize publication.

Before every native subagent spawn, the caller discovers the tools available at that moment and selects the exact task-scoped MCP/tool identifiers, or `none`. It records only that selection under `Allowed tools`; tracked rules never hardcode concrete MCP identifiers, and `runtime default surface` is invalid for native dispatch. The subagent must not use an unlisted tool even when the host inherits it. This is behavioral isolation enforced by caller and subagent instructions until the native runtime provides per-spawn tool filtering; prompts and hooks are not a sandbox and do not establish host-level containment.

Preserve exact accepted profession/task inputs, genuine authority and all independent risk, review, human publication and leak gates. Supply applicable execution restrictions in the trusted child handoff before relying on them, including when `fork_turns="none"`; a path, catalog entry or marker alone is not proof of inherited content.

Reuse unchanged applicable procedure content actually present in the receiver's context under shared **Context handoff economy**. If required content, selected-layout identity or current controls are missing, stale, conflicting or uncertain, hold only the dependent operation and restore its owning inputs. After handoff, interruption, compaction or resume, restore missing applicable obligations and current authority before the next dependent decision or action, including receiving an outstanding result; do not reread unchanged content already actually present. Missing inputs, rejection or drift confer no retry, fallback, alternative-route or permission-reset authority and prove no runtime qualification. A genuinely authorized later action still requires resolved owner inputs and its own applicable gates.

If approved delivery work needs delegation and no narrower delegated role is already named, use `$lead` from `$HOME/.agents/skills/lead` as the default coordinator. If the task is about roadmap ownership, prioritization, milestone shaping, or admission into discovery or delivery, use `$product-manager` instead.

## Template routing

The main session owns every chain, invokes its specialists in order and passes accepted artifacts downstream. Light routes do not require the full `$lead` skill; heavy routes activate it for work-items, risk owners, integration and gates. Never spawn `$lead`. This is pack routing policy, not a runtime limit. Explicit `$lead` use and `delegationMode: auto|force` change coordination, not template admission or artifact requirements.

Classify the task, choose the narrowest matching workflow shape, and re-classify immediately if scope widens. Decision tree:
1. User explicitly names a role: invoke it directly.
2. Roadmap, prioritization or milestone shaping: `$product-manager`.
3. Standalone bounded fact lookup: answer inline, no artifact.
4. Non-trivial factual investigation without a decision: one `$analyst` by default; an explicitly named role or narrower factual domain specialist remains valid.
5. Decision, Architecture Decision Record (ADR), or material alternatives without implementation: light `research`, `$analyst` then `$architect`; add `$planner` only for an explicitly requested execution plan.
6. PR review, quality gate or post-implementation validation without new code: light `review`, objective-named reviewer plus only evidence-triggered helpers; order present helpers as research → QA → review.
7. Task satisfies the shared `quick-fix` predicate: light `quick-fix`, implementer then `$qa-engineer`.
8. Auth, trust boundaries, credentials or vulnerabilities: heavy `security-sensitive`, with `$security-engineer` and `$security-reviewer` mandatory.
9. Hard performance budgets, service-level agreements or latency targets: heavy `performance-sensitive`, with `$performance-engineer` and `$performance-reviewer` mandatory.
10. Spatial computation, transforms, meshing or geometry: heavy `geometry-review`, with `$computational-scientist` and `$architecture-reviewer` mandatory.
11. Multiple risk domains: heavy `combined-critical`, with all risk owners and reviewers.
12. Otherwise: heavy `full-delivery`, full pipeline coordinated with `$lead` active.

In factual work, a decision, ADR or material alternatives adds `$architect`; add `$planner` only when the user explicitly requests an execution plan.

Apply shared **Primary-task continuity and side work**, including same-turn primary progress and all authority, capacity, resource and hold constraints. This is governance, not a new provider runtime guarantee.

Hook authors must expect a `SubagentStart` / `SubagentStop` fire and an `agent_id`-bearing envelope exactly as on Claude Code's, and the `agent_id`-present skip this pack's `PreToolUse` blocking hooks implement (see the Codex hook procedure in the existing Lead operating-model) is load-bearing, not defensive — the two `Stop` guards register only on `Stop` (not `SubagentStop`), where the skip remains belt-and-suspenders. Independent external adapters may still run in parallel when the routing contract and provider runtimes allow it.

Use `$review-changes` for a direct full repository impact review of recent changes: current local diff or specified target plus wider affected surfaces, unchanged dependents and adjacent logic. A bugfix with a known file or function stays on `quick-fix` by default; log adjacent issues in the configured bug registry instead of widening the plan.

## Recovery rule

- Apply the shared `quick-fix` rule. Its four minimal recovery facts are task, current step, last result and next action. Re-classification enriches the same work-item; delivery closes and archives immediately under the normal rule.
- The main session owns heavier or multi-stage recovery in the configured task-memory directory; heavy routes above run the full pipeline with `$lead` active.
- Main-conversation routes needing continuation save recovery after each accepted stage: `status.md` (template, current stage, next role) plus the accepted artifact. One-Analyst factual work needs recovery only for continuation. A decision/ADR route records Analyst's accepted artifact before Architect, and Planner only for a requested execution plan.
- Close a main-conversation-managed item when delivered, parked, cancelled or reprioritized; delivered-but-active is an orphan. Lead writes `closure.md` with nonempty `Closed`, `Outcome`, `Evidence` and `Residual risk`; `Closed` exactly matches `--terminal-instant` in strict UTC `YYYY-MM-DDTHH:MM:SSZ`. A proportionate retrospective is optional. Lead writes `bug-dispositions.json` under the versioned Lead/lifecycle-owner contract for bug selection, recontextualization, transition and receipts; apply shared **Physical lifecycle V1** for the rollback-safe disposition/archive/receipt/README transaction and pending-close rules. Routine single-item mechanics may run inline; multi-item or drifted state routes to `$knowledge-archivist`. `work-items/index.md` remains compatibility-only. Keep-worthy lessons go to `work-items/lessons/`; full rules are in the lead skill.
- Epics: when several work-items serve one initiative, group them as an epic. active `work-items/epics/<date>-<slug>.md`; after all children close and the goal is met, the lifecycle owner archives it at `work-items/epics/archive/<YYYY-MM>/<slug>.md`, reconciles physical roots and regenerates `work-items/README.md`. Each child's `status.md` has one bare `Epic: <slug>` line; progress derives only from archive location. Distinguish unique active, unique archived, missing and duplicate lookup; duplicates fail closed. `$product-manager` admits; `$lead` links, rolls up and decides closure; `$knowledge-archivist` owns location mechanics.
- A work-item needing prior work declares `Depends-on: <slug>, <slug>` (work-item slugs) in `status.md`, a standing planned dependency edge distinct from runtime `BLOCKED:*` verdicts; Lead derives blocked-by/ready. Durable cross-cutting architecture decisions go in flat `work-items/decisions/<date>-<slug>.md`, `status: proposed|accepted|dropped|superseded|reverted`, referenced from `design.md` rather than buried there. Full rules: Lead `## Dependencies`, `## Decisions`, and Architect skill.
- A direct single-specialist invocation needs no recovery file unless itself admitted as `quick-fix`; this does not broaden recovery to trivial questions.

## Role resolution paths

Roles and utilities live in `.agents/skills/<name>/SKILL.md` for repo-local installs or `$HOME/.agents/skills/<name>/SKILL.md` globally. Use the skill/custom-agent overlay matching the assigned role. For other work, use the narrowest matching installed specialist, including non-core or repo-local specialists. Utility skills may be invoked directly when their workflow fits. The shared role index lists the core team, not an exhaustive catalog.

Use `$init-project` to initialize root `AGENTS.md` project policies and `.agents/.agents-mode.yaml` for a new Codex project. Use `$external-brigade` to launch a bounded set of independent external helpers together instead of ad hoc orchestration.

Global anchors are `$lead` for approved delivery coordination, routing, artifact acceptance and gates; `$product-manager` for roadmap ownership, prioritization and admission; and `$consultant` for optional non-blocking independent advice, with usage rules, toggle check and execution paths in `$HOME/.agents/skills/consultant/SKILL.md`.

`$external-worker` and `$external-reviewer` are bidirectional adapters, not Consultant aliases. Both use `auto | codex | claude | kimi | grok`; production `auto` uses only Codex/Claude, Kimi is explicit-only through fixed `kimi-code/k3`, results stay independently verified and nonauthorizing, and Grok is unavailable in 1.x.
- Worker: eligible non-owner, non-review roles. Kimi uses the canonical file-prompt wrapper; validated capability files may select scoped worker tools only for `engineering` and a taxonomy-mapped `external-worker` profession.
- Reviewer: eligible review/QA roles. Explicit Kimi supports policy-admitted read-only exploration, research, planning or review. Omitted capability files leave tools, Model Context Protocol servers and subagents empty with permission `reject`; validated files may select read tools/servers.

Repository-specific `AGENTS.md` files should add local priorities, canonical paths, build/test rules and source-of-truth references instead of restating the full global role catalog.

## Project bootstrap

If the project root `AGENTS.md` lacks `## Project policies`, or if no `.agents-mode.yaml` exists at any layer for the current project, suggest `$init-project` before substantial implementation work so the project policy surface and operator mode file are explicit instead of inferred.

**Read-order precedence** (highest to lowest, per-key resolution): project-local `.agents/.agents-mode.yaml` > local legacy `.agents/.agents-mode` > pack-local global `~/.codex/.agents-mode.yaml` > pack-local global legacy `~/.codex/.agents-mode` > shared cross-pack global `~/.agents-mode.yaml` > built-in defaults. Each key resolves to the highest layer that defines it; layers compose, they do not replace each other wholesale. The shared cross-pack global (`~/.agents-mode.yaml`, alongside `~/.claude.json`) is created during default global install and serves as the single source of truth shared between Claude Code and Codex CLI; pack-local globals stay as Codex-specific overrides where needed. `scripts/resolve-agents-mode.py --provider codex --json` is the executable reference in the source repository.

## Publication safety scan

For repo-local installs, run `bash .agents/skills/lead/scripts/check-publication-safety.sh` from Git Bash / macOS / Linux, or `python .agents/skills/lead/scripts/check-publication-safety.py` from Windows PowerShell. For global installs, use the same sibling entrypoints under `$HOME/.agents/skills/lead/scripts/` (`python "$HOME/.agents/skills/lead/scripts/check-publication-safety.py"` in PowerShell).

The default command is the pre-commit staged-blob check only. A manual range invocation is diagnostic; at push evaluation the gate runs its own fresh canonical sibling range scan. Human review and explicit user publication approval remain separate requirements.
