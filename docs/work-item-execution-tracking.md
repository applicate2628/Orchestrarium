# Work-Item Execution Tracking

This runbook describes the operator path for tracking real agent work in Orchestrarium task memory.

Use it when a repository keeps active task memory under `work-items/active/<slug>/` and the main session (as Lead) must prove which roles ran, what they accepted, and which gates remain open.

Only the root main conversation holding Lead writes `agent-runs.jsonl`; a validated helper or wrapper may perform that write on the root's behalf. Specialists return their artifact, evidence, and gate result to that owner rather than appending their own events.

Lifecycle commands accept the documented repository or work-items root spelling. The shared identity owner acquires an untyped root from the selected lifecycle subject or existing canonical namespace, evaluates both supported interpretations together, and refuses ambiguous or unbound inputs. The actual declared request subject takes precedence over unrelated namespace tasks; same-subject cross-root ambiguity still refuses. Archive identity uses the existing classifier’s structural observation without reading unrelated bodies, while full inventory retains exact snapshots and validation. Proved repository/work-items roles normalize cheaply and travel explicitly across direct helpers and independently loaded H1 readers. Identity acquisition supplies no completion or mutation authority; digest, record and operation admission follow one unique binding. Subjectless topology observation outside a transaction, without a proved root role and with an absent contract, may read a directory alias; a linked namespace keeps its selected repository association. That returned path supplies no acquisition authority. Lifecycle and bound acquisition still validate the original path without following links before lock acquisition; the existing transaction then retains canonical repository/work-items roles and forwards the repository role to outer and nested operations. Repository-relative scratch, retention and receipt joins do not change with spelling or reinterpret a proved repository by its basename. Command-line transition recovery forwards the original caller path into one outer lifecycle participant before intent selection, recovery and nested README/receipt readback; positive `--apply` remains required. The state checker preserves its configured active/archive namespace while separately acquiring its base repository from the existing scope equations. Category, transfer and dependency checks use that same base; a selected component never replaces it. A different or unsafe caller root cannot borrow the held scope; original admission, missing-evidence, ownership and failure/cleanup guards still apply.

## Files

Normal public ledger, validation, checker and lifecycle operations omit both numerical ledger options. The owning operation derives finite admission from its actual selected descriptor/captured image and planned effects, then holds one final event/byte pair throughout its atomic transaction and receiving. An automatic terminal selects its current image, including independent completed writes since launch. An explicitly supplied positive `--ledger-max-events N --ledger-max-bytes B` pair remains a hard cap; partial and invalid pairs refuse. Python callers can pass the owning operation's actual `ledger_resource_budget=C`. No manual capacity estimate, history rewrite or unlimited fallback is required. The low-level resolver without selected demand retains its diagnostic defaults.

Each active work item should keep these files together:

| File | Purpose |
| --- | --- |
| `status.md` | Human-readable recovery state in the existing quick-fix four-fact or staged scalar form. |
| `agent-runs.jsonl` | Machine-readable append-only ledger for each launched or accepted role result. |
| `reviews/`, `design.md`, `plan.md`, or role artifacts | Accepted artifacts referenced by ledger events. |

`status.md` remains the readable recovery surface. `agent-runs.jsonl` is the state that validators can inspect.

Current dashboards and resume flows read staged scalar status plus `agent-runs.jsonl`: `status.md` supplies `Task`, `Current step`, `Last result`, `Next action`, and other optional top-level scalar relations, while the ledger supplies launched/running/terminal role state and reported model or effort. The quick-fix four-fact form remains current for admitted quick fixes. Legacy sectioned `status.md` records remain readable through an explicit compatibility fallback; maintaining one does not make its sections current-write requirements.

## Project root topology

Optional project-owned auxiliary roots are defined only by the shared
[`work-items root contract`](../shared/references/work-items-root-contract.md).
Use that reference for the exact JSON schema, reserved built-in roots,
non-reparse confinement, compatibility, and lifecycle failure/recovery rules;
do not infer topology from `README.md` or create an auxiliary root ad hoc.

## Full-goal completion receiving

This is the public recipe for Lead's **Full-goal completion workflow**, only when the original full/project Goal is enrolled through an admitted brief/epic. Existing ordinary lifecycle and trivial-task defaults remain valid. The Root binds original human scope, all criteria/operations, actual native Goal identity/objective/status, accepted root/member authority and current semantic proof in the existing records. Taskless preservation domains remain explicit; physical counts and archive labels do not establish delivery.

Use the source checker, or the corresponding checker in the explicitly selected installed Lead scripts directory. Select by the admitted layout; do not guess from cwd, ancestors or provider names. Verify the selected helper/imported closure after its writers release; a checker hash alone does not prove other changed owners. With the actual coordinator root and epic slug:

```text
python -B scripts/check-work-items-state.py --root <explicit-coordinator> --goal <actual-epic> --goal-phase <observe|preclose|final> --json
```

Consume the completed metadata frame and actual structured version-1 result: admissionId, phase, decision, criteria, roots/members and quote contract/admission/evaluator hashes/references. Match the original scope and current observations. The quote binds observation-time inputs, not an atomic native transaction; quiesce/recheck admitted inputs and native identity before acting. A missing/malformed/pending result is unavailable, not empty/clean. Exit zero may mean ready-for-last-close or eligible; only final/eligible can qualify for native completion.

At wider readiness, observe and act on continue/unverified with exact cause/owner/resume and ready work. After substantive semantic/review/custody/install/Git/resource proof is accepted, preclose ready-for-last-close allows the existing delivered coordinator close and actual archive/receipt/README/absence receiving, then epic terminal move/readback. Keep original roots/criteria intact and never archive unfinished work to reach covered-empty. Local Children remain same-root; the Goal block binds multi-root members. Independent item A may close while B remains active.

Fresh final must find the unique archived epic eligible with the same originals and accepted full proof. Root separately accepts current native identity/objective and quote binding immediately before supported completion, then authoritative same-target readback. Refusal/mismatch stays pending; no retry/bypass or post-hoc undo claim. Persist finalization resume before close; after archive use fresh final/native/readback, never active-ledger append, closure tamper or reverse move. Native completion bookkeeping is a consequence of eligibility, not a pending other action creating a self-cycle. Required adapter proof, Git and resources stay substantive. This Root route is no host-wide interception, atomicity guarantee or publication grant. Real original-root/native/install and required commission gates need their own accepted receiving evidence; synthetic core PASS cannot satisfy them.

## Canonical Staged Start

Classify new work before creating recovery state: use the existing quick-fix four-fact status or the staged lifecycle owner. `agent-run-ledger init` is compatibility-only for a legacy or manual recovery surface; it is not a creation path for newly admitted work.

`python scripts/mutate-work-item.py start` creates a staged `candidate -> active`
item with `admission.md`, `status.md`, and one schema-version 2 settled
`standalone` admission event in `agent-runs.jsonl` as one directory publication.
That event records the completed lifecycle admission only: `role: lead`,
`executionRole: main`, and `gate: none`; it does not claim a specialist launch
or an accepted artifact. A successful canonical staged start is immediately
valid, so do not run `init` just to create an empty ledger afterward.

## Initialize A Work Item

Use the helper only when migrating a legacy work item that already has `status.md`,
or when a manual recovery requires compatibility initialization before the first ledger event.
Canonical staged starts already have their admission event; the undelegated
quick-fix path remains ledger-free until real delegated work needs a ledger.

```bash
python scripts/agent-run-ledger.py --work-item work-items/active/<slug> init --primary-task "Implement accepted plan" --stage "Plan"
```

```powershell
python .\scripts\agent-run-ledger.py --work-item work-items\active\<slug> init --primary-task "Implement accepted plan" --stage "Plan"
```

The init command creates missing legacy status sections and `agent-runs.jsonl` without replacing existing task-memory content. It does not admit a new work item or select its quick-fix versus staged lifecycle.

## Append A Gate Event

An admitted execution uses one matching launch/terminal pair through its selected recording owner: Root for native and already-admitted direct external owner-equivalent execution, or actual supported tracked wrapper on Root's behalf when it runs. A direct external equivalent follows external-dispatch and uses real manual evidence plus Root's exact canonical pair/readback, never wrapper identity. Append a standalone event only for a genuine separate accepted result or substantive main-session gate action outside the pair. Ordinary calls preserve omission and let the selected owner admit the current transaction; explicit positive ceilings remain unchanged. Polling, progress, readback, or status acknowledgment alone adds no event.

```bash
python scripts/agent-run-ledger.py --work-item work-items/active/<slug> append \
  --role lead \
  --execution-role main \
  --status completed \
  --gate PASS \
  --scope <substantive-main-session-gate> \
  --artifact <accepted-item-relative-artifact> \
  --evidence "command:<actual-gate-check>"
```

```powershell
python .\scripts\agent-run-ledger.py --work-item work-items\active\<slug> append `
  --role lead `
  --execution-role main `
  --status completed `
  --gate PASS `
  --scope <substantive-main-session-gate> `
  --artifact <accepted-item-relative-artifact> `
  --evidence "command:<actual-gate-check>"
