---
name: manual-repo-transfer
description: Use when a Git repository moves machines without losing dirty work, ignored task memory, or local runtime evidence.
---

# Manual Repository Transfer

Transfer Git history when it exists plus a verified local-state overlay. Size, age, naming, and ignored status never prove data disposable.

## Invariants

- For a committed repository, Git covers required commits/refs; the overlay covers selected local state. An unborn repository has no `HEAD` history to claim, so its overlay and Git metadata are evidence only.
- Inventory is all-or-nothing: traverse ordinary directories, record reparse entries as metadata without descending, and admit only non-reparse regular files. An unreadable subtree or entry, named pipe, socket, device, or unknown filesystem type blocks inventory before output.
- Inventory and selection JSON inputs are each one identity-bound ordinary file from classification through bounded parse. POSIX opens the no-follow leaf nonblocking before `fstat`, so a FIFO without a writer cannot stall classification; Windows rejects reparse points, directories, devices, alternate data streams, and namespace aliases before reading. Type, size, held identity, parent identity, and pathname binding must remain stable through parse.
- Each selected ZIP payload is one identity-bound ordinary file from no-follow, nonblocking classification through chunked hashing and ZIP emission. The helper streams the already-open descriptor, never reopens the pathname for content, and requires the held leaf, parents, size, digest, and final pathname binding to remain stable before close; FIFOs, sockets, links, directories, devices, alternate data streams, and reparse points fail promptly.
- One manifest assigns every local file or link one non-overlapping disposition.
- ZIP contains regular-file bytes. Restricted data and links use content-bound external receipts.
- A Lead or human selects and verifies one explicit absolute Git executable outside the repository before invoking the helper; the helper never resolves `git` from PATH, the current directory, or an environment override.
- Before the first process launch, the helper resolves a repository alias or subdirectory to the nearest physical root with a strict ordinary `.git` directory or gitfile marker, then binds one physically canonical, reparse-free Git executable outside that root by identity and SHA-256. It discards the alias for process working directories, requires Git's reported top-level to match, and rechecks the executable around later Git launches. Failures use `TRANSFER-REPOSITORY-BOUNDARY-INVALID`, `TRANSFER-GIT-BINDING-INVALID`, `TRANSFER-GIT-ROOT-MISMATCH`, or `TRANSFER-GIT-BINDING-DRIFT`; a same-user replacement after the final pre-open check remains outside this guarantee.
- UTF-8 `surrogateescape` path bytes round-trip in canonical JSON by escaping only `U+DC80..U+DCFF`; ordinary Unicode keeps the existing Version 1 bytes and digests, while every other lone surrogate fails as `TRANSFER-PATH-ENCODING-INVALID`. Such paths are hostile metadata-only entries requiring one exact external receipt; payload, deletion, ancestor inclusion, or ZIP placement fails as `TRANSFER-HOSTILE-PATH-EXTERNAL-REQUIRED`.
- The helper verifies and previews; only a repository/lifecycle owner applies an authorized deletion plan.
- `inventory` and `bundle` refuse an existing output by default; only their explicit `--force` replaces one output. The helper binds the ordinary parent and, when present, the exact ordinary output identity before generation. After the completed temporary is flushed and synchronized, an absent output is published by one atomic no-replace link, while a forced existing output is published by rechecking that same parent and exact ordinary identity immediately before one `os.replace`. Raced outputs, links, reparse points, directories, unsafe ancestors, and identity drift fail closed. A same-user substitution after the final identity check is outside the 1.x guarantee. `verify` and `cleanup` never accept `--force`.
- Any Git, lifecycle, recovery, or tool-state mutation invalidates the inventory. Rebuild.

## Receiving from repository cleanup

When `$repo-cleanup` transfer mode invokes this skill, accept only a current-invocation `RepoCleanupReportV1` with `PASS`, bound to the same physical repository identity and `HEAD`/unborn state. Then own exactly `cleanup PASS -> final inventory -> bundle -> trusted verify -> post-transfer classification`. This skill does not run cleanup again, and the cleanup report does not authorize bundle creation, copying, deletion, wipe, or publication. A direct explicit `$manual-repo-transfer` request without cleanup intent continues to enter this skill directly.

## Workflow

1. Read repository governance and validation docs. Inventory dot-directories, ignored/untracked state, and self-ignored workspaces. A clean `git status` is insufficient. Query owning tools through API/MCP; validate stored config/memory against the active project. Use [local-state categories](references/manifest-schema.md#local-state-categories).
2. Quiesce writers. Record the repository history state, `HEAD` when committed, refs, credential-redacted remotes, dirty/index state, reparse points, lifecycle state, stashes, registered worktrees, and Git recovery surfaces. The helper excludes `.git`; audit it separately.
3. Generate an inventory outside the worktree:

   ```text
   python <skill>/scripts/repo_transfer.py inventory --repo <repo> --git-executable <absolute-git-executable> --output <inventory.json> [--force]
   ```

4. Create a selection using [the manifest schema](references/manifest-schema.md). Assign every required entry exactly one disposition:

   | Disposition | Meaning |
   | --- | --- |
   | `include` | Preserve ordinary unique local state in the ZIP. |
   | `external` | Preserve restricted data or link metadata in separately verified storage. |
   | `delete` | Add a content-bound, evidence-backed item to the preview-only deletion plan. |

   Rows may not overlap. Ambiguity means `include`. Never follow a link; classify its target separately.
5. For a committed repository, use the selected remote's local-tracking evidence plus policy-required server probes. Otherwise create and verify a Git bundle; copying `.git` is not the default. For an unborn repository, select only `gitStrategy.mode: none`: no remote can cover a nonexistent `HEAD`, and a standard Git bundle cannot preserve nonexistent history.
6. Build and source-verify the overlay:

   ```text
   python <skill>/scripts/repo_transfer.py bundle --repo <repo> --git-executable <absolute-git-executable> --inventory <inventory.json> --selection <selection.json> --output <transfer.zip> [--force]
   python <skill>/scripts/repo_transfer.py verify --bundle <transfer.zip> --git-executable <absolute-git-executable> --inventory <inventory.json> --selection <selection.json> --source <repo>
   ```

7. Store the artifact independently from the source PC. If the receiver is unavailable, rehearse a clean local restore before authorizing a wipe. Generate the deletion preview with `cleanup`; after separate authorization, the owner applies it and proves the resulting census.
8. Finish lifecycle and Git recovery cleanup, quiesce again, inventory again, rebuild, and reverify. Only this post-finalization artifact is the handoff.
9. On the receiver: verify the ZIP against its separate SHA-256; restore Git and regular-file overlay entries; run payload/source verification; restore external artifacts through receipts; regenerate dependencies/caches; run repository checks. For an unborn inventory, the ZIP preserves file bytes plus staged/unstaged/status evidence but does not recreate index equivalence or fabricate an initial commit. Retain artifacts until acceptance.

## Stop conditions

Unclassified or incompletely enumerated state, unreadable or unsupported filesystem entries, overlap, drift, unsafe archive members, missing hashes, live writers, path escapes, unexpected links, unverifiable receipts, or failed restore checks block cleanup and wipe. Copy success, listing, size, or callback is not integrity evidence. Transfer preparation never grants publication, wipe, or deletion authority.

## Terms and Abbreviations

- Local-state overlay: selected state outside verified Git history.
- Reparse point: Windows link-like filesystem object, including a junction.
- SHA-256: Secure Hash Algorithm 256-bit digest.
