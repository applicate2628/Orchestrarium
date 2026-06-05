# General-case over local symptoms

## Fundamental rule

Do not implement a local special case when the requested behavior, observed problem, or verified cause belongs to a broader state, contract, invariant, lifecycle, pipeline, or ownership boundary.

Default to implementing the general case owned by the underlying boundary. A narrow, surface-specific implementation is allowed only when the user or accepted task explicitly defines that exact limited boundary, and the implementation records why the broader case is intentionally out of scope.

This applies to all implementation work: new features, behavior changes, UI changes, refactors, workflow changes, tests, documentation that defines behavior, and bug fixes.

## Operational test

Before editing or committing an implementation, answer these checks:

1. What is the owner: state, contract, invariant, lifecycle, pipeline, or component boundary?
2. Is the requested or observed case just one mode, surface, input shape, or timing window of that owner?
3. Would the same requirement or cause apply to sibling modes, surfaces, inputs, or timing windows?
4. If yes, target the owner-level general case, not only the reported symptom.
5. If no, cite the evidence that proves the defect is confined to the specific boundary.

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

## Terms and Abbreviations

- **General case**: the full class of behavior governed by the same requirement, cause, owner, or invariant.
- **Invariant**: a rule that must remain true across all relevant states.
- **Owner**: the module, state machine, contract, lifecycle, or pipeline boundary responsible for maintaining an invariant.
- **Local special case**: an implementation that handles one visible example while leaving the owner-level class undefined or inconsistent.
