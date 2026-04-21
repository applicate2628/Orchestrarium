Date: 2026-04-21
Owner: `$lead`
Status: `PASS`

## Rubric Result

| Row | Score | Read |
|---|---:|---|
| `X1 / gpt-5.4` | `60 / 60` | wins E3 |
| `X3 / opus 4.7max` | `59 / 60` | below X1 on E3 |

E3 verdict: `X1`.

## Source Roots

| Row | Scratch root |
|---|---|
| `X1` | `..\..\.scratch\v2-cohort-runs\2026-04-21_14-43-50-X1-x1-v3-ui-review-e2-hardening-2026-04-21` |
| `X3` | `..\..\.scratch\v2-cohort-runs\2026-04-21_15-00-47-X3-x3-v3-ui-review-e2-hardening-2026-04-21` |

## Scenario Scores

| Scenario | X1 | X3 | Delta |
|---|---:|---:|---:|
| `N11` | `20 / 20` | `20 / 20` | `0` |
| `N12` | `20 / 20` | `20 / 20` | `0` |
| `N13` | `20 / 20` | `19 / 20` | `-1` |

## Criterion Detail

| Scenario | Criterion | X1 | X3 | Delta |
|---|---|---:|---:|---:|
| `N11` | source specificity | `4` | `4` | `0` |
| `N11` | conflict resolution precision | `4` | `4` | `0` |
| `N11` | ownership seam | `4` | `4` | `0` |
| `N11` | adapter boundary | `4` | `4` | `0` |
| `N11` | route-policy separation | `4` | `4` | `0` |
| `N12` | source ranking | `4` | `4` | `0` |
| `N12` | confirmed fact precision | `4` | `4` | `0` |
| `N12` | legacy conflict handling | `4` | `4` | `0` |
| `N12` | top-pair non-claim | `4` | `4` | `0` |
| `N12` | gap discipline | `4` | `4` | `0` |
| `N13` | finding localization | `4` | `4` | `0` |
| `N13` | scoreability semantics | `4` | `4` | `0` |
| `N13` | fix specificity | `4` | `4` | `0` |
| `N13` | false-positive discipline | `4` | `4` | `0` |
| `N13` | denominator reporting | `4` | `3` | `-1` |

## Method

This is a deterministic structural rubric over already generated artifacts.
It does not replace scenario verifiers and does not add a routing lane.

| Boundary | Meaning |
|---|---|
| supplied run roots | scores the `N11..N13` artifacts in the roots named above |
| no pass/fail override | both rows still pass E2 binary verifiers |
| diagnostic-only | use only as E3 top-pair signal, not as `externalPriorityProfiles` input |
