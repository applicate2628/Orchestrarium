# Dependency Map

## Current dependency direction

```text
accepted planning docs
        |
        v
  scenario bundle root
  +-------------------------------+
  | scenario.yaml                 |
  | inputs/                       |
  | candidate/design-package.md   |
  | oracle/                       |
  | verifiers/                    |
  +-------------------------------+
        |
        v
 local verifier result
        |
        v
 shared score profile
        |
        v
 publication tables
```

## Protected boundaries

- `scenario.yaml` is a universal metadata contract, not a design-only schema surface.
- `inputs/`, `oracle/`, and `verifiers/` are scenario-local bundle surfaces.
- the shared scorer consumes role-class scoring profiles and verifier outcomes, not scenario-specific
  architecture prose
- publication tables depend on scored results and scenario mapping, not on bundle-internal ADR
  structure

## Dependency rule to preserve

The accepted design may let bundle-local verifier logic depend on the stable bundle contract and
score-profile model, but the global scorer must not become the owner of scenario-specific architect
seam rules.
