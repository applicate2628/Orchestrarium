# Repository Cleanup Coordination

`$repo-cleanup` is the common semantic front door for a clean-repository request and for repository transfer preparation. It coordinates read-only discovery and current evidence; it is not a deletion, lifecycle, Git, transfer, or process-control implementation.

## Ownership

The coordinator performs only `scan -> classify -> route -> recheck`. It may classify workspace resources itself, but it projects lifecycle, Git, and transfer results from the exact existing owner evidence. When `work-items/` is selected, it enumerates every immediate child exactly once as `category | derived | repository-local exception | unknown`; audit `PASS` does not satisfy this census. It does not recompute those owners' predicates or turn its report into approval.

Existing owners remain authoritative:

- the lifecycle owner applies admitted work-item moves and dispositions;
- `$knowledge-archivist` coordinates multi-item or drifted physical reconciliation;
- the exact Git-operation owner changes Git state;
- `$manual-repo-transfer` owns final inventory, bundle creation, trusted verification, and receiver restoration;
- each producing role owns settlement of its process trees, temporary worktrees or branches, locks, and generated residue.

Task scratch under `.scratch/work-items/<work-item-slug>/` is disposable work-item storage, not an archive: producers promote required load-bearing results to canonical artifacts, finish the task rather than endlessly sorting scratch, then the producing owner settles its temporary state. Retain legacy scratch only until its recovery or transition settles; unfinished, foreign, ambiguous, or denied state remains preserved.

The coordinator has no mutation engine, persistent state, receipt ledger, registry, cache, resumable state, or generic process killer. Every destructive action still requires the existing owner's genuine current-user authorization and safety checks.

When the host refuses a validated owner action before execution because a host policy denies it, preserve the exact target. Do not confuse that denial with an operating-system or filesystem lock, access, or permission error returned after an attempted action; target-side failures remain ordinary unsettled residue. Use the existing `ResourceRowV1` identity, settlement-probe/result, and disposition fields to record the requested action, pre-action and post-refusal settlement probe results, disposition `preserved`, the redacted refusal reason, owner, and needed action. Do not evade the refusal: no alternate shell, API, provider, command shape, retry, or allow-rule is allowed; neither are configuration relaxation, rename, move, or truncation. Only a genuine host-supported permission route for the same validated action may be requested. Without that route, hand the exact action to the root main conversation and its existing current work-item. Repeat cleanup only after a material condition change and fresh same-target checks, never as a blind per-turn loop. Independent non-overlapping work continues, but dependent zero-residue predicates remain `fail`.

The target may be explicitly deferred only when fresh checks prove an ordinary empty agent-owned disposable directory, including no hidden children, link or reparse identity, live handle/process/lock/other active resource, valuable data, or dependency on the functional result, accepted artifact, or downstream action. Keep disposition `preserved`; use the existing current work-item `status.md` to note current probes, requested action, redacted reason, owner, and resume condition. Create no registry, engine, schema, report status, daemon, or marker file. Unknown, sensitive, live, valuable, non-empty, correctness-affecting, or delivery-affecting items cannot use the exception.

Deferral leaves cleanup incomplete: the affected cleanup predicate and all dependent zero-residue predicates remain `fail`, the row remains residue, and cleanup never becomes `PASS` or zero residue. An independently verified delivery, handoff, commit, or transfer may proceed only when all its own gates pass, it has no dependency on the directory, and it reports the exact residue and resume condition. The exception grants no removal authority and waives no other blocker.

## User-selected manual quarantine inside `.scratch`

Manual quarantine is a separately selected user operation, not an automatic fallback after a denied deletion. The refusal grants no move authority. The root main conversation may route the move only after the user independently selects manual quarantine and authorizes the exact source and destination, the existing producing owner retains the action, and the host permits it. A host refusal preserves the source and ends mutation attempts; another shell, application programming interface (API), command form, or move route is not a substitute.