```

The append command validates the selected work item against its temporary candidate ledger before replacing `agent-runs.jsonl`. Refusal preserves the previous ledger bytes and attempts cleanup of the helper's owned candidate and lock; an actual cleanup refusal is reported with the retained state.

The writer and effective reader first authenticate Historical Compatibility (H1) metadata and the selected item's canonical ledger identity. A proved ordinary nonmember uses ordinary validation without acquiring unrelated historical ledger contents, artifacts, or derived views. Selected or potentially aliased historical members still require their complete receipt-bound group and authority checks; malformed or ambiguous metadata, unsafe selected identity, and invalid selected records remain failures. Ordinary success neither repairs the historical group nor clears its obligations. An ordinary append may return exit zero with `RESULT: PASS append` when its complete received result contains only unrelated qualification observations; full diagnostics remain visible, while required acquisition/admission failures, denied requested effects, or a selected invalid member still fail without ledger replacement.

Canonical ledger append and recovery append keep the exclusive journal lock, original captured identity/bytes, existing event or replay decision, and one whole-candidate validation. A real mutation uses the lifecycle owner's existing-parent native custody to create one exclusive candidate, retain that same object through qualification, run the original callback once, verify candidate and destination currentness, and receive its exact placement. A conflicting temporary entry is preserved. Empty existing ledgers remain distinct from absent destinations; absence uses create-only placement.

On Windows, only this selected ledger publication path queries the held parent's filesystem features. Advertised POSIX-style rename support selects native extended rename with replace and POSIX flags; a clear feature or genuinely missing optional query export retains legacy behavior without promising retained-reader support. A failed query refuses before candidate creation. Access and ReadOnly refusals remain visible, and an attempted operation never changes backend or retries automatically. Existing lifecycle publishers keep their existing mode. Successful unchanged replay makes no publication-only parent, feature query, candidate, callback, or placement attempt.

Placement receiving determines cleanup. Proved unchanged target and unchanged owned candidate permit ordinary abort cleanup. Received publication or unknown effects preserve the new/current objects and required custody while closing owned handles and returning any native, receiving, or cleanup failure. A first actual finalization failure propagates after the remaining required release attempts even when the body returns normally; an earlier raised failure retains its identity and receives secondary notes. The existing outcome composer retains cleanup-only failures without inventing a body failure. Each native cleanup cause and each additional actual diagnostic-delivery failure remains a separate occurrence in its existing cleanup phase; delivery does not replay the native occurrence. Recovery and the top-level writer forward these notes on their existing failure streams. An API success value alone is insufficient. These operations retain the current kill-safe old-or-new scope and do not add power-loss durability or authorize recovery of another project's journal.

Current external provider wrappers record the exact resolved model, effort, and policy-admitted sandbox, input/output, permission, or tool flags in both their `launch` and `terminal` events. The flags use the bounded provider-specific `launchFlags` string array on the wire and `--launch-flags-json` at the append command boundary. Positional prompts, arbitrary configuration, path-bearing, credential-bearing, malformed, or oversized flag bindings are rejected before launch or append. Older Version 2 events without `launchFlags` remain valid compatibility input; `realization` remains unsupported and is not inferred from this field.

`--execution-role` takes one of the canonical values from `shared/schemas/agent-runs.schema.json`: `main` (the one main-conversation identity, which also holds the Lead role), `internal`, `consultant`, `external-worker`, `external-reviewer`, or `external-brigade`. Orchestration weight belongs to the selected template and routing process; current staged status does not require a separate `orchestration: light | full-lead` field. Ledgers written before 2026-07-11 may carry the legacy value `lead`; validators and rollups read it as `main` (same owner), but a new append with `lead` is rejected — write `main`.

## Close External Review Findings

An external review records `role` and `executionRole` as `external-reviewer`; `assignedRole` identifies its professional reviewer. Its `external-nonauthorizing` terminal has empty `closesRunIds` and cannot authorize publication.

A later native professional PASS may close its findings through a launch-bound terminal or a genuine standalone event. Preserve launch provenance when a launch exists:

- The closer's `role` equals the target's `assignedRole`; any closer `assignedRole` must agree. Native `executionRole` stays `internal`, not the adapter role.
- `artifact` identifies each produced report. The native and external reports must have distinct paths.
- Matching nonblank `artifactIdentity` values identify the reviewed subject, not those report paths; `scope` must match exactly.
- `closesRunIds` names the exact external REVISE event. Existing own launch/profile, lane, and other authority checks still apply. Descriptive effort on another run imposes no closer requirement.

This flag fragment supplements an otherwise valid native PASS append; use the actual target's identity and scope:

```text
--artifact reviews/native-qa.md --artifact-identity topic:subject --closes external-review-event
```

Unrelated professions, subjects, scopes, and invalid report relations still fail.

## Close A Lead/Main QA Finding

For a `role=lead`, `executionRole=main` REVISE, the independent closer keeps its actual `role=qa-engineer`, `executionRole=internal`, and truthful `assignedRole` (if any). Its PASS names exactly one earlier target with `--closes <run-id>` and sets `--reviewed-role lead`. `assignedRole=lead` is not authority for this case, even alongside `reviewedRole`; Lead/main cannot close its own finding. Matching artifact, lane, evidence, and own launch/profile checks still apply. Reasoning effort is model-local descriptive data, so a previous run does not impose an effort ordering or an otherwise optional effort declaration on its closer. Other reviewer professions retain their existing C3 authority rule.

## Preserve A Linked-Worktree Review Artifact

When a parent work item must close a review of bytes in a distinct linked worktree, the independent reviewer first records the full approved artifact SHA-256, source worktree administration ID, artifact key, and verdict. The parent writer then uses ordinary `append` with `--source-worktree`, `--expected-source-worktree-id`, `--expected-reviewed-sha256`, `--expected-ledger-sha256`, and `--target-raw-line-sha256`, along with the exact target `--closes`, matching `--artifact` and `--lane`, and `--artifact-revision` equal to the approved SHA-256. All five custody inputs are required together. An ordinary append without them remains a local-artifact append, not a W-byte transfer.

Under its ledger lock, the writer verifies the exact open target and parent ledger, checks the linked worktree identity and current HEAD, captures only bytes matching the reviewer's pre-supplied digest, and creates or verifies `review-artifact-custody/<digest>` under the parent. The typed V2 `reviewArtifactCustody` row binds the target's raw-line hash and the snapshot; the validator hashes that local snapshot during replay and never substitutes an archived same-name file or requires the source worktree to remain mounted. Source paths may resolve through an in-worktree link, but may not escape that worktree. The parent snapshot itself must be an ordinary non-link file. Stale inputs, changed W bytes, and conflicting snapshots fail without a closer. The independent reviewer still owns the PASS verdict; custody alone grants none. Deploy matching writer, schema, and validator before a typed append; older closed-schema readers cannot replay it afterward.

## Retain An Active Historical PASS Artifact

Before removing an active work item's old artifact pointer, independently admit the exact original bytes and their SHA-256 (Secure Hash Algorithm, 256-bit) digest; a reviewed rewrite is not the original. Run `python scripts/mutate-work-item.py retain-pass-artifact --root <repo> --slug <slug> --run-id <id> --raw-line-ordinal <physical-line> --expected-raw-line-sha256 <line-sha256> --expected-ledger-sha256 <ledger-sha256> --source-artifact <repo-relative-original-copy> --expected-original-sha256 <original-sha256> --apply`. Supply lowercase hexadecimal digests. The line digest excludes its carriage-return/line-feed terminator; the initial ledger digest covers every captured byte. Omitted `--apply` refuses without publication. Success prints `WI-PASS-CUSTODY:` and stores one immutable association under the item plus a digest-only snapshot, without appending a verdict or changing finding/closure authority. Deploy the matching validator on every consuming machine before removing the old pointer; older readers still require it. Exact replay uses the same original request digests even after later ledger appends. Stale row/prefix inputs, rewritten source bytes, and snapshot drift refuse. The snapshot moves with an archived item. Rollback requires separate authorization to withdraw this association and only a newly owned, unreferenced snapshot; never remove a shared snapshot or rewrite ledger history.

## Validate One Work Item

Run this before stage closeout or archive movement.

```bash
python scripts/validate-work-item-state.py --work-item work-items/active/<slug>
```

```powershell
python .\scripts\validate-work-item-state.py --work-item work-items\active\<slug>
```

Validation fails for duplicate run IDs, running agents, missing ledger files, missing evidence for `PASS`, missing accepted artifacts, artifact paths that escape the work item, and inconsistent `BLOCKED` or `REVISE` gates.

### Archived-ledger compatibility

This compatibility is limited to validation of an already archived work item's immutable ledger. When a later Version 2 (V2) closing event explicitly names an earlier run through `closesRunIds`, the archive reader treats that target as eligible for closure even if its raw, unprojected event uses numeric `schemaVersion: 1`. The target must have literal `gate: REVISE`, belong to that archived work item, have a `runId` unique case-insensitively in the complete ledger, and pass the existing Version 1 (V1) per-event validator in isolation. The target must precede its closer, and the link must use its exact `runId` spelling. A missing, duplicate, malformed, projected, migrated, non-`REVISE`, or otherwise invalid target gets no compatibility authority.

This grants only the closure-target eligibility bit for that explicit relationship. It does not convert V1 to V2, make unrelated historical V1 `REVISE` events open obligations, validate an invalid V2 closer, or alter active-item validation. The common C1–C5 closure checks still decide order, unique discharge, reviewer/role/artifact/lane authority, and protected waivers; their existing errors remain visible. The reader writes no archive bytes and adds no command, manifest, or sidecar. A clean archived-reader result does not establish that other current-item obligations in the periodic checker are closed.

## Check All Active Work Items

Run the periodic checker at handoff boundaries, before publication review, or when resuming after interruption.

```bash
python scripts/check-work-items-state.py --root . --stale-hours 24
```

```powershell
python .\scripts\check-work-items-state.py --root . --stale-hours 24
```

`--root` points to the repository root. `--active-dir` defaults to `work-items/active`. `--stale-hours 0` disables age checks; any positive value reports running events older than that threshold. `--max-age-days <N>` reports (informational, never a FAIL) active items whose `<date>-` directory prefix is older than N days; the checker also reports any open `Depends-on` blockers and dangling dependency targets it derives from each item's `status.md`. These informational notes are printed as `info:` lines and never change the exit code — a blocked or aging active item is expected state, not a defect.

For deterministic automation, pass `--now`:

```bash
python scripts/check-work-items-state.py --root . --stale-hours 24 --now 2026-05-03T12:00:00Z
```

## Roll Up Ledger Events

```bash
python scripts/agent-run-ledger.py rollup --root .            # all active items
python scripts/agent-run-ledger.py --work-item work-items/active/<slug> rollup   # one item
python scripts/agent-run-ledger.py rollup --root . --json     # machine-readable
```

`rollup` aggregates `agent-runs.jsonl` events read-only: total runs, counts by role, execution-role, gate, and status, evidence coverage, and a malformed-line count. Use it for a quick execution audit across the active set or one item.

## Installed Runtime Paths

Global installs copy the helper surface into the production provider runtime.

| Provider | Installed helper directory |
| --- | --- |
| Codex | `$HOME/.agents/skills/lead/scripts/` |
| Claude Code | `~/.claude/agents/scripts/` |

Project installs copy to the matching project-local runtime:

| Provider | Project-local helper directory |
| --- | --- |
| Codex | `<repo>/.agents/skills/lead/scripts/` |
| Claude Code | `<repo>/.claude/agents/scripts/` |

Use the installed equivalent when the source checkout is not available in the target repository.

## Recover one invalid closure attempt

Use this recovery only when an earlier schema-version-2 closure event is valid as an individual event but invalid under the closure relation rules. The Lead-owned main conversation is the sole authority: the recovery record is fixed to `role=lead`, `executionRole=main`, and `scope=["ledger-recovery:closure-invalidation"]`. It invalidates the whole target event for derived closure and launch reduction; it never edits or removes the historical line.

Derive the target digest from the exact stored JSONL line bytes after removing only the terminal line ending: remove one `LF`, or one terminal `CRLF` pair, and hash every remaining byte with SHA-256. Do not parse and reserialize the event. Supply the exact earlier `runId` as `invalidatesRunId` and the lowercase digest as `invalidatesEventSha256`; the manual-check evidence must name both exact tokens.

```powershell
python scripts/agent-run-ledger.py --work-item work-items/active/<slug> recover-invalid-closure --run-id <new-recovery-run-id> --target-run-id <invalid-closer-run-id> --target-event-sha256 <64-lowercase-hex> --evidence "manual-check:<invalid-closer-run-id> <64-lowercase-hex>"
```

The target must be one unique earlier V2 non-launch, non-recovery closer, must remain valid under every per-event rule, and must fail the shared closure relation evaluation. A valid closer is authoritative and cannot be invalidated. V3 events, malformed or otherwise per-event-invalid records, duplicate or future targets, recovery chains, and a second invalidation of the same target are refused. In particular, `ledger-recovery:target-per-event-invalid` means this mechanism is not applicable; repair requires a separately designed typed migration, not a broader recovery event.

The writer holds the existing ledger lock, builds and validates a temporary candidate, replaces the ledger, then reads back and verifies the exact prefix, appended record, length, and digest. `RESULT: PASS recover-invalid-closure` means only **store-commit/readback** succeeded. It makes no `fsync`, power-loss, or crash-durability claim. A failure before replacement preserves the old bytes. A readback failure after replacement is indeterminate: inspect the ledger directly and do not rerun blindly or rewrite it back.

Invalidation removes every closure edge contributed by the target event. It can therefore reopen a `REVISE` obligation or a launch. Append an ordinary independently authorized replacement terminal or closure event through the normal writer; the invalidation itself never satisfies the reopened obligation.

## Recover one noncanonical historical ledger

Use this only after the Lead-owned main conversation admits one exact active-item
ledger whose nonblank lines are bounded, duplicate-key-free UTF-8 JSON objects
but are not canonical ledger events. Every row must fail the current event
validator; a declared schema Version 1, 2, or 3, a valid Version 1/Version 2
`runId`, a complete valid Version 3 identity tuple, any valid current event, or
a mixture containing one of those forms is refused unchanged. Lone generic
`status`, `gate`, `eventId`, or `operationId` fields remain opaque, as does a
seven-character `runId`; none of those field names alone is treated as
authority.

Capture the exact current ledger digest without parsing or reserializing its
rows. The same digest, new bounded operation identity, and strict Coordinated
Universal Time (UTC) value bind preflight, apply, replay, and any pre-append
rollback. ASCII hexadecimal digest casing is accepted and normalized; the
history filename and marker store lowercase.

Raw acquisition preserves every admitted byte, including CRLF/LF terminators,
blank or whitespace-only lines, and an unterminated final line. Each physical
line is limited to the existing 131,072-byte body plus an optional CRLF
terminator, with at most 4,096 nonblank events and a finite aggregate ceiling
of `4,096 * (131,072 + 2)` bytes. Blank padding and terminators consume that
aggregate ceiling; this intentionally tightens the former unlimited blank-line
admission while still allowing 4,096 maximum-body CRLF events.

```powershell
$ledger = 'work-items\active\<slug>\agent-runs.jsonl'
$sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $ledger).Hash

python -B scripts\agent-run-ledger.py --work-item work-items\active\<slug> recover-noncanonical-history --expected-ledger-sha256 $sha256 --operation-id <new-bounded-operation-id> --recorded-at <strict-UTC>

