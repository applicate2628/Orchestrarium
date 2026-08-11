# Codex Platform Rules

Platform-specific rules for OpenAI Codex. Merged with shared governance (`AGENTS.shared.md`) into a single `AGENTS.md` at install time.

Treat `AGENTS.md` as the universal minimum contract for Codex work in a repository. Installed skills and custom-agent overrides provide the detailed role overlays: they narrow execution posture, scope, and prompting for a specific role, but they do not replace the base `AGENTS.md` rules.

## Bootstrap — verified premises plus edit/commit checkpoints

> **STOP. Universal premise rule first; three stricter trigger moments below.**
>
> Every decision, plan, review verdict, root-cause claim, fix, implementation action, or behavior-changing commit must rest on verified premises. The trigger moments below add mandatory edit/commit checkpoints; they do not limit the universal rule. Run the checklist at each trigger moment.
>
> **(a0) Pre-action orientation trigger** — before the first repository-local runner/build invocation or mutating tool call in an unfamiliar repo/subtree, complete step 0. This trigger is independent of whether the task is a bug fix; bug-fix steps 1-3 still apply at their existing trigger.
>
> **(a) Pre-fix trigger** — before the first code-mutating tool call (file write, patch, `apply_patch`, or equivalent) in response to a bug report, runtime failure, error trace, regression, "does not work" claim, "не работает" claim, "broken" claim, or any user message naming a defect in behavior — or before changing behavior that already works, for speed, cleanup, or refactor with no defect reported (there, runtime diagnosis or profiling before the edit is mandatory) — **steps 1-3 must complete before the first edit lands**. The trigger fires regardless of whether the session invoked the bugfix flow or any other routing — the discipline binds the session independent of the routing wrapper. Step 5 (Recovery readiness) does not apply at this moment; step 4 (Scope proportionality) and 4.5 (No-kostyl check) apply when you draft the planned edit.
>
> **(b) Pre-commit trigger** — before committing any change that fixes a bug, alters behavior, modifies a contract, or implements a feature, run **all 5 steps**. Step 5 is pre-commit-specific.
>
> This Bootstrap is the operational form of the shared `Hypothesis disclosure discipline` and `Pre-fix diagnostic gate` rules (above in this merged `AGENTS.md`). It binds the main Codex session and any installed skill that authors code mutations or commits.
>
> 0. **Repository orientation.** Before the first repository-local run, build, or mutation in an unfamiliar repo/subtree, state `scope`, `status`, `workflow`, `protected`, and `evidence` from applicable governing docs; `evidence` carries `file:line` citations. Names, counts, recency, and layout do not prove liveness. Missing or conflicting authority means `status=conflict`: do not run/build/edit until the owning source or user resolves it.
>
>    ```text
>    REPOSITORY ORIENTATION: scope=<repo-relative path>; status=<live|mutable|frozen|archived|deprecated|superseded|conflict>; workflow=<repo-relative entry point(s)>; protected=<repo-relative path(s)|none>; evidence=<path:line[,path:line...]>
>    ```
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
> **Pre-action orientation triggers** (fire before the first repository-local run, build, or mutation in an unfamiliar repo/subtree):
>
> - "This has the most files, so it is the live/current suite," or any target choice based on name, count, recency, or layout without governing-doc evidence.
> - "I will fork/copy this runner/scorer" without first proving its status and inventorying the current owner/mechanism.
> - Running, building, or editing an archived/deprecated/superseded/frozen target without explicit user-approved historical scope.
> - Treating missing or conflicting orientation as permission to proceed.
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

