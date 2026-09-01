# Repository Cleanup Common Skill — Frozen Design A

Status: frozen for implementation and independent review
Date: 2026-08-28
Proposed ADR: `work-items/decisions/2026-08-28-repo-cleanup-front-door.md`

The ADR record is a separate local lifecycle artifact. This design names but does not create, accept, or archive it.

## Decision

Add `$repo-cleanup` as a cross-provider coordinator that only scans through existing read-only mechanisms, classifies findings, routes approved work to existing owners, rechecks fresh owner evidence, and returns one current-invocation report.

It has no mutation engine, state machine, process killer, lifecycle/Git/transfer writer, persistent receipt, ledger, registry, cache, or resumable state. It never loads a previous cleanup result from the repository.

Existing owners remain unchanged:
- shared governance owns common-skill routing: `shared/AGENTS.shared.md:12-13`;
- Lead owns Lead-managed acceptance: `src.codex/skills/lead/SKILL.md:14-28,74-90`;
- the lifecycle owner alone applies work-item moves/dispositions: `shared/AGENTS.shared.md:21-22`;
- the Archivist coordinates complete multi-item/drifted reconciliation: `src.codex/skills/knowledge-archivist/SKILL.md:51-55`;
- `$manual-repo-transfer` alone owns final inventory/bundle/verify: `src.codex/skills/manual-repo-transfer/SKILL.md:12-21,23-56`;
- `scripts/maintenance/cleanup.py` stays a read-only valuables watchdog: `scripts/maintenance/cleanup.py:18-21,40-56`.

## TriggerContractV1

This is a semantic skill-routing contract applied by the host's existing intent classification, not a phrase parser. It adds no router code.

| Imperative user intent anchors | Route |
| --- | --- |
| explicit `$repo-cleanup` | repo-cleanup, requested/default mode |
| explicit `$manual-repo-transfer` without cleanup intent | manual-repo-transfer directly |
| `prepare for transfer`, `prepare repo for transfer`, `подготовь к переносу`, `подготовь репозиторий к переносу` | repo-cleanup transfer mode |
| `clean repo`, `clean the repo`, `почисти репозиторий`, `убери репозиторий` | repo-cleanup clean mode |

Precedence:
1. Explicit `$repo-cleanup` wins and preserves any requested transfer intent.
2. Explicit `$manual-repo-transfer` is direct only when no cleanup intent is also requested.
3. Imperative prepare-for-transfer intent routes through repo-cleanup transfer mode.
4. Imperative clean-repo intent routes through repo-cleanup clean mode.
5. Compound prepare-plus-cleanup intent performs one cleanup, then one transfer chain; it never invokes cleanup twice.

Quoted, code-fenced, documentation, and example mentions are non-triggering because the host classifies them as non-imperative context. Near-misses remain `clean code`, `clean build`, `clean target`, `copy repo`, `transfer file`, `prepare release`, `archive work item`, and `close work item`.

## Universal no-self-residue invariant

No actor may claim lane/task `PASS`, hand off, commit, push, or declare transfer readiness while non-canonical agent-owned residue remains. Pre-existing user state is untouched; ambiguous ownership blocks destructive work and never authorizes deletion.

Agent-owned residue includes:
- trash, temporary/generated artifacts, half-finished alternatives, dead/superseded code, helpers, docs, names, or registry entries;
- live processes/descendants, temporary worktrees/branches, locks, handles, subscriptions, transactions, quarantine/recovery directories, or tombstones;
- temporary reports, plans, logs, captures, caches, or scratch roots without an accepted canonical pointer.
A locally owner/config-identified ephemeral temp volume may classify disposable files as `ephemeral-volume-exempt` under fixed v1 free-space hysteresis owned canonically by `$repo-cleanup` `SKILL.md`. Let `freeRatio = freeCapacityBytes / volumeCapacityBytes`. When `freeRatio >= 0.20`, classified disposable material may remain exempt. When `freeRatio < 0.20`, route cleanup to the existing owner and delete only classified disposable material until `freeRatio >= 0.30` or no classified disposable material remains. Exactly `0.20` does not trigger cleanup and exactly `0.30` satisfies the preferred target. `cleanupCandidateBytes` remains accounting and deletion-bound evidence but is not a cleanup trigger; there is no separate urgent tier. `volumeCapacityBytes` must be readable and `> 0`, and `freeCapacityBytes` must be within `[0, volumeCapacityBytes]`; invalid or unknown capacity/classification yields preserve + `REVISE`. Sensitive data, live handles/processes, correctness/lifecycle error, or explicit user request override exemption. If classified disposable material is exhausted while `freeRatio` remains `< 0.20`, preserve all other state and return `REVISE:cleanup-capacity-unresolved`; reaching the safe floor without reaching the preferred target is nonblocking. No volume identity is hardcoded and hotfix v1 permits no local threshold override.

