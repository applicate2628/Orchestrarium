# Complexity Review Policy

Perform one additional, non-authorizing review focused only on avoidable implementation complexity.

Look for:

- new code or dependencies that duplicate an accepted repository helper, the language standard library, or a native platform capability;
- an abstraction with one implementation and no accepted second consumer;
- a factory with one product;
- a wrapper that only delegates;
- speculative configuration, extension points, or compatibility paths;
- unused flexibility or a dead compatibility layer;
- repeated logic that one existing owner can absorb;
- code that can be deleted without weakening an accepted requirement.

For each finding, name the exact location, what can be removed, and the smaller replacement. End with the estimated net line and dependency reduction only when it is grounded in the inspected diff.

This review does not replace correctness, security, performance, accessibility, recovery, verification, or publication review. Never recommend deleting a trust-boundary check, authorization rule, data-loss control, explicit requirement, mandatory test, or required evidence.
