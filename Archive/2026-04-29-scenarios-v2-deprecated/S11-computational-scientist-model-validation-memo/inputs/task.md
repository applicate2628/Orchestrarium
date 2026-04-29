# Task

Surface: `R11 $computational-scientist`
Artifact type: `model and validation memo`
Modality family: `numerical or physical reasoning`

## Goal

Produce `candidate/model-validation-memo.md` for the proposed single-state thermal model of the
calibration block described in this packet.

The memo must stay in the computational-scientist lane: identify the governing equations, state
the assumptions, check units and invariants, assess the validation evidence against the declared
criteria, and describe uncertainty or limitation handling before any implementation work exists.
Do not return a code patch, a design packet, a security policy, or a performance budget note.

## Required output content

Your memo must include:

1. the system and operating range
2. governing equations and state variables
3. assumptions and admissibility
4. units and invariants
5. validation evidence and criteria
6. residual interpretation
7. uncertainty and limitations
8. a recommended model disposition
9. a numbered claims section
10. a final gate decision of `PASS`, `REVISE`, or `BLOCKED`

## Evidence use rule

Reference the supplied evidence IDs (`E1` through `E5`) in the memo. The scenario is scored on how
well the model read and validation judgment trace back to the evidence rather than drift into
generic scientific prose.

## Scope discipline

- Edit only `candidate/model-validation-memo.md`
- Keep the answer memo-only and non-web
- Distinguish governing equations, assumptions, invariants, and validation criteria explicitly
- State uncertainty and limitations instead of masking them with optimistic wording
- Do not drift into implementation repair, generic architecture prose, security policy, or
  performance policy
