# Scope Boundaries

The scored repair must stay inside the platform-owned observability workspace.

## Explicitly out of scope

- backend instrumentation or application code in `candidate/backend-code/**`
- CI or packaging edits in `candidate/toolchain-owned/**`
- shared execution wrappers in `candidate/shared-runners/**`
- provider selection or routing material in `candidate/provider-routing/**`
- results snapshots or report surfaces in `candidate/results-surfaces/**`
- any file outside `Scenarios-v2/S20-platform-engineer-observability-patch/`

`S20` is a platform implementation bundle, not a backend, toolchain, runner, routing, or results
publication task.
