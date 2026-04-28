# N82 UX Runtime State Spec

`N82` benchmarks `design.ui-ux-structure` with an objective state-machine contract. The candidate
must write a UX-owned runtime state specification that maps workflow states, breakpoints, visible
affordances, forbidden cues, handoff boundaries, and non-goals.

## Scenario Summary

The ConsoleShip publish workflow shows misleading visual readiness. Local checks may be green while
remote review is stale, an owner may be missing, a risk may be accepted before regression evidence,
and auditor-only hidden exports can be misrepresented as available to all users. The correct UX
artifact prevents false publish readiness without drifting into frontend implementation.

## Expected Candidate Work

Edit only `candidate/ux-state-spec.json`.

The correct output:

- stays owned by `$ux-designer`
- defines exactly five runtime states
- defines exactly three breakpoint layout invariants
- defines exactly six affordance rules
- defines exactly five copy-ledger entries
- defines exactly three handoff contracts
- defines exactly five non-goals
- preserves the product boundary: UX may specify cues and priority, but not component APIs, CSS,
  tests, or implementation steps

## Bundle Map

- `inputs/` holds the workflow context, observed screen faults, and task contract
- `candidate/` holds the editable UX state spec
- `oracle/` defines the expected state, breakpoint, affordance, copy, handoff, and non-goal tuples
- `verifiers/` contains the local checker
