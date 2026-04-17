# Expected Findings

The ground-truth report for `S26` should return `REVISE` with these findings, in severity order.

## 1. Blocking: downstream scoring dependency in bundle-authoring code

- anchor file: `candidate/review-target/tools/review_bundle_builder.py`
- supporting reference: `candidate/review-target/publication/score_profiles.py`
- reason: the authoring helper imports a downstream publication score profile to populate
  `score_profile`, which reverses the intended dependency direction and couples bundle authoring to
  publication-time concerns

## 2. Blocking: findings-only contract breach through embedded repair-plan path

- anchor files:
  - `candidate/review-target/tools/review_bundle_builder.py`
  - `candidate/review-target/review_bundle/README.md`
  - `candidate/review-target/review_bundle/candidate/README.md`
  - `candidate/review-target/review_bundle/candidate/repair-plan.md`
- reason: the changed bundle adds `candidate/repair-plan.md` as an editable artifact and instructs
  the reviewer to hand implementation steps directly to an implementer, which breaks the `P06`
  findings-only review contract

## 3. Major: duplicated maintained rule lists invite drift

- anchor file: `candidate/review-target/tools/review_bundle_builder.py`
- reason: `REVIEW_READONLY_SURFACES` and `PROTECTED_SURFACES` carry the same maintained control
  plane values in separate owners, raising needless drift risk and cognitive load

## Expected gate

`REVISE`
