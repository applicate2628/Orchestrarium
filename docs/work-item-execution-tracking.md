# Work-Item Execution Tracking

This runbook describes the operator path for tracking real agent work in Orchestrarium task memory.

Use it when a repository keeps active task memory under `work-items/active/<slug>/` and the main session (as Lead) must prove which roles ran, what they accepted, and which gates remain open.

## Files

Each active work item should keep these files together:

| File | Purpose |
| --- | --- |
| `status.md` | Human-readable recovery state: current stage, active agents, completed agents, next action. |
| `agent-runs.jsonl` | Machine-readable append-only ledger for each launched or accepted role result. |
| `reviews/`, `design.md`, `plan.md`, or role artifacts | Accepted artifacts referenced by ledger events. |

`status.md` remains the readable recovery surface. `agent-runs.jsonl` is the state that validators can inspect.

## Project root topology

Optional project-owned auxiliary roots are defined only by the shared
[`work-items root contract`](../shared/references/work-items-root-contract.md).
Use that reference for the exact JSON schema, reserved built-in roots,
non-reparse confinement, compatibility, and lifecycle failure/recovery rules;
do not infer topology from `README.md` or create an auxiliary root ad hoc.

## Canonical Staged Start

`python scripts/mutate-work-item.py start` creates a staged `candidate -> active`
item with `admission.md`, `status.md`, and one schema-version 2 settled
`standalone` admission event in `agent-runs.jsonl` as one directory publication.
That event records the completed lifecycle admission only: `role: lead`,
`executionRole: main`, and `gate: none`; it does not claim a specialist launch
or an accepted artifact. A successful canonical staged start is immediately
valid, so do not run `init` just to create an empty ledger afterward.

## Initialize A Work Item

Use the helper when migrating a legacy work item that already has `status.md`,
or when a manual recovery requires the helper before the first ledger event.
Canonical staged starts already have their admission event; the undelegated
quick-fix path remains ledger-free until real delegated work needs a ledger.

```bash
python scripts/agent-run-ledger.py --work-item work-items/active/<slug> init --primary-task "Implement accepted plan" --stage "Plan"
```

```powershell
python .\scripts\agent-run-ledger.py --work-item work-items\active\<slug> init --primary-task "Implement accepted plan" --stage "Plan"
```

The init command creates missing status sections and `agent-runs.jsonl` without replacing existing task-memory content.

## Append A Gate Event

Append exactly one event for one role result or main-session gate action.

```bash
python scripts/agent-run-ledger.py --work-item work-items/active/<slug> append \
  --role qa-engineer \
  --execution-role internal \
  --status completed \
  --gate PASS \
  --scope tests/test_work_items_state_checker.py \
  --artifact reviews/qa.md \
  --evidence "command:pytest -q"
```

```powershell
python .\scripts\agent-run-ledger.py --work-item work-items\active\<slug> append `
  --role qa-engineer `
  --execution-role internal `
  --status completed `
  --gate PASS `
  --scope tests/test_work_items_state_checker.py `
  --artifact reviews/qa.md `
  --evidence "command:pytest -q"
