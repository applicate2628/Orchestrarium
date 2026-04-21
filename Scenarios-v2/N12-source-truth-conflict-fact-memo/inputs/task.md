Role: `$analyst`

Goal: produce a factual memo about the routing source of truth and current hardened-result status.

Edit only `candidate/repository-fact-memo.md`.

The memo must rank sources, resolve plural-vs-singular profile conflict, separate route status from
model capability, and state whether the hardened core12 read separates `X1` from `X3`.

Hardening requirements:

- include a `## Evidence Line Ledger` table with columns `Citation`, `Source`, `Fact extracted`,
  and `Status`
- include the exact term `providerRoutes` when describing route status for `X4`
- include at least one explicit `Gap:` line under confidence and gaps
- keep the `X1`/`X3` statement non-directional unless a cited source actually ranks them
- include a `## Non-Claim And Gap Ledger` table with columns `Non-claim`, `Why excluded`, and
  `Required follow-up`
- cite concrete snapshot lines using `path:line` for every major fact; required citations include
  `config/agents-mode.defaults.yaml:1`, `config/agents-mode.defaults.yaml:10`,
  `config/agents-mode.defaults.yaml:11`, `docs/operator-routing.md:7`,
  `results/hardened-core12.md:5`, `results/hardened-core12.md:6`,
  `results/hardened-core12.md:9`, `results/result-manifest.md:3`,
  `results/result-manifest.md:4`, `results/result-manifest.md:6`,
  `results/legacy-top-pair.md:5`, `results/legacy-top-pair.md:6`,
  `docs/legacy-notes.md:3`, and `docs/legacy-notes.md:5`
- explicitly reject `legacy-top-pair.md` as `superseded_result`; it does not override the
  manifest-selected `authoritative_result`
