---
name: repo-cleanup
description: Coordinate read-only repository cleanup and prepare-for-transfer requests by classifying current state, routing separately authorized work to existing owners, and rechecking evidence; when work-items/ is selected, enumerate every immediate child exactly once and never treat audit PASS as the census; never use as a deletion or process-killing engine.
---

# Repository Cleanup

Coordinate one current invocation through `scan -> classify -> route -> recheck`. Return `RepoCleanupReportV1` in-band. The report is never persisted or reloaded and never authorizes mutation.

This skill has no mutation engine, state machine, process killer, lifecycle or Git writer, transfer implementation, persistent receipt, ledger, registry, cache, or resumable state. It never deletes, moves, terminates, unlocks, rewrites, commits, pushes, or archives. Existing owners retain every action and approval boundary.

## Select the mode

Use semantic intent classification, not a phrase parser.

| Imperative user intent | Mode |
| --- | --- |
| explicit `$repo-cleanup` | requested/default mode; preserve any transfer intent |
| explicit `$manual-repo-transfer` with no cleanup intent | invoke `$manual-repo-transfer` directly; do not activate this skill |
| `prepare for transfer`, `prepare repo for transfer`, `подготовь к переносу`, `подготовь репозиторий к переносу` | transfer |
| `clean repo`, `clean the repo`, `почисти репозиторий`, `убери репозиторий` | clean |

Explicit `$repo-cleanup` wins. Compound prepare-plus-cleanup intent performs one cleanup followed by one transfer chain; never invoke cleanup twice. Quoted, code-fenced, documentation, and example mentions do not trigger. Near-misses include `clean code`, `clean build`, `clean target`, `copy repo`, `transfer file`, `prepare release`, `archive work item`, and `close work item`.

## Scan and classify

1. Bind the physical repository identity and current `HEAD`, or record the unborn state. Take a pre-mutation Git/resource census. Treat prior cleanup reports as nonexistent.
2. Use governance plus existing read-only inventories and audits. For Orchestrarium work-item structure, project the exact current result of `python scripts/check-work-items-state.py`; do not duplicate its logic.
3. When `work-items/` is selected, enumerate every immediate child exactly once as `category | derived | repository-local exception | unknown`; audit `PASS` does not satisfy this census. An `unknown` remains preserved and yields `REVISE`.
4. Create one `ResourceRowV1` for every selected resource. Direct-root work derives rows only from its own census and tool/resource actions.
5. Project lifecycle, Git, and transfer predicate rows only from one exact existing owner result. Missing, stale, null, cross-repository, cross-`HEAD`, or incomplete evidence yields `REVISE`; never combine partial owner evidence.

### ResourceRowV1

Each transient row contains:

- category;
- creator/adopter role + run;
- exact identity;
- `preexisting` flag;
- settlement probe and current result;
- disposition.

An absent or unknown field, invalid exception, or missing settlement result classifies the row as `unclassified`, preserves the resource, and yields `REVISE`. Pre-existing user state is untouched. Ambiguous ownership never authorizes deletion.

Agent-owned residue includes temporary/generated artifacts, half-finished alternatives, dead or superseded code/helpers/docs/names/registry entries, live process descendants, temporary worktrees or branches, locks, handles, subscriptions, transactions, quarantine/recovery roots, tombstones, and temporary reports/plans/logs/captures/caches/scratch roots without an accepted canonical pointer.

### Ephemeral volume hysteresis

Only owner/config-identified disposable material on an ephemeral temp volume may use disposition `ephemeral-volume-exempt`. Let `freeRatio = freeCapacityBytes / volumeCapacityBytes`.

- Require readable `volumeCapacityBytes > 0` and `freeCapacityBytes` within `[0, volumeCapacityBytes]`.
- When `freeRatio >= 0.20`, classified disposable material may remain exempt. Exactly `0.20` does not trigger cleanup.
- When `freeRatio < 0.20`, route action to the existing owner. The owner may delete only classified disposable material until `freeRatio >= 0.30` or candidates are exhausted. Exactly `0.30` satisfies the preferred target.
- `cleanupCandidateBytes` is accounting and deletion-bound evidence, never a trigger. There is no urgent tier or local threshold override.
- Invalid or unknown capacity, identity, or classification preserves data and yields `REVISE`.
- Sensitive data, live handles/processes, correctness or lifecycle errors, and explicit user requests override exemption.
- If classified candidates are exhausted while `freeRatio < 0.20`, preserve all other state and return `REVISE:cleanup-capacity-unresolved`. Reaching the `0.20` safe floor without the `0.30` preferred target is nonblocking.