Eligible sources are confirmed trash already within the repository-local `.scratch/`. The `.scratch/` root, `.scratch/trash/` and its descendants, links or reparse points, active or in-use resources, canonical artifacts, and valuable, ambiguous, unclassified, or unproven data are excluded. Each source maps exactly to `.scratch/trash/YYYY-MM-DD/<path-relative-to-.scratch>` under the same physically bound `.scratch/` root. The source cannot equal, contain, or be beneath its destination. Before a move, the producing owner keeps a transient in-band no-follow inventory and ordinary-file checksums, proves no process or active resource uses the source, and proves that every selected destination is absent. The date container may already exist only when it is a verified ordinary non-link directory under the bound quarantine root. A collision at any selected destination stops the whole pending set: there is no selected-source-tree merge, overwrite, or generated suffix.

The producing owner performs only the explicitly authorized literal-path moves. It then proves that each destination exists with identical inventory and checksums and that its source is absent. A failure stops the operation; completed moves and untouched sources are preserved and their exact states are reported without a completion claim or silent rollback. Restoration is a separately authorized owner action and requires the original `.scratch/` path to be vacant plus the same no-follow checks.

No agent deletes anything within `.scratch/trash/`, including during later cleanup. The human operator alone may separately delete the whole quarantine tree. Until then, the human-facing result is `quarantine prepared; manual deletion pending`, never `deleted`, cleanup `PASS`, or zero residue. Only a necessary recovery list may be recorded in an existing current work-item `status.md`; this mode adds no manifest, registry, schema, daemon, helper, or report/disposition state. Transfer inventory and selection evidence explicitly accounts for all retained quarantine entries, including policy-restricted entries, without silently excluding them.

## Universal no-self-residue invariant

No actor may claim lane or task `PASS`, hand off, commit, push, or declare transfer readiness while non-canonical agent-owned residue remains, except for the bounded independent-action rule above; even there, cleanup itself remains non-`PASS` and the residue stays visible. This includes temporary or generated files, half-finished alternatives, dead or superseded code, temporary plans/reports/logs without an accepted pointer, live process descendants, handles, locks, temporary worktrees or branches, and quarantine or recovery roots.

Pre-existing user state remains untouched. Ambiguous ownership preserves the state and blocks destructive action. Each selected resource has a current-invocation `ResourceRowV1`; `unknown` remains preserved, and unknown ownership, identity, classification, settlement, or disposition makes that row `unclassified` and yields `REVISE`.

The only general exemption is owner/config-identified disposable material on an ephemeral temp volume. The fixed safe-floor and preferred-target hysteresis, its input validation, and the exact `ResourceRowV1` evidence are canonically owned by the installed `$repo-cleanup` `SKILL.md`; there is no repository-local threshold override.

## Current-invocation report

`RepoCleanupReportV1` is a bounded, transient, nonauthorizing projection. It binds the physical repository identity, observed `HEAD` or unborn state, selected trigger and mode, resource rows, finite predicate rows, observation time, and exact owner-evidence references. It is returned in-band and is never persisted or reloaded.

Only Lead-managed flows use the mechanical report gate. A missing, stale, incomplete, or non-zero-residue report yields `REVISE:self-residue`; only the exact deferred-directory exception above lets an independent receiving action advance while cleanup retains that result. Direct-root flows retain the universal text invariant and turn anchor without fabricating a Lead report gate.

## Transfer order

Transfer mode has one order:

`cleanup PASS or qualifying deferred residue accounted -> final inventory -> bundle -> trusted verify -> post-transfer classification`

Any cleanup, lifecycle, Git, recovery, or tool-state mutation invalidates prior inventory. The transfer owner supplies the final inventory, bundle, verification, and post-transfer evidence; the coordinator only projects it.

## Terms and Abbreviations

- **Coordinator**: a workflow that scans, classifies, routes authorized owner work, and rechecks evidence.
- **Git**: the distributed version-control system and its repository state.
- **Lead-managed flow**: a workflow whose root main conversation has `$lead` active and owns mechanical acceptance.
- **RepoCleanupReportV1**: the transient repository-cleanup report contract.
- **ResourceRowV1**: one transient resource ownership and settlement row.
