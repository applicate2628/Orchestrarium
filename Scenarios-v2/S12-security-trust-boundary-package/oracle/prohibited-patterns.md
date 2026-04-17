# Prohibited Patterns

The following patterns should lose correctness, role-fidelity, or scope-discipline points.

- Generic security language with no boundary IDs, no control IDs, and no evidence references
- Treating provider output as trusted because it came from an approved CLI or service
- Suggesting real credentials, live tokens, or runnable provider wrappers inside the fixture
- Returning a code patch, config patch, or runtime execution transcript instead of a constraint
  package
- Returning a findings-only review report with severities but no forward constraints
- Collapsing the raw evidence vault and analyst export into one shared trust surface
- Deferring secret-handling and path-confinement concerns to "later review"
