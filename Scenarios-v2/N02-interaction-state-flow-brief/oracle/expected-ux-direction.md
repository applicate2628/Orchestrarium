# Expected UX Direction

The strongest `N02` responses converge on the same structural direction:

1. Introduce one explicit state ladder across both surfaces.
   - example shape: `Local draft -> Ready for review handoff -> In web review -> Question or
     change loop -> Returned for local revision -> Ready to re-enter review -> Approved to publish`
2. Separate progress states from interruption states.
   - validation failures, timed pauses, deferred approvals, and open reviewer questions should not
     masquerade as ordinary progress
3. Make the return loop explicit.
   - a reviewer question or publish blocker should route the curator back to the correct desktop
     checkpoint with the reason and owning next action visible
4. Preserve context when work resumes.
   - the system should show where the operator left, what changed, and what state they are
     re-entering
5. Gate publish behind resolved loops.
   - publish should not compete with unresolved question, change, or interruption states

The exact labels may vary, but the best briefs define both the state model and the resumable path.
