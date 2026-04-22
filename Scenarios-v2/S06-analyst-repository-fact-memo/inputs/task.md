# S06 Task

Produce one factual research memo that answers the following questions from the bundle-local repo
slice under `candidate/repo-snapshot/`:

1. Which files and symbols currently determine which scenario bundles are loaded for a requested
   surface ID?
2. Where does the active `score_profile` come from when a result row is written?
3. What evidence shows whether archived v1 scenario material is still part of the live path or
   only retained as historical reference?
4. Which claims from `inputs/noisy-intake-notes.md` are false leads in the visible slice?
5. What remains unknown because the bounded slice does not include the relevant caller or runtime
   surface?

## Required output shape

Edit only `candidate/repository-fact-memo.md`. Produce exactly these top-level sections in this
order:

1. `# S06 Repository Fact Memo`
2. `## Investigation goal`
3. `## Confirmed Facts`
4. `## False Leads Rejected`
5. `## Explicit Unknowns`
6. `## Gate Decision`

### `## Confirmed Facts`

One Markdown table with this exact header row and column order:

```text
| # | Question | File | Line | Symbol | Fact |
```

Rules for each row:

- `#` — row number `1`, `2`, `3`, …
- `Question` — the investigation question number this fact answers (`1`, `2`, `3`, or a
  combination like `1/2` when the same fact answers more than one question).
- `File` — bundle-relative path under `candidate/repo-snapshot/`.
- `Line` — a single integer — the primary line where the fact is visible in the file.
- `Symbol` — the specific Python symbol, constant, dataclass field, function, or import name
  that the fact cites.
- `Fact` — a short factual statement (3–25 words) that names what the code does at that
  location, with enough keyword specificity that a reader can cross-check it against the file.

### `## False Leads Rejected`

One Markdown table with this exact header row and column order:

```text
| # | Note Theme | File | Why Rejected |
```

Rules for each row:

- `#` — row number.
- `Note Theme` — a short phrase (3–10 words) naming which abstract theme from
  `inputs/noisy-intake-notes.md` this rejection addresses (for example `legacy config module
  drives profile lookup`).
- `File` — the bundle-relative path to the file in the repo slice that the theme pointed at,
  once you discovered it through investigation.
- `Why Rejected` — a short explanation (4–25 words) citing why the visible slice shows the
  theme is not the live path (which symbol or test demonstrates the real path instead).

### `## Explicit Unknowns`

One Markdown table with this exact header row and column order:

```text
| # | Unknown | Why |
```

Rules for each row:

- `Unknown` — a short label for the missing piece (3–12 words).
- `Why` — a short explanation that names what the bounded slice does not cover.

### `## Gate Decision`

One line containing exactly one of: `PASS`, `REVISE`, `BLOCKED`.

Use `PASS` when every question is answered from the visible slice with confirmed evidence, every
false-lead theme is rejected against the real path, and the remaining gaps are recorded as
explicit unknowns.

## Scope rules

- Cite bundle-relative paths under `candidate/repo-snapshot/`.
- Keep the memo factual. Do not include recommendations, design choices, phase plans, or code
  changes.
- Do not fabricate line numbers or symbol names — every cited `(file, line, symbol)` must exist
  in the visible slice.
- Do not edit `candidate/repo-snapshot/`, `inputs/`, `oracle/`, or `verifiers/`.
- If any cell in the tables needs a literal `|` character, escape it as `\|`.