Codex CLI exposes hook events that can intercept tool calls and turn completion. The Codex pack ships eight structural hooks: three blocking-enforcement (bugfix-discipline, git-push-gate, passive-polling) and five warn-only audits (machine-local-path, no-trash-in-repo, stale-relation-residue, repository-orientation, mcp-momentum). They are backstops; they do not replace the text rules above. Separately, it ships four reminder/context hooks: three registered on `SessionStart` with no matcher so they fire on every SessionStart source including `compact` (`mcp-usage-reminder`, `agents-mode-reminder`, `check-scratch-valuables`), plus one registered on `UserPromptSubmit` (`turn-anchor-reminder`) that fires at the START of every user turn instead of only at session boundaries — a deliberately different surface, because a once-per-session reminder decays across one long turn's own tool-call momentum exactly as it decays across a session. Codex 0.144.4 accepts the structured JavaScript Object Notation (JSON) envelope `{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"..."}}` as added developer context. That version also retains a non-JSON-like plain-text fallback, but output beginning with `[` or `{` is treated as JSON-like and rejected when it is not valid hook JSON; Orchestrarium therefore deliberately emits all four reminders through the structured envelope. The universal MCP hook is shared with Claude Code, while the Codex agents-mode, scratch-valuables, and turn-anchor hooks remain provider-specific; all four are fail-open, emitting nothing and exiting 0 on any error. The first, `mcp-usage-reminder`, re-injects an MCP/tools-usage reminder into context at every session start AND after every compaction. It exists because agents keep forgetting the connected MCP servers, especially once a compaction summarizes working memory; it makes MCP/tool-discovery an explicit checkpoint for codebase, architecture, API/docs, search, browser, debugger, profiler, and repository-understanding tasks. Dispatched subagents inherit the runtime tool surface, but prompts should allow relevant MCP use within the assigned role, scope, and safety limits rather than hiding tool availability. Generic by design — it names no specific server (a hardcoded machine-local list would be wrong to ship), so the agent discovers the actual connected servers via tool discovery. The second, `agents-mode-reminder`, re-injects the ACTIVE delegation posture: it reads the effective `delegationMode` from a self-contained first-match walk of the documented `.agents-mode.yaml` read-order (`./.agents/…` → `~/.codex/…` → `~/.agents-mode.yaml`) and, ONLY when that mode is `force` or `auto`, emits an imperative directive telling the main conversation to adopt the `$lead` orchestration role in-session and activate the matching specialist role/skill for non-trivial tasks, and to maintain `work-items/` recovery state; it is SILENT on `manual` and on the no-file/unresolved state (fail-safe), so the block's presence is itself the signal and never becomes wallpaper. Because the shipped default is now `auto`, a default install surfaces the auto delegation directive automatically, without an `/agents-init-project` run. It exists because `delegationMode` is Orchestrator-pack governance the host never parses on its own — without this hook the main conversation never sees `force` and never applies it, which is exactly how a `force` config silently fails to route work and stops `work-items/` from being maintained. The third, `check-scratch-valuables`, is a READ-ONLY watchdog for the pack's own `.scratch/` local-evidence convention: at each `SessionStart` it scans for files whose exact content is not already recoverable from the repository's git object database (checked via `git hash-object`, never `-w`, plus `git cat-file --batch-check`), surfaces the valuable-looking ones before the operator accidentally overwrites them, and stays completely silent when nothing qualifies; when git is unavailable it falls back to an age-only gate (older than 7 days) rather than going silent. It never deletes, moves, renames, or otherwise mutates anything — its only calls are directory reads, stats, and the two read-only git subprocesses above. The fourth, `turn-anchor-reminder`, fires on `UserPromptSubmit` — the START of every user turn, not only session boundaries — and re-anchors two turn-level postures ("a passed slice is not completion, keep going until blocked" and "delegate at the first decision point via `$lead`") that a once-per-session reminder cannot reach once a long turn's own tool-call momentum takes over; it always emits and is deliberately short, since its text is paid for on every turn.

**PreToolUse bugfix-discipline hook.** `check-bugfix-discipline.py` catches the most common pre-fix discipline violation: the model is about to make a code-mutating tool call (`apply_patch`) in response to a user message that contains a bug-report or change-request signal (e.g. `fix`, `change`, `broken`, `не работает`, `исправь`, `пофикси`, `поменяй`, traceback, `Error:`), but it did NOT first invoke `/agents-bugfix` or otherwise capture diagnostic data. The hook reads the PreToolUse envelope's `transcript_path`, parses the recent transcript tail, and:

- If the envelope carries `agent_id` (a subagent context) → exit 0 (allow; the dispatching main conversation owns the diagnostic discipline, and a subagent must never be blocked).
- If the write target path is under `.reports/`, `.scratch/`, `.plans/`, `work-items/`, or `docs/` (matched as a `/`-bounded segment) → exit 0 (allow; a doc/report/scratch/plan/task-memory write is never the CODE fix this guard targets — verified on a real transcript where the guard fired legitimately on a `.reports/` memo write under a bug-fix-review prompt with no prose marker; `apply_patch` keeps its paths in the patch body and stays fully guarded).
- If the last user message contains no bug-trigger phrase → exit 0 (allow; not a bug context).
- If the last user message contains the override marker `[skip-bugfix-discipline]` → exit 0 (allow; user explicitly opted out).
- If the current turn shows discipline signals (`/agents-bugfix` invocation, `agents-bugfix` skill load, text containing `diagnostic`/`hypothesis`/`reproducing`/`VERIFIED:`) → exit 0 (allow).
- Otherwise → emit a structured `permissionDecision: "deny"` payload telling the model how to comply.

