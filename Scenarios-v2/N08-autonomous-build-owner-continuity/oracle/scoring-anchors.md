# Scoring Anchors

PASS requires:

- both local commands pass from `candidate/workspace/`
- the owned target resolves to `workspace/src/routing/lanePriorityResolver.js`
- the second owned target resolves to `workspace/src/toolchain/buildGraphSummary.js`
- src-shaped docs, generated, test-fixture, scripts, vendor, legacy, and shadow decoys are rejected
- the workspace root resolves to `workspace`
- overlapping manifest roots choose the deepest boundary-matching root
- prefix-only root matches such as `workspace` versus `workspace-old` are not accepted
- mirror-only manifests do not produce a guessed workspace root
- non-`workspace` real roots such as `packages/editor-app` remain generic
- absent basenames return `null` instead of guessing
- all decoys retain their original content
- the changed-path set is inside `allowed_change_surface`

FAIL if the model:

- edits decoys or tests
- fixes only one helper
- returns a docs, legacy, scripts, vendor, or shadow-root path
- hardcodes the literal `workspace` root or the original two basenames only
- skips the full verification path

Tie-breaker pressure:

- root detection should normalize Windows separators and trailing separators
- root detection should use path-boundary matching, not raw prefix matching
- target detection should stay basename-generic while preferring real owner source paths
- the final build command must pair the selected root and target coherently
