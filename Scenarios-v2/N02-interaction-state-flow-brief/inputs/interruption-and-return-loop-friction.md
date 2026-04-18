# Interruption And Return-Loop Friction

## High-cost failures

1. A reviewer question returns the curator to the desktop surface with no indication of the exact
   section or checkpoint that needs attention.
2. A validation failure that happens after a reviewer handoff wipes out the web-review context and
   makes the bundle look like an ordinary local draft.
3. Review sessions paused for time or dependency checks come back with no visible `resume from
   here` anchor.
4. Publish approval can look available even when the bundle is still in a change-return loop.

## Repeated complaints

- "I know the bundle came back, but I do not know from which state."
- "Every interruption feels like a reset instead of a resume."
- "The reviewer question and the local fix step are connected, but the UI hides that connection."
- "I cannot tell whether I am continuing the same loop or starting a new review cycle."

## Design pressure

The brief should solve explicit states, interruption handling, ownership, and resumable re-entry
first. It should not spend most of its energy on static visual hierarchy or implementation detail.