**PreToolUse git-push publication-gate hook.** `check-git-push-gate.py` is the blocking structural backstop for human review plus a leak-check before `git push`. The existing typed shell grammar still admits only an exact solitary push; one exact positive `--dry-run` remains the non-publishing fast allow. Default/tracked and path scans are manual pre-commit checks only. For scan-derived credit the gate freezes route, remote, destination, resolved source, and current `HEAD`; captures the verified `hook_common.py` + machine-path-classifier + scanner closure through open handles; and executes it through the current trusted interpreter with no shell or path lookup. Generic and strict pull-request routes consume only the exact pending invocation's fresh bounded, reaped authoritative observation and require a non-empty version-2 receipt whose tip matches the frozen source and `HEAD`. Transcript/manual, legacy/v1/tracked/path/zero-commit, malformed, finding, refusal, correlation, provenance, execution, identity-drift, or reused results deny without fallback. The genuine user's one-turn `[approve-publication]` marker and exact pull-request grant/revocation syntax remain; the grant replaces repeated confirmation only. Arbitrary same-process mutation defeats harness observation and may run arbitrary caller code; the only proven invariant is that unchanged shipped source contains no external adapter or launcher, and its cooperative result has zero production/publication consumers. Repository identity, remote URL/server freshness, and Git metadata outside selected commit messages/current-tip blobs remain outside the claim. Governance remains binding.

**Stop passive-polling hook.** `check-passive-polling-stop.py` catches a different failure: the model is about to end its turn by saying it is waiting for an async external source (bot/review/CI/job/notification/reply) without a relevant current-turn state check. The hook reads `last_assistant_message` directly from the Stop envelope, exits immediately when `stop_hook_active=true`, and parses the transcript only after a passive-polling phrase is detected. It allows user handoffs such as `waiting for your response` / `жду твоего подтверждения`, allows the per-stop override marker `[acknowledge-passive-stop]`, and otherwise requires a relevant probe in the current turn: time/status commands (`date`, `Get-Date`, `gh pr view`, `gh run list`, `gh api`, `curl`), process/task output, or reads of output/log/task files. If no relevant probe is present, it emits top-level `{"decision":"block","reason":"..."}` telling the model to check state now, use the override for a real handoff, or invoke a concrete tool like `Bash: gh pr view`.

**Work-item lifecycle.** No archival Stop hook or sentinel registry is registered. Physical location owns membership; the installed lifecycle owner validates terminal evidence, performs the archive move, and reconciles derived views.


