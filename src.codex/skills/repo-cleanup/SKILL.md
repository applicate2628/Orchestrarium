---
name: repo-cleanup
description: Coordinate read-only repository cleanup and prepare-for-transfer requests by classifying current state, routing separately authorized work to existing owners, and rechecking evidence; never use as a deletion or process-killing engine.
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
3. Create one `ResourceRowV1` for every selected resource. Direct-root work derives rows only from its own census and tool/resource actions.
4. Project lifecycle, Git, and transfer predicate rows only from one exact existing owner result. Missing, stale, null, cross-repository, cross-`HEAD`, or incomplete evidence yields `REVISE`; never combine partial owner evidence.

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

`cleanup PASS -> final inventory -> bundle -> trusted verify -> post-transfer classification`

Final inventory follows the last cleanup, lifecycle, Git, recovery, or tool-state mutation. `$manual-repo-transfer` supplies each transfer result; project it without reevaluation. Transfer preparation grants no delete, wipe, commit, push, publication, or external-copy authority.

## Stop and safety rules

- Missing/stale/incomplete owner evidence or unclassified state is `REVISE`, not a guessed `PASS`.
- Use `BLOCKED` only for a real external blocker.
- Never follow links or broaden an owner's mutation scope.
- Redact credentials, remotes, secrets, customer data, raw logs, and machine-local paths.
- On Windows, preserve junction/reparse refusal, literal paths, identity rechecks, and locked-file handling. On POSIX, preserve no-follow, device/inode, mount-boundary, and special-file refusal.
- No actor may claim completion, `PASS`, transfer readiness, commit, push, or handoff while non-canonical agent-owned residue remains.

## Terms and Abbreviations

- **Git**: the distributed version-control system and its repository state.
- **POSIX**: Portable Operating System Interface conventions used by Unix-like systems.
- **RepoCleanupReportV1**: one transient, nonauthorizing cleanup projection.
- **ResourceRowV1**: one transient resource ownership and settlement row.
