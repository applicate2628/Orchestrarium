# General-case over local symptoms

## Fundamental rule

Do not implement a local special case when the requested behavior, observed problem, or verified cause belongs to a broader state, contract, invariant, lifecycle, pipeline, or ownership boundary.

Default to implementing the general case owned by the underlying boundary. A narrow, surface-specific implementation is allowed only when the user or accepted task explicitly defines that exact limited boundary, and the implementation records why the broader case is intentionally out of scope.

This is a correctness rule, not a request to make everything abstract. The right implementation targets the correct concept/abstraction level: the smallest owner-level class that explains the verified requirement or cause. It should be general enough to keep sibling cases consistent, but not so broad that it invents future requirements or hides a simpler owner.

Correctness beats speed unless the user explicitly scopes the work as prototype, fastest-path, throwaway, or otherwise time-boxed. Even then, record the boundary so the shortcut is visible rather than mistaken for the canonical design.

This applies to all implementation work: new features, behavior changes, UI changes, refactors, workflow changes, tests, documentation that defines behavior, and bug fixes.

## Operational test

Before editing or committing an implementation, answer these checks:

1. What concept is really involved, and what is the correct concept/abstraction level?
2. What is the owner: state, contract, invariant, lifecycle, pipeline, or component boundary?
3. Is the requested or observed case just one mode, surface, input shape, or timing window of that owner?
4. Would the same requirement or cause apply to sibling modes, surfaces, inputs, or timing windows?
5. If yes, target the owner-level general case, not only the reported symptom.
6. If no, cite the evidence that proves the defect is confined to the specific boundary.
7. Is the chosen path correct, or merely faster? If it is a speed-scoped shortcut, cite the explicit user scope.

## Operational ladder

Use this ladder when a request names one concrete example:

1. Visible symptom or requested example.
2. Common concept behind it.
3. Owner/invariant that governs the concept.
4. Sibling cases the same owner must keep consistent.
5. Smallest correct implementation at that owner.
6. Explicit special-case boundary only if the broader class is user-rejected, out of scope, or disproved by evidence.

## Commit discipline

The commit body for an implementation must state the preserved or generalized invariant when the user request or visible symptom names only one example of a broader class.

If the patch intentionally implements only one special case, the commit body must include:

- the explicit user-approved boundary;
- the broader cases left untouched;
- the verification that those broader cases are either unaffected or intentionally out of scope.

## Banned justifications

These are not valid reasons for a narrow fix:

- "The user mentioned only this mode."
- "The example was visible only here."
- "This is the fastest patch."
- "Other modes probably do not hit it."
- "We can generalize it later."
- "The correct abstraction would take longer."

## Terms and Abbreviations

- **General case**: the full class of behavior governed by the same requirement, cause, owner, or invariant.
- **Concept/abstraction level**: the level of behavior being changed, from one visible symptom up through the owner-level invariant that explains all sibling cases.
- **Invariant**: a rule that must remain true across all relevant states.
- **Owner**: the module, state machine, contract, lifecycle, or pipeline boundary responsible for maintaining an invariant.
- **Local special case**: an implementation that handles one visible example while leaving the owner-level class undefined or inconsistent.