**Five PreToolUse audit hooks (warn-only).** `check-machine-local-path.py` warns when a machine-local absolute path (a concrete user home or workstation dev root; placeholders like `<you>`, `%USERPROFILE%`, `${CLAUDE_PROJECT_DIR}` are allowed) is written into a non-`.scratch/` file. `check-no-trash-in-repo.py` (the stray-artifact guard — filename and install-marker retained for install continuity; a rename to `check-stray-artifact` is a tracked follow-up) warns on every confidently parsed `git worktree add` except one add whose command ends with the exact `# orchestrarium:requested-isolation-worktree` marker required by the installed parallel-isolation protocol; missing, near-match, quoted, reused, or batch markers do not suppress the audit. `git worktree list/remove/prune`, `git add` (not `git worktree add`), `git` inside a quoted string, and non-git commands never warn; the parser is shell-aware (shlex tokenization, command-position tracking across `&&`/`;`/`|`/`(`, env-assignment-prefix and git-global-option skipping) and fails open on any tokenizer error. This replaced a name-based version that warned only on new dirs named `kosyaks`/`mistake-log` — useless, because those are the *user's* personal-process vocabulary, not names the *agent* (the actor a PreToolUse hook guards) ever creates, so it never fired; the real reported problem was the agent creating stray artifacts, chiefly unrequested worktrees, so the guard now keys on the OPERATION, not a name. Deferred: the Claude `Agent` tool's `isolation: "worktree"` form (Codex CLI has no analogous Agent-isolation, so that branch is moot on this side anyway). Dropped: outside-repo writes (a static allow-list false-positive-floods on legitimate installs/temp/global-config/memory writes) and arbitrary in-repo trash (no reliable non-name signal — that stays governance). Both read their own call's `tool_input` and ALWAYS allow — AUDIT mode. On a hit each now delivers its warning to the MODEL via `hookSpecificOutput.additionalContext` on stdout and exits 0 (`hook_common.emit_advisory`), replacing the stderr-plus-exit-1 form this pack shipped before. **That form's open question is now closed, and closed negative:** the probe this section used to name — trusting the hook, triggering a hit, and inspecting the Codex transcript or `--debug` output for a visible difference from exit 0 — was performed on the installed Codex CLI 0.145.0, and the non-2-exit branch does **not** surface a hit any differently from a clean exit-0 pass; it does not even copy stderr anywhere the operator or the model can see it. So the old exit-1 form reached nobody on Codex, exactly as it reached nobody (transcript-only, model-invisible) on the sibling Claude Code pack — the `ASSUMPTION (UNVERIFIED)` this section previously carried is refuted, not merely removed. `emit_advisory` reads the firing event's own `hookEventName` off the incoming envelope first and uses it verbatim; on the sibling Claude Code pack a `hookEventName` that does not match the event that actually fired makes that runtime silently discard the entire `hookSpecificOutput` payload — worth guarding against here too, since this hook shares the same `hook_common.emit_advisory` implementation. A clean check emits nothing and also exits 0. Promotion to a blocking `deny` (exit 2) remains a separate reviewed step once the false-positive rate is measured. Both fail open — a wrapper-level or internal error emits nothing and exits 0, so a hook malfunction can never masquerade as a real hit. `check-stale-relation-residue.py` is the structural backstop for architecture law C6 ("a superseding change leaves only the correct current state; stale-relation residue is erased"): it warns when an `Edit`/`Write` ADDS a stale-relation residue phrase — fixed-vocabulary markers that almost always assert an OBSOLETE relationship a completed rename / merge / deprecation / move / fix should have erased (`deprecated alias`, `former alias` / `former name`, `now-retired ... kept as a historical example`, `(was X)` / `(formerly X)` / `(previously X)` parentheticals, `misregistered as`, `X -> Y alias`, `this is wrong, the correct is Y`) — into a LIVE-tree file. It cannot run C6's full change-specific old-name grep (the hook does not know the old name), so it keys on those operation-independent residue phrases instead. The STALE-vs-LIVE discriminator is review-bound — a real dependency, a deliberate split, or a current `X vs Y` comparison uses some of the same words — so this is WARN-only; it exempts the targets where recording a superseded relation IS legitimate provenance: decision/closure/task-memory registries (`work-items/`), changelogs / release notes (`RELEASE_NOTES`, `CHANGELOG`, `HISTORY`), archival trees (`/archive/`, `/legacy/`, `_archive`), the local scratch area (`.scratch/`), and git internals (`.git/`). It reads its own call's `tool_input`, delivers a hit to the model via the same `hookSpecificOutput.additionalContext` stdout channel, ALWAYS allows, exits 0 on both a hit and a clean check (never 2), and fails open — same AUDIT contract as the other two.

**Repository-orientation audit.** `check-repository-orientation.py` warns before a risky repository mutation or repository-local run/build/test when assistant-authored prose after the last genuine user task lacks exactly one valid `REPOSITORY ORIENTATION:` record. It validates the five required fields, a `path:line` citation, non-conflict status, and scope ancestry; skips discovery-only commands, local artifact writes, and subagent envelopes; and emits an extra warning for `archive`, `deprecated`, `superseded`, or `frozen` path segments unless the matching non-live status and explicit user-approved historical scope are stated. It never scans repository prose or treats deprecation words as canonical-status evidence. It delivers a hit to the model via `hookSpecificOutput.additionalContext` on stdout, ALWAYS allows the tool call, and fails open; a hit and a clean check both return exit 0, matching its four sibling audits. This section previously recorded an `ASSUMPTION (UNVERIFIED)` about whether a non-zero, non-2 PreToolUse exit is visible any differently from exit 0 on the Codex line; that was verified by triggering a hit and inspecting the transcript / `--debug` output, and refuted — it is not, which is exactly why this audit no longer relies on that channel.

**MCP-momentum audit.** `check-mcp-momentum.py` is one consumer of the shared three-event MCP continuity policy documented in [`references-codex/mcp-continuity.md`](../references-codex/mcp-continuity.md). It admits exactly `Grep|Bash|PowerShell|shell_command|exec_command`; treats `rg`, `ag`, and `ack` as recursive by default and `grep` as recursive only with an explicit recursive option; stays silent only when every explicit scope resolves from the raw envelope `cwd` to `work-items/`, `.reports/`, `.plans/`, or `.scratch/` at the nearest repository root; a matching segment at any other depth is not exempt; and fires for a mixed source/exempt search. Root and `agent_id` envelopes are evaluated identically. It emits only safe matched server names (at most three plus a count), always allows, exits 0 on hit and miss, never exits 2, and fails open. The advisory re-anchors tool choice; it cannot prove model obedience.