```

The append command validates the work item after writing the event. If the new event makes the ledger invalid, the helper rolls `agent-runs.jsonl` back.

Current external provider wrappers record the exact resolved model, effort, and policy-admitted sandbox, input/output, permission, or tool flags in both their `launch` and `terminal` events. The flags use the bounded provider-specific `launchFlags` string array on the wire and `--launch-flags-json` at the append command boundary. Positional prompts, arbitrary configuration, path-bearing, credential-bearing, malformed, or oversized flag bindings are rejected before launch or append. Older Version 2 events without `launchFlags` remain valid compatibility input; `realization` remains unsupported and is not inferred from this field.

`--execution-role` takes one of the canonical values from `shared/schemas/agent-runs.schema.json`: `main` (the main conversation — the ONE main-conversation identity; it also holds the Lead role, and orchestration weight lives in the `status.md` `orchestration: light | full-lead` field, never in this value), `internal`, `consultant`, `external-worker`, `external-reviewer`, or `external-brigade`. Ledgers written before 2026-07-11 may carry the legacy value `lead`; validators and rollups read it as `main` (same owner), but a new append with `lead` is rejected — write `main`.

## Validate One Work Item

Run this before stage closeout or archive movement.

```bash
python scripts/validate-work-item-state.py --work-item work-items/active/<slug>
```

```powershell
python .\scripts\validate-work-item-state.py --work-item work-items\active\<slug>
```

Validation fails for duplicate run IDs, running agents, missing ledger files, missing evidence for `PASS`, missing accepted artifacts, artifact paths that escape the work item, and inconsistent `BLOCKED` or `REVISE` gates.

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

`WI-LEDGER-MIGRATION-COMMITTED` is authoritative only after exact anchor
readback and receipt reconciliation. The anchor is the commit marker; the
receipt is a derived read model. Its exact fields are `operationId`,
`targetRunId`, `targetEventSha256`, `anchorRunId`, `anchorEventSha256`,
`beforeLedgerBytes`, `beforeLedgerSha256`, `afterLedgerBytes`,
`afterLedgerSha256`, `replacementEventSha256`, `normalizationKind`, `diagnosticId`,
`sourcePath`, `receiptPath`, and `recordedAt`. `findingClass` is present only
when the normalized target had one. Missing or conflicting derived
receipt bytes are reconstructed only from the valid anchor and exact ledger.

### Revoke before physical transition

Revocation is append-only and allowed only while the item is still active and
no transition intent or receipt exists:

```powershell
python scripts/mutate-work-item.py --root . revoke-legacy-ledger-obligation --slug <active-slug> --apply-run-id <apply-run-id> --apply-event-sha256 <apply-raw-sha256> --expected-ledger-sha256 <current-ledger-sha256> --operation-id <bounded-revoke-id> --recorded-at <strict-UTC>
```

`WI-LEDGER-MIGRATION-REVOKED` restores the original invalid diagnostic in the
effective view; it never deletes the apply anchor or the source line.

### Archive with a backlog successor

Use this only after strict ledger closure, accepted terminal evidence, exact
`bug-dispositions.json`, and the first-use gates below:

```powershell
python scripts/mutate-work-item.py --root . archive-with-successor --slug <active-slug> --closure-file <closure.md-input> --terminal-instant <strict-UTC> --successor-slug <new-backlog-slug> --successor-file <successor.md-input> --operation-id <bounded-transition-id> --expected-ledger-sha256 <current-ledger-sha256> --expected-readme-sha256 <current-readme-sha256>
```

The owner fsyncs transition intent, applies the bound bug dispositions, moves
the item to its final archive, writes the flat successor only after that
archive exists, refreshes README, and writes
`lifecycle-transition-receipt.json`. Its `status: settled` record binds
`archivePath`, `successorPath`, `successorSha256`, `ledgerSha256`,
`statusSha256`, `closureSha256`, `bugDispositionReceiptSha256`,
`migrationReceiptSha256`, and `readmeSha256`.

### Failures, recovery, and telemetry

| Failure class | Exact discriminator |
| --- | --- |
| Missing/non-unique target; target digest; ledger drift; ineligible target | `WI-LEDGER-MIGRATION-TARGET-IDENTITY`; `WI-LEDGER-MIGRATION-TARGET-DIGEST`; `WI-LEDGER-MIGRATION-LEDGER-DRIFT`; `WI-LEDGER-MIGRATION-TARGET-INELIGIBLE` |
| Wrong defect class; replacement mismatch; V3; chain/cycle | `WI-LEDGER-MIGRATION-DEFECT-CLASS`; `WI-LEDGER-MIGRATION-REPLACEMENT-MISMATCH`; `WI-LEDGER-MIGRATION-V3-UNSUPPORTED`; `WI-LEDGER-MIGRATION-TOPOLOGY` |
| Unknown normalization kind, kind/scope/evidence drift, or cross-kind revoke | `WI-LEDGER-MIGRATION-NORMALIZATION-KIND` |
| Lock; invalid candidate; uncertain commit; receipt mismatch | `WI-LIFECYCLE-LOCK-HELD`; `WI-LEDGER-MIGRATION-CANDIDATE-INVALID`; `WI-LEDGER-MIGRATION-COMMIT-INDETERMINATE`; `WI-LEDGER-MIGRATION-RECEIPT-MISMATCH` |
| Corrupt intent; rollback failure; roll-forward failure; settlement mismatch; late revoke | `WI-LIFECYCLE-TRANSITION-INTENT-INVALID`; `WI-LIFECYCLE-TRANSITION-ROLLBACK-INDETERMINATE`; `WI-LIFECYCLE-TRANSITION-ROLLFORWARD-INDETERMINATE`; `WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH`; `WI-LEDGER-MIGRATION-REVOCATION-FROZEN` |

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
creates no admission, active, or closure history. `terminalize-v1` applies the
same operator-authorized missing-evidence repair to every supported flat
category, including roadmaps, using that category's own UTC/detail/evidence
fields.

## Operator Rules

- Do not trust a subagent report without a matching ledger event and independent verification evidence.
- Do not close a stage while `agent-runs.jsonl` contains a running event.
- Do not accept `PASS` without evidence and an artifact when the role contract requires one.
- Do not hand-edit JSONL unless no helper is available; prefer `agent-run-ledger.*`.
- Run `check-work-items-state.* --root .` before broad closeout so stale active work items are visible, not silently skipped.

## Terms and Abbreviations

- `agent-run-ledger.*`: helper script family that initializes work-item ledger files and appends validated `agent-runs.jsonl` events.
- `agent-runs.jsonl`: JSONL execution ledger stored beside `status.md` for machine-readable work-item state.
- `artifact`: accepted output of a role or gate, such as a review file, design note, patch, or report.
- `BLOCKED`: gate state for a real external blocker or missing prerequisite.
- `check-work-items-state.*`: helper script family that checks every active work item under a repository root.
- `Codex`: OpenAI Codex runtime and production provider line.
- `executionRole`: ledger field naming the actual executor of an event: `main` (the one main-conversation identity), `internal`, `consultant`, `external-worker`, `external-reviewer`, or `external-brigade`; the pre-2026-07-11 legacy value `lead` reads as `main`.
- `gate`: acceptance result recorded for a scoped artifact, commonly `PASS`, `REVISE`, `BLOCKED`, or `none`.
- `JSONL`: JSON Lines; one JSON object per line, used here for append-only ledger events.
- `PASS`: gate state meaning a scoped artifact passed the relevant checks.
- `REVISE`: gate state meaning the artifact must return to the same role for bounded correction.
- `stale running agent`: a ledger event still marked `running` after the configured age threshold.
- `status.md`: human-readable task-memory recovery summary.
- `validate-work-item-state.*`: helper script family that validates one work-item ledger and its referenced artifacts.
- `work-item`: one admitted task directory under task memory, usually `work-items/active/<slug>/`.
