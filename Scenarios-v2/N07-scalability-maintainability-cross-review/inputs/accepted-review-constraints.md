# Accepted Review Constraints

1. Routing-basis lane membership should have one maintained owner.
2. Building the lane matrix should not repeatedly rescan and reparse the full scenario tree for
   each lane.
3. Snapshot history should stay bounded or summary-only rather than storing full repeated payloads.
4. The admitted change stays findings-only and does not open a repair-plan or redesign path.