Hook entry points: `~/.codex/skills/lead/scripts/check-{bugfix-discipline,git-push-gate,passive-polling-stop}.py`;
`~/.codex/skills/lead/hooks/check-{machine-local-path,no-trash-in-repo,stale-relation-residue,repository-orientation,mcp-momentum}.py`.

This list covers the eight structural hooks (blocking + audit); the four reminder/context hooks are registered through `~/.codex/skills/lead/scripts/<name>.py`. Hook implementations have no shell or PowerShell rollback copies.

Per the source-hygiene placement law, the five warn-only audits live in `skills/lead/hooks/`, while blocking and reminder/context hooks live in `skills/lead/scripts/` beside `hook_common.py`. Python is the sole registered and implementation runtime for hooks.

**The installer auto-installs all twelve hook entries by default on all platforms** into `~/.codex/hooks.json` (`--global`) or `<project>/.codex/hooks.json` (`--target`): eight structural/audit entries plus the three informational `SessionStart` entries (`mcp-usage-reminder` + `agents-mode-reminder` + `check-scratch-valuables`) and the one `UserPromptSubmit` entry (`turn-anchor-reminder`). The JSON merge is idempotent and preserves all other user keys and hooks. Opt out with `--no-hypothesis-hook` (legacy flag kept for back-compat) or `ORCHESTRARIUM_NO_HYPOTHESIS_HOOK=1` in the environment.

The installer invokes each installed `.py` target directly with the absolute `sys.executable` of the Python process running the installer. Before registration mutation, the interpreter and `.py` target must be absolute regular files; on Windows the interpreter must be a non-reparse `.exe`, and on POSIX it must have execute permission. The later health gate actually launches every registered hook. The reserved native profile requires a real native executable and fails before mutation because no native hook binaries ship. On Windows, the registered command is the verified `cmd.exe`/PowerShell-compatible unquoted absolute interpreter followed by the unquoted absolute `.py` path; unsupported whitespace or metacharacters fail the install instead of creating a dead registration.

Upgrade ordering is strictly **SYNC → REGISTER → VERIFY → RECLAIM**. `scripts/check-hook-health.py` verifies every registered executable and target, then reconciles current owned Codex registrations one-to-one with host `hooks/list` before reclaim can run. Installer VERIFY uses `report`: only complete registration identities changed by that transaction may remain `untrusted` or `modified`, reported as `PENDING_MANUAL_TRUST`; the identity includes event, matcher, handler type, exact command, and exact registration source, while pre-existing drift fails. The installed helper's `require` mode automatically consumes its sibling generated `codex-hook-inventory.json`, fails closed when that inventory is missing, accepts only `trusted` host entries, and is the post-Trust and controlled-Codex-launch gate. Reclaim is last, idempotent, and dry-run-visible; it removes only byte-identical retired shell copies and preserves customized files.

Unlike Claude Code, Codex marks every newly-installed or changed hook entry as untrusted.

#### Manual trust step required (Codex security model)

After reinstall, start interactive `codex` — not `codex exec` — and choose **Trust all and continue** for all 12 affected entries.
Do not press Esc and do not choose **`Continue without trusting`**, because all hooks and guards remain installed but inactive.
`codex exec` silently skips untrusted hook entries instead of showing the trust prompt, so interactive `codex` must run first.
The trust modal does not time out and the operator must review all 12 entries before making the explicit choice.

Afterward, verify the host sees every current entry as runnable: `python ~/.codex/skills/lead/scripts/check-hook-health.py --target ~/.codex/hooks.json --platform codex --codex-trust-mode require`.

#### Trust identity

Trust is keyed to the normalized registration identity, so changing the command from a wrapper to direct Python intentionally requires this one-time review; later Python-source edits do not change that identity.

**Windows hook command shape.** The command is `<absolute-python.exe> <absolute-script.py>`, with both tokens unquoted. That exact form was verified under both `cmd.exe` and PowerShell. The installer rejects unsupported tokens instead of guessing a quoting form.

To remove already-installed entries independently:

