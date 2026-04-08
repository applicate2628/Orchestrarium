# Project Policies

Copy this file to your repository and uncomment the choices that apply.
Each policy area has a default noted in parentheses. If you leave a line commented,
the default applies. Agents read this file as binding project policy.

## How to use

1. Copy this file into your repository (recommended: `.codex/policies/project-policies.md`).
2. For each area, uncomment exactly one option.
3. Commit the file. Agents will treat the uncommented values as active policy.

---

## testing-methodology

How should tests be written?

<!-- testing: tdd -->
<!-- testing: test-after -->
<!-- testing: minimal -->
<!-- testing: none -->

Default: test-after

## coverage-target

What test coverage target should agents aim for?

<!-- coverage: 90 -->
<!-- coverage: 80 -->
<!-- coverage: 60 -->
<!-- coverage: none -->

Default: none

## commit-format

What commit message format should be used?

<!-- commits: conventional -->
<!-- commits: descriptive -->
<!-- commits: custom — provide your format below: -->
<!-- commits-custom-format: <your format here> -->

Default: conventional

## branching-model

What branching strategy does this project use?

<!-- branching: trunk -->
<!-- branching: gitflow -->
<!-- branching: simple -->

Default: simple

## file-size-policy

Should agents flag large files?

<!-- file-size: strict — hard review at 400 lines, split required at 800 -->
<!-- file-size: moderate — soft guidance under 500, review at 800 -->
<!-- file-size: none -->

Default: none

## error-handling

How should errors be handled?

<!-- errors: explicit — every fallible operation handles errors explicitly -->
<!-- errors: boundary — validate at system boundaries only, trust internal code -->
<!-- errors: framework — follow the framework's default conventions -->

Default: boundary

## pr-review

What is the PR review policy?

<!-- pr-review: required -->
<!-- pr-review: optional -->
<!-- pr-review: none -->

Default: required

## documentation

When should documentation be written?

<!-- docs: public-api — required for all public APIs and exported interfaces -->
<!-- docs: decision-only — document non-obvious decisions and trade-offs only -->
<!-- docs: minimal — only when explicitly requested -->

Default: decision-only

## language-style

Language-specific style preferences (free-form).

<!-- language-style: Follow existing codebase conventions -->
<!-- language-style: <your preference here> -->

Default: Follow existing codebase conventions

## dependency-policy

How conservative should agents be with new dependencies?

<!-- dependencies: conservative — minimize external deps, prefer stdlib -->
<!-- dependencies: pragmatic — add when they save significant effort -->
<!-- dependencies: liberal — use best available package -->

Default: pragmatic
