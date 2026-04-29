# Task

Surface: `R12 $security-engineer`
Artifact type: `security constraint package`
Modality family: `threat and trust analysis`

## Goal

Produce `candidate/security-constraint-package.md` for the proposed `relay-and-export` mode in the
benchmark runner.

The package must be suitable input to later planning and later security review. It must stay in the
security-engineer lane: define constraints and required controls before implementation. Do not
return a code patch, runtime wrapper change, or findings-only review.

## Required output content

Your package must include:

1. a system and evidence summary
2. explicit trust boundaries
3. sensitive assets and data classes
4. a threat model
5. abuse cases
6. required controls
7. implementation constraints
8. must-fix items
9. verification expectations
10. a numbered claims section
11. a final gate decision of `PASS`, `REVISE`, or `BLOCKED`

## Evidence use rule

Reference the supplied evidence IDs (`E1` through `E5`) in the package. The scenario is scored on
how well the constraints trace back to the evidence instead of drifting into generic security
guidance.

## Scope discipline

- Edit only `candidate/security-constraint-package.md`
- Use only synthetic or redacted security material
- Treat bundle-controlled inputs and provider output as untrusted until a control says otherwise
- Do not assume later review can repair an unsafe design choice that should be constrained now