An exempt row also records owner/config volume identity, `cleanupCandidateBytes`, `volumeCapacityBytes`, `freeCapacityBytes`, the fixed thresholds above, computed ratio, and override evidence.

## Route authorized owner work

The report supplies no approval. Route only separately authorized work:

- work-item changes to the lifecycle owner; route complete multi-item or drifted reconciliation to `$knowledge-archivist`;
- Git changes to the exact Git-operation owner;
- final inventory, bundle, trusted verification, and receiver restoration to `$manual-repo-transfer`;
- process trees, temporary worktrees/branches, locks, and generated residue to the producing role.

Owners retain their existing genuine current-user approval, no-follow traversal, exact-target, drift, rollback, redaction, and postcondition requirements. If authority is absent, report the owner/action needed without acting.

When the host refuses a validated owner action before execution, preserve the exact target. This is a host-policy denial, not an operating-system or filesystem lock, access, or permission error returned after an owner attempts the action; those target-side failures remain ordinary unsettled residue and do not open this route. In the existing `ResourceRowV1` identity, settlement-probe/result, and disposition fields, record the requested action, pre-action and post-refusal settlement probe results, disposition `preserved`, the redacted refusal reason, and the owner/action still needed; add no disposition or report state.

Do not evade a host-policy denial: no alternate shell, API, provider, command shape, retry, or allow-rule is allowed, and do not relax configuration or rename, move, or truncate the target. Only a genuine host-supported per-action permission route may be requested, and only for the same validated action. Without that route or grant, hand the exact operator action to the root main conversation and its existing current work-item while `$repo-cleanup` remains transient. Repeat cleanup only after a material condition change and fresh same-target ownership, identity, and settlement checks; never run a blind per-turn retry loop.

A denied target may be explicitly deferred only when fresh checks prove it is an ordinary empty agent-owned disposable directory, including no hidden children; it is not a link or reparse point, has no live handle, process, subscription, transaction, lock, or other active resource, and cannot affect or be required by the functional result, accepted artifact, or any downstream action. Keep its existing `ResourceRowV1` disposition `preserved`. In the existing current work-item `status.md`, note the current probes, requested action, redacted denial reason, owner, and concrete condition for resuming cleanup. Add no registry, engine, schema, report status, daemon, or marker file. Unknown, sensitive, live, valuable, non-empty, or correctness-, lifecycle-, security-, or delivery-affecting targets cannot use this exception.

Independent non-overlapping work continues. Deferral never settles cleanup: the affected cleanup predicate and all dependent zero-residue predicates remain `fail`, the row remains residue, and neither the report nor the cleanup lane may claim `PASS` or zero residue. An independently verified delivery, handoff, commit, or transfer may nevertheless proceed only when all of that action's own gates pass, no action depends on the deferred directory, and the handoff reports the exact residue and resume condition. This is not a waiver of any other blocker or removal authority.

### User-selected manual quarantine inside `.scratch`

Manual quarantine is a separately selected user operation, not a fallback after deletion is denied. A deletion refusal grants no move authority. The root main conversation may route a quarantine move only when the user independently selects this mode, authorizes the exact source and destination, the existing producing owner retains the action, and the host permits that move. If the host forbids the mutation, preserve the source and report the refused action; do not try another mutation path.

Only confirmed trash already inside the repository-local `.scratch/` is eligible. Exclude `.scratch/` itself, `.scratch/trash/` and all its descendants, links or reparse points, active or in-use resources, canonical artifacts, and anything valuable, ambiguous, unclassified, or not proven disposable. This mode never reaches outside `.scratch/`.

Map each eligible source to exactly `.scratch/trash/YYYY-MM-DD/<path-relative-to-.scratch>`. For example, `.scratch/build/run.log` maps to `.scratch/trash/YYYY-MM-DD/build/run.log`. Bind the physical repository and `.scratch/` root once, keep every source and destination under that same root without following links, and reject a source that is the destination, contains it, or lies beneath it. Before moving, the producing owner keeps a transient in-band no-follow tree inventory and checksums of every ordinary file, proves no process or active resource uses the source, and proves that every selected destination is absent. The date container may already exist only when it is a verified ordinary non-link directory under the bound quarantine root. A collision at any selected destination stops the whole pending set: do not merge selected source trees, overwrite, or generate a suffix.

The producing owner performs only the explicitly authorized literal-path moves. After each move, it proves the destination exists with the same inventory and checksums and that the source is absent. On any failure, stop, preserve any completed moves and untouched sources, and report every exact source/destination state; do not claim completion or silently roll back. Restoration is another separately authorized owner action and is allowed only when the original `.scratch/` path is vacant and the same no-follow checks pass.

