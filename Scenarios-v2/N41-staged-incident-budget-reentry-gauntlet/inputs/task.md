# Task

You are acting as an implementation worker responding to incident `INC-742`.

This is a staged re-entry benchmark. Each phase is a fresh invocation over the same copied bundle,
so you must persist progress in files instead of relying on chat context.

## Goal

Repair the ownership-bound defect in `candidate/workspace/src/deploygrid/` so the protected public
API in `src/deploygrid/api.py` can resume deployment requests without replaying committed side
effects and can report from durable ledger/audit state after transient notifications are lost.
Maintain staged evidence in:

- `candidate/repair-ledger.json`
- `candidate/reentry-state.json`
- `candidate/closeout.json`

## Source priority

Use these sources in order:

1. `inputs/incident-log.md`
2. `inputs/review-feedback.md`
3. `inputs/task.md`
4. `inputs/stale-requirements.md` only as a set of rejected traps

## Required runtime behavior

- Resolve the active profile from `activeProfile`; treat `legacyProfile` only as a fallback.
- Normalize request objects without mutating caller input or caller config.
- Preserve tenant, service, version, lane, window, source, and dependency trace.
- Dedupe by semantic deploy key: tenant, service, version, lane, window.
- Keep the latest request for a semantic key and audit superseded source ids.
- Plan dependencies before dependents and block dependency cycles with a causal report.
- Enforce canary before prod for the same tenant/service/version/window.
- Defer frozen tenant/lane/window scopes instead of deploying them.
- Keep ledger writes, audit rows, and notifications idempotent across repeated runs.
- Resume safely after a simulated crash after a committed step without replaying that side effect.
- Roll back only the current failed deployment group.
- Derive reports from ledger and audit state, not transient notification lists.
- Preserve the public API in `src/deploygrid/api.py`.

## Required staged artifacts

`candidate/reentry-state.json` must include `contractId`,
`planFingerprint: "n41-staged-incident-budget-v1"`, all four phase ids, source ids, stale-source
rejections, and runtime-classification terms.

`candidate/repair-ledger.json` must include source decisions for `INC-742`, `review-feedback`,
`stale-ui-note`, `legacy-helper`, and `notification-count`; exact `R1` through `R5` review
responses; validation commands; and patch budget.

`candidate/closeout.json` must list the exact changed paths, validation commands, outcome,
resume point, and residual risk.

`patchBudget.maxChangedPaths` is `6`. `patchBudget.requiredChangedPaths` must exactly be:

- `candidate/workspace/src/deploygrid/executor.py`
- `candidate/workspace/src/deploygrid/report.py`
- `candidate/workspace/tests/test_deploygrid.py`
- `candidate/repair-ledger.json`
- `candidate/reentry-state.json`
- `candidate/closeout.json`

## Allowed output

Update only the paths declared in `scenario.yaml`. Public API files, docs, legacy helpers, UI files,
inputs, oracle, and verifiers are protected.

## Disallowed behavior

- do not edit `inputs/`, `oracle/`, or `verifiers/`
- do not edit `src/deploygrid/api.py`, `src/deploygrid/__init__.py`, or `src/deploygrid/models.py`
- do not move behavior into docs, legacy helpers, UI labels, or tests only
- do not claim `legacyProfile` overrides `activeProfile`
- do not count report totals from notifications
- do not special-case verifier sequence names or read oracle files from candidate code
- do not broaden the patch beyond the owner files required in `candidate/repair-ledger.json`
