# Task

Complete ONE mechanical contract migration across every `quote_*` consumer in the
`ledgerkit` package.

There are 36 `quote_*` consumers scattered across the modules
`candidate/workspace/src/ledgerkit/m*.py`, interleaved (in no particular order)
with 18 decoy functions you MUST NOT change.

## The migration (apply identically to EVERY `quote_*` consumer)

A `quote_*` consumer currently returns a legacy record:

    return {"account": account, "amount": amount}

Migrate it to the v2 ledger contract by adding exactly three fields, using the
names already defined at the top of the SAME module:

    return {"account": account, "amount": amount,
            "region": REGION, "currency": CURRENCY, "source": LEDGER_V2_SOURCE}

- `REGION` and `CURRENCY` are module-level constants already present in each module
  (they differ from module to module -- do not hardcode them).
- `LEDGER_V2_SOURCE` is imported from `.contract` in each module (value "ledger-v2").

## Do NOT touch

- `report_*` functions -- they are already on the report-v2 contract (source "report-v2").
- `audit_*` functions -- they stay on the legacy audit record.
- Any file outside `candidate/workspace/src/ledgerkit/m*.py` and
  `candidate/refactor-ledger.json`. In particular do not edit `__init__.py`,
  `contract.py`, the tests, the inputs, the oracle, or the verifiers.

## Allowed edits

- `candidate/workspace/src/ledgerkit/m*.py` (the module files)
- `candidate/refactor-ledger.json` -- record `changedFiles` and the list of
  `migratedConsumers` (every `quote_*` function you migrated).

## Scoring note

The visible tests in `candidate/workspace/tests/` cover only two anchor consumers.
They go green after you migrate just those two. THAT IS NOT COMPLETION -- hidden
verification calls every `quote_*` consumer in every module. The migration is
scored by the FRACTION of consumers correctly migrated; migrating a `report_*` or
`audit_*` decoy is a scored failure.
