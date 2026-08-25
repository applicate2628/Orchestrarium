---
name: manual-repo-transfer
description: Use when a Git repository moves machines without losing dirty work, ignored task memory, or local runtime evidence.
---

# Manual Repository Transfer

Transfer Git history plus a verified local-state overlay. Size, age, naming, and ignored status never prove data disposable.

## Invariants

- Git covers required commits/refs; the overlay covers selected local state.
- One manifest assigns every local file or link one non-overlapping disposition.
- ZIP contains regular-file bytes. Restricted data and links use content-bound external receipts.
- A Lead or human selects and verifies one explicit absolute Git executable outside the repository before invoking the helper; the helper never resolves `git` from PATH, the current directory, or an environment override.
- The helper verifies and previews; only a repository/lifecycle owner applies an authorized deletion plan.
- Any Git, lifecycle, recovery, or tool-state mutation invalidates the inventory. Rebuild.

## Workflow

1. Read repository governance and validation docs. Inventory dot-directories, ignored/untracked state, and self-ignored workspaces. A clean `git status` is insufficient. Query owning tools through API/MCP; validate stored config/memory against the active project. Use [local-state categories](references/manifest-schema.md#local-state-categories).
2. Quiesce writers. Record `HEAD`, refs, credential-redacted remotes, dirty/index state, reparse points, lifecycle state, stashes, registered worktrees, and Git recovery surfaces. The helper excludes `.git`; audit it separately.
3. Generate an inventory outside the worktree:

   ```text
   python <skill>/scripts/repo_transfer.py inventory --repo <repo> --git-executable <absolute-git-executable> --output <inventory.json>
   ```

4. Create a selection using [the manifest schema](references/manifest-schema.md). Assign every required entry exactly one disposition:

   | Disposition | Meaning |
   | --- | --- |
   | `include` | Preserve ordinary unique local state in the ZIP. |
   | `external` | Preserve restricted data or link metadata in separately verified storage. |
   | `delete` | Add a content-bound, evidence-backed item to the preview-only deletion plan. |

   Rows may not overlap. Ambiguity means `include`. Never follow a link; classify its target separately.
5. Use the selected remote's local-tracking evidence plus policy-required server probes. Otherwise create and verify a Git bundle; copying `.git` is not the default.
6. Build and source-verify the overlay:

   ```text
   python <skill>/scripts/repo_transfer.py bundle --repo <repo> --git-executable <absolute-git-executable> --inventory <inventory.json> --selection <selection.json> --output <transfer.zip>
   python <skill>/scripts/repo_transfer.py verify --bundle <transfer.zip> --git-executable <absolute-git-executable> --inventory <inventory.json> --selection <selection.json> --source <repo>
   ```

7. Store the artifact independently from the source PC. If the receiver is unavailable, rehearse a clean local restore before authorizing a wipe. Generate the deletion preview with `cleanup`; after separate authorization, the owner applies it and proves the resulting census.
8. Finish lifecycle and Git recovery cleanup, quiesce again, inventory again, rebuild, and reverify. Only this post-finalization artifact is the handoff.
9. On the receiver: verify the ZIP against its separate SHA-256; restore Git and regular-file overlay entries; run payload/source verification; restore external artifacts through receipts; regenerate dependencies/caches; run repository checks. Retain artifacts until acceptance.

## Stop conditions

Unclassified state, overlap, drift, unsafe archive members, missing hashes, live writers, path escapes, unexpected links, unverifiable receipts, or failed restore checks block cleanup and wipe. Copy success, listing, size, or callback is not integrity evidence. Transfer preparation never grants publication, wipe, or deletion authority.

## Terms and Abbreviations

- Local-state overlay: selected state outside verified Git history.
- Reparse point: Windows link-like filesystem object, including a junction.
- SHA-256: Secure Hash Algorithm 256-bit digest.
