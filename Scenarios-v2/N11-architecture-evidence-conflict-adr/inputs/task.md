Role: `$architect`

Goal: write a conflict-aware ADR for normalizing external priority profile policy without hiding
provider-specific route constraints inside the worker or reviewer adapters.

Edit only `candidate/design-package.md`.

The ADR must choose one owning seam, reject the two alternatives, resolve the source conflict, and
write falsifiable claims for later review.

Hardening requirements:

- name each concrete evidence source path in the evidence ledger, not only `E-A`..`E-D`
- include a `## Evidence Binding Table` with columns `Evidence`, `Concrete source`,
  `Accepted claim`, `Decision use`, and `Conflict risk`
- explicitly mention `providerRoutes` when explaining why `X4` is route state, not a profile key
- name the forbidden dependency direction: adapters must not parse or infer lane/profile policy
- include a `## Forbidden Direction Test` table with columns `Forbidden read`, `Why forbidden`,
  and `Test implication`
- include a `## Migration And Tests` section with compatibility, route-state, and adapter-boundary regression tests
- each numbered claim must contain both `Verification:` and `Regression:` so a reviewer can falsify it
- include a `## Machine-Checkable Decision` section with one parseable JSON object exactly matching the selected seam,
  authoritative profile key, compatibility alias, route-state keys, non-profile routes, and forbidden adapter reads
