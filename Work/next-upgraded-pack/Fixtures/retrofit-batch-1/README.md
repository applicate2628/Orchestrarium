Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This directory is the implementation staging area for the first retrofit batch:

- `T08`
- `T09`
- `T10`
- `T22..T28`

## Scope

| Test range | Main line impact | Primary reuse source |
|---|---|---|
| `T08..T10` | `L06`, `L07`, `L08`, `L10` | legacy `M08..M10` fixtures and notes |
| `T22..T28` | `L08`, `L09`, `L10` | preserved `G12..G18` fixture families |

## Intended implementation rule

| Rule | Meaning |
|---|---|
| preserve legacy semantics where possible | retrofit should strengthen rather than erase what already separated models |
| upgrade to the shared hardening contract | every migrated test must gain broken-state, control-pass, owner verification, anti-hardcode, and anti-drift expectations |
| reuse concrete layout patterns from preserved fixtures | prefer existing `workspace/` or `repo/apps/<owner>/` patterns over inventing a new layout family |

## Known risk notes

| Risk | Meaning |
|---|---|
| `T10` remains text-output-heavy | the new runnable local fixture is now concrete, but it still verifies memo discipline rather than a code patch |
| worker-line pressure must stay nasty | do not soften `T22..T28` into toy fixtures |

## Next concrete action

Continue the retrofit fixture trees and verifier scripts inside this directory, starting with:

1. `T23`
2. `T24`
3. `T25..T28`

## Current concrete retrofit fixtures

- `T08-provider-local-note-fix/`
- `T09-root-cause-owner-debug/`
- `T10-resume-stale-context-rejection/`
- `T22-build-owner-continuity/`
