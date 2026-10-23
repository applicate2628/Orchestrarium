# Work-items Root Contract

This is the canonical shared contract for the Physical Lifecycle V1 topology
extension at `work-items/root-contract.json`. `ProjectTopology` is the sole
owner that resolves this contract for lifecycle operations. Physical Lifecycle
V1 is the lifecycle design version; both on-disk root-contract profiles below
use schema Version 2.

## Unknown-root recovery

`ProjectTopology` retains `WI-CATEGORY-UNKNOWN-ROOT` and sorted actual names with present or absent contracts. Its diagnostic names `work-items/root-contract.json` and this owner contract. Preserve bytes; identify creator/data owner and classify actual format/lifecycle. An eligible project-owned Version 2 `flat-json` auxiliary may be declared by its owner under this contract; otherwise the owner maps/migrates to a supported lifecycle category using existing admitted semantics. The error grants no declaration/migration/deletion authority and never accepts by directory name. Unsafe/malformed contracts retain distinct `WI-CATEGORY-ROOT-CONTRACT-INVALID` refusal.

## Exact schema

Initial V0 decision admission is owned by `scripts/mutate-work-item.py` through
`admit_current_decision_v0` / `admit-current-decision-v0`, using the same bound
repository/work-items root and lifecycle transaction. It captures without
authority, then creates `work-items/decision-v0-compatibility.json` only after
explicit current accepted V1 policy binding and fresh expected byte hashes.
Historical records and README remain untouched. The caller selects an ordinary
repository-relative `.scratch/` settlement receipt; its `.pending` sibling
binds actual staged identities for same-operation recovery, not a new registry
or declaration authority. Existing strict reader, cutover and retirement rules
remain authoritative. A valid historical replay separately validates present
compatibility and tolerates lawful retirement/README advancement. A controlled
owner-executed manual equivalent must retain the same binding, create-only
publication, recovery, readback and foreign-byte-preservation guarantees.

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

The lifecycle transaction retains separate canonical repository and work-items
roles after validating the original caller path. Wrapped operations and nested
same-repository checks consume those held roles; topology never reinterprets an
already-proved repository from its basename. Repository-relative scratch,
receipt and retention paths therefore use the same repository for either
documented root spelling. Foreign roots and original linked/reparse inputs
cannot borrow a held transaction's authority. The shared identity owner distinguishes raw acquisition from proved-role
normalization. The declared request category/slug or transition operation
is observed before generic namespace identity; a different neighboring subject
is not a competing binding. A same-subject dual root refuses, while multiple
locations within one root remain the domain owner’s duplicate-location error. Untyped roots bind through the selected subject or canonical-W
namespace owner; protocol candidates are evaluated together before domain/digest
admission, with ambiguous/unbound/unsafe/unavailable inputs remaining failures.
The existing optional contract may supply typed identity when present; it is
never required as a new marker. Proved repository-root/work-items-root inputs
return plain paths without rereading this contract or granting authority.
The checker keeps its configured selected namespace separate from its base;
existing scope equations prove the base role, which audit, transfer and dependency
consumers receive through the same owner. Component selection never rebases it.
Readonly H1 location acquisition defaults to caller-root; bound consumers carry
the repository-root role explicitly across module boundaries. Public transition
recovery admits the original caller path once into the existing transaction,
which encloses intent selection, recovery and nested README/receipt readback.
The command-line positive `--apply` gate remains required.

Settlement and mixed recovery bind their parsed logical work-item before receipt
or target lookup, then forward the acquired repository role through existing
readers. Settlement rechecks readonly binding before output and carries original
input/evidence into its existing transaction. Mixed recovery rechecks under its
existing ledger lock before staging; no-apply keeps its existing staging cleanup
and rechecks binding before output. No additional readonly lock/context is used.

Identity observation consumes plain structural rows from that same archive
classifier and reads no unrelated metadata/retained bodies. Full inventory alone
constructs complete entities with exact bounded file snapshots; structural
identity/stat observations do not claim content proof.

The readonly `archive_entity_inventory` API exposes the same physical owner
model and its `logical_work_item_paths`, including invalid known tasks. The
default checker validates only each selected task's immediate canonical ledger;
nested retained ledger snapshots remain data. Lexical presence preserves
dangling, directory and unreadable-ledger failure rather than skipping them.
Requested archive scope and captured currentness must agree; unavailable or
drifting owner acquisition is not clean-empty. Real current and archived review
obligations retain their existing validator and failure semantics.

Ordinary direct files at the built-in work-item archive root or a canonical
month are nonauthorizing archive metadata, acquired through the lifecycle
owner's bounded no-follow snapshots. Their exact bytes feed the same board
input digest and currentness checks; a conditional `Archive metadata` section
shows each physical link and SHA-256 without a task checkbox. Filenames,
extensions, prose and date/status fields supply no logical identity, terminal
time, completion or obligation authority. A real captured empty file is valid;
missing/unsafe acquisition is not. Existing malformed work-item, unbound
collection, selected-identity and noncanonical evidence contracts remain
strict. This classification adds no topology declaration or lifecycle category.

Directory relocation belongs to the existing lifecycle transaction. After a
native move, the owner proves the same ordinary directory and the complete
rebased parent chains while retaining captured leaf identities and bytes.
It updates observation locations together; captures outside the moved subtree
remain strict. Failed post-move proof compensates before returning, and an
unsafe inverse preserves conflicting state with a visible rollback failure.
An unverified inverse retains its actual source, destination and original
directory identity in the invocation. Intersecting caller cleanup, including
containing-ancestor removal, is withheld through exit; unrelated cleanup stays
available. Caught secondary errors cannot turn unsettled rollback into completion.
This changes no topology declaration, receipt schema or file-move contract.

The owner-local `archive-fixed-bug` route uses the existing built-in `bugs/`
and `bugs/archive/YYYY-MM/` roots. It does not add an auxiliary root or change
this schema: with explicit `--apply` and strict UTC terminal evidence, the
lifecycle owner archives one already-`fixed` bug under a uniquely active or admitted archived parent, preserving parent lifecycle/identity,
repairs mutable incoming physical links, and binds the move, link images, and
README in a settlement receipt. See the operator command in
`docs/work-item-execution-tracking.md`.

If no contract exists, the prior built-in-root-only behavior is preserved for
compatibility. Subjectless topology observation outside a transaction, without
a proved root role, may read a repository or work-items namespace alias only
when the contract entry is absent. A namespace alias retains its selected
repository association. This observation supplies no lifecycle, held-root, or
mutation authority; those acquisitions still validate the original caller path
without following links. A present, linked, unreadable, or malformed contract
never becomes absence. The narrow profile remains accepted. If a contract is malformed,
has an unknown schema or version, or declares an unsafe, reserved, linked,
reparse, unconfined, or non-directory
root, lifecycle operations fail closed with
`WI-CATEGORY-ROOT-CONTRACT-INVALID`. They make no topology-dependent move or
README refresh. Resolve the contract defect and rerun the same lifecycle
command; archive identities are immutable, so recovery never reverses an
already archived item and instead uses the ordinary explicit successor/reopen
path.

## Terms and Abbreviations

- `SHA-256`: Secure Hash Algorithm with a 256-bit byte-content digest.

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