Structural enforcement:
- shared AGENTS states the universal invariant;
- both subagent receiving contracts require cleanup disposition and fresh settlement evidence before root acceptance;
- the direct-root turn-anchor reminder restates the invariant before direct-root completion, commit, push, or handoff;
- only Lead-managed flows have the mechanical report gate: Lead maps a missing, stale, incomplete, or non-zero report to `REVISE:self-residue`.

Direct-root flows retain the text invariant and turn anchor but do not fabricate a Lead gate or persistent report.

### ResourceRowV1

Each selected resource has one transient current-invocation row supplied through the existing receiving contract: `category`; creator/adopter `role + run`; exact identity; `preexisting` flag; settlement probe and current result; disposition. `ephemeral-volume-exempt` additionally requires owner/config volume identity, classified `cleanupCandidateBytes`, readable positive `volumeCapacityBytes`, bounded `freeCapacityBytes`, fixed v1 safe-floor/preferred-target values sourced from `$repo-cleanup` `SKILL.md`, computed free ratio, and override evidence. An absent/unknown input, invalid exception, or missing settlement result classifies the row as `unclassified`, preserves the data, and yields `REVISE`.

Direct-root work derives the same rows from its own tool/resource actions plus a pre-mutation Git/resource census. Rows exist only in current conversation state and are never written or reloaded.

## RepoCleanupReportV1

`RepoCleanupReportV1` is a bounded read-only projection created and consumed only in the current invocation. It is returned in-band, never persisted/reloaded, and never authorizes mutation.

Fields:
- repository physical identity and observed `HEAD` or unborn state;
- matched trigger and selected mode;
- current `ResourceRowV1` rows;
- finite `PredicateRowV1` rows and `PASS | REVISE | BLOCKED`.

`PredicateRowV1` contains predicate ID, subject identity, exact owner-evidence digest/reference, physical repository identity, `HEAD`/unborn binding, observation time, and `pass | fail | not-selected`. For work-items/lifecycle/Archivist, Git, and transfer, every field/result is a strict projection of one exact existing owner result; the coordinator never recomputes, independently evaluates, combines partial evidence, or synthesizes those predicates. It may only detect missing/stale/null evidence and return `REVISE`. Counts are derived only from rows and are never independent evidence.

Finite predicate IDs:
- workspace: `WS-CLASSIFIED`, `WS-SELF-RESIDUE-ZERO`, `WS-PREEXISTING-UNTOUCHED`, `WS-EPHEMERAL-EXEMPT-VALID`;
- work-items: `WI-EXISTING-AUDIT`, `WI-UNIQUE-LOCATION`, `WI-NO-TERMINAL-CURRENT`, `WI-NO-PENDING-MANIFEST`, `WI-CLOSE-EVIDENCE`, `WI-README-CURRENT`, `WI-NO-STANDALONE-DUPLICATE`, `WI-RELATIONS-RESOLVE`, `WI-SEMANTIC-CURRENT`, `WI-OWNED-RESIDUE-ZERO`;
- optional Git: `GIT-CLASSIFIED`, `GIT-TEMP-RESOURCES-ZERO`, `GIT-PREEXISTING-UNTOUCHED`;
- transfer: `XFER-ORDER`, `XFER-TRUSTED-VERIFY`, `XFER-POST-CLASSIFIED`.

`PASS` requires all mode-required predicates to pass, zero unclassified Resource rows, and zero row-derived residue; valid `ephemeral-volume-exempt` rows are nonblocking and excluded from residue counts. Git/transfer predicates may be `not-selected` only when the bound mode genuinely excludes that phase.

The report is not an approval token. Existing lifecycle, Git, transfer, publication, and genuine-current-user rules remain the only mutation authorities.

## Coordinator contract

Scan/classify reads governance and existing inventories/audits. Coordinator-owned evaluation is limited to workspace and transient Resource-row classification; all other predicate results are projected from exact existing owner evidence. It performs no action.

