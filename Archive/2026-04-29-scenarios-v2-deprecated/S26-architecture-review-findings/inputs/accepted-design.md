# Accepted Design Packet

This review phase is verifying the implementation against the accepted design claims below.

## Claims list

1. `P06` review bundles produce one semantic artifact: a findings-only review report.
   The editable surface for the candidate remains `candidate/review-report.md` only.
2. Review-bundle authoring stays self-contained under the scenario root. Authoring helpers may use
   local bundle assets, but they must not depend on publication or result-ranking modules to derive
   bundle metadata.
3. Protected-path and read-only rules must have one maintained owner. Readmes, verifiers, and local
   helper code may reference that contract, but they should not each carry separately maintained
   copies that can drift.
4. The admitted phase is additive and stays inside one new `Scenarios-v2/S26-...` root without
   widening into implementation guidance, patch planning, or scoring-model changes.

## Expected review posture

- focus on maintainability, cohesion, dependency direction, and governance coherence
- return concrete findings with required fixes before merge
- avoid turning the review into a redesign packet or patch plan
