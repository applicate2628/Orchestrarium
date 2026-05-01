Date: 2026-05-01
Owner: `$qa-engineer`
Status: `ADMITTED`

## Verifier

Use `check_adr_long_horizon.py`.

| Check | Command |
|---|---|
| bundle shape | `python Scenarios-v3/V3L02-adr-long-horizon-source-conflict/verifiers/check_adr_long_horizon.py --bundle-shape-only` |
| reference candidate | `python Scenarios-v3/V3L02-adr-long-horizon-source-conflict/verifiers/check_adr_long_horizon.py --candidate-root .scratch/verifier-probes/2026-05-01-v3l02-reference/candidate` |
| completed model candidate | `python Scenarios-v3/V3L02-adr-long-horizon-source-conflict/verifiers/check_adr_long_horizon.py` |

The verifier is deterministic and uses only local files.

## Terms and Abbreviations

- `ADR`: Architecture Decision Record.
