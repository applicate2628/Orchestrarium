# Evidence Conflict Repo Action Plan Task

Review the bounded repository snapshot in `candidate/repo-snapshot/` and write a source-bound action
plan in `candidate/action-plan.md`. Do not patch code, do not update docs, do not edit tests, and do
not invent a product decision.

## Required Output Shape

Write `candidate/action-plan.md` with exactly these top-level sections in this order:

1. `## Source Authority`
2. `## Evidence Conflict Ledger`
3. `## Command Evidence`
4. `## Action Plan`
5. `## Non-Claims`
6. `## Re-Intake Trigger`

### `## Source Authority`

One Markdown table with this exact header:

```text
| Rank | Source | Status | Why |
```

### `## Evidence Conflict Ledger`

One Markdown table with this exact header:

```text
| # | Claim | Current evidence | Conflicting evidence | Decision | Action |
```

### `## Command Evidence`

One Markdown table with this exact header:

```text
| Command | Observed status | Implication | Action |
```

### `## Action Plan`

One Markdown table with this exact header:

```text
| Owner | Files | Change type | Gate | Do not do |
```

### `## Non-Claims`

One Markdown table with this exact header:

```text
| # | Non-claim | Reason |
```

### `## Re-Intake Trigger`

One short paragraph. It must state when product re-intake is required.

Evidence cells should cite bundle-relative paths and line numbers. You must not edit
`candidate/repo-snapshot/`, `inputs/`, `oracle/`, or `verifiers/`.