Route delegates only to the already-authorized owner:
- lifecycle owner for work-item state;
- exact Git-operation owner for Git state;
- transfer owner for inventory/bundle/verify;
- producing role for its process tree, temporary worktree/branch, lock, or generated residue.

The report never supplies approval. Destructive owners consume only genuine current-user approval through their existing provenance rules.

Recheck discards prior observations after owner work and rereads exact current evidence. Nothing is cached or written to the repository.

## Work-items zero

Structural evidence comes only from the repository's existing lifecycle audit. In Orchestrarium the exact entry is `python scripts/check-work-items-state.py`. The coordinator projects that result without rerunning its logic. No checker is added or duplicated.

The lifecycle/Archivist owner supplies exact results for these manual predicates; the coordinator only projects each bound result and rejects missing/stale/null evidence:
- every identity occupies exactly one allowed lifecycle location;
- no terminal record remains current and no active `bug-dispositions.json` remains pending;
- every completed close has exact context-linked dispositions and its existing owner receipt;
- generated `work-items/README.md` agrees with physical state;
- active artifacts are not duplicated in `.reports/` or `.plans/`;
- dependency, epic, registry, and logical-link targets resolve;
- current semantic claims have current owner evidence;
- agent-owned lifecycle locks, tombstones, temporary roots, and undeclared scratch evidence are absent.

A valid active item is not residue. Zero means no invalid, stale, duplicate, terminal-in-current, unclassified, or agent-owned temporary state; it never means blindly forcing active count to zero. Lead decides closure/disposition semantics; Archivist/lifecycle owner applies accepted mechanics only.

## Transfer mode

Exact chain:

`cleanup PASS -> final inventory -> bundle -> trusted verify -> post-transfer classification`

Final inventory follows the last cleanup/lifecycle/Git/tool-state mutation. Bundle, verify, and post-transfer classification results come exclusively from `$manual-repo-transfer`/existing resource owners; the coordinator projects their exact evidence without reevaluation. Owner evidence covers intentional external placement/classification, settled helpers, and zero task-owned temporary material.

Transfer preparation grants no delete, wipe, commit, push, publication, or external-copy authority.

## Preview/apply/QA separation

Coordinator preview/report is read-only: it cannot apply, simulate apply success, or turn an owner action into approval. QA first proves scan/classify/report mutates no filesystem, Git, lifecycle, process, or external state. After an existing owner performs a separately approved action, QA observes that real result and requires a fresh coordinator recheck.

Required scenarios:
1. semantic imperative/quoted/example intents, explicit-skill precedence, and one-cleanup compound routing without parser code;
2. report-only execution creates no mutation or persistent file;
3. every Resource row field/ownership/settlement gap becomes unclassified; direct-root rows derive from its census/actions only;
4. every required Predicate row exists with current repo/HEAD/time/evidence binding; missing/stale rows fail and counts equal row derivation;
5. pre-existing state remains untouched; tests prove valid exempt rows are excluded from counts, free ratio `0.20` does not trigger, `< 0.20` cleans toward `>= 0.30`, target equality `0.30` passes, cleanup-candidate ratio alone never triggers, invalid/unreadable/unknown capacity or out-of-range free capacity preserves + `REVISE`, only classified disposable is removed, exhaustion below the `0.20` safe floor yields `REVISE:cleanup-capacity-unresolved`, and reaching the safe floor below the preferred target is nonblocking;
6. every residue category independently blocks Lead acceptance;
7. valid active work passes while each work-item predicate fails distinctly;
8. transfer runs only after cleanup `PASS`, then final inventory/bundle/verify/post-classification in order;
9. both providers expose byte-equivalent coordinator semantics.

## Security and platform safety

The coordinator never deletes, moves, terminates, unlocks, rewrites, commits, pushes, archives, or follows links. Existing owners enforce exact targets, approvals, bounded paths, no-follow traversal, identity/drift checks, rollback, and postcondition evidence.

Windows owner expectations: junction/reparse refusal, literal-path use, file-identity recheck, locked-file handling, and no cross-volume atomicity assumption.

POSIX owner expectations: symlink/no-follow handling, device/inode recheck, mount-boundary awareness, and refusal of FIFOs, sockets, devices, or unsupported types.

All owners redact credentials/remotes, secrets, customer data, raw logs, and machine-local paths. Independent `$security-reviewer` approval is mandatory because routing is adjacent to data-loss operations.

## Change-Surface Contract

