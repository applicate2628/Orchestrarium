# State and Flow Friction

## Observed state labels

| Desktop label | Web label | Actual meaning | Current problem |
|---|---|---|---|
| `In progress` | `Draft` | curator is still assembling the packet | roughly aligned, but the web card appears too early |
| `Ready` | `Waiting` | local checks passed and reviewer pickup is needed | `Waiting` hides whether review has started |
| `Returned` | `Needs work` | packet needs revision | neither label exposes the reason for return |
| `Published` | `Published` | done | the only state with shared language |

## Known interruption cases

### Reviewer sends packet back for missing rollback note

- reviewer marks `Needs work`
- curator returns to desktop and lands on step 1
- curator rechecks files instead of the note field that triggered the return

### Local verifier fails after a web comment is already attached

- curator fixes files locally
- desktop loses the reviewer comment context
- reviewer later sees a new upload but cannot tell whether the original concern was addressed

### Approver is ready to publish while reviewer still has an unresolved clarification

- the publish affordance is visible because the packet has local green checks
- the unresolved clarification is buried in the history tab
- approver and curator disagree on whether the packet is actually publish-ready

## Design requirement implied by the friction

The revised UX must make:

- the current owner of the packet obvious
- the reason for a blocked or returned state visible without opening raw logs
- the desktop re-entry point explicit when work comes back from the web surface
- the publish step unavailable until review-specific blockers are resolved