python -B scripts\agent-run-ledger.py --work-item work-items\active\<slug> recover-noncanonical-history --expected-ledger-sha256 $sha256 --operation-id <same-operation-id> --recorded-at <same-strict-UTC> --apply-admitted
```

Omitting both action flags performs a read-only preflight: it creates no lock,
temporary file, history blob, or marker. `--apply-admitted` holds the existing
item lock, preserves the original bytes beside the ledger as
`agent-runs.history.<lowercase-sha256>.jsonl`, validates one genuinely new
canonical marker, atomically replaces the ledger, and verifies exact readback.
The marker records only this recovery operation and has no historical launch,
terminal, `REVISE`, closer, artifact, evidence, provider, model, gate, identity,
or timestamp authority. `RESULT: PASS recover-noncanonical-history action=apply`
means the exact history blob and marker passed readback; it makes no `fsync` or
power-loss-durability claim. An exact blob plus exact marker replays without a
duplicate.

Continue only through the ordinary writer with new identities and times:

```powershell
python -B scripts\agent-run-ledger.py --work-item work-items\active\<slug> append --run-id <new-launch-run-id> --role <role> --execution-role internal --status running --gate none --scope <bounded-scope> --event-kind launch --started-at <new-started-at> --updated-at <new-started-at>

python -B scripts\agent-run-ledger.py --work-item work-items\active\<slug> append --run-id <new-terminal-run-id> --role <same-role> --execution-role internal --status completed --gate PASS --scope <same-bounded-scope> --event-kind terminal --launch-run-id <new-launch-run-id> --artifact <accepted-item-relative-artifact> --evidence "command:<verification>" --started-at <new-terminal-at> --updated-at <new-terminal-at>
```

Before any later append, the admitted operator may restore the exact opaque
bytes with the same binding:

```powershell
python -B scripts\agent-run-ledger.py --work-item work-items\active\<slug> recover-noncanonical-history --expected-ledger-sha256 $sha256 --operation-id <same-operation-id> --recorded-at <same-strict-UTC> --rollback-admitted
```

After a later append, rollback fails with
`WI-LEDGER-NONCANONICAL-ROLLBACK-NOT-EMPTY`. Other stable refusal classes are
`LOCKED`, `DRIFT`, `MALFORMED`, `CURRENT-EVENT`, `IDENTITY-BEARING`,
`HISTORY-CONFLICT`, `CANDIDATE-INVALID`, and `READBACK-INDETERMINATE`, each
prefixed by `WI-LEDGER-NONCANONICAL-`. A readback-indeterminate result requires
inspection or exact replay; it never authorizes an ad hoc ledger rewrite.

## Dispose one invalid-current row

Use this only after the user admits one exact current-schema-invalid row. This mode is separate from `recover-invalid-closure`: an individually valid relation-invalid closer continues to use that existing command, while `dispose-invalid-current` preserves one invalid target's exact bytes and makes no closure, gate, launch, terminal, `PASS`, or evidence authority claim.

Bind the target through the supplied Version 2 ledger manifest's exact sealed prefix. Its physical raw-line ordinal must be strictly greater than the manifest's `prefixLineCount`; the ordinal, `runId`, and SHA-256 must identify one unique suffix row. Hash the exact physical raw line including its terminal `LF`; do not parse and reserialize it.

```powershell
python -B scripts/agent-run-ledger.py --work-item work-items/active/<slug> dispose-invalid-current --run-id <new-disposition-run-id> --target-run-id <invalid-run-id> --target-raw-line-ordinal <positive-physical-line-ordinal> --target-event-sha256 <64-lowercase-hex> --ledger-manifest <ledger-manifest-v2.json> --evidence "manual-check:<invalid-run-id> <64-lowercase-hex-raw-line-sha256> <reason>"
```

For an ordinary unprojected, all-Version-2 ledger with no live H1 compatibility participants, select the separate whole-ledger binding instead of `--ledger-manifest`:

```powershell
python -B scripts/agent-run-ledger.py --work-item work-items/active/<slug> dispose-invalid-current --run-id <new-disposition-run-id> --target-run-id <invalid-run-id> --target-raw-line-ordinal <positive-physical-line-ordinal> --target-event-sha256 <64-lowercase-hex-physical-line-sha256> --expected-ledger-sha256 <64-lowercase-hex-whole-ledger-sha256> --evidence "manual-check:<invalid-run-id> <64-lowercase-hex-physical-line-sha256> <reason>"
```

The ordinary raw-V2 branch admits only a `completed` terminal whose isolated current-schema errors are exactly `invalid gate 'BLOCKED'` plus `BLOCKED gate requires blocked status` for bare `BLOCKED`, or exactly the status error for an accepted qualified `BLOCKED:<reason>` gate. Malformed or duplicate-key lines, non-V2 ledgers, control rows, valid targets, additional target errors, conflicting dispositions, and preimage digest drift refuse the append. An exact replay retains the existing bytes. Its effective reader skips only the disposed terminal's diagnostics and authority; the linked launch and all other obligations remain open.

The `manual-check` evidence must contain the exact target run ID and exact raw-line digest as standalone whitespace-delimited tokens. Forms such as `target=<id>` or `sha256=<digest>` do not satisfy that binding. The target must remain invalid under the unchanged current event validator. An exact replay is a no-op; a reused disposition `runId`, conflicting disposition, identity mismatch, H1 target inside the sealed prefix, or target that is now valid fails closed. `RESULT: PASS dispose-invalid-current` proves only the append transaction and exact readback; it does not claim `fsync` or crash durability.

For H1, appending the disposition does not activate compatibility. A refused current suffix-disposition request does not invalidate a separately verified historical activation or grant target authority, and it emits no disposition notice for that target; the requested target's blocking diagnostics and current obligations remain. Before an active compatibility receipt exists, the raw target errors remain. Only the active receipt-gated effective-view reader may suppress errors for that exact target, keep all authority axes false, and expose the ordered `disposition_notices` through the public read model. Every other row remains under unchanged validation. Ordinary raw V2 requires no H1 activation; the exported `load_effective_ledger_view` used by the work-items checker and `validate_work_item` consume the same disposition-effective ordinary context.

## Recover one mixed current V1/V2 ledger

Use the lifecycle owner only for an active, parseable, integer-Version-1/Version-2 ledger whose exact original lines must remain inspectable. This is one append-only batch, not `settle-legacy-ledger`, H1 activation, or the single-row `dispose-invalid-current` command. The request must explicitly cover every invalid current row; a valid-schema terminal with no valid earlier launch is also an explicit disposition target, even when no finding-class migration is needed. Unrelated diagnostics, overlapping targets, changed launch relations, duplicate case-insensitive run IDs, and Version 1/control targets refuse. A migrated unknown `findingClass` becomes protected `legacy-unclassified` at its original position; it remains a review target but gains no terminal, closer, artifact, or waiver authority. A disposed terminal has no authority on any axis. Neither control creates a launch or closes a review obligation.

The two existing digest codecs are intentionally distinct. `eventBodySha256` for `migrate-invalid-finding-class` hashes the original JSONL line *without* its `LF` or `CRLF` terminator, matching the migration anchor. `physicalLineSha256` for `dispose-invalid-terminal` hashes the complete original physical line *including* its terminator, matching the disposition control. `expectedLedgerSha256` hashes the entire original ledger byte stream. Do not substitute one row digest for the other or parse and reserialize the input to compute them. The original must have complete nonblank newline-terminated lines.

```json
{
  "schemaVersion": 1,
  "operationId": "bounded-recovery-id",
  "recordedAt": "2026-09-20T12:00:00Z",
  "workItem": "work-items/active/active-item-slug",
  "expectedLedgerSha256": "<whole-ledger-sha256>",
  "targets": [
    {
      "action": "migrate-invalid-finding-class",
      "rawLineOrdinal": 3,
      "runId": "review-run-id",
      "eventBodySha256": "<body-line-sha256>",
      "launchRunId": "earlier-launch-run-id"
    },
    {
      "action": "dispose-invalid-terminal",
      "rawLineOrdinal": 5,
      "runId": "invalid-terminal-run-id",
      "physicalLineSha256": "<full-physical-line-sha256>",
      "launchRunId": "recorded-launch-run-id"
    }
  ]
}
```

First run the exact request without the positive apply marker. This acquires and releases the normal ledger-writer lock, rebinds digest, row identity and relation, validates one complete candidate with open work allowed, reports targets and obligations with `applied:false`, and leaves ledger, history, receipt, status, and selector bytes unchanged. It does not approve a receiving-machine apply or establish source-versus-installed parity; verify those separately on that machine. For this operation, `beforeAuthority` is evaluated from the captured original and `afterAuthority` from the exact candidate under the same authenticated current admission. They are operation-bound comparisons, not ordinary raw-ledger booleans or claims about historical grants. Qualification-only `OBSERVATION` diagnostics from this recovery operation go to stderr, leaving its normal JSON result on stdout.

```powershell
python -B scripts/mutate-work-item.py recover-mixed-current-ledger --root . --request-file <reviewed-request.json>
```

Only after the separately required review and gates, apply that same request with `--apply-admitted`. The owner publishes `agent-runs.history.<original-ledger-sha256>.jsonl` create-once from the exact old bytes, validates and atomically appends all typed controls under the existing writer lock, reads back the complete suffix, then creates `agent-runs.mixed.<operation-id>.receipt.json`. A handled pre-append failure reclaims only newly owned unchanged staging/history; pre-existing or changed files are preserved and reported. An interrupted pre-append attempt may replay only exact owned bytes. A committed exact suffix with a missing receipt is reconstructed without appending again. Partial suffix, changed history, drift, or ambiguous residue fail closed without truncation. Normal append remains available afterward; default strict close/audit still reject open `REVISE` and launch obligations.

```powershell
python -B scripts/mutate-work-item.py recover-mixed-current-ledger --root . --request-file <reviewed-request.json> --apply-admitted
```

### General historical custody and qualified disposition (request Version 2)

The same `recover-mixed-current-ledger` command admits malformed application history without requiring a historical semantic run ID. Version 1 requests and receipts retain their existing migration/disposition behavior. Version 2 targets use `custody-invalid-history` or `dispose-history-custody`; they bind `sourcePrefixSha256`, `sourcePrefixBytes`, `rawLineOrdinal`, and `physicalLineSha256`. The prefix is the exact captured byte stream and the line digest includes its terminator. Missing or invalid old IDs remain opaque. All valid decoded IDs remain reserved, and case-insensitive collisions, forged work-item identities, conflicting valid terminal relations, or damaged owner controls refuse.

Admission appends a nonauthorizing `closure-invalidation` with `invalidationMode="historical-custody"` and `custodyAction="admit"`. It neither invents old timestamps/scope nor turns old output into a successful verdict. The existing evaluator conserves independently valid authority and closure effects, including valid orphan artifact/closer axes. The public obligation state exposes physically bound `unresolved_history` separately from real review/launch obligations. Fresh fully valid launches and terminals remain appendable; invalid fresh input still refuses the whole candidate. Default strict validation, ordinary close, and transfer reject unresolved historical holds with `WI-LEDGER-HISTORY-UNRESOLVED`.

A structurally exact ordinary invalidation whose current effect is unresolved may also enter this existing custody route. Its earlier unique closer, body digest, and every earlier review target must bind exactly. The preserved control cannot execute; the reducer withholds only that referenced closer's closing effect for all its targets, preserving independently proved terminal and artifact axes. Those original obligations remain visible until a different genuine current closer discharges them. Malformed, ambiguous, nested custody/migration, or foreign controls still refuse. Disposition cannot relabel dependent review obligations as bookkeeping, and resolving a hold never revives the old closing effect.

For a sealed History 1 (H1) prefix, the reader first verifies the complete existing profile `sealed-active-prefix-v1`, version 1, with its exact original wire, authority masks, digest domains and group oracle. That frozen prefix projection includes its format's effort-sensitive reduction; it proves compatibility identity, not current closure authority. A real fully verified base context qualifies sealed targets for custody before the final context binds the actual resulting holds. Live review and launch state always comes from the current reducer, including later suffix records. New seals retain genuine current-qualified closers even when the frozen format projection reports an open target. Missing, revoked, partial or corrupt proof never falls back to raw authority.

Disposition uses the same Version 2 command and positive `--apply-admitted` flag. One target is:

```json
{
  "action": "dispose-history-custody",
  "sourcePrefixSha256": "<admitted-prefix-sha256>",
  "sourcePrefixBytes": 123,
  "rawLineOrdinal": 7,
  "physicalLineSha256": "<complete-physical-line-sha256>",
  "kind": "non-obligating",
  "classificationRunId": "<actual-current-classification-run-id>",
  "resolutionRunIds": [],
  "evidence": [{"kind":"review","ref":"<classification-report>","result":"<exact recorded JSON result string>"}]
}
```

Accepted kinds are `non-obligating`, `current-evidence-covered`, and `admitted-historical-disposition`. Each requires an actual current internal Quality Assurance (`qa-engineer`) PASS classification against a digest-bound current acceptance contract and report. Its existing `review` evidence entry carries a strict JSON object encoded in the `result` string, with exact fields `schemaVersion:1`, `kind:"history-classification"`, `workItem`, the four-field `subject`, `currentContract:{ref,sha256}`, `report:{ref,sha256}`, `dispositionKind`, `findingClass`, and `requirements`. The report reference equals the record artifact and evidence reference; its digest equals `artifactRevision`. These are explicitly produced evidence fields, not fields automatically invented by the ledger writer.

Bookkeeping-only classification requires `findingClass:"other"` and empty requirements/resolutions. Covered current requirements are nonempty exact `{requirementId,role,scope,lane,minimumEffort}` objects. Each needs exactly one later qualified current reviewer PASS whose `history-resolution` result binds the same subject/contract, its own report, classification run, and requirement ID; profession, scope, lane and minimum effort must match. Specifically admitted irrecoverable bookkeeping additionally needs a target-bound `manual-check` statement with a strict `history-disposition-approval` result binding subject, contract, classifier/report digest, and `decision:"accept-irrecoverable-bookkeeping"`. Generic PASS, generic permission, caller-only evidence, missing fields, mismatched hashes and vacuous coverage cannot retire a hold. Actual ordinary obligations and protected/unclassified risk cannot be relabeled away.

The control uses `custodyAction:"dispose"` and a `historyDisposition` object containing exactly `kind`, `classificationRunId`, `resolutionRunIds`, `evidence`, and `boundEvents` (the owner-captured canonical event SHA-256 map by run ID). Every reader verifies this proof; a receipt alone grants no authority. Preview captures report/contract bytes without publishing files. Apply publishes those same captured bytes in the existing digest-only custody store and binds each referenced PASS to its exact raw-record/artifact snapshot association. Accepted evidence remains usable after the original report pointer changes. Abort reclaims only newly owned identity-bound evidence; reused or ambiguous data is preserved. Exact replay also validates a later valid suffix without appending controls twice or truncating history. A disposition retires only its bound bookkeeping hold; it does not close a real review or settle a launch. Strict validation and ordinary lifecycle close become available only when both sets are genuinely resolved.

## Settle one identity-bearing legacy ledger

Use this owner operation only for an active ledger whose complete frozen
population matches a closed, explicitly selected profile. The string-`1.0`
format uses `identity-ledger-v1-string`, profile version 1. The request
binds the complete ledger digest and must list every obligation reported by the
existing reducer exactly once. `preserve-open` takes an empty evidence list and
continues to block close; `satisfied-by-current-evidence` names one or more
existing repository-relative artifacts and their exact SHA-256 digests.

```json
{
  "schemaVersion": 1,
  "operationId": "bounded-id",
  "recordedAt": "2026-09-20T12:00:00Z",
  "workItem": "active-item-slug",
  "expectedLedgerSha256": "<sha256>",
  "profileId": "identity-ledger-v1-string",
  "profileVersion": 1,
  "settlements": [
    {
      "targetRunId": "legacy-run-id",
      "disposition": "satisfied-by-current-evidence",
      "evidence": [{"path": "work-items/active/active-item-slug/evidence.md", "sha256": "<sha256>"}]
    }
  ]
}
```

Preflight is the safe default and writes nothing:

```powershell
python -B scripts/mutate-work-item.py settle-legacy-ledger --root . --request-file <request.json>
```

After reviewing the reported identities and obligations, apply the same request
with the positive mutation marker:

```powershell
python -B scripts/mutate-work-item.py settle-legacy-ledger --root . --request-file <request.json> --apply-admitted
```

The original ledger remains an exact prefix. The owner appends only current
closure-invalidation records for `satisfied-by-current-evidence`, validates the
complete after-image, and commits the projection manifest, registry, ledger
suffix, and receipt under the lifecycle lock. Exact replay is a byte-identical
no-op. There is no public reverse command; failures during apply restore every
participant to its exact preimage.

For omission-valid historical identity records, explicitly select
`identity-record-v0`, profile version 1, through this same command and request
shape. Each raw record contains bounded string fields `runId`, `timestamp`,
`executionRole`, `status`, `gate`, `artifact`, `artifactSha256`, and `summary`.
Identities must be unique; timestamps use strict UTC; status is `completed`;
gate is `PASS` or `REVISE`; the artifact key is confined to the item and its
digest is 64 hexadecimal characters. Optional `candidateRevision` is 40
hexadecimal characters. Optional `provenance` contains exactly the string fields
`requestedProvider`, `resolvedProvider`, `actualExecutionPath`, and
`modelProfile`. Unknown fields and duplicate keys are refused.

This profile admits **only `preserve-open` with empty evidence** for every
reported obligation. Apply enrolls the complete frozen population in the
existing projection manifest and registry but appends no closing ledger rows;
exact bytes and run identities survive replay. Historical `PASS`, artifact
digests, summary, revision, and provenance remain nonauthorizing even when an
artifact currently matches. The typed projection grants only `REVISE`-target
eligibility, never launch, terminal, closer, or artifact-evidence authority.
It does not infer `role` from a profession-valued `executionRole` or synthesize
`role`,
`scope`, `workItem`, `evidence`, or a numeric schema version. Item association
belongs only to the request and manifest. The shared closure owner requires a
concrete, nonempty target profession before matching a closer's `role` or
`assignedRole`; missing, empty, or whitespace-only professions fail closed and
leave the obligation open. This also applies when generic projection combines
historical prefix rows with a current PASS suffix. Known-profession current and
string-`1.0` closures and the Lead/main pathway retain their contracts. Existing
projection revocation removes enrollment without rewriting raw records.

## Migrate one legacy obligation

This is the sole operator procedure for exactly two closed normalizations of a
legacy V2 terminal event. The original raw events stay byte-for-byte present.
`invalid-finding-class` changes only an unknown historical `findingClass` to
`legacy-unclassified`; `remove-string-scratch-evidence` removes only a present
string `scratchEvidence`. The caller selects neither a field nor a replacement:
the lifecycle owner derives the one allowed projection from
`--normalization-kind`.

### Eligibility and exclusions

| Input | Eligible? | Handling |
| --- | --- | --- |
| One unique earlier V2 `REVISE`, exact raw-line digest, complete diagnostic set `{LEDGER-EVENT-FINDING-CLASS-INVALID}` | Yes | The lifecycle owner generates the replacement; callers cannot provide it or select the class. |
| p95 V2 terminal with a present string `scratchEvidence`, valid earlier launch relation, and a valid remove-only replacement | Yes, only with `--normalization-kind remove-string-scratch-evidence` | The lifecycle owner removes exactly that key in the effective projection; the raw line, original status, gate, and every other field remain unchanged. |
| Relation-invalid C2/C1-C5 closer | No | Use `recover-invalid-closure` only when that separate contract admits it. |
| Malformed, duplicate-key, ambiguous identity, missing field, unsafe artifact/evidence, or any non-class defect | No | Stop without writing. No value is inferred or repaired. |
| V1, V3, or a ledger containing V3 | No | V1 has no V2 finding class; V3 keeps its separate reducer and writer. |
| Apply/revoke/closure-invalidation control event | No | Cross-mechanism targeting, chains, duplicate recovery, and cycles are forbidden. |
| architecture-pattern sibling | Type-eligible, not admitted by another item's operation | Require a separate explicit digest-bound invocation and its own gates. |

### Apply

Capture the current full-ledger SHA-256 and the exact target raw-line SHA-256
after removing only its terminal line ending. Then run the one lifecycle-owned
apply command:

```powershell
python scripts/mutate-work-item.py --root . migrate-legacy-ledger-obligation --slug <active-slug> --target-run-id <target-run-id> --target-event-sha256 <target-raw-sha256> --expected-ledger-sha256 <current-ledger-sha256> --operation-id <bounded-operation-id> --recorded-at <strict-UTC> --normalization-kind <invalid-finding-class|remove-string-scratch-evidence>
```

Before ledger replacement, the lifecycle owner stages the migration and admits the exact receipt target and any current/quarantine conflict. Atomic lifecycle writes use the same short-lived bound parent/leaf resource for relative exclusive temporary creation, replacement, readback, quarantine and unpublished-temp cleanup; a later pathname check is not write authority. Initial unsafe receipt admission refuses before the anchor and preserves ledger bytes. Default write resources release before legitimate directory moves; the migration receipt target spans only early admission through reconciliation.

`WI-LEDGER-MIGRATION-COMMITTED` is authoritative only after exact anchor readback and receipt reconciliation. The anchor is the commit marker; the receipt is a derived read model. A valid late anchor followed by failure remains causal pending state, not a rolled-back success or an invitation to append again. Exact committed replay reacquires its bound receipt target and reconciles without a duplicate anchor. Primary write failure stays primary; all cleanup attempts run, repeated write-phase failures retain their distinct causes/counts within the existing sanitized diagnostic bound, and cleanup-only failure stays nonzero. The migration receipt's exact fields are `operationId`,
`targetRunId`, `targetEventSha256`, `anchorRunId`, `anchorEventSha256`,
`beforeLedgerBytes`, `beforeLedgerSha256`, `afterLedgerBytes`,
`afterLedgerSha256`, `replacementEventSha256`, `normalizationKind`, `diagnosticId`,
`sourcePath`, `receiptPath`, and `recordedAt`. `findingClass` is present only
when the normalized target had one. Missing or conflicting derived receipt bytes are reconstructed only from the valid anchor and exact ledger through the same admitted bound receipt/read/quarantine owner. Boundary/native acquisition failures remain visible; byte mismatch keeps its existing atomic-byte diagnostic. Published bytes are never cleaned to hide a failure.

Native Windows receiving covers the bound write and recovery routes. The observed POSIX public workflow used Windows Subsystem for Linux on a Windows-mounted filesystem; it is not ext4, macOS or all-POSIX adversarial proof. Relative directory effects do not promise atomic absolute-path containment against privileged reparenting, and returned/reaped child processes do not prove physical release of a borrowed host context.

### Revoke before physical transition

Revocation is append-only and allowed only while the item is still active and
no transition intent or receipt exists:

```powershell
python scripts/mutate-work-item.py --root . revoke-legacy-ledger-obligation --slug <active-slug> --apply-run-id <apply-run-id> --apply-event-sha256 <apply-raw-sha256> --expected-ledger-sha256 <current-ledger-sha256> --operation-id <bounded-revoke-id> --recorded-at <strict-UTC>
```

`WI-LEDGER-MIGRATION-REVOKED` restores the original invalid diagnostic in the
effective view; it never deletes the apply anchor or the source line.

### Close with current-bug dispositions

The existing close command consumes the active item's `bug-dispositions.json`:

The supplied `closure.md` MUST contain nonempty `Closed`, `Outcome`, `Evidence`,
and `Residual risk` fields. `Closed` MUST exactly equal the requested
`--terminal-instant` and use strict UTC `YYYY-MM-DDTHH:MM:SSZ`.

```powershell
python scripts/mutate-work-item.py close --root . --slug <active-slug> --closure-file <closure.md-input> --terminal-instant <strict-UTC>
```

Ordinary directory `close` is the positive operation and omits `--apply`. That
flag belongs only to the separate `--legacy-evidence-file` close route, not an
extra confirmation for ordinary close.

When the active item has `agent-runs.jsonl`, ordinary `close` writes a schema
version 3 `lifecycle-transition-receipt.json` in the archive as part of the
same rollback-safe lifecycle transaction. The lifecycle owner binds the close
inputs and captured source ledger to the archived ledger and archive location,
and binds the README preimage (including captured absence) and historical final
digest, then verifies the written proof. This lets
existing history consumers recognize an ordinary ledger relocation; it does
not transfer successor or review ownership. An archived replay must match the
recorded closure and terminal instant, and a mismatch refuses. Existing
archives are not backfilled. This proof does not replace ordinary close's
current-result, bug-disposition, status, current-obligation, or README checks.

Incoming-link upkeep changes only captured hrefs that still name the same
target at its archive location. The lifecycle owner first admits the captured
record format, physical-current membership and mutability; category-known
current or terminal semantic states can then receive this href-only upkeep.
Status, identity, context, supersession meaning, other bytes and link fragments
stay unchanged: no semantic transition, retirement or invented `Terminal-at`
follows. For an active-document consumer owner, link upkeep requires only the
existing current-membership check; the full lifecycle template and recovery
validation still applies to the selected item being closed. Membership and UTF-8
refusals at this seam identify the work-items-relative consumer and captured status
paths, retain the failure code, and include the concrete cause. Current-state validation
and lifecycle-audit diagnostics are unchanged.
Read-only decision-format `V0`/`H1` records remain protected: if a physical href
needs rewriting, close refuses before effects rather than skipping that
consumer or changing its frozen bytes. Captured-byte/currentness checks, exact
target binding, existing positive authority for protected links, receipts,
replay, rollback and resource guarantees remain unchanged. A `current-metadata`
receipt records in-place address upkeep, not semantic acceptance or a later
write grant.

Version 1 remains exact-context-only. Its `bugs` array enumerates every current
bug whose parsed `context` equals the closing slug. A `terminalize` row contains
`id`, `action`, `inputSha256`, `status`, `resolution`, and `evidence`; a
`preserve-current` row uses `reason` instead of `resolution`.

Physical-current membership differs from semantic mutation eligibility. `preserve-current` keeps an intact exact-context bug byte-identical for a recognized current or terminal status, without closing, reopening, normalizing or archiving it. Preparation and archived receipt/replay use the same action/status contract. Newly admitted terminal preservation requires one status/context, a matching single id when present (legacy absence is supported), unambiguous owned terminal fields and one physical selected source. Its equal status/hash receipt and null target are close-time evidence, not fresh bug re-verification. Version 2 may retain existing terminal metadata unchanged for exact-context preservation; placeholders remain terminalize-only. `terminalize` still requires semantic-current input and every existing evidence/context/target guard. A separate broad category audit may report retained current-root terminal-state debt; this supplies no bug mutation or global clean claim.

Version 2 keeps the same top-level fields (`schemaVersion`, `workItem`,
`closedAt`, and `bugs`) and adds `contextBefore` and `contextAfter` to every
Version 1 row. Every exact-context current bug remains required. The manifest
may additionally select a current `adjacent-finding` or `standalone` bug only
with `action: terminalize`; `contextBefore` must equal that bug's actual
original context and `contextAfter` must equal `workItem`. Exact-context Version
2 rows therefore use the closing slug for both context images. Unselected
placeholder bugs remain current and byte-identical, and a placeholder cannot be
`preserve-current`. Do not manually edit a bug's context: the lifecycle owner
performs the admitted recontextualization and writes both context images to the
Version 2 receipt. The ordinary `close` path alone admits Version 2;
`archive-with-successor` keeps Version 1 bug-disposition admission.

This is a complete one-row Version 2 shape for a close whose complete required
set is one selected `adjacent-finding` bug. It is not runnable unchanged:
replace every angle-bracket value with the actual current value, and add every
exact-context bug row when the repository has any.

```json
{
  "schemaVersion": 2,
  "workItem": "<active-slug>",
  "closedAt": "<same-strict-UTC-terminal-instant>",
  "bugs": [
    {
      "id": "<selected-current-bug-id>",
      "action": "terminalize",
      "inputSha256": "<sha256-of-exact-current-bug-bytes>",
      "status": "fixed",
      "resolution": "<accepted-terminal-resolution>",
      "evidence": "<accepted-evidence-reference>",
      "contextBefore": "adjacent-finding",
      "contextAfter": "<active-slug>"
    }
  ]
}
```

### Archive an already-fixed flat bug under an active or archived parent

When one current `work-items/bugs/<bug-slug>.md` already has parsed
`status: fixed` and names one active or admitted archived parent, use the lifecycle owner's
separate fixed-bug route; do not change it back to `open`, hand-move it, or close
the parent just to archive the bug:

```powershell
python scripts/mutate-work-item.py --root . archive-fixed-bug --slug <bug-slug> --terminal-instant <strict-UTC> --resolution <single-line-text> --evidence <single-line-text> --apply
```

`--apply` is required positive mutation intent; without it the command writes
nothing. Supply real, nonempty, single-line resolution and evidence and a strict
UTC `YYYY-MM-DDTHH:MM:SSZ` instant. Matching existing terminal fields are
preserved; conflicting or duplicate fields fail before mutation. The recorded
instant selects `work-items/bugs/archive/YYYY-MM/`, not the bug slug's date or
wall clock. The bug keeps its id, `fixed` status, and context; parent lifecycle
and identity remain unchanged. The existing unique physical resolver admits active
or archived parents, with readable-legacy and stamped-strict archive admission;
missing, duplicate, backlog or invalid archived parents refuse. Incoming-link
selection follows each file's actual work-item role before interpreting its bytes.
Ordinary files under an owned active or archived item's `inputs/` remain opaque
data regardless of encoding, filename, native format, or incidental logical,
Markdown-like, or literal paths; their bytes are preserved. This role does not
assert format validity or reference freedom. Exact retained-preimage claims and
reserved custody keep their separate validation, and an invalid selected claim
does not become an ordinary-data exemption. Current Markdown/JSON/JSONL records
and other selected current text consumers keep their codec and reference
obligations. The owner reads each leaf through its existing raw or
acquired-history carrier and verifies its current identity and bytes before
skipping interpretation. A failed read of the retained ledger is not proof that
no claim exists; unrelated malformed legacy rows still do not become a global veto.
Known Portable Network Graphics (PNG), bitmap, and Portable Document
Format (PDF) attachments and Word Office Open XML packages retain the existing
narrow content/package recognition; they are preserved without extracting
metadata or native navigation. Names alone do not exclude ordinary text outside
the owned input-data role. Unknown or unreadable current consumers retain each
caller's strict or tolerant acquisition policy. Attachment identity asserts
neither native validity nor reference freedom. An unsafe or immutable physical
text consumer fails closed.
It refreshes `work-items/README.md` and writes a sibling
`<bug-slug>.fixed-archive-receipt.json` binding the source/archive identity,
terminal instant, source and archived hashes, each changed link's before/after
hashes, and README hash. Identical replay validates that settlement without a
second move; drift or interrupted transition uses the owner's recovery path.
This operation does not consume the parent's `bug-dispositions.json`; ordinary
`close`, `terminalize-v1`, and successor supersession keep their separate
admission and receipt contracts.

### Archive with a backlog successor

Use this after accepted terminal evidence, exact `bug-dispositions.json`, and
the first-use gates below. Omit the optional transfer file for the ordinary
strict-close path; supply it only when every unresolved review obligation is
being transferred to the one successor created by this command:

```powershell
python scripts/mutate-work-item.py --root . archive-with-successor --slug <active-slug> --closure-file <closure.md-input> --terminal-instant <strict-UTC> --successor-slug <new-backlog-slug> --successor-file <successor.md-input> --operation-id <bounded-transition-id> --expected-ledger-sha256 <current-ledger-sha256> --expected-readme-sha256 <current-readme-sha256> [--obligation-transfer-file <strict-json>]
```

Without `--obligation-transfer-file`, the owner runs the unchanged strict
validator and writes the existing schema-version 1 receipt. With the option,
the strict UTF-8 JSON object is schema version 1 and binds the source slug,
successor slug, expected source-ledger SHA-256, and the exact set of currently
open REVISE rows by `runId`, raw line ordinal, raw line SHA-256, raw event
SHA-256, and projected event SHA-256. Transfer requires zero open launches;
missing, extra, duplicate, closed, or drifted rows fail before mutation.

The owner fsyncs transition intent, applies the bound bug dispositions, moves
the item to its final archive, writes the flat successor only after that
archive exists, refreshes README, and writes
`lifecycle-transition-receipt.json`. Both receipt versions bind the existing
archive, successor, ledger, status, closure, bug-disposition, migration-receipt,
and README results. Transfer writes schema version 2 with owner
`mutate-work-item:archive-with-successor-v2` and additionally binds the transfer
input, immutable archive identity, predecessor operation, and derived
obligation rows. Version 1 receipts remain readable and exact-replayable but
confer no transferred ownership.

The successor input must contain exactly one `Continues: <source-slug>` and
`Obligation-transfer: <operation-id>` field. Ordinary `start` preserves both.
Backlog, active, close, and re-transfer views resolve the same obligation under
one current owner without copying source-ledger events: closure remains
`closesRunIds`-driven, and a later transfer carries forward only the still-open
set with its predecessor operation. Identical replay is a byte no-op; request,
receipt, ledger, or ownership drift fails closed through the existing recovery
owner.

Plain `audit` is read-only. If a transition intent is pending, it fails with
`WI-LIFECYCLE-TRANSITION-RECOVERY-REQUIRED`, names the bounded operation ID,
and prints the exact command to run. Recover only that operation explicitly:

```powershell
python scripts/mutate-work-item.py recover-transition --root <repo> --operation-id <bounded-transition-id> --apply
```

The command delegates to the existing transition recovery owner and reports
`outcome=rolled-back` or `outcome=settled`; rerun `audit` afterward. Omitting
`--apply` or naming a non-pending operation changes no bytes. Do not use audit
as a batch recovery command.

The generated README is a diagnostic view, not a global acceptance verdict. The lifecycle owner's single typed `ArchiveEntityInventory` supplies archive candidate projection, lookup, board rendering, observation and audit. Existing work-item and supported legacy readers retain their admitted rules; canonical empty or owned-input work-item candidates missing evidence keep their original strict failures. Unknown physical collections do not become work-items or terminal records from their name, month, extension, title or status word.

Ordinary direct files at the work-item archive root and canonical-month level are `archive-metadata`: each requires one exact bounded no-follow snapshot and has no logical task reference. A conditional `Archive metadata` section shows every path and SHA-256 as nonauthorizing data, without a task checkbox or empty-section churn. Raw bytes feed the existing input digest and repeated snapshot/membership checks; metadata is excluded before UTF-8 timestamp/field interpretation. Binary and genuinely captured empty files are supported. Name, extension, `Closed`/`Updated` prose and registry counts confer no terminal or obligation authority. Metadata alone preserves complete schema-version-1 `archiveInventory` with empty `unbound`; C's existing scope/member/criterion/receipt checks still govern readiness. Actual unknown collections remain incomplete and ineligible, and malformed/linked/unreadable/drifting inputs still refuse. This explicit direct-file acquisition migration restores useful resolve/refresh/transaction behavior; it grants no archive mutation or historical terminal admission.

Within the existing canonical-month candidate domain, an acquired nonempty ordinary flat collection without work-item-owned inputs is unbound. The board shows an unchecked `Blockers` row for its container and EVERY leaf, with physical links, `WI-ARCHIVE-ENTITY-UNBOUND` and creator/format recovery guidance; exact leaf hashes belong to the structured `archiveInventory` observation and its aggregate `inputDigest` binding. The view key `archive-observation:<relative-path>` is not a category or lifecycle reference. Mixed, nested, unsafe, unreadable or drifting in-domain input retains explicit refusal/unverified state; no skipped leaf or fallback empty inventory. In a noncanonical outer collection, only immediate lexical owned inputs admit an immediate directory to the existing work-item candidate domain. Noncanonical direct evidence and attachment-only directories without those inputs remain non-owning historical evidence; do not scan/promote their bodies, create board rows or infer a readiness veto. Malformed or linked owned inputs still enter strict checks. This is owner-domain classification, not a folder-name ignore rule or new category authority.

Readable invalid current statuses in unrelated backlog, active or Version 1 roadmaps remain unchecked diagnostics with their original failure, parsed status, physical link and source digest; no normalization. Unrelated admitted operations may commit and refresh despite unknown collections, but a selected unbound physical container/leaf or selected work-item identity colliding with unresolved in-domain data refuses `WI-ARCHIVE-ENTITY-UNBOUND`; known logical duplicates still refuse. Selected start/import/close/migration inputs keep all existing evidence, hash, link, UTC and missing/empty-status admission guards. Archive bytes/identities remain immutable; history recovery requires its existing owner and actual authority, not inferred terminal dates.

The separate readonly `archive_entity_inventory(root)` API exposes that owner's logical archived work-item paths, including invalid known tasks, without a writer lock or new files. The default archived-ledger check consumes this model for the actual configured archive scope and validates only immediate canonical `agent-runs.jsonl` entries. Nonlogical nested snapshots never become tasks by filename. Lexical presence retains dangling/directory/unreadable failures; paired API/acquisition/currentness mismatch remains visible and non-clean. Actual current/archived review and historical-custody rules stay in the unchanged validator; active-only and no-strict-revise modes keep their existing boundaries.

Read-only `observe_readme` retains byte-currentness fields and adds `archiveInventory` from the SAME acquired rendering inventory:

```json
{"schemaVersion":1,"acquisitionComplete":true,"classificationComplete":false,"unbound":[{"path":"<work-items-relative-path>","container":"<container-relative-path>","kind":"leaf","sha256":"<captured-leaf-sha256>","diagnostic":"WI-ARCHIVE-ENTITY-UNBOUND"}]}
```

Rows are sorted; kinds are `container` or `leaf`, container hash is null, leaf hash exact. Acquisition and classification are separate: acquired ordinary unknowns may produce the useful board while classification remains incomplete. The two-read observation must agree on membership, source hashes and expected bytes and performs no writes. Goal/root readiness requires this typed version-1 inventory, complete acquisition AND classification, and empty unbound rows in addition to existing scope/proof checks. Missing/null/ill-typed fields or mixed-version producer/consumer pairs are unavailable/unverified, never clean-empty. Preservation-only root applicability remains governed by the admitted Goal topology; no phantom task domain or universal gate is added.

All public refresh paths, including explicit static-guide reset, publish the current diagnostic board with sorted `INFO WI-ARCHIVE-ENTITY-UNBOUND` lines and operational success when ordinary unknowns were acquired. This is the explicit operational exit migration; it is not silent fail-quiet output or a full validity PASS. `check_readme` certifies byte currency only. Full `audit` still exits nonzero for unresolved archive classification or invalid current statuses, and Goal completion remains unverified/ineligible. Marker/acquisition/receipt/replay/rollback checks and malformed canonical candidates remain strict; non-Version-1 roadmap projection exclusion is unchanged. Direct, shadow and precomputed boards share the owner, and receipts bind the complete board. Deploy the matching owner/receiver pair; older coherent pairs keep their prior behavior, not a bypass.

An acquired historical work-item with an incomplete pair of lifecycle schema declarations is a separate, nonauthorizing catalogue observation when every declaration that is present is exactly canonical. Its no-checkbox row in **Archive metadata** carries `WI-CATEGORY-SCHEMA-INVALID`, the actual root-relative archive/member path, and the qualification that Version 1 terminal proof is unavailable. Both source files remain byte-bound in the canonical input digest; the observation contributes no terminal timestamp. This applies in either missing-declaration direction and does not repair archive bytes, supply missing closure fields, or turn a date into a UTC instant.

Public `refresh`, including static-guide reset, reports these rows as `INFO WI-CATEGORY-SCHEMA-INVALID` with the actual historical input and succeeds after complete board readback. This explicitly changes catalogue/refresh behavior for known incompleteness. It does not suppress malformed, duplicate, unsupported, wrong-case, complete-invalid, unreadable or changed inputs. Full `audit` independently checks every archived candidate through the strict reader, including candidates without bug-disposition files, and still refuses incomplete schema pairs. Goal selected members, historical ledger/artifact owners, close replay and other proof consumers use that strict reader; README byte currency supplies no terminal or Goal completion authority. A valid unrelated current close may proceed while retaining the informational historical row, its original bytes, and its real diagnostic attribution. An already schema-marked active status remains an invalid current close preimage.

If `start`, `update`, or `reopen` reports `WI-README-STALE` after saying the
canonical state committed, do not retry that operation. Run `refresh`, then
use `resolve` and `audit` to verify the target. To replace a reviewed static guide
or adopt a legacy README with neither generated marker, first retain the original
README bytes as named canonical task data and verify their SHA-256 digest. Then
run `python scripts/mutate-work-item.py refresh --root . --reset-static-guide
--expected-readme-sha256 <original-sha256>`. This explicit reset replaces the live
guide with the default guide and the current generated board; retained history
does not remain a live prefix. Partial, duplicate, or reversed markers still
refuse, and ordinary `refresh` retains marker and acquisition checks. Rollback restores the retained
README bytes under caller authority without changing lifecycle records.

### Finish an accepted current-bug successor handoff

The receiving registry first creates and accepts its successor record. The
source lifecycle owner then consumes a strict schema-version 1 binding for that
accepted record plus a complete owner-bound incoming-link inventory:

```powershell
python scripts/mutate-work-item.py --root . supersede-current-bug --slug <bug-slug> --successor-record <runtime-path> --successor-binding-file <strict-json> --terminal-instant <strict-UTC> --incoming-links-inventory <strict-json> --expected-bug-sha256 <current-bug-sha256> --expected-readme-sha256 <current-readme-sha256> --operation-id <bounded-operation-id> --apply
```

The binding names the exact operation, `bug:<source-slug>`, stable registry and
record references, accepted record SHA-256, accepting owner, strict UTC
acceptance time, and bounded acceptance evidence. The inventory binds the same
operation/source/binding and every current source-local incoming link with its
exact before/after image. Before intent creation the owner verifies the
successor as a no-follow regular file, its hash, the unique current source, and
complete link coverage. It never writes the receiving registry or persists the
runtime successor path.

Settlement terminalizes and archives the source bug as `superseded`, replaces
every inventoried local incoming link with the stable successor reference,
refreshes README, and writes the source-local supersession receipt through the
existing transition recovery dispatcher. Identical replay verifies the bound
receipt and changes no bytes; mismatched replay or incomplete binding/inventory
fails closed. Receiving-registry preparation is not claimed as local completion
or rollback.

### Failures, recovery, and telemetry

| Failure class | Exact discriminator |
| --- | --- |
| Missing/non-unique target; target digest; ledger drift; ineligible target | `WI-LEDGER-MIGRATION-TARGET-IDENTITY`; `WI-LEDGER-MIGRATION-TARGET-DIGEST`; `WI-LEDGER-MIGRATION-LEDGER-DRIFT`; `WI-LEDGER-MIGRATION-TARGET-INELIGIBLE` |
| Wrong defect class; replacement mismatch; V3; chain/cycle | `WI-LEDGER-MIGRATION-DEFECT-CLASS`; `WI-LEDGER-MIGRATION-REPLACEMENT-MISMATCH`; `WI-LEDGER-MIGRATION-V3-UNSUPPORTED`; `WI-LEDGER-MIGRATION-TOPOLOGY` |
| Unknown normalization kind, kind/scope/evidence drift, or cross-kind revoke | `WI-LEDGER-MIGRATION-NORMALIZATION-KIND` |
| Lock; invalid candidate; uncertain commit; receipt mismatch | `WI-LIFECYCLE-LOCK-HELD`; `WI-LEDGER-MIGRATION-CANDIDATE-INVALID`; `WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE`; `WI-LEDGER-MIGRATION-RECEIPT-MISMATCH` |
| Corrupt intent; rollback failure; roll-forward failure; settlement mismatch; late revoke | `WI-LIFECYCLE-TRANSITION-INTENT-INVALID`; `WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE`; `WI-LIFECYCLE-TRANSITION-ROLLFORWARD-INDETERMINATE`; `WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH`; `WI-LEDGER-MIGRATION-REVOCATION-FROZEN` |
| Transfer coverage, ownership, or immutable-evidence drift; invalid accepted bug successor | `WI-OBLIGATION-TRANSFER-COVERAGE`; `WI-OBLIGATION-TRANSFER-OWNER`; `WI-OBLIGATION-TRANSFER-DRIFT`; `WI-BUG-SUCCESSOR-BINDING` |

Telemetry always reports raw events separately from apply, revoke, and
projected counts. Raw count never decreases; one active apply adds one raw
control and one projected event, while revocation adds another raw control and
returns projected count to zero. `legacy-unclassified` never enters a security
count.

Before first use, require focused migration tests, the contract checker, strict
item validation, lifecycle audit, deterministic crash recovery, independent
Architecture Review, Security Review, and Quality Assurance to pass on one
frozen byte set. Before the first valid anchor, the implementation can revert
as one atomic group. After a valid anchor, reader/projection support and the
operator contract are forward-only. Before archive movement, operational
rollback is the exact revoke command; after archive movement, recovery is
forward-only to one exact successor, README, bug receipt, and settled receipt.

## Initial legacy-decision byte admission

`mutate-work-item.py admit-current-decision-v0 --root <repository>` captures the
complete direct set of legacy frontmatter (V0) decisions without admitting it.
The callable `admit_current_decision_v0` uses the same lifecycle owner. Optional
`--policy-decision <slug>` and `--cutover-date YYYY-MM-DD` render the existing
five-field manifest candidate; an absent policy digest remains unknown. Capture
does not create a manifest or receipt and never supplies historical consent.

The actual current policy owner must first accept a canonical Version 1 (V1)
decision binding that exact baseline, manifest path and cutover. Its acceptance
describes preservation of historical bytes and unknown historical approval or
review facts. A truthful owner-executed manual equivalent is valid under the
same contract; no helper marker grants authority. Apply never accepts or edits
the policy on the owner's behalf.

After verifying that current acceptance, use the captured baseline and actual
policy byte hash with `--apply --policy-decision <slug> --cutover-date YYYY-MM-DD
--expected-baseline-sha256 <UPPERCASE64HEX>
--expected-policy-sha256 <UPPERCASE64HEX> --operation-id <id>
--receipt .scratch/<receipt>.json`. All apply inputs are required. The owner
recaptures the full set, validates it through the existing strict reader, and
creates the first manifest and settlement receipt without replacing a foreign
destination. Historical omissions and raw statuses remain unchanged; admission
neither retires a decision nor closes review obligations. Empty first apply
refuses. README is outside this operation and keeps its independent audit.

Repeat the same positive apply request after interruption. The receipt sibling
`<receipt>.json.pending` retains actual input bytes, root bindings and flushed
stage identities before manifest promotion. Matching unfinished state is
revalidated and receives a fresh `recovered` settlement receipt; it never
claims the interrupted process succeeded. Invalid, missing or conflicting
evidence refuses while preserving foreign or uncertain state. Caught safe
pre-receipt failures compensate owned effects; that does not promise crash or
power-loss rollback. A crash before durable pending publication can leave an
ambiguous stage requiring owner reconciliation.

A real matching settled receipt returns historical `replayed` after a separate
present strict-reader check. Lawful later retirement or README changes do not
require the old after-images to remain current. Present reader errors remain
visible, and the receipt is never rewritten to imply fresh historical consent.

## Physical lifecycle V1

For a tracked work-item, `status.md` is active recovery state and `closure.md`
is terminal outcome. The lifecycle owner writes or moves the physical record,
derives the archive month from strict UTC closure evidence, and preserves the
archived identity. `README.md` and `index.md` are generated compatibility
views; do not use either to infer, backfill, or execute a state transition.

Legacy directory-shaped backlog records use the same owner. Run
`mutate-work-item.py convert-legacy-candidate` only for an admitted record and
supply the current candidate text; the command appends every legacy source text
with its byte digest, replaces the directory only after the README refresh
succeeds, and rolls the whole operation back on failure. Run
`mutate-work-item.py retire-legacy-backlog` only with an explicit product
disposition and strict UTC instant; it preserves the original source bytes plus
an incoming-link inventory in the existing monthly archive and deliberately
creates no admission, active, or closure history. The generated historical
catalogue validates that retirement's stored incoming inventory and actual
archived source bytes, lengths, hashes and membership. It does not select a new
current mutable-consumer sweep merely to display the historical row. Strict
retirement and integrity/audit receiving still require their current-link check;
a later bad citation remains a real current integrity finding. The derived row,
source paths, digest and repeated refresh receiving remain unchanged.
`terminalize-v1` applies the
same operator-authorized missing-evidence repair to every supported flat
category, including roadmaps, using that category's own UTC/detail/evidence
fields.

## Complete an accepted legacy flat work-item

Use the existing lifecycle owner for an **accepted completed flat work-item** that remains current. This is distinct from ordinary tracked close, conversion, never-admitted retirement and archive-with-successor. Preserve the original slug and source bytes; do not invent an active interval, status, admission, ledger events or a successor merely to make validation pass. An archive location or a completion heading alone is not delivery evidence.

### Prepare the selected evidence and preview

The owning Root supplies accepted original admission, useful completion, applicable criteria and the bounded history/evidence selection. Those roles may reference different sections of the same real artifact; they do not require invented historical documents. The legacy evidence input has exact keys `schemaVersion`, `kind`, `operationId`, `source`, `acceptedEvidence`, `historySelection`, `bugDispositions` and `expectedReadmeSha256`; use version 1 and kind `legacy-work-item-evidence`. Bind actual selected paths, lengths and digests, original logical bases and required supporting artifacts. Prepare the existing bug-disposition manifest under its unchanged admission/status rules.

History applicability follows the original accepted criteria, not the flat filename. Present history is acquired and evaluated through the existing validator, preserving raw rows, epochs, original `Closed`, authority and obligations. Evidenced nonrequired absence is permitted without inventing an empty ledger or obligation result. Missing required input, unknown criteria, corrupt or incomplete acquisition and open obligations refuse dependent effects. Supporting history may be copied into custody while its original shared location remains; do not report all originals absent unless the actual selected evidence proves it.

Supply the existing closure fields and strict UTC `Closed` matching `--terminal-instant`. The new terminal instant dates this actual action and archive month; it does not rewrite the historical completion or validate a previously invalid closer. Without `--apply`, the explicit legacy branch validates and previews without canonical writes:

```powershell
python -B scripts/mutate-work-item.py --root <repo> close --slug <legacy-slug> --closure-file <closure.md-input> --terminal-instant <YYYY-MM-DDTHH:MM:SSZ> --legacy-evidence-file <legacy-evidence.json> --transition-read-admission selected-native
```

After the original outcome and evidence are accepted, use the same bound request with positive apply. A prior preview is optional; the first apply derives its finite output reservation before writing an intent:

```powershell
python -B scripts/mutate-work-item.py --root <repo> close --slug <legacy-slug> --closure-file <closure.md-input> --terminal-instant <YYYY-MM-DDTHH:MM:SSZ> --legacy-evidence-file <legacy-evidence.json> --apply --transition-read-admission selected-native
```

`operationId` belongs to the bound evidence request. Matching reentry/replay retains that exact request, closure and selected bindings; a different request or conflicting identity refuses. Preview success is not apply, settlement or Goal acceptance. Observed physical support is Windows NT; unsupported hosts refuse before physical effects. Portable metadata and preview do not establish all-platform physical support or authorize a weaker rename/ownership route.

### Admit finite transition resources

For managed lifecycle, checker, validator and ledger invocations, positively select `--transition-read-admission selected-native` or supply the complete `--transition-max-intent-bytes`, `--transition-max-inventory-bytes` and `--transition-max-inventory-entries` tuple. The existing lifecycle owner acquires native directory metadata before decoding pending JavaScript Object Notation (JSON), then freezes the input allowance (R). The dimensions are encoded UTF-8 bytes per intent, aggregate selected JSON bytes and every actual directory entry. With selected-native mode, an accompanying numeric tuple is a hard acquisition ceiling. Zero is valid for a proved empty input; incomplete, negative, Boolean or incoherent tuples refuse.

The prepared operation separately seals its finite output reservation (W) before initial publication or business effects. An optional complete `--transition-output-max-intent-bytes`, `--transition-output-max-inventory-bytes` and `--transition-output-max-inventory-entries` tuple supplies a hard output ceiling (H). Omitted H permits the actual prepared demand; it does not create an infinite allowance. R never grows to accommodate W, H never grows to accommodate demand, and a pending file cannot grant itself either allowance. Progress and compensation retain one reservation and refuse unexpected growth. Only the actual owner-published native image may use W for readback; a reserved but unpublished image, a matching pathname or a foreign replacement cannot.

When all resource controls are omitted, the existing limited diagnostic profile remains. It can refuse an enlarged pending intent and does not certify managed receiving. Deploy the common readers and all caller forwarding before enlarged writes. Keep those capable readers while dependent pending state exists; downgrade must preserve the full bytes and visible pending outcome. No historical schema, ledger row, receipt or journal migration is required. Resource admission does not change lifecycle authority, proof selection, native identity, inverse, replay or receipt requirements.

Fresh recovery acquires the current intent under its genuine R, then derives W before the next effect. It needs no guessed allowance for future progress and no prior failed command. Every public receiver that inspects pending state needs the same explicit resource input; a ledger budget is a separate control.

### Receive the archive and distinct receipts

The applied representation preserves the raw source and selected original history/evidence in one archive envelope. Permanent metadata version 2 records logical origin and custody; the separate lifecycle action receipt version 1 binds the request, metadata, archive membership, history selection, links, README and execution provenance. The existing bug-disposition receipt remains a distinct required receipt with its own schema and purpose. Neither receipt substitutes for the other or proves semantic acceptance by its filename.

Verify actual source/location membership, retained bytes, closure/instant, required evidence navigation and both receipt relationships through the lifecycle owner's fresh readers. Original-relative targets, query/fragment suffixes and distinct same-basename evidence must resolve to the exact retained bytes. Preserved historical incoming-link/README snapshots do not freeze lawful later consumer edits. Current category, dependency, original-path, descendant, README and audit receiving must agree on settlement; an incomplete observation has no terminal disposition or instant.

For a legacy-flat close, the owner derives the generated README from one prepared final image of the same operation: affected source and consumer paths contribute their final bytes or explicit absence, and the new archive entry contributes its prepared closure and metadata. The static guide and unrelated inputs stay on their existing acquisition path. The rendered board digest is bound into the receipts. This operation-time projection does not replace subsequent receiving: after apply, existing readers independently acquire the persisted category, dependency, README, replay and audit state.

The original historical selection stays with its existing history owner. A fresh process binds recorded logical topology to real current native custody; it does not deserialize old native identities or module seals. Successful structural acquisition alone cannot satisfy an open historical obligation. Hold and reverify the actual captured objects during receiving; a same-byte replacement during that held read remains drift.

The accepted public physical receiving covers bounded Windows absence and one genuine required-current-history cohort, plus distinct pending/read/replay/ordinary regression controls. It does not establish every raw/H1/transfer physical variant, crash cut, filesystem or installed runtime. The Goal consumer adapter has an accepted contract but no runtime convergence credit from these physical results. Use the [full-goal receiving workflow](#full-goal-completion-receiving) only with its actual implemented producer/consumer gates and original admitted scope; this section grants no Goal eligibility.

### Preserve pending recovery and actual provenance

A pending intent, missing or altered action/metadata, unknown settlement or unresolved original history stays nonauthorizing across owner readers. Preserve the exact request, retained original native holds, creator/postimage/parent bindings and failure evidence. Do not clear the intent, recreate a disposed original, edit a receipt or change a hash to make the record look settled. Inspect the actual bounded cause, then use the existing explicit recovery command for that operation:

```powershell
python -B scripts/mutate-work-item.py recover-transition --root <repo> --operation-id <bounded-operation-id> --apply --transition-read-admission selected-native
```

The accepted finalization contract requires complete actual request/action/postimage/history/board proof before cleanup-only recovery can dispense with an already-disposed original hold. Remaining live holds and created parents still require their native ownership checks; foreign substitutions or children must be preserved. Public readers remain pending until cleanup and intent settlement are verified. The independently observed post-hold-disposal recovery correction is not certified by this runbook; do not assume every interrupted finalization state is recoverable from the earlier precommit or board-before-receipt tests. Retain an explicitly indeterminate state when current proof cannot establish safe replay, compensation or finalization, keeping the original failure and secondary recovery cause visible.

Helpers assist the already authorized operation. An unavailable or defective helper alone does not remove the owning guarantees or create a workflow-wide blocker. A lawful manual equivalent must preserve the same evidence, identity, history/obligation, rollback/replay, receipt/link/README and independent readback requirements, with actual `manual-equivalent` provenance; it must not impersonate `public-helper`, forge a native seal or bypass host denial. Live resources and retained evidence are separate: release newly owned handles/processes, while preserving user, foreign, ambiguous and genuinely load-bearing recovery state under its owner.

## Release one archived retained scratch entry

This section describes Version 1 live-inventory release. Recording an accepted
completed disposal uses the separate metadata-only operation below; it cannot
fabricate this inventory or delete a newly present root.

An archived ledger entry with `scratchEvidence.disposition: retain` remains
required by ordinary close replay. Release is an opt-in post-close operation
for exactly one terminal `runId` and `entryId`; it does not authorize a batch
cleanup or change existing archive bytes. First independently accept a
same-item canonical artifact and a concrete evidence or reproduction rationale.
Copy the exact artifact into the archived item as an additive file. Derive
`--expected-event-sha256` from the terminal ledger line's stored bytes after
removing its line ending, without parsing and reserializing the event.

```powershell
python scripts/mutate-work-item.py release-retained-scratch --root <repository> --slug <archived-slug> --terminal-run-id <run-id> --expected-event-sha256 <raw-line-sha256> --entry-id <entry-id> --artifact <item-relative-artifact> --rationale "<specific accepted evidence or reproduction>" --apply
```

Absent `--apply`, the command refuses without creating a receipt or removing
scratch. It inventories the exact selected ordinary file or directory without
following symbolic links, then creates one item-scoped receipt under
`retained-scratch-releases/` before renaming or unlinking the source. Each
surviving tombstone entry must still match its receipt row; retry the same
command after an interruption. A complete, exactly matching private receipt
stage left before final publication is removed on retry. If final and stage
are the sole two hard links to the same complete, valid receipt, both release
retry and archived close replay unlink only the stage before strict receipt
readback. A partial, mismatched, extra-linked, or unclassifiable stage is
preserved and blocks release pending owner review.
A valid receipt lets archived close replay
settle an unchanged partial tombstone or accept final absence. Missing or
changed artifact, receipt, survivor, or relied-on archived target fails closed.

An in-root link target may be removed only under the operator's independently
accepted artifact/reproduction rationale. A repository target outside that root
must either be an ordinary file or link-free directory inside the same archive,
or an ordinary file whose exact bytes equal the canonical artifact. The latter
is bound as artifact custody and no longer requires the old target path on
receiver replay. A definitively absent target has link-object-only custody:
the receipt binds its original literal digest, repository-relative path and
class with `targetKind: "absent"` and `targetCustody: "no-content"`; it carries
no `targetSha256`. Every existing path prefix must be ordinary and inspected
without following links. Malformed, escaping, unreadable or reparse-crossing
paths refuse release. Absence is rechecked at admission, receipt replay and
immediately before a surviving link is unlinked; targets are never created,
followed or modified. Existing live-target rows and version-1 envelopes are
unchanged. Other targets stay retained. Receiver or rollback software
without this receipt reader must not consume a released archive; release of one
declared root never grants a whole-repository cleanup `PASS`.

For an ordinary owned file, a Windows permission failure permits exactly one
ReadOnly retry only when the same non-reparse, single-link leaf and its bytes
remain verified. Only ReadOnly is cleared; a failed retry restores that flag
on the verified identity and leaves the failure visible. Access-control lists
and ownership are never repaired. This operation is shared with ordinary
scratch disposition; links and directory targets do not use it.

### Record an accepted completed disposal

For a unique active or archived item, the lifecycle owner can record a reviewed
past removal of exact valid retained entries without rewriting their terminal
ledger rows. The trusted operator first reviews the request's subject-to-action
and admission mapping. Hashes pin its current bytes; the writer does not infer
historical acceptance from arbitrary Markdown, a copied PASS or rationale text.

```powershell
python scripts/mutate-work-item.py reconcile-retained-scratch --root <repository> --slug <item-slug> --request-file <reviewed-request.json> --apply
```

The strict UTF-8 JSON request has exactly `schemaVersion: 1`,
`mode: "accepted-prior-disposal"`, `workItem`, `recordedAt` and nonempty `subjects`.
Each subject has exactly `runId`, `entryId`, `eventSha256`, `sourcePath`,
`canonicalPointer`, `canonicalPointerSha256`, `actionEvidence`,
`admissionEvidence` and `rationale`. Action references have exactly `artifact`,
`sha256`, `actionFrom` and `actionThrough`; the admission reference has exactly
`artifact` and `sha256`. All artifacts are confined ordinary same-item files.
Use the original stored terminal line without its ending for `eventSha256`,
never a parsed/reserialized event. Action times and current recording time use
strict UTC; recording must follow each completed action range. The request
reuses existing ledger JSON byte and scratch-entry bounds. Duplicate selectors,
unknown/default/missing fields and unbound or changed evidence refuse.

Without positive `--apply`, the command refuses before acquiring a lifecycle
transaction or creating persistent state. Apply captures the reviewed inputs
under the existing lifecycle transaction and selected ledger lock, validates
the complete batch, and creates only additive Version 2 receipts in
`retained-scratch-releases/`. Each receipt binds stable `workItem`, exact raw
event/entry/path, current pointer, action/admission hashes, recording time,
`evidenceScope: "canonical-observations"` and `rawRecovery: "not-certified"`.
It has no live inventory or archive-location field. Both original and tombstone
must be absent; present/reappeared data is preserved and refuses this mode.
Failed publication rolls back only newly owned metadata. Exact identical
repetition reads back existing receipts; changed inputs or conflicting mode/stage
do not overwrite them.

One retained-scratch reader interprets this completed-disposal state for active
close and archived replay, rechecking proof and absence before close writes and
after archive placement. It performs no payload rename, unlink, restoration or
inventory. Unknown or unselected missing retains and ordinary open obligations
still block close. This mode certifies neither exact raw recovery nor future
custody, parent closure or publication authority. Root runs its normal receiving
and closure checks after Source acceptance; installed command availability still
requires rollout verification.

## Retained preimages and incoming-link selection

An exact historical preimage is not a live document merely because its bytes resemble current links. Admission is opt-in and byte-bound: an actual internal `knowledge-archivist` standalone completed/PASS record, with no `closesRunIds` and no different assigned role, may declare one ordinary item-relative leaf below its own `inputs/`. This does not admit the directory, root status/ledgers/receipts/registries, or arbitrary digest-store leaves. Same-named historical input copies are distinct from their live counterparts.

Use the existing `agent-run-ledger.py append --evidence-json` surface. Keep the normal PASS artifact/evidence requirements: artifact and its SHA-256 `artifactRevision` identify the accepted stewardship report. Add this existing evidence object; `result` is the serialized JSON **string**, not a new event field:

```json
{
  "kind":"artifact",
  "ref":"inputs/example.before",
  "result":"{\"schemaVersion\":1,\"kind\":\"retained-preimage\",\"workItem\":\"example-item\",\"purpose\":\"historical-only\",\"byteCount\":4,\"sha256\":\"<payload-sha256>\",\"provenance\":{\"ref\":\"stewardship.md\",\"sha256\":\"<report-sha256>\",\"snapshot\":\"review-artifact-custody/<report-sha256>\"}}"
}
```

The public writer captures the unchanged payload and accepted report, validates the ordinary whole append candidate, and publishes the report through the existing digest store and exact historical-PASS association. Failed append reclaims only its unchanged owned residue. The incoming-link owner resolves only the matching declaration's selected association and per-record schema/unique decoded identity; unrelated malformed legacy rows or unrelated associations do not become additional vetoes. Admission is ineffective without the exact validated association. The stewardship report remains usable through its immutable snapshot after its original path is overwritten or removed.

Only the exact declared payload or exact derived `provenance.snapshot` is excluded because of historical admission. Ordinary data under its actual work-item `inputs/` role is independently left uninterpreted after the existing input carrier verifies that the leaf has not changed. A failed read of the retained ledger is not proof that no claim exists. Both paths preserve bytes and purpose; neither asserts that historical links are absent, grants goal completion, closes a review obligation, or waives a gate. Actual current consumers retain the existing native-content recognition, strict UTF-8 and reference checks. Unknown unreadable current input still refuses strict inventory.

Mutating lifecycle calls capture the admission carrier, selected association, provenance snapshot and payload in their existing invocation-owned transaction. Existing verification boundaries recheck those observations before intent or later mutations. When that owner moves an ordinary directory, its transaction preserves each captured leaf's original native identity and bytes and proves the moved directory and rebased parent chains before publishing the new observation locations. Unrelated observations remain strict. A failed post-move proof compensates before returning; an unsafe inverse preserves the conflicting state and reports both failures. File and detached-shadow moves retain their existing paths. A standalone inventory grants no future mutation credit. Preview, apply and owning-item relocation use the same selector and retain their existing caller strictness. Positive version-1 retained-scratch release runs admission, receipt publication, settlement and replay in this transaction; omission of `--apply` still refuses before entering it. For the two existing local verifier ports, the transaction checks the complete selected directory collection before local native proofs and again after a successful nonempty collection; each selected proof keeps its existing order. Integrity attribution binds to the actual admitted observation before its callback, while an unadmitted local failure does not create transaction history.

If inverse compensation cannot be verified, the transaction retains the actual move's source, destination and original directory identity through caller cleanup and exit. Cleanup that intersects either subtree or removes a containing ancestor is withheld; renames check both operands. This preserves moved originals and reappeared foreign data even with zero captures or caught secondary errors. Unrelated cleanup and verified-restored failure cleanup continue normally. The existing outcome remains rollback-incomplete, with its primary and compensation diagnostics. This invocation-only disposition grants no later recovery or deletion authority.

Downgrade is not generally safe: an older reader may refuse opaque bytes or treat UTF-8 historical links as live. Use a capable lifecycle owner; recovery restores capable code, never rewrites, moves or deletes the retained payload to bypass classification.

## Record one archived missing-artifact disposition

The validator's sole store, `work-items/legacy-ledger-historical-dispositions/`, holds create-only Version 2 evidence for one missing artifact referenced by an immutable archived execution ledger; it is outside the work-item lifecycle categories. Keep the record with its archived reference. Do not treat it as scratch, move it into or edit the archive, or reconstruct approval from status prose. The existing writer is `python .\scripts\mutate-work-item.py write-historical-artifact-disposition --root . --disposition-file <disposition.json>`; invocation writes immediately, with no dry-run or `--apply` mode, and an exact repeat replays the existing record. The writer and sole storage path are in [mutate-work-item.py](../scripts/mutate-work-item.py#L27024) and [validate-work-item-state.py](../scripts/validate-work-item-state.py#L7448).

Each record binds the archived work-item and archive identity, complete ledger SHA-256, raw ledger line ordinal and SHA-256, event SHA-256 and run ID, missing repository-relative artifact path, and artifact revision SHA-256. Its state is one of:

- `content-recovered`: includes the original artifact bytes, whose digest must equal the archived artifact revision.
- `irrecoverable-approved`: includes the complete search receipt and the exact approval identity, time, and statement digest.

Version 1 records remain nonauthorizing. Version 2 can let the archive validator accept only the exact missing artifact bound to its archived PASS row; it does not create a PASS, close a work item, or independently discharge a review. See the [V2 validator](../scripts/validate-work-item-state.py#L7516) and [archived reader](../scripts/validate-work-item-state.py#L7654).

## Operator Rules

- Do not trust a subagent report without a matching ledger event and independent verification evidence.
- Do not close a stage while `agent-runs.jsonl` contains a running event.
- Do not accept `PASS` without evidence and an artifact when the role contract requires one.
- Do not hand-edit JSONL unless no helper is available; prefer `agent-run-ledger.*`.
- Run `check-work-items-state.* --root .` before broad closeout so stale active work items are visible, not silently skipped.

## Selected-item obligation observation

After successful terminal append/settlement, including already-settled replay, run `python -B scripts/validate-work-item-state.py --work-item work-items/active/<slug> --obligations-json`. Installed Lead uses its sibling validator. Omission derives finite read-only admission from the current selected image; an explicit positive pair remains a hard ceiling. Receive the current deployed owner before relying on its omission behavior; an unsupported/stale helper records unavailable observation, never a false clean count.

The optional mode emits one JSON object: `schemaVersion: 1`, `workItem`, `ledgerPath`, `ledgerSha256`, `selection` (`live`, `candidate`, `ledger-free`), `strict`, `obligations`, `diagnostics`, and `result` (`PASS`/`FAIL` for validation). `--telemetry` nests counters. Default text format and exit polarity remain unchanged; required-read secondary diagnostics and error counts have the exception described below. Candidate/non-strict triage is not a completion oracle. Selected bytes are captured once and passed to the existing evaluator; the digest binds that revision. Approved ledger-free quick fixes explicitly identify absent ledger/null digest; required missing ledgers fail.

The observation freezes selected presence as well as bytes. A captured present image, including empty bytes, is validated even if the path later disappears. Genuine captured absence stays absent if a file later appears and is ledger-free only under the existing live quick-fix contract; required, candidate and compatible-member absence refuse. The direct validator API distinguishes explicit `selected_ledger_absent=True` from omitted legacy acquisition and rejects combining absence with `selected_ledger_bytes`. A failed read stays incomplete and is never parsed as successful empty data. Default failure output retains its original cannot-read cause and nonzero exit; the manufactured `ledger has no events` diagnostic after that failed read is removed, so its error count can change.

Available typed projection contains `openLaunches`, `openRevises`, `unresolvedHistory`. Current rows expose run/source digests and ordinals, source kind, obligation/predecessor IDs, and declared artifact/lane. History rows expose prefix digest/length, raw line identity, admission/disposition run and declared run ID. Arbitrary notes/prompts/raw evidence are excluded. Null is unavailable; errors plus empty arrays remain FAIL. The optional telemetry `result` remains a full-observation validation `PASS`/`FAIL`, so retained historical forensic findings can keep that audit at `FAIL`. Current close eligibility comes from the lifecycle owner's existing complete, target-bound current-result receiving and operation diagnostics, together with the close's existing current-obligation and lifecycle guards; empty arrays or the audit label alone do not establish it. Missing, incomplete or mismatched receiving and genuine unresolved duties still refuse. The original historical event and its audit interpretation remain unchanged.

Root consumes the completed tool frame and verifies item/selection/strictness/digest/diagnostics, then checks current selected presence and digest before dependent action; changed presence or bytes require a fresh observation. Persist terminal identity, observed revision/selection, exact pending IDs/causes and action owner/resume in existing `Last result`/next-action text. Known strict obligation FAIL is useful state; tool/acquisition failure records unavailable/resume. Continue independent admitted ready work. No acknowledgment-only ledger event mutates the observed revision. Writer success/replay markers stay independent; observation is neither task completion nor publication authority. Independent QA inspects actual tool receipt and persisted Root acknowledgment.

## Terms and Abbreviations

- R: immutable input acquisition allowance for transition intent bytes and inventory.
- H: optional immutable caller ceiling on an operation's output reservation.
- W: finite reservation sealed by the actual prepared operation before effects; only bound native output may use it for receiving.

- `agent-run-ledger.*`: helper script family that initializes work-item ledger files and appends validated `agent-runs.jsonl` events.
- `agent-runs.jsonl`: JSONL execution ledger stored beside `status.md` for machine-readable work-item state.
- `artifact`: accepted output of a role or gate, such as a review file, design note, patch, or report.
- `BLOCKED`: gate state for a real external blocker or missing prerequisite.
- `check-work-items-state.*`: helper script family that checks every active work item under a repository root.
- `Codex`: OpenAI Codex runtime and production provider line.
- `executionRole`: ledger field naming the actual executor of an event: `main` (the one main-conversation identity), `internal`, `consultant`, `external-worker`, `external-reviewer`, or `external-brigade`; the pre-2026-07-11 legacy value `lead` reads as `main`.
- `gate`: acceptance result recorded for a scoped artifact, commonly `PASS`, `REVISE`, `BLOCKED`, or `none`.
- `JSONL`: JSON Lines; one JSON object per line, used here for append-only ledger events.
- `identity-record-v0`: explicit preservation-only historical identity-record profile, version 1; absent current-schema fields are not synthesized.
- `PASS`: gate state meaning a scoped artifact passed the relevant checks.
- `REVISE`: gate state meaning the artifact must return to the same role for bounded correction.
- `SHA-256`: Secure Hash Algorithm with a 256-bit byte-content digest.
- `UTC`: Coordinated Universal Time; historical identity-record timestamps end in `Z`.
- `V1` / `V2`: Version 1 / Version 2 of the execution-ledger event schema.
- Decision-format `V0` / `H1`: existing read-only historical decision identifiers, distinct from the ledger schema.
- `href`: the destination text of a link.
- `C1`–`C5`: existing closure-relation checks for target order and eligibility, unique discharge, closing authority, and protected waivers.
- `stale running agent`: a ledger event still marked `running` after the configured age threshold.
- `status.md`: human-readable task-memory recovery summary.
- `validate-work-item-state.*`: helper script family that validates one work-item ledger and its referenced artifacts.
- `work-item`: one admitted task directory under task memory, usually `work-items/active/<slug>/`.