`intended change surface`: shared registration/invariant; coordinator skill bodies and Codex interface; Lead report gate; subagent receiving contract; direct-root turn anchor; focused pins/tests.

`approved seams`: Common skills registry, Lead acceptance, receiving contract, turn-anchor reminder, existing lifecycle audit/owner, Git owner, and manual-transfer evidence.

`protected`: manual-transfer skill/engine/schema/tests, scratch watchdog, lifecycle mutation/audit semantics, Git/publication gates, process supervision, and pre-existing user state.

`blast radius`: additive routing plus stricter Lead-managed acceptance; no mutation, persistence, schema migration, dependency, service, or external wire-shape change.

## Minimal hotfix surfaces

- `shared/AGENTS.shared.md` and one shared reference;
- Codex `repo-cleanup/SKILL.md` plus `agents/openai.yaml`, and byte-equivalent Claude skill;
- both Lead skills and both subagent receiving-contract copies;
- canonical turn-anchor source and provider projections;
- provider common-skill pins/catalog validation and focused trigger/report/gate/reminder/installer tests;
- installer accepted-prior data only where updating installed Lead requires it;
- `RELEASE_NOTES.md`.

No transfer, lifecycle, cleanup-watchdog, Git, publication, process-runner, or product source belongs to the hotfix.

## Dirty overlap and isolation

Do not implement source in the current dirty worktree. Read-only Architecture, Security, and QA reviews may run in parallel against this design.

Implementation starts only after PR #3 has one exact clean head containing all accepted current dirty work. Lead records that SHA and creates one explicitly requested isolation worktree at that commit using the required marker. One integration owner performs all hotfix edits there.

No copying uncommitted files, whole-file replacement, implicit conflict resolution, or concurrent mutation/test execution against shared source surfaces is allowed. The worktree and temporary branch are agent-owned residue and require fresh Git absence evidence before terminal `PASS`, unless the user explicitly promotes the branch.

## Compatibility

Trigger/report contracts are additive. There is no persisted migration, historical backfill, registry, receipt compatibility window, or recovery format. Installed/source mismatch fails closed; only behavior verified in the active installed version may run.

## Claims

1. `{ guarantee: coordinator never mutates; owner: repo-cleanup; probe: read-only scenario shows zero state change and no persistent output }`.
2. `{ guarantee: transfer remains single-owned; owner: manual-repo-transfer; probe: no bundle/verify code exists in coordinator and ordered transfer scenario passes }`.
3. `{ guarantee: work-item mutation/evaluation remains single-owned; owner: lifecycle/Archivist owners; probe: coordinator only projects exact existing audit and predicate results }`.
4. `{ guarantee: Lead rejects self-residue; owner: Lead gate; probe: every non-zero category returns REVISE:self-residue }`.
5. `{ guarantee: direct-root/subagent paths keep the invariant without a fake Lead gate; owner: shared/receiving/turn-anchor contracts; probe: contract tests pin all three }`.
6. `{ guarantee: pre-existing user state is untouched; owner: existing action owners; probe: cross-platform preservation scenarios pass }`.

## Diff-invisible invariants

- Transfer cleanup remains preview-only; existing apply-refusal regression stays green.
- Scratch scanning remains read-only; existing zero-mutation regressions stay green.
- Work-item terminality remains location-owned/rollback-safe; lifecycle regressions stay green.
- Report never proves approval; destructive-owner approval tests stay green.
- Agent-owned processes/worktrees/branches/locks/quarantines cannot survive Lead acceptance; category-isolated gate scenarios stay green.
- Cleanup never implies publication; existing human and publication gates are unchanged.

## Gate

Any mutation capability, persistence, new checker, process termination, ownership change, broader trigger matching, or report-as-approval behavior is a material revision requiring Architecture and Security re-review.

## Terms and Abbreviations

- **Coordinator**: read-only scan/classify/route/recheck workflow.
- **Genuine-user approval**: current-user authority accepted by an existing owner's provenance rules.
- **Lead-managed flow**: workflow whose root has Lead active and owns mechanical acceptance.
- **Near-miss**: finite phrase confirmed not to activate TriggerContractV1.
- **RepoCleanupReportV1**: nonpersistent, nonauthorizing current-invocation owner-evidence projection.
- **Residue**: non-canonical agent-owned state remaining after its purpose.
- **SHA**: Secure Hash Algorithm identifier for an exact Git commit.
- **Zero**: selected existing audits pass and all listed residue predicates are false.
