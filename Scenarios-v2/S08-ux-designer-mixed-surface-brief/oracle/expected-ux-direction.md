# Expected UX Direction

The strongest `S08` responses converge on the same structural direction:

1. Keep the workflow split across two surfaces, but make the split legible.
   - desktop remains the place for local preparation, validation context, and revision work
   - web remains the place for shared review, approval, and publish decisions
2. Replace the current mismatched labels with one visible state ladder.
   - example shape: `Draft in desktop -> Ready for web review -> In web review -> Changes requested -> Approved to publish -> Published`
3. Make ownership explicit at every state.
   - curator owns desktop preparation and desktop revisions
   - reviewer owns the active review step
   - approver owns the final publish confirmation when review is clear
4. Make the return path explicit.
   - a change request from the web surface should send the curator back to the relevant desktop
     section with the reason and affected field or step visible
5. Gate publish behind review completion.
   - the publish affordance should not compete visually with unresolved review or clarification
     states

The exact labels may vary, but the best briefs clearly restructure both flow and state. Merely
asking for clearer copy, better styling, or more comments is not sufficient.
