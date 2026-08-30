---
name: generalize-from-instance
description: Use when Codex must turn fixture-specific, geometry-specific, dataset-specific, user-case-specific, or one-off code/docs/tests/UI logic into a general implementation contract. Trigger on requests such as "make it general", "not for this geometry", "remove hardcoding", "general logic", "do not map to this case", or when a private validation case is leaking into production behavior, documentation, naming, tests, or UI.
---

# Generalize From Instance

Use this skill to extract a reusable contract from a working private case without
preserving the private case as the owner of the behavior. The goal is a general
implementation that still passes the original case as one regression example.

## Core Rule

Treat the private case as evidence, not as the model.

The accepted output must name the general entity types, their input contracts,
their ownership boundary, and the verification gate. It must not depend on
fixture names, file paths, coordinates, result magnitudes, mesh ids, material ids,
or UI labels that only make sense for one sample.

## Workflow

1. Capture the private anchors.
   List the concrete names, paths, coordinates, ids, labels, result values, or
   visual features that currently make the work specific. Quote file and line
   references when code or docs already contain the private assumption.

2. Classify each anchor.
   Mark every anchor as one of:
   - `contract`: a real input/output rule that must remain.
   - `example`: a valid sample that belongs in docs, tests, or fixtures only.
   - `accident`: a leaked assumption that must be removed.
   - `unknown`: a claim that needs inspection before editing.

3. Derive the general entities.
   Replace private nouns with owner-owned categories. Prefer categories that come
   from parsed input schemas, runtime metadata, typed records, cell arrays,
   boundary tags, roles, or explicit config.

4. Move behavior to the owner.
   Implement the general rule in the module that owns the data contract. Do not
   add consumer-side patches that special-case the original fixture.

5. Preserve the private case as a regression.
   Keep the original case in examples or tests only. If possible, add one
   synthetic or alternate case that proves the code is not tied to the original
   names, ids, coordinate axis, count, or ordering.

6. Document the general contract.
   Say what input fields drive the behavior, what output is produced, what is
   intentionally example-only, and how the verification proves generality.

## Generality Checks

Before editing, ask:

- Does the rule depend on a fixture path, file basename, geometry name, or case
  nickname?
- Does it infer semantics from coordinates, ordering, counts, colors, result
  magnitudes, or current screenshot layout when an explicit input field exists?
- Does a function, type, option, test, or heading use a private noun where a
  typed entity name would be clearer?
- Would the same code handle an added body, port, terminal, material, mode,
  field, column, or result convention without another branch?
- Are hidden defaults safe when the private case omits a field, or should the
  code fail with a concrete diagnostic?

If any answer exposes a private assumption, fix the contract rather than adding
a compatibility branch.

## Implementation Rules

- Prefer schema-driven parsing, typed records, metadata arrays, and declared
  roles over string matching against private names.
- Keep examples and validation fixtures named after their physical case, but keep
  production functions and UI groups named after general entities.
- Preserve original fixture behavior only through the general path.
- Fail fast on unknown roles or malformed general inputs; do not silently map an
  unknown value to the private case's default.
- Keep the diff at the owning boundary. If generalization requires a broader
  interface, state the verified reason before expanding scope.
- Do not use empirical scaling, fixture-specific ids, hardcoded coordinates, or
  path-based dispatch as a generalization substitute.

## Output Artifact

Return one compact implementation note with:

- private anchors found;
- classification table for `contract`, `example`, `accident`, and `unknown`;
- general entity contract;
- files changed and ownership boundary;
- verification commands and evidence;
- residual assumptions, each labelled `ASSUMPTION (UNVERIFIED)` if not checked.

Use a Markdown table when several anchors or mappings are involved.

## Gate

The work passes only when:

- the original private case still works through the general path;
- no production logic depends on fixture paths, names, ids, coordinates, or
  screenshot-only layout assumptions;
- docs separate general rules from examples;
- tests or smoke checks exercise the original case and at least one
  non-private variation when practical;
- completion claims cite fresh verification evidence.

## Terms and Abbreviations

- `contract`: the stable input/output rule owned by a module or interface.
- `fixture`: a concrete sample case used for tests, examples, or validation.
- `general path`: implementation driven by typed input or metadata rather than a
  private case.
- `owner`: the module or boundary responsible for the behavior and its
  invariants.
- `private anchor`: a name, coordinate, id, path, label, or result value that
  ties behavior to one specific case.
