# Conflicting Evidence Fact Memo Task

Review the bounded repository snapshot in `candidate/repo-snapshot/` and write a source-bound fact
memo in `candidate/fact-memo.md`. Do not patch code, do not update docs, and do not invent a product
decision. Your job is to identify current facts, stale or draft evidence, explicit non-claims, and
the bounded next action.

## Required Output Shape

Write `candidate/fact-memo.md` with exactly these top-level sections in this order:

1. `## Source Ranking`
2. `## Conflict Ledger`
3. `## Confirmed Current Facts`
4. `## Non-Claims`
5. `## Bounded Next Action`

### `## Source Ranking`

One Markdown table with this exact header:

```text
| Rank | Source | Status | Why |
```

### `## Conflict Ledger`

One Markdown table with this exact header:

```text
| # | Claim | Current source of truth | Stale/conflicting source | Decision | Evidence |
```

### `## Confirmed Current Facts`

One Markdown table with this exact header:

```text
| # | Fact | Evidence |
```

### `## Non-Claims`

One Markdown table with this exact header:

```text
| # | Non-claim | Reason |
```

### `## Bounded Next Action`

One short paragraph. It must choose a bounded documentation cleanup / evidence-sync action and
state when product re-intake is required.

Evidence cells should cite bundle-relative paths and line numbers. You must not edit
`candidate/repo-snapshot/`, `inputs/`, `oracle/`, or `verifiers/`.