```bash
python scripts/install-hypothesis-hook.py --target <hooks.json path> --platform codex --host-os posix --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target <hooks.json path> --platform codex --host-os posix --script-marker check-git-push-gate --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target <hooks.json path> --platform codex --host-os posix --hook-event Stop --script-marker check-passive-polling-stop --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target <hooks.json path> --platform codex --host-os posix --script-marker check-machine-local-path --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target <hooks.json path> --platform codex --host-os posix --script-marker check-no-trash-in-repo --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target <hooks.json path> --platform codex --host-os posix --script-marker check-stale-relation-residue --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target <hooks.json path> --platform codex --host-os posix --script-marker check-repository-orientation --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target <hooks.json path> --platform codex --host-os posix --script-marker check-mcp-momentum --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target <hooks.json path> --platform codex --host-os posix --hook-event SessionStart --script-marker mcp-usage-reminder --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target <hooks.json path> --platform codex --host-os posix --hook-event SessionStart --script-marker agents-mode-reminder --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target <hooks.json path> --platform codex --host-os posix --hook-event SessionStart --script-marker check-scratch-valuables --script-path <ignored> --remove
python scripts/install-hypothesis-hook.py --target <hooks.json path> --platform codex --host-os posix --hook-event UserPromptSubmit --script-marker turn-anchor-reminder --script-path <ignored> --remove
```

