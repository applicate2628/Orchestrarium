# Repository Orientation and Mechanism Inventory

The binding compact rule lives in `shared/AGENTS.shared.md`. This reference explains how to produce the evidence record before the first repository-local run, build, or mutation in an unfamiliar repository or subtree.

## Orientation Record

Read every applicable governing source before side effects: the nearest `AGENTS.md`, root or subtree `README`, manifest, how-to, index, and owner-maintained status surface. Record:

- `scope`: the repository-relative subtree covered by the evidence;
- `status`: `live`, `mutable`, `frozen`, `archived`, `deprecated`, `superseded`, or `conflict`;
- `workflow`: the repository-owned entry point, runner, build, test, or scorer for the task;
- `protected`: frozen or otherwise non-mutable surfaces;
- `evidence`: one or more `file:line` citations from governing documents.

Use the installed Bootstrap format:

```text
REPOSITORY ORIENTATION: scope=<repo-relative path>; status=<live|mutable|frozen|archived|deprecated|superseded|conflict>; workflow=<repo-relative entry point(s)>; protected=<repo-relative path(s)|none>; evidence=<path:line[,path:line...]>
```

Names, file counts, recency, apparent completeness, and directory layout are attraction signals, not proof that a surface is current. Documented task-specific status wins. Missing or conflicting authority yields `status=conflict` and blocks repository side effects until the owning source or user resolves it.

## Mechanism Inventory

After orientation establishes the authoritative surface, identify the existing owner and propagation path before adding a mechanism. For non-trivial changes, inventory the relevant files, symbols, contracts, events, stores, configuration surfaces, lifecycle rules, and error paths. Extend that owner when applicable. A new owner is justified only when the existing mechanism cannot own the behavior; name the new consistency path and removal or migration relationship explicitly.

## Audit-Hook Boundary

The repository-orientation PreToolUse hook is warn-only and fail-open. It checks process evidence in assistant-authored current-turn prose; it does not read arbitrary repository prose, classify a directory from deprecation vocabulary, or decide which source is canonical. Path segments named `archive`, `deprecated`, `superseded`, or `frozen` are only high-confidence action-target warnings, not proof derived from document wording. The text rule remains binding when the hook is absent, untrusted, skipped, or unable to parse an envelope.

## Terms and Abbreviations

- **Canon**: the repository-owned source or workflow that governs the intended operation.
- **PreToolUse**: a hook event emitted immediately before a tool invocation.
- **Repository side effect**: a repository-local run, build, test, mutation, or other execution that changes state, consumes material resources, or produces decision-driving results.
- **Spine**: the always-loaded shared governance source in `shared/AGENTS.shared.md`.
