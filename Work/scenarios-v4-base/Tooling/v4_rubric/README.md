# v4 Rubric Library

`score_candidate()` validates an oracle-owned rubric and computes component/atom partial credit.
Signal families include categorical checks, set/source F1, source-order pair accuracy, continuous
numeric error with units, observable case fractions, required-field coverage, and deterministic
maximum-weight one-to-one findings matching. JSON reports are canonicalized with sorted keys.

Rubric validation rejects repeated observation identities. An identity is the candidate path plus
the signal's relevant projection, so disjoint case or source-binding IDs may share a collection path
but the same projected target cannot award points twice. Finding compatibility includes severity as
well as the configured location fields.

`python -m v4_rubric.cli --root <fixture> --candidate <answer.json>` runs the common adapter.
Per-root `verifiers/score.py` files only resolve their fixture root and call that adapter.
The adapter validates the candidate against `inputs/output-schema.json` before scoring. Schema
violations, malformed or missing candidates, and duplicate logical IDs return a deterministic
`INVALID-CANDIDATE` report with score 0; scorer-owned faults remain `SCORER-ERROR` with no score.

## Threat Model

The scorer is designed for honest frontier models producing genuine structured answers. Within
that boundary, the tested gaming classes are closed:

- finding compatibility includes configured locations and severity, and a rubric-declared wrong
  present commitment activates a score cap below the partial threshold; an omitted commitment
  keeps ordinary partial credit
- duplicate JSON keys and duplicate logical IDs fail closed across array and map forms, including
  compatibility-normalized, case, whitespace, and Unicode default-ignorable variants
- visible schemas reject unknown fields, free-form denial prose inside scored structures, and
  unbounded map keys; C04's non-scored finding identifier is limited to a category prefix plus digits
- candidate numeric ingestion rejects non-finite values, binary64 overflow or underflow, integral
  values outside the strict $|n| < 2^{53}$ domain, and finite decimal lexemes that change value at
  the scorer's binary64 publication precision
- zero-width and other default-ignorable Unicode code points are removed by the canonical identity
  owner before collision checks

A dedicated adversary may still construct visual homoglyphs that are not Unicode
default-ignorables, or encode a covert message entirely inside an otherwise legal ASCII token or
path. General confusable detection and content moderation are deliberately out of scope: they add
language- and policy-dependent equivalence to a benchmark whose threat model is genuine model
answers, not hand-crafted steganography. On the current C04 root, this residual class cannot turn a
wrong commitment into a high score: ignored finding IDs have the prefix-plus-digits grammar, while
wrong scored tokens and paths activate the low-band commitment cap. No residual remains in the
explicitly tested classes above.

## Terms and Abbreviations

- `F1`: harmonic mean of precision and recall.
- `C04`: the v4 findings-review calibration root.
- `NFKC`: Unicode Normalization Form Compatibility Composition.
