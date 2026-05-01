Date: 2026-05-01
Owner: `$knowledge-archivist`
Status: `RUN / BINARY TIE`

# V3L02 ADR Long-Horizon Source Conflict

This Scenarios-v3 root targets `L02 advisory.design-adr`.

The task is intentionally ordinary ADR work, not a staged review gate and not an output-budget
separator. It measures whether a model can resolve conflicting source authority over a
long-horizon migration decision without overclaiming stale design notes.

## Candidate Contract

| Field | Value |
|---|---|
| role | `$architect` |
| output files | `candidate/adr-decision.json`, `candidate/adr-decision.md` |
| allowed edits | candidate decision files only |
| target decision | boundary-owned compatibility adapter |
| forbidden shortcut | global bus rewrite, direct schema switch, consumer-side shims, or stale-ADR-first decision |

## Local Checks

| Check | Command |
|---|---|
| oracle JSON parse | `python -c "import json; json.load(open('Scenarios-v3/V3L02-adr-long-horizon-source-conflict/oracle/adr-long-horizon-contract.json'))"` |
| bundle shape | `python Scenarios-v3/V3L02-adr-long-horizon-source-conflict/verifiers/check_adr_long_horizon.py --bundle-shape-only` |
| reference candidate | `python Scenarios-v3/V3L02-adr-long-horizon-source-conflict/verifiers/check_adr_long_horizon.py --candidate-root .scratch/verifier-probes/2026-05-01-v3l02-reference/candidate` |
| completed model candidate | `python Scenarios-v3/V3L02-adr-long-horizon-source-conflict/verifiers/check_adr_long_horizon.py` |

The starter candidate is intentionally incomplete; the completed model-candidate check is expected
to pass only after a model run edits the allowed candidate files.

## Run Boundary

`X1` and `X3` were launched on 2026-05-01 and both passed the completed-candidate verifier.
`binary tie remains` for the primary pair on this root. `X2` was run as cheap calibration and
scoreably failed by leaving the starter candidate unchanged. `X4` was not run because it is disabled
for the current cycle.

## Terms and Abbreviations

- `ADR`: Architecture Decision Record.
- `RF12`: role-fit scorecard over twelve routing lines plus one owner/control line.
- `v3`: Scenarios-v3 benchmark generation.
