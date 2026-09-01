# Repository Cleanup Coordination

`$repo-cleanup` is the common semantic front door for a clean-repository request and for repository transfer preparation. It coordinates read-only discovery and current evidence; it is not a deletion, lifecycle, Git, transfer, or process-control implementation.

## Ownership

The coordinator performs only `scan -> classify -> route -> recheck`. It may classify workspace resources itself, but it projects lifecycle, Git, and transfer results from the exact existing owner evidence. It does not recompute those owners' predicates or turn its report into approval.

Existing owners remain authoritative:

- the lifecycle owner applies admitted work-item moves and dispositions;
- `$knowledge-archivist` coordinates multi-item or drifted physical reconciliation;
- the exact Git-operation owner changes Git state;
- `$manual-repo-transfer` owns final inventory, bundle creation, trusted verification, and receiver restoration;
- each producing role owns settlement of its process trees, temporary worktrees or branches, locks, and generated residue.

The coordinator has no mutation engine, persistent state, receipt ledger, registry, cache, resumable state, or generic process killer. Every destructive action still requires the existing owner's genuine current-user authorization and safety checks.

## Universal no-self-residue invariant

No actor may claim lane or task `PASS`, hand off, commit, push, or declare transfer readiness while non-canonical agent-owned residue remains. This includes temporary or generated files, half-finished alternatives, dead or superseded code, temporary plans/reports/logs without an accepted pointer, live process descendants, handles, locks, temporary worktrees or branches, and quarantine or recovery roots.

Pre-existing user state remains untouched. Ambiguous ownership preserves the state and blocks destructive action. Each selected resource has a current-invocation `ResourceRowV1`; unknown ownership, identity, classification, settlement, or disposition makes that row `unclassified` and yields `REVISE`.

The only general exemption is owner/config-identified disposable material on an ephemeral temp volume. The fixed safe-floor and preferred-target hysteresis, its input validation, and the exact `ResourceRowV1` evidence are canonically owned by the installed `$repo-cleanup` `SKILL.md`; there is no repository-local threshold override.

## Current-invocation report

`RepoCleanupReportV1` is a bounded, transient, nonauthorizing projection. It binds the physical repository identity, observed `HEAD` or unborn state, selected trigger and mode, resource rows, finite predicate rows, observation time, and exact owner-evidence references. It is returned in-band and is never persisted or reloaded.

Only Lead-managed flows use the mechanical report gate. A missing, stale, incomplete, or non-zero-residue report yields `REVISE:self-residue`. Direct-root flows retain the universal text invariant and turn anchor without fabricating a Lead report gate.

## Transfer order

Transfer mode has one order:

`cleanup PASS -> final inventory -> bundle -> trusted verify -> post-transfer classification`

Any cleanup, lifecycle, Git, recovery, or tool-state mutation invalidates prior inventory. The transfer owner supplies the final inventory, bundle, verification, and post-transfer evidence; the coordinator only projects it.

## Terms and Abbreviations

- **Coordinator**: a workflow that scans, classifies, routes authorized owner work, and rechecks evidence.
- **Git**: the distributed version-control system and its repository state.
- **Lead-managed flow**: a workflow whose root main conversation has `$lead` active and owns mechanical acceptance.
- **RepoCleanupReportV1**: the transient repository-cleanup report contract.
- **ResourceRowV1**: one transient resource ownership and settlement row.
