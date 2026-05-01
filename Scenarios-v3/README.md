Date: 2026-05-01
Owner: `$knowledge-archivist`
Status: `RUN / BINARY TIE`

# Scenarios-v3

`Scenarios-v3/` is the active discovery root for the next benchmark generation.

At base creation it contained no admitted scenario roots. V3 now starts from the embedded pre-v3
RF12 line map, the active registry, and newly admitted V3 roots. No v2 roots, release packages,
or retired diagnostics are copied forward.

## Current State

| Field | Value |
|---|---|
| admitted roots | `1` |
| admitted root | `V3L02-adr-long-horizon-source-conflict` |
| target line | `L02 advisory.design-adr` |
| model runs | `X1 PASS`; `X3 PASS`; `X2 scoreable FAIL calibration`; `X4 NOT-RUN / disabled` |
| admission evidence | `../Work/scenarios-v3-base/Evidence/v3l02-admission-2026-05-01.json` |
| current result | `binary tie remains` for `X1` vs `X3` |
| next action | design the next stronger L02 separator or move to the next unresolved v3 line |

## Source of Truth

| Surface | Use |
|---|---|
| `_registry/scenarios-v3-base.json` | machine-readable v3 line, trigger, and admission registry |
| `../Work/scenarios-v3-base/` | mutable v3 design, templates, evidence, and future draft results |
| `V3L02-adr-long-horizon-source-conflict/` | first admitted v3 root and current L02 result |

## Active Discovery Rule

Only admitted Scenarios-v3 roots may live at top level under `Scenarios-v3/`.

| Allowed at top level | Rule |
|---|---|
| `_registry/` | metadata only; not a score root |
| admitted v3 scenario root | requires accepted task, oracle, verifier, reference/synth pass, and score policy |

| Not allowed at top level | Destination |
|---|---|
| exploratory drafts | `../Work/scenarios-v3-base/Planning/` or `../Work/scenarios-v3-base/Evidence/` |
| diagnostics without denominator admission | `../Work/scenarios-v3-base/Results-drafts/` |
| deprecated or superseded roots | future `../Archive/<snapshot>/` |

## Admission Gate

Each new v3 scenario root must pass these checks before it is placed in active discovery:

| Gate | Required evidence |
|---|---|
| task contract | explicit role trigger, source package, output shape, and forbidden shortcuts |
| oracle | machine-readable expected behavior or scored rubric with exact tuple terms |
| verifier | deterministic local verifier with scoreable FAIL vs runtime/route separation |
| reference probe | synthesized or reference candidate passes the verifier |
| shape check | bundle-shape or equivalent structural check passes |
| result policy | line, denominator impact, row scope, and rerun policy are declared |

## Terms and Abbreviations

- `RF12`: role-fit scorecard over twelve routing lines plus one owner/control line.
- `pre-v3 RF12 line map`: distilled line-priority and role-fit basis embedded in the v3 registry and planning map.
- `v3 root`: an admitted Scenarios-v3 scenario directory under this top-level folder.
