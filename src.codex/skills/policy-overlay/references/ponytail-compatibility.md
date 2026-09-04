# Ponytail compatibility reference

## Table of contents

- [Observed upstream contract](#observed-upstream-contract)
- [Ownership split](#ownership-split)
- [Recommended co-installation](#recommended-co-installation)
- [Compatibility matrix](#compatibility-matrix)
- [Non-goals](#non-goals)
- [Terms and abbreviations](#terms-and-abbreviations)

## Observed upstream contract

The compatibility fixture was reviewed against `DietrichGebert/ponytail` main commit `2ed6c52c9d7e5e56942508591085fd45dea277d3` and package version `4.9.0`.

The observed Claude/Codex hook manifest contains:

- `SessionStart` for activation;
- `SubagentStart` for child-agent propagation;
- `UserPromptSubmit` for mode tracking.

Ponytail also exposes the independent skills `ponytail`, `ponytail-review`, `ponytail-audit`, `ponytail-debt`, `ponytail-gain`, and `ponytail-help`.

This reference records the compatibility fixture, not a runtime pin or dependency. A newer Ponytail release remains external and must be re-audited if it changes storage ownership or hook shape.

## Ownership split

Orchestrarium owns only its marked hook entries, provider-pack files, routing settings, and policy-overlay catalog. Ponytail owns its package files, mode state, hook commands, skills, and uninstall/update lifecycle.

Unknown third-party entries are preserved. Name similarity, event sharing, or installation order does not transfer ownership.

## Recommended co-installation

Ponytail stays under its own plugin manager. For Codex, install Ponytail with its current upstream plugin commands, then run the normal Orchestrarium installer; the reverse order is also supported:

```bash
codex plugin marketplace add DietrichGebert/ponytail
codex plugin add ponytail@ponytail
python scripts/install-codex.py --global
```

For Claude Code, enter the two Ponytail plugin commands as separate host prompts and run the normal Orchestrarium installer independently:

```text
/plugin marketplace add DietrichGebert/ponytail
/plugin install ponytail@ponytail
```

```bash
python scripts/install-claude.py --global
```

After either order, verify that the provider still contains Ponytail's `SessionStart`, `SubagentStart`, and `UserPromptSubmit` registrations and Orchestrarium's own marked hooks. Reinstalling Orchestrarium must not remove Ponytail entries or its skill directory.

## Compatibility matrix

| Sequence or state | Required Orchestrarium behavior |
| --- | --- |
| Orchestrarium only | Existing behavior; no optional overlay selected by default |
| Ponytail only | Outside Orchestrarium ownership |
| Orchestrarium then Ponytail | Ponytail remains external; its host/plugin manager must preserve unrelated Orchestrarium state |
| Ponytail then Orchestrarium | Orchestrarium preserves Ponytail hooks, skills, settings, and instruction blocks |
| Orchestrarium reinstall with Ponytail | Only Orchestrarium-owned stock is reconciled |
| Ponytail reinstall with Orchestrarium | Outside Orchestrarium mutation authority; Ponytail remains responsible for preserving unrelated host state |
| Orchestrarium hook removal | Only the matching Orchestrarium marker is removed |
| Ponytail removal | External plugin manager removes only Ponytail-owned state |

## Non-goals

Orchestrarium does not copy Ponytail source, manage Ponytail modes, execute Ponytail hooks, provide a Ponytail-specific core manager, or treat package presence as policy activation.

## Terms and abbreviations

- **Codex:** the OpenAI coding-agent provider pack supported by Orchestrarium.
- **Claude Code:** the Anthropic coding-agent provider pack supported by Orchestrarium.
- **Hook:** a command registered for a host lifecycle event.
- **MIT License:** a permissive software license used by Ponytail.
- **Upstream:** the independently maintained external source repository.
