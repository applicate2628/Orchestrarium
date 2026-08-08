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
| Codex | `~/.codex/skills/lead/scripts/` |
| Claude Code | `~/.claude/agents/scripts/` |

Project installs copy to the matching project-local runtime:

| Provider | Project-local helper directory |
| --- | --- |
| Codex | `<repo>/.agents/skills/lead/scripts/` |
| Claude Code | `<repo>/.claude/agents/scripts/` |

Use the installed equivalent when the source checkout is not available in the target repository.

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
