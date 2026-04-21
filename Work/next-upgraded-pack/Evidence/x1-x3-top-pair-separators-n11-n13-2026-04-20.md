Date: 2026-04-20
Owner: `$lead`
Status: `PASS`

## Scope

This evidence covers diagnostic overlay `E2 top-pair-separator` for `X1` and `X3`.

`E2` is not a routing lane and is not part of `externalPriorityProfiles`. It was added after
the hardened core-12 weak-separator subset left `X1` and `X3` tied.

## Local Validation

| Check | Result |
|---|---|
| `N11` JSON contract parse | `PASS` |
| `N12` JSON contract parse | `PASS` |
| `N13` JSON contract parse | `PASS` |
| `N11` `--bundle-shape-only` | `PASS` |
| `N12` `--bundle-shape-only` | `PASS` |
| `N13` `--bundle-shape-only` | `PASS` |
| `git -C benchmarks diff --check` before execution | `PASS` |
| `mcp-free` before hardened2 execution | `STATS kill: none` |

## Run Roots

| Attempt | Row | Root |
|---|---|---|
| initial E2 | `X1 / gpt-5.4` | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_11-51-25-X1-x1-top-pair-separators-n11-n13-2026-04-20/` |
| initial E2 | `X3 / opus 4.7max` | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_11-51-25-X3-x3-top-pair-separators-n11-n13-2026-04-20/` |
| hardened2 E2 | `X1 / gpt-5.4` | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_12-02-56-X1-x1-top-pair-separators-n11-n13-hardened2-2026-04-20/` |
| hardened2 E2 | `X3 / opus 4.7max` | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_12-02-56-X3-x3-top-pair-separators-n11-n13-hardened2-2026-04-20/` |

## Hardening Delta

| Scenario | Added after initial tie |
|---|---|
| `N11` | requires visible deprecation signal, singular-to-plural rewrite, non-exported adapter parsing boundary, regression test, and `X4` never appearing as a profile key |
| `N12` | requires explicit `X4` no lane-profile membership, no directional claim between `X1` and `X3`, and gaps for additional separators plus `X4` recovery timeline |
| `N13` | requires concrete fix guidance for every finding, including distinct `REQUEUE`, `TIMEOUT-ARTIFACT-OK`, `len(scoreable)`, and non-scoreable counts surfaced separately |

## Result Matrix

| Attempt | Scenario | X1 `gpt-5.4` | X3 `opus 4.7max` |
|---|---|---|---|
| initial E2 | `N11` | `PASS` | `PASS` |
| initial E2 | `N12` | `PASS` | `PASS` |
| initial E2 | `N13` | `PASS` | `PASS` |
| hardened2 E2 | `N11` | `PASS` | `PASS` |
| hardened2 E2 | `N12` | `PASS` | `PASS` |
| hardened2 E2 | `N13` | `PASS` | `PASS` |

## Scoreable Read

| Row | Initial E2 | Hardened2 E2 | Runtime caveat |
|---|---:|---:|---|
| `X1 / gpt-5.4` | `3 / 3` | `3 / 3` | none |
| `X3 / opus 4.7max` | `3 / 3` | `3 / 3` | none |

## Interpretation

| Question | Evidence-backed answer |
|---|---|
| Did E2 separate `X1` and `X3`? | No. Both rows passed all initial and hardened2 gates. |
| Did hardening create scoreable failures? | No. The stricter gates were still passed by both rows. |
| What does this prove? | `X1` and `X3` both handle this class of architecture, source-truth, and adversarial review separator. |
| What remains unresolved? | Binary gates in `N11..N13` do not rank `X1` versus `X3`; a quality/rubric score or a different task family is needed for a defensible top-pair ordering beyond the full-v2 score. |
