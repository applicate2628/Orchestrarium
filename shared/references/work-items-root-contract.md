# Work-items Root Contract

This is the canonical shared contract for the Physical Lifecycle V1 topology
extension at `work-items/root-contract.json`. `ProjectTopology` is the sole
owner that resolves this contract for lifecycle operations. Physical Lifecycle
V1 is the lifecycle design version; both on-disk root-contract profiles below
use schema Version 2.

## Exact schema

The contract is optional. When present, it is a regular UTF-8 JavaScript Object
Notation (JSON) file at the repository-relative path
`work-items/root-contract.json`. The narrow profile has exactly these keys:

```json
{
  "schema": "work-items-root-contract",
  "version": 2,
  "auxiliaryRoots": {
    "repair-receipts": { "kind": "flat-json" }
  }
}
```

`auxiliaryRoots` is an object whose keys are auxiliary directory names and
whose every value is exactly `{ "kind": "flat-json" }`. An auxiliary name
MUST be one bare, repository-relative slug: it cannot be absolute, contain a
path separator or traversal component, or name a reserved built-in lifecycle
root. Built-in roots remain owned by `ProjectTopology` and include `backlog`,
`active`, `archive`, and the current roots of built-in flat categories; they
MUST NOT be redeclared in `auxiliaryRoots`.

The expanded profile uses exactly nine top-level keys, with no optional or
mixed-profile fields. For example (project-owned names may differ):

```json
{
  "schema": "work-items-root-contract",
  "version": 2,
  "rootFiles": ["README.md", "root-contract.json"],
  "lifecycleRoots": [
    {"path": "active", "kind": "active-items"},
    {"path": "archive", "kind": "archived-items"}
  ],
  "registries": [
    {"path": "backlog", "kind": "flat-markdown"},
    {"path": "bugs", "kind": "flat-markdown-with-month-archive"},
    {"path": "decisions", "kind": "flat-markdown-with-month-archive"},
    {"path": "epics", "kind": "flat-markdown-with-month-archive"},
    {"path": "lessons", "kind": "flat-markdown"},
    {"path": "roadmaps", "kind": "flat-markdown-with-month-archive"}
  ],
  "auxiliaryRoots": [
    {"path": "repair-receipts", "kind": "flat-json"}
  ],
  "activeItemSubdirectories": ["constraints"],
  "archiveRootFiles": ["README.md"],
  "historicalItemDirectoryExceptions": [
    "archive/2026-01/example-item/retained-evidence"
  ]
}
```

Each array is byte-ordered by its string path and contains no duplicate.
`rootFiles`, `activeItemSubdirectories`, and `archiveRootFiles` contain direct
names; `rootFiles` must include `root-contract.json`. The three root arrays
contain only exact `path`/`kind` records. Lifecycle roots are exactly `active`
and `archive` in their respective roles; registries are exactly `backlog` and
the built-in flat-category roots. Registry kinds are `flat-markdown` or
`flat-markdown-with-month-archive`; auxiliary kind is only `flat-json`.
No root path may appear in more than one root array. Relative paths must be
nonempty and have no backslash, leading slash, colon, empty segment, `.` or
`..` segment. Historical exceptions must be at least four-component paths
under `archive/`. Duplicate JSON object keys, including nested keys, are
invalid. The version must be integer `2`, not Boolean `true`.

`ProjectTopology` validates the expanded metadata but only its auxiliary
declarations grant allowed top-level auxiliary roots, after the same checks as
the narrow profile. Other expanded fields do not rename a lifecycle root,
authorize a new registry or move target, or relax audit for historical paths.
An auxiliary directory name also cannot case-insensitively collide with an
expanded `rootFiles` entry.

The generated top-level file `work-items/README.md` is also reserved. An
auxiliary name MUST NOT collide with `README.md` under case-insensitive name
comparison. This rule is host-independent, so a contract accepted on a
case-sensitive filesystem cannot alias the generated file on a
case-insensitive filesystem.

Each declared auxiliary root is confined to
`work-items/<name>`. It may be absent, but if present it MUST be a directory.
The repository root, `work-items/`, the contract file, and each declared root
MUST be non-reparse, non-link paths. A declaration does not authorize a
different repository location or a nested category hierarchy.

## Lifecycle behavior

`ProjectTopology` supplies the same allowed-root set to audit, close, reopen,
and generated `work-items/README.md` refresh. A declared `flat-json` root is a
project-owned top-level auxiliary directory, so audit does not classify it as
unknown; it is otherwise outside the built-in item lifecycle. Close and reopen
continue to move only the owning work-item records, and README remains a
derived view rather than a topology source.

The owner-local `archive-fixed-bug` route uses the existing built-in `bugs/`
and `bugs/archive/YYYY-MM/` roots. It does not add an auxiliary root or change
this schema: with explicit `--apply` and strict UTC terminal evidence, the
lifecycle owner archives one already-`fixed` bug while its parent stays active,
repairs mutable incoming physical links, and binds the move, link images, and
README in a settlement receipt. See the operator command in
`docs/work-item-execution-tracking.md`.

If no contract exists, the prior built-in-root-only behavior is preserved for
compatibility. The narrow profile remains accepted. If a contract is malformed,
has an unknown schema or version, or declares an unsafe, reserved, linked,
reparse, unconfined, or non-directory
root, lifecycle operations fail closed with
`WI-CATEGORY-ROOT-CONTRACT-INVALID`. They make no topology-dependent move or
README refresh. Resolve the contract defect and rerun the same lifecycle
command; archive identities are immutable, so recovery never reverses an
already archived item and instead uses the ordinary explicit successor/reopen
path.

## Terms and Abbreviations

- `auxiliary root`: a declared project-owned top-level `work-items/` directory
  with the `flat-json` kind.
- `flat-json`: the only Version 2 auxiliary-root kind; it reserves one flat
  top-level directory without creating a lifecycle category.
- `expanded profile`: the nine-key Version 2 envelope whose auxiliary entries
  normalize into the same lifecycle topology as the narrow profile.
- `JSON`: JavaScript Object Notation, the contract file format.
- `ProjectTopology`: the lifecycle owner that resolves built-in and declared
  auxiliary work-items roots.
- `reparse point`: a filesystem indirection such as a symbolic link or
  platform-specific reparse object; these paths are rejected for this contract.
