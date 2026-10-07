# Repository Cleanup Coordination

`$repo-cleanup` is the common semantic front door for a clean-repository request and for repository transfer preparation. It coordinates read-only discovery and current evidence; it is not a deletion, lifecycle, Git, transfer, or process-control implementation.

## Ownership

The coordinator performs only `scan -> classify -> route -> recheck`. It may classify workspace resources itself, but it projects lifecycle, Git, and transfer results from the exact existing owner evidence. When `work-items/` is selected, it enumerates every immediate child exactly once as `category | derived | repository-local exception | unknown`; audit `PASS` does not satisfy this census. It does not recompute those owners' predicates or turn its report into approval.

Existing owners remain authoritative:

Report-candidate evidence custody and its before-classification ordering belong to the Archivist working rules ([Codex](../../src.codex/skills/knowledge-archivist/SKILL.md#working-rules), [Claude](../../src.claude/agents/knowledge-archivist.md#working-rules)); this coordinator observes that owner rather than adding a second custody predicate.

- the lifecycle owner applies admitted work-item moves and dispositions;
- `$knowledge-archivist` coordinates multi-item or drifted physical reconciliation;
- the exact Git-operation owner changes Git state;
- `$manual-repo-transfer` owns final inventory, bundle creation, trusted verification, and receiver restoration;
- each producing role owns settlement of its process trees, temporary worktrees or branches, locks, and generated residue.

Task scratch under `.scratch/work-items/<work-item-slug>/` is disposable work-item storage, not an archive: producers promote required load-bearing results to canonical artifacts, finish the task rather than endlessly sorting scratch, then the producing owner settles its temporary state. Retain legacy scratch only until its recovery or transition settles; unfinished, foreign, ambiguous, or denied state remains preserved.

The coordinator has no mutation engine, persistent state, receipt ledger, registry, cache, resumable state, or generic process killer. Every destructive action still requires the existing owner's genuine current-user authorization and safety checks.

When the host refuses a validated owner action before execution because a host policy denies it, preserve the exact target. Do not confuse that denial with an operating-system or filesystem lock, access, or permission error returned after an attempted action; target-side failures remain ordinary unsettled residue. Use the existing `ResourceRowV1` identity, settlement-probe/result, and disposition fields to record the requested action, pre-action and post-refusal settlement probe results, disposition `preserved`, the redacted refusal reason, owner, and needed action. Do not evade the refusal: no alternate shell, API, provider, command shape, retry, or allow-rule is allowed; neither are configuration relaxation, rename, move, or truncation. Only a genuine host-supported permission route for the same validated action may be requested. Without that route or grant, hand the exact action to the root main conversation and its existing current work-item. In that work-item's existing `status.md`, record the exact unresolved action, current denial reason, concrete resume condition, and next step. After a material condition change that could affect the action, route one fresh same-target cleanup reassessment before treating the blockage as current or completing the item; an old denial without that reassessment is not current evidence. Reassessment repeats ownership, identity, settlement, and current-authority checks and grants no approval, bypass, retry, deletion, or other mutation authority. If conditions are unchanged, do not retry; if the exact grant remains absent, preserve the target and request that grant. Independent non-overlapping work continues, but dependent zero-residue predicates remain `fail`.

The target may be explicitly deferred only when fresh checks prove an ordinary empty agent-owned disposable directory, including no hidden children, link or reparse identity, live handle/process/lock/other active resource, valuable data, or dependency on the functional result, accepted artifact, or downstream action. Keep disposition `preserved` and keep the `status.md` record required above current with these fresh deferral probes. Create no registry, engine, schema, report status, daemon, or marker file. Unknown, sensitive, live, valuable, non-empty, correctness-affecting, or delivery-affecting items cannot use the exception.

Deferral leaves cleanup incomplete: the affected cleanup predicate and all dependent zero-residue predicates remain `fail`, the row remains residue, and cleanup never becomes `PASS` or zero residue. An independently verified delivery, handoff, commit, or transfer may proceed only when all its own gates pass, it has no dependency on the directory, and it reports the exact residue and resume condition. The exception grants no removal authority and waives no other blocker.

## Producing-owner trash fallback after an attempted deletion

Within an already authorized cleanup, a genuine operating-system or filesystem deletion error after the producing owner's attempted action permits that owner, without a new per-path user question, to move only the exact confirmed agent-owned disposable remainder into the current physically bound project or task root's `.scratch/trash/YYYY-MM-DD/<path-relative-to-bound-root>`. A partial deletion requires a fresh no-follow inventory of what actually remains; the original deletion inventory does not authorize moving absent or changed paths. Bind the root from the task's established physical project identity, never from an arbitrary current directory or another repository. This permission does not apply to pre-execution host-policy denial, automatic lifecycle-close scratch deletion with its separate receipt and rollback contract, `.scratch/trash/` and its descendants, tracked or canonical content, unfinished or valuable data, or foreign, ambiguous, unclassified, or active resources.

Before moving, the owner verifies every source is still within that bound root, is not a link or reparse point, and has no live user; records a transient no-follow tree inventory and ordinary-file checksums; and proves that each destination is absent. Check every existing destination ancestor without following links. As part of this authorized move only, the owner may create and verify missing ordinary non-link directories solely along each exact prevalidated destination's ancestor chain beneath the already bound root: `.scratch/`, `.scratch/trash/`, the date container, and any relative parent directories. Check each newly created component without following links before using it; never create an unrelated sibling or broaden the destination. Reject a source equal to, containing, or beneath its destination; never follow links, merge, overwrite, invent a suffix, or change roots. After each literal-path move, verify byte-identical destination inventory and checksums and source absence. On failure, stop and report every exact remaining source, completed destination, and created container (including empty ones) as residue without silent cleanup, rollback, or another mutation route.

A successful move clears the original location but leaves the trash as agent-owned residue: report `quarantine prepared; manual deletion pending`, not `deleted`, cleanup `PASS`, or zero residue. Independent work, delivery, handoff, or commit may continue only when it does not depend on that residue, its own gates pass, and the exact residue and manual-deletion action are reported. Final clean-transfer readiness remains non-`PASS` until manual deletion and a fresh inventory establish zero residue; explicit accounting may support only the separately authorized unfinished/direct-transfer or provisional-snapshot route, not a clean-transfer claim. The producing owner alone moves; `$repo-cleanup` remains a read-only coordinator and adds no engine, schema, registry, receipt, or lifecycle-close behavior.

## User-selected manual quarantine inside `.scratch`

Manual quarantine is a separately selected user operation, not a fallback after a host-policy-denied deletion. That refusal grants no move authority. The root main conversation may route this distinct inside-`.scratch/` move only after the user independently selects manual quarantine and authorizes the exact source and destination, the existing producing owner retains the action, and the host permits it. A host refusal preserves the source and ends mutation attempts; another shell, application programming interface (API), command form, or move route is not a substitute.

Eligible sources are confirmed trash already within the repository-local `.scratch/`. The `.scratch/` root, `.scratch/trash/` and its descendants, links or reparse points, active or in-use resources, canonical artifacts, and valuable, ambiguous, unclassified, or unproven data are excluded. Each source maps exactly to `.scratch/trash/YYYY-MM-DD/<path-relative-to-.scratch>` under the same physically bound `.scratch/` root. The source cannot equal, contain, or be beneath its destination. Before a move, the producing owner keeps a transient in-band no-follow inventory and ordinary-file checksums, proves no process or active resource uses the source, and proves that every selected destination is absent. The date container may already exist only when it is a verified ordinary non-link directory under the bound quarantine root. A collision at any selected destination stops the whole pending set: there is no selected-source-tree merge, overwrite, or generated suffix.

The producing owner performs only the explicitly authorized literal-path moves. It then proves that each destination exists with identical inventory and checksums and that its source is absent. A failure stops the operation; completed moves and untouched sources are preserved and their exact states are reported without a completion claim or silent rollback. Restoration is a separately authorized owner action and requires the original `.scratch/` path to be vacant plus the same no-follow checks.

No agent deletes anything within `.scratch/trash/`, including during later cleanup. The human operator alone may separately delete the whole quarantine tree. Until then, the human-facing result is `quarantine prepared; manual deletion pending`, never `deleted`, cleanup `PASS`, or zero residue. Only a necessary recovery list may be recorded in an existing current work-item `status.md`; this mode adds no manifest, registry, schema, daemon, helper, or report/disposition state. Transfer inventory and selection evidence explicitly accounts for all retained quarantine entries, including policy-restricted entries, without silently excluding them.

## Universal no-self-residue invariant

No actor may claim lane or task `PASS`, hand off, commit, push, or declare transfer readiness while non-canonical agent-owned residue remains, except for the bounded independent-action rules above; even there, cleanup itself remains non-`PASS` and the residue stays visible. This includes temporary or generated files, half-finished alternatives, dead or superseded code, temporary plans/reports/logs without an accepted pointer, live process descendants, handles, locks, temporary worktrees or branches, and quarantine or recovery roots.

Pre-existing user state remains untouched. Ambiguous ownership preserves the state and blocks destructive action. Each selected resource has a current-invocation `ResourceRowV1`; `unknown` remains preserved, and unknown ownership, identity, classification, settlement, or disposition makes that row `unclassified` and yields `REVISE`.

The only general exemption is owner/config-identified disposable material on an ephemeral temp volume. The fixed safe-floor and preferred-target hysteresis, its input validation, and the exact `ResourceRowV1` evidence are canonically owned by the installed `$repo-cleanup` `SKILL.md`; there is no repository-local threshold override.

## Current-invocation report

`RepoCleanupReportV1` is a bounded, transient, nonauthorizing projection. It binds the physical repository identity, observed `HEAD` or unborn state, selected trigger and mode, resource rows, finite predicate rows, observation time, and exact owner-evidence references. It is returned in-band and is never persisted or reloaded.

Only Lead-managed flows use the mechanical report gate. A missing, stale, incomplete, or non-zero-residue report yields `REVISE:self-residue`; only the exact deferred-directory or producing-owner trash-fallback exceptions above let independent receiving actions advance under their stated limits while cleanup retains that result. Direct-root flows retain the universal text invariant and turn anchor without fabricating a Lead report gate.

## Transfer order

Transfer mode has one order:

`cleanup PASS or qualifying deferred residue accounted -> final inventory -> bundle -> trusted verify -> post-transfer classification`

Any cleanup, lifecycle, Git, recovery, or tool-state mutation invalidates prior inventory. The transfer owner supplies the final inventory, bundle, verification, and post-transfer evidence; the coordinator only projects it.

For a user-admitted cleanup-and-transfer completion target, Root Lead owns post-transfer classification against the original admitted outcome, using current lifecycle-owner and Git-disposition results across every requested repository root and registered worktree. Reconcile the existing cleanup gate, selected work-item and owned bug-inbox obligations, material observed active tasks and required Git outcomes; the latest primary slice or a narrowed checkpoint cannot replace that target. Classify material tasks as target-required, independently active/unrelated, or ownership/completion unknown. Preserve unrelated/unknown state; resolve unknown semantics only where requested readiness depends on them. An unrelated valid active item is no global blocker, and no task closes from age, PASS or byte preservation. If a required obligation remains open, an intact, byte-verified ZIP is only a provisional recovery snapshot, not final handoff; report the exact unfinished obligations, owning cause, next action and resume point. An explicit direct transfer without cleanup or recovery-copy request may preserve unfinished work and complete its own copy outcome while the broader unfinished target stays provisional. No forced clean tree, commit, push, merge or automatic parking is admitted. Any subsequent owner mutation invalidates prior inventory; neither byte/history verification nor cached tracking refs prove semantic Git settlement.

## Terms and Abbreviations

- **Coordinator**: a workflow that scans, classifies, routes authorized owner work, and rechecks evidence.
- **Git**: the distributed version-control system and its repository state.
- **Lead-managed flow**: a workflow whose root main conversation has `$lead` active and owns mechanical acceptance.
- **RepoCleanupReportV1**: the transient repository-cleanup report contract.
- **ResourceRowV1**: one transient resource ownership and settlement row.
