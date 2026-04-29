# Evidence Map

| Evidence ID | Source | Read |
|---|---|---|
| `E-A` | `Orchestrarium/shared/agents-mode.defaults.yaml` | authoritative policy shape uses `externalPriorityProfiles` plural |
| `E-B` | `Archive/legacy-provider-runbook.md` | stale note still says `externalPriorityProfile` singular |
| `E-C` | `benchmarks/Work/next-upgraded-pack/Results-drafts/short-results-current-2026-04-18.md` | `X4` is a runtime transport route constraint: secret-backed Claude only, not a separate policy key |
| `E-D` | `Orchestrarium/shared/external-adapter-contract.md` | adapters consume resolved priority order and must not infer lane semantics |

Conflict to resolve:

`E-B` conflicts with `E-A`. The ADR must name `E-A` authoritative and `E-B` stale compatibility input.
