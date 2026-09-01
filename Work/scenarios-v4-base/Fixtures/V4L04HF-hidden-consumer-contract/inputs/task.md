# Migration readiness review: relaycfg v1.11 -> v2.0

The platform team wants to ship relaycfg v2.0. Their own acceptance tests
(`inputs/sources/tests/`) all pass. Twenty-four registered downstream
services consume the SDK; their code is not available here -- only the
census extraction records in `inputs/sources/consumers.md`. Your job is the
readiness call: predict, per consumer, whether v2.0 breaks it, what change
is responsible, and the required call-site remediation.

Read `inputs/sources/changelog.md`, both provider snapshots under
`inputs/sources/provider/`, and `inputs/sources/consumers.md`. Write one
JSON object to `candidate/migration-answer.json` using
`inputs/output-schema.json`.

## Decision rules

- A consumer **breaks** exactly when at least one of its `Relies on` lines
  stops holding for its listed operations in its listed deployment under
  v2.0. Otherwise it is **safe**.
- The **cause** of a breaking consumer is the changelog ID of the entry
  that stops the line from holding; if several entries are jointly
  involved, report the lowest-numbered involved entry. For a safe
  consumer the cause is `none`.
- A changelog entry is **breaking** when it is involved in the causal
  chain of at least one breaking consumer -- jointly involved entries all
  count. `breaking_change_ids` is exactly that set. Claiming an entry
  that is involved in no registered break counts against you.
- `migration_clearance` is `ship` only if zero registered consumers break,
  otherwise `block`. This field is your committed release call.

## Output contract

Fill every consumer ID `CONS-01`..`CONS-24` in each of the three maps.
Each visible property key is the identity; do not embed an `item_id`.

- `verdicts`: per consumer, `value` is `break` or `safe`; `unit` is `verdict`.
- `causes`: per consumer, `value` is one changelog ID `C01`..`C12` or
  `none`; `unit` is `change-id`.
- `fixes`: per consumer, `value` is one fix ID from the menu below;
  `unit` is `fix-id`.
- `breaking_change_ids`: array of changelog IDs.
- `release_gate.migration_clearance`: `ship` or `block`.
- `narrative`: optional, unscored.

## Fix menu

The required remediation for a breaking consumer is the single cheapest
call-site fix that restores every `Relies on` line under v2.0. A safe
consumer takes `FIX-NONE`.

| Fix ID | Meaning |
|---|---|
| `FIX-NONE` | no change needed |
| `FIX-DEFAULT` | pass an explicit default argument at the call site |
| `FIX-UNITS` | write the duration value with an explicit unit suffix |
| `FIX-CATCH` | name the specific exception type in the handler or retry predicate |
| `FIX-ORDER` | derive the required ordering at the call site instead of relying on `items()` order |
| `FIX-PRECEDENCE` | remove the duplicate definition so only one layer defines the key |
| `FIX-FRESH` | request an uncached read via the documented fresh option |
| `FIX-RENAME` | move to the new parameter or API name |
| `FIX-KEYS` | deduplicate the key spellings so only one source entry folds to the key |

## Terms and Abbreviations

- SDK: software development kit.
- Census extraction record: the authoritative usage/expectation statement
  for one downstream service.