The auto-installed entries on Windows have this direct-Python shape:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|NotebookEdit|apply_patch",
        "hooks": [
          {
            "type": "command",
            "command": "C:\\Python314\\python.exe C:\\Users\\<you>\\.codex\\skills\\lead\\scripts\\check-bugfix-discipline.py"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "C:\\Python314\\python.exe C:\\Users\\<you>\\.codex\\skills\\lead\\scripts\\check-passive-polling-stop.py"
          }
        ]
      }
    ]
  }
}
```

Codex's `matcher` field is regex on tool name only (no `if`-style argument filter like Claude Code has); the bugfix-discipline PreToolUse script self-filters on transcript-derived bug-context, while the five audit PreToolUse hooks (machine-local-path, no-trash-in-repo, stale-relation-residue, repository-orientation, mcp-momentum) self-filter on their own `tool_input`. `Stop`, `SessionStart`, and `UserPromptSubmit` all ignore matcher, so the installer omits it for those entries. Both `~/.codex/hooks.json` and inline `[hooks]` tables in `~/.codex/config.toml` are supported; project-local `<repo>/.codex/hooks.json` is also supported but requires the project to be trusted.

**Codex PreToolUse tool-name coverage.** As currently observed, Codex's `PreToolUse` event fires only for Bash-tool-shaped calls, not for a distinct `Edit`/`Write`/`NotebookEdit`/`Grep` tool the way Claude Code's hook surface does — Codex file edits go through `apply_patch` and are not currently seen by a PreToolUse hook the way Claude Code's `Edit`/`Write` calls are. This is why several audit hooks (`check-no-trash-in-repo`, `check-repository-orientation`, `check-mcp-momentum`) carry a broad, defensive matcher listing multiple possible tool names (`Bash|PowerShell`, or the fuller `Edit|Write|NotebookEdit|apply_patch|Bash|PowerShell|shell_command|exec_command` union) rather than a single Codex tool name: the exact string Codex reports for a given tool call is not stable across versions, so the matcher is deliberately over-inclusive rather than tuned to today's behavior. In practice, on today's Codex builds, only the `Bash`/`PowerShell`/`shell_command`/`exec_command` portion of any such matcher is live; the `Edit`/`Write`/`NotebookEdit`/`apply_patch`/`Grep` portions stay dormant until Codex exposes matching PreToolUse tool names for those calls.

**Bypass is by design.** `[skip-bugfix-discipline]` bypasses the PreToolUse guard for the next turn. `[approve-publication]` opens the git-push gate for one turn — honored ONLY when it appears in the user's own last message, never from assistant prose or tool output. The exact `[approve-pr-publication:v1 pr=...]` grant is not a bypass: it remains bound to one current PR and still requires fresh oracle checks plus a new range receipt for every push. `[acknowledge-passive-stop]` bypasses one passive-polling Stop decision when the assistant is intentionally handing off to the user. Status or closure prose never makes a work-item terminal; use the lifecycle owner to archive and reconcile it. False discipline markers remain review territory; the Bootstrap text rule remains binding regardless of whether hooks are installed or trusted.

## Default delegation entry point

If approved delivery work needs delegation and no narrower delegated role is already named, use `$lead` from `$CODEX_HOME/skills/lead` as the default coordinator. If the task is about roadmap ownership, prioritization, milestone shaping, or admission into discovery or delivery, use `$product-manager` instead.

## Template routing

Classify the task, choose the narrowest matching workflow shape, and re-classify if scope widens. This pack's own routing keeps every chain owned by the main session: simple chains use light orchestration, heavier chains run with the full `$lead` skill active — the owner never changes, and `$lead` is never spawned as a subagent. That is a pack ROUTING POLICY choice, not a runtime limit: as of the installed `codex-cli 0.145.0`, Codex ships native subagent execution — dedicated `SubagentStart` / `SubagentStop` hook events whose envelopes require `agent_id` and `agent_type` fields, `CollabAgentTool` variants (`spawn_agent`, `send_input`, `resume_agent`, `wait`, `close_agent`; `codex-rs/protocol/src/items.rs:250-256`), and the `multi_agent` (stable, default-on) and `multi_agent_v2` (stable, opt-in) features (`codex-rs/features/src/lib.rs`; all of `spawn_agent`, `SubagentStart`, `SubagentStop`, `multi_agent_v2` confirmed present in the installed 0.145.0 binary's own string table) — so a hook author on this line must expect a `SubagentStart` / `SubagentStop` fire and an `agent_id`-bearing envelope exactly as on Claude Code's, and the `agent_id`-present skip this pack's `PreToolUse` blocking hooks implement (see above) is load-bearing, not defensive — the two `Stop` guards register only on `Stop` (not `SubagentStop`), where the skip remains belt-and-suspenders. Independent external adapters may still run in parallel when the routing contract and provider runtimes allow it.

**Decision tree:**
1. User explicitly names a role: invoke it directly.
2. Roadmap, prioritization, or milestone shaping: route to `$product-manager`.
3. Investigation, ADR, or alternatives exploration with no implementation: use **research**.
4. PR review, quality gate, or post-implementation validation with no new code: use **review**.
5. Task satisfies the shared **quick-fix** predicate: use **quick-fix**.
6. Auth, trust boundaries, credentials, or vulnerability work: use **security-sensitive**.
7. Hard performance budgets, SLAs, or latency targets: use **performance-sensitive**.
8. Spatial computation, transforms, meshing, or geometry: use **geometry-review**.
9. Multiple risk domains at once: use **combined-critical**.
10. Otherwise: use **full-delivery**.

| Template | Full lead pipeline? | Chain |
|---|---|---|
| `quick-fix` | No | Main conv picks implementer, then `$qa-engineer` |
| `research` | No | Main conv chains `$analyst` then `$architect`, optionally `$planner` |
| `review` | No | Main conv chains `$analyst` then `$qa-engineer` then reviewer(s) |
| `full-delivery` | Yes | `$lead` coordinates full pipeline |
| `security-sensitive` | Yes | `$lead` coordinates; `$security-engineer` and `$security-reviewer` mandatory |
| `performance-sensitive` | Yes | `$lead` coordinates; `$performance-engineer` and `$performance-reviewer` mandatory |
| `geometry-review` | Yes | `$lead` coordinates; `$computational-scientist` and `$architecture-reviewer` mandatory |
| `combined-critical` | Yes | `$lead` coordinates all risk owners and reviewers |

For BOTH "No" and "Yes", the main conversation runs the chain directly — it invokes the listed specialists in order and passes each accepted artifact downstream. "Yes" means it does so with the fuller `$lead` skill active (heavier orchestration: work-items, risk owners, integration, gates); it never spawns a separate `$lead`. `Quick-fix` follows the shared predicate; explicit `$lead` use and `delegationMode: auto|force` change coordination, not template admission or artifact requirements. Re-classify immediately if scope widens beyond the current template.

For a direct full repository impact review of recent changes, use `$review-changes`. It starts from the current local diff or a specified review target, but checks the wider affected surface, including unchanged dependents and adjacent logic. A bugfix with a known file or function stays on `quick-fix` by default; log adjacent issues in the configured bug registry instead of widening the current plan.

## Recovery rule

- Every admitted `quick-fix` creates a minimal `work-items/active/<slug>/status.md` before its first repository mutation. That file contains only ordinary lifecycle fields plus task, current step, last result, and next action; no `roadmap.md`, `brief.md`, Research, Design, Plan, consultant, pre-implementation review, or report is required before that mutation. Re-classification enriches the same work-item instead of creating a late unrelated item, and delivery applies the normal immediate closure/archive rule.
- Recovery for heavier or multi-stage templates remains owned by the main session through the configured task-memory directory; for lead-managed chains (`full-delivery`, `security-sensitive`, `performance-sensitive`, `geometry-review`, `combined-critical`) it runs the full lead pipeline with `$lead` active.
- For main-conversation-managed chains with 2+ stages (`research`, `review`), save recovery state after each accepted stage as `status.md` (template name, current stage, next role) plus the accepted artifact.
- Closing a main-conversation-managed item is the main conversation's job, and the close step is as mandatory as the create step above. When the item is delivered (its changes committed or pushed) or the user parks, cancels, or reprioritizes it, the main conversation must close it — a delivered item left active is an orphan. Close = DECIDE the close and write `closure.md` (outcome, residual risk, archive location) — the main conversation (as Lead) owns this decision and content; it MAY include a `## Retrospective` (what went well / what didn't / lessons, proportionate to the item) and MUST carry a `Closed: <YYYY-MM-DD>` line — then invoke the lifecycle owner to move the item to the configured archive location, reconcile physical lifecycle state, and regenerate `work-items/README.md`. The mechanics contract (physical placement, reconciliation after every state change, generated read-model refresh) is owned by `$knowledge-archivist`; a routine single-item close is applied directly by the main conversation, multi-item or drifted states route to `$knowledge-archivist`. `work-items/index.md` is a compatibility snapshot and has no ongoing sync requirement. This mirrors the `$lead` close step (`closure.md` mandatory before the configured archive location). A keep-worthy delivery lesson goes in the `work-items/lessons/` registry (consulted by `$product-manager`/`$lead` on admission; full rules in the lead skill `## Lessons` + `docs/lessons.md`, a maintainer reference not installed at runtime).
- Epics: when several work-items serve one initiative, group them as an epic. An active epic is the flat file `work-items/epics/<date>-<slug>.md`; after all children close and the goal is met, the lifecycle owner moves its terminal record to `work-items/epics/archive/<YYYY-MM>/<slug>.md`, reconciles physical lifecycle roots, and regenerates `work-items/README.md`. Each child work-item declares one bare `Epic: <slug>` line in `status.md`; child progress is derived only from archive location. Epic lookup distinguishes unique active, unique archived, missing, and duplicate state; duplicates fail closed. `$product-manager` admits the epic; `$lead` links, rolls up, and decides closure; `$knowledge-archivist` owns location mechanics.
- Dependencies & decisions: a work-item that needs prior work declares `Depends-on: <slug>, <slug>` (work-item slugs) in its `status.md` — a standing, planned inter-work-item dependency edge (distinct from the runtime `BLOCKED:*` gate verdicts); the lead derives blocked-by/ready from these. Durable cross-cutting architecture decisions go in a `work-items/decisions/` registry (flat `<date>-<slug>.md`, `status: proposed|accepted|dropped|superseded|reverted`), referenced from a work-item's `design.md`, not buried in it. Full rules in the lead skill `## Dependencies` + `## Decisions` + the architect skill.
- For a direct single-specialist invocation, no recovery file is needed unless that invocation is itself admitted as `quick-fix`; this exception does not broaden recovery to trivial questions.

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

