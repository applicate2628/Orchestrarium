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

Producing owners retain preflight-to-action control flow: consume the selected owner/action's actual positive proof before mutation; null, missing, wrong-type, failed or ambiguous required proof terminates that attempt before effects, never reaches unconditional or later independent removal. Apply the selected contract's no-follow/ownership/provenance predicates, not a blanket link ban or guessed stricter identity rule: positively admitted disposal of an owned link itself may preserve its foreign target without traversal. Existing public assistance or declared owner-equivalent execution retains the same guarantees; this read-only coordinator grants no action. Keep failed preflight/action-not-attempted distinct from attempted cleanup, partial failure and observed postcondition in existing evidence.

Task scratch under `.scratch/work-items/<work-item-slug>/` is disposable work-item storage, not an archive: producers promote required load-bearing results to canonical artifacts and settle selected temporary dispositions under the shared Engineering hygiene rule. Unfinished, foreign, ambiguous or denied state remains preserved; a fulfilled general manual handoff does not replace lifecycle receipt or resource settlement requirements.

The coordinator has no mutation engine, persistent state, receipt ledger, registry, cache, resumable state, or generic process killer. Every destructive action still requires the existing owner's genuine current-user authorization and safety checks.

When the host refuses a validated owner action before execution because a host policy denies it, preserve the exact target under the shared host-denial and artifact-disposition rules. This is distinct from an attempted OS/filesystem error. In existing `ResourceRowV1` fields retain the requested action, pre-action and post-refusal settlement probe results, disposition `preserved`, redacted refusal reason, owner and needed action. For the same validated action there is no alternate shell, API, provider, command shape, retry, or allow-rule. A separately user-selected operation is not inferred from that refusal and cannot bypass a denial covering it. Hand the unresolved action to the root main conversation and its existing current work-item; record current reason/resume condition/next step. After a material condition change reassess ownership/identity/settlement/current authority before treating the old refusal as current; reassessment grants no mutation. Independent non-overlapping work continues; dependent unmet-disposition or explicit physical-deletion predicates remain `fail`.

The target may be explicitly deferred only when fresh checks prove an ordinary empty agent-owned disposable directory, including no hidden children, link or reparse identity, live handle/process/lock/other active resource, valuable data, or dependency on the functional result, accepted artifact, or downstream action. Keep disposition `preserved` and keep the `status.md` record required above current with these fresh deferral probes. Create no registry, engine, schema, report status, daemon, or marker file. Unknown, sensitive, live, valuable, non-empty, correctness-affecting, or delivery-affecting items cannot use the exception.

Deferral leaves cleanup incomplete: the affected cleanup predicate and all dependent zero-residue predicates remain `fail`, the row remains residue, and cleanup never becomes `PASS` or zero residue. An independently verified delivery, handoff, commit, or transfer may proceed only when all its own gates pass, it has no dependency on the directory, and it reports the exact residue and resume condition. The exception grants no removal authority and waives no other blocker.

## General artifact-disposition consumer

The shared Engineering hygiene **Artifact disposition and project hygiene** rule in `AGENTS.md` is the single general owner for ordinary disposal, attempted-deletion fallback, user-selected manual quarantine and receiving. Every producing role applies it without invoking `$repo-cleanup`; this coordinator only projects the selected owner/action evidence. It creates no mutation engine, helper, schema, registry, receipt or mandatory cleanup stage.

Use the existing `ResourceRowV1` fields to bind the selected disposition, actual identity, owner proof and observed remaining action. A proved user-selected manual-deletion handoff may satisfy the agent duty while physical trash remains listed: report `quarantine prepared; manual deletion pending`, never physical deletion. Unproved handoff, lost bytes, collision, active writer, foreign/valuable evidence, denied action or an explicit unmet physical-deletion outcome still fails its dependent predicate. The coordinator neither grants a move nor asks the human to empty already accepted trash merely to advance independent work. Existing lifecycle scratch/receipt and creator-resource contracts stay distinct.

## Universal no-self-residue invariant

Before lane/task `PASS`, handoff, commit, push or transfer readiness, receive fulfillment of each selected agent disposition under the shared Engineering hygiene rule. Physically retained trash with a proved accepted manual handoff is accounted for but is not an unsettled agent obligation; it must not trigger an automatic human-emptying wait. Do not claim physical absence, settle active resources by moving files, discard required evidence or archive unfinished work. Unmet required disposition, unknown ownership/identity or explicit physical-deletion obligations remain visible and hold only the dependent action.

Pre-existing user state remains untouched. Ambiguous ownership preserves the state and blocks destructive action. Each selected resource has a current-invocation `ResourceRowV1`; `unknown` remains preserved, and unknown ownership, identity, classification, settlement, or disposition makes that row `unclassified` and yields `REVISE`.

The existing ephemeral-volume exemption is owned by the installed `$repo-cleanup` `SKILL.md`: fixed safe-floor/preferred-target hysteresis and exact `ResourceRowV1` evidence, with no repository-local threshold override. It is separate from a fulfilled manual-deletion handoff under the shared general rule.

## Current-invocation report

`RepoCleanupReportV1` is a bounded, transient, nonauthorizing projection. It binds the physical repository identity, observed `HEAD` or unborn state, selected trigger and mode, resource rows, finite predicate rows, observation time, and exact owner-evidence references. It is returned in-band and is never persisted or reloaded.

Only the existing selected report/Lead triggers require a complete current-invocation report. Missing/stale/incomplete evidence or unresolved agent dispositions yield `REVISE:self-residue`; an accepted proved manual handoff is evaluated as fulfilled without hiding its physical entries. An explicit physical-empty/deletion predicate still needs its own proof. The existing deferred-directory rule can permit independent work while that denied cleanup duty stays non-`PASS`; direct-root work consumes the same shared rule without fabricating a Lead report gate.

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