No agent deletes anything in `.scratch/trash/`, including during a later cleanup. The human operator alone may separately delete the whole quarantine tree. Until then, report `quarantine prepared; manual deletion pending`, never `deleted`, cleanup `PASS`, or zero residue. Record only a necessary recovery list in an existing current work-item `status.md` when continuation needs it; add no manifest, registry, schema, daemon, helper, or new report/disposition state. Transfer inventory and selection evidence must explicitly account for every retained quarantine entry, including policy-restricted entries; none may be silently excluded.

## Recheck from scratch

After owner work, discard every prior observation. Rebind repository identity and `HEAD`/unborn state, rerun the exact existing owner probes, rebuild all rows, and return one fresh report. Do not write the report into the repository or load an earlier one.

### RepoCleanupReportV1

Return:

- repository physical identity and observed `HEAD` or unborn state;
- matched trigger and selected mode;
- current `ResourceRowV1` rows;
- finite `PredicateRowV1` rows;
- row-derived counts and final `PASS | REVISE | BLOCKED`.

Each `PredicateRowV1` contains predicate ID, subject identity, exact owner-evidence digest/reference, physical repository identity, `HEAD`/unborn binding, observation time, and `pass | fail | not-selected`.

Finite predicate IDs:

- workspace: `WS-CLASSIFIED`, `WS-SELF-RESIDUE-ZERO`, `WS-PREEXISTING-UNTOUCHED`, `WS-EPHEMERAL-EXEMPT-VALID`;
- work-items: `WI-EXISTING-AUDIT`, `WI-UNIQUE-LOCATION`, `WI-NO-TERMINAL-CURRENT`, `WI-NO-PENDING-MANIFEST`, `WI-CLOSE-EVIDENCE`, `WI-README-CURRENT`, `WI-NO-STANDALONE-DUPLICATE`, `WI-RELATIONS-RESOLVE`, `WI-SEMANTIC-CURRENT`, `WI-OWNED-RESIDUE-ZERO`;
- optional Git: `GIT-CLASSIFIED`, `GIT-TEMP-RESOURCES-ZERO`, `GIT-PREEXISTING-UNTOUCHED`;
- transfer: `XFER-ORDER`, `XFER-TRUSTED-VERIFY`, `XFER-POST-CLASSIFIED`.

Counts derive only from rows. Valid `ephemeral-volume-exempt` rows are excluded from residue counts. `PASS` requires every mode-required predicate to pass, zero unclassified rows, and zero row-derived residue. Git or transfer rows may be `not-selected` only when the bound mode excludes that phase. A valid active work-item is not residue.

## Transfer mode

Enforce exactly:

`cleanup PASS or qualifying deferred residue accounted -> final inventory -> bundle -> trusted verify -> post-transfer classification`

Qualifying deferred residue is exactly the host-policy-denied directory exception above; it leaves cleanup non-`PASS`. Final inventory follows the last cleanup, lifecycle, Git, recovery, or tool-state mutation and, with a deferral, the inventory and selection process explicitly accounts for the target and proves that no valuable data is silently omitted. `$manual-repo-transfer` supplies each transfer result; project it without reevaluation. Transfer preparation grants no delete, wipe, commit, push, publication, removal, or external-copy authority.

## Stop and safety rules

- Missing/stale/incomplete owner evidence or unclassified state is `REVISE`, not a guessed `PASS`.
- Use `BLOCKED` only for a real external blocker.
- Never follow links or broaden an owner's mutation scope.
- Redact credentials, remotes, secrets, customer data, raw logs, and machine-local paths.
- On Windows, preserve junction/reparse refusal, literal paths, identity rechecks, and locked-file handling. On POSIX, preserve no-follow, device/inode, mount-boundary, and special-file refusal.
- No actor may claim cleanup completion, cleanup `PASS`, or zero residue while non-canonical agent-owned residue remains. Delivery, handoff, commit, or transfer may advance with residue only under the exact host-policy-denied directory exception above: all receiving gates pass, no receiving action depends on the directory, and the residue and resume condition are reported.

## Terms and Abbreviations

- **Git**: the distributed version-control system and its repository state.
- **POSIX**: Portable Operating System Interface conventions used by Unix-like systems.
- **RepoCleanupReportV1**: one transient, nonauthorizing cleanup projection.
- **ResourceRowV1**: one transient resource ownership and settlement row.
