Date: 2026-04-21
Owner: `$lead`
Status: `APPROVED`

# N15 Stateful System Gauntlet Design

## Context

The current hardening program has not separated `X1 / gpt-5.4` from `X3 / opus 4.7max`.
Tuple-exact review cells, factual investigation, adversarial geometry, and the first
multi-file dependency patch all tied at `PASS / PASS`. `N14` separated `X2` lower, but the top
pair both solved the local multi-file coupling.

The next separator must change task class, not add another small oracle case. `N15` is a heavy
stateful implementation gauntlet.

## Scenario Shape

`N15-stateful-batch-rollback-gauntlet` is a Python implementation scenario on diagnostic surface
`E5`.

The candidate owns a small batch execution system:

| Component | Responsibility |
|---|---|
| `planner.py` | normalizes plan steps without mutating caller input |
| `executor.py` | applies steps in deterministic order and resumes from checkpoints |
| `journal.py` | records append-only events with stable sequence numbers |
| `checkpoint.py` | stores committed position per batch |
| `rollback.py` | reverts only effects committed by the failed batch attempt |
| `retry.py` | schedules failed retryable steps while preserving causal order |
| `report.py` | derives summaries from the event log, not transient state |
| `store.py` | in-memory state/effect store used by verifier sequences |

The public API remains protected in `api.py`; implementation files own the behavior.

## Pressure Model

The verifier should execute deterministic action sequences, not a single snapshot. It must cover:

| Pressure | Required invariant |
|---|---|
| idempotency | re-running the same committed batch must not duplicate effects |
| resume | after a crash, the next run resumes from the committed checkpoint |
| rollback scope | a failed batch rolls back only effects from the current failed attempt |
| input immutability | caller-supplied plan objects are not mutated across runs |
| retry order | retryable failures are requeued in original causal order |
| accounting | report counts come from committed journal events and caveat events |
| isolation | separate batch ids do not share checkpoint, retry, or rollback state |
| decoy rejection | legacy/docs/ui helpers must remain untouched and do not own behavior |

## Verifier Contract

The verifier has three modes:

| Mode | Requirement |
|---|---|
| `--bundle-shape-only` | exact bundle shape and metadata |
| `--expect-start-state` | the provided buggy candidate must fail a named subset of invariant checks |
| completed run | all deterministic sequences and metamorphic checks pass, direct tests pass, no oracle literals are hardcoded, and scope guard passes |

The verifier should include around 30-60 checks generated from fewer human-readable scenarios.
Candidate code may not read `oracle/`, hardcode sequence IDs, or special-case verifier literals.

## Expected Signal

This is intended to be materially harder than `N14`:

- local one-file fixes are insufficient
- correct behavior depends on state across multiple invocations
- pass requires a coherent model of journal/checkpoint/retry/rollback ownership
- models that patch toward visible unit tests should fail hidden sequence checks

If `X1` and `X3` both pass, the next separator should move away from binary patch tasks and toward
scored long-horizon rubric evaluation. If one passes and one fails, `N15` becomes the first honest
binary top-pair separator.
