---
name: generalize-from-instance
description: Use when Codex must turn fixture-specific, geometry-specific, dataset-specific, user-case-specific, or one-off code/docs/tests/UI logic into a general implementation contract. Trigger on requests such as "make it general", "not for this geometry", "remove hardcoding", "general logic", "do not map to this case", or when a private validation case is leaking into production behavior, documentation, naming, tests, or UI.
---

# Generalize From Instance

Use this skill to extract a reusable contract from a working private case without
preserving that case as the owner of the behavior. A general implementation
handles valid instances and accepted variation through the correct owner; it does
not erase legitimate concrete contracts or predict hypothetical variants.

## Core Rule

Treat the private case as evidence, not as the model.

Generality, extensibility, low coupling, cohesion, simplicity, and efficiency are
one architecture tradeoff. Keep each needed change local to the correct owner;
use the smallest stable seam justified by an accepted requirement, an accepted
declared future direction, or evidenced domain variability. A current second
consumer is useful evidence, not a prerequisite. Do not add speculative
frameworks, duplicate decisions, or cascade edits across unrelated modules.
Preserve correctness, required performance, user constraints, and external
contracts.

Concrete does not mean private. Schema-defined identifiers, protocol paths,
coordinate systems, domain constants, user-selected labels, and supported API
shapes may be legitimate contracts. Classify them before changing them.

## Workflow

Apply the workflow proportionally. A single-anchor documentation or test-name
correction needs only a concise classification, owner, and check; multiple
anchors or behavior and contract changes need the fuller mapping below.

1. Capture the private anchors.
   List the concrete names, paths, coordinates, ids, labels, result values, or
   visual features suspected of making the work specific. Quote file and line
   references when code or docs contain the assumption.

2. Classify each anchor.
   Mark every anchor as one of:
   - `contract`: a real input/output rule that must remain.
   - `example`: a valid sample that belongs in docs, tests, or fixtures only.
   - `accident`: a leaked assumption that must be removed.
   - `unknown`: a claim that needs inspection before editing.

3. Derive the general entities.
   Replace private nouns with owner-owned categories. Prefer categories that come
   from parsed input schemas, runtime metadata, typed records, cell arrays,
   boundary tags, roles, or explicit config. Generalize over valid instances,
   accepted future directions, and evidenced domain variability, not imagined
   semantic variants.

4. Move behavior to the owner.
   Implement the general rule in the module that owns the data contract. Do not
   add consumer-side patches that special-case the original fixture or repeat the
   same decision across callers.

5. Preserve the private case as a regression.
   Keep the original case in examples or tests only. If possible, add one
   synthetic or alternate case that proves the code is not tied to the original
   names, ids, coordinate axis, count, or ordering.

6. Document the general contract.
   Say what input fields drive the behavior, what output is produced, what is
   intentionally example-only, which compatibility behavior remains, and how the
   verification proves generality.

## Generality Checks

Before editing, ask:

- Does the rule depend on a fixture path, file basename, geometry name, or case
  nickname?
- Does it infer semantics from coordinates, ordering, counts, colors, result
  magnitudes, or current screenshot layout when an explicit input field exists?
- Does a function, type, option, test, or heading use a private noun where a
  typed entity name would be clearer?
- Would the same code handle other valid instances and accepted or evidenced
  variation within its declared contract without a fixture-specific branch? A
  genuinely new semantic behavior may require new owner-level dispatch and does
  not prove that the prior implementation was instance-specific.
- Are hidden defaults safe when the private case omits a field, or should the
  code fail with a concrete diagnostic?
- Did the change add an abstraction, plugin system, duplicated decision, or
  multi-module cascade without evidence that the owning contract needs it?

If an answer exposes a private assumption, correct it at the owning boundary.
Preserve authorized external contracts; when compatibility is required, keep it
in one owner-owned adapter or migration path rather than a fixture-specific
consumer branch.

## Implementation Rules

- Prefer schema-driven parsing, typed records, metadata arrays, and declared
  roles over string matching against private names.
- Keep examples and validation fixtures named after their physical case, but keep
  production functions and UI groups named after general entities.
- Preserve supported behavior through the general path or its owner-owned
  compatibility boundary.
- Follow the owning contract's unknown-value policy. Reject an unknown value only
  when required semantic interpretation cannot be performed under that contract;
  otherwise explicitly preserve, ignore, or round-trip it as the contract allows.
  Never map an unknown value silently to the private case's default.
- Keep the diff at the owning boundary. If generalization requires a broader
  interface, state the verified reason before expanding scope.
- Do not use empirical scaling or example-only ids, coordinates, or path dispatch
  to imitate the original result. A concrete value remains valid when the owning
  schema, protocol, domain model, or user contract defines it.

## Output Artifact

Return only the detail the change needs. For a single-anchor documentation, test,
or naming correction, a short result naming its classification, owner, and check
is sufficient. For multiple anchors or behavior and contract changes, return one
compact implementation note with:

- private anchors found;
- classification table for `contract`, `example`, `accident`, and `unknown`;
- general entity contract;
- files changed and ownership boundary;
- verification commands and evidence;
- residual assumptions, each labelled `ASSUMPTION (UNVERIFIED)` if not checked.

Use a Markdown table only when several anchors or mappings are involved. Do not
create a new artifact, abstraction, or gate unless the task contract requires it.

## Gate

The work passes only when:

- the original private case still works through the general path or a required
  owner-owned compatibility boundary;
- no production logic depends on example-only or accidental anchors; each
  remaining concrete path, name, id, coordinate, label, or layout rule is a
  verified contract owned at the correct boundary;
- accepted future directions or evidenced domain variation stay local to the
  owning implementation or stable seam without speculative mechanisms;
- required correctness, performance, user constraints, and external contracts
  remain preserved, or an authorized migration is explicit;
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
