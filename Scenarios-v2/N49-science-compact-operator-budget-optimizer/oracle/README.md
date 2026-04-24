# Oracle

`optimizer-contract.json` is the source of truth for bundle shape, analytical physics cases, runtime budgets, staged artifact requirements, and expected start-state failures.

The verifier computes analytical cylinder and hydrogenic references internally. Candidate code must not read oracle files or copy verifier helper logic.