**Read-order precedence** (highest to lowest, per-key resolution): project-local `.agents/.agents-mode.yaml` > local legacy `.agents/.agents-mode` > pack-local global `~/.codex/.agents-mode.yaml` > pack-local global legacy `~/.codex/.agents-mode` > shared cross-pack global `~/.agents-mode.yaml` > built-in defaults. Each key resolves to the highest layer that defines it; layers compose, they do not replace each other wholesale. The shared cross-pack global (`~/.agents-mode.yaml`, alongside `~/.claude.json`) is created during default global install and serves as the single source of truth shared between Claude Code and Codex CLI; pack-local globals stay as Codex-specific overrides where needed. `scripts/resolve-agents-mode.py --provider codex --json` is the executable reference in the source repository.

## Publication safety scan

For repo-local installs, run `bash .agents/skills/lead/scripts/check-publication-safety.sh` from Git Bash / macOS / Linux, or `python .agents/skills/lead/scripts/check-publication-safety.py` from Windows PowerShell. For global installs, use the same sibling entrypoints under `~/.codex/skills/lead/scripts/` (`python "$HOME/.codex/skills/lead/scripts/check-publication-safety.py"` in PowerShell).

The default command is the pre-commit staged-blob check only. A manual range invocation is diagnostic; at push evaluation the gate runs its own fresh canonical sibling range scan. Human review and explicit user publication approval remain separate requirements.
