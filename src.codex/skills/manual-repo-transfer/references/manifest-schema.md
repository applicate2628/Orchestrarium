# Transfer Manifest Schema

The helper uses two JSON documents. `inventory` is generated; `selection` is the semantic owner's decision. Both use `schemaVersion: 1`.

## Inventory

Generate it with `repo_transfer.py inventory`. Do not edit it.

```json
{
  "schemaVersion": 1,
  "repository": {
    "historyState": "committed",
    "head": "<commit>",
    "remotes": [{"name": "origin", "url": "<credential-redacted URL>"}],
    "remoteEvidence": {
      "origin": {"headReachable": true, "kind": "local-tracking"}
    },
    "gitExecutable": {"path": "<absolute path>", "sha256": "<digest>"},
    "gitMetadataHashes": {
      "_repo-transfer/git-status.bin": "<digest>",
      "_repo-transfer/git-staged.diff": "<digest>",
      "_repo-transfer/git-unstaged.diff": "<digest>"
    }
  },
  "entries": [
    {
      "path": ".scratch/evidence.json",
      "entryType": "file",
      "gitClass": "ignored",
      "dirtyTracked": false,
      "size": 123,
      "sha256": "<64 lowercase hex digits>"
    }
  ],
  "snapshot": {"digest": "<SHA-256 of canonical repository evidence plus sorted entries>"}
}
```

`repository.historyState` is `committed` or `unborn`. A committed inventory has a string `head`; an unborn inventory has `head: null`, treats the `HEAD` tree as empty, and derives dirty tracked paths from the cached and worktree diffs. Existing schema-version-1 committed inventories without `historyState` remain readable and mean `committed`. An unborn inventory records every configured remote with `headReachable: false` because there is no commit on which to run a merge-base reachability check.

`entryType` is `file`, `reparse`, or `deleted`. A `deleted` entry is a tracked path present in `HEAD` but absent from the physical tree; it has no `size` or `sha256`. Reparse entries and Windows-hostile paths are metadata-only and are never traversed or placed in the ordinary ZIP. `gitClass` is `tracked`, `untracked`, or `ignored`. The bundle gate requires a selection disposition for every untracked, ignored, dirty tracked, hostile, reparse, and deleted entry. The inventory takes tracked paths from both the current index and `HEAD`, so staged deletions remain visible. Files marked `assume-unchanged` or `skip-worktree` are conservatively dirty tracked state and bind their physical bytes.

Inventory enumeration is all-or-nothing. Directory traversal errors and no-follow metadata (`lstat`) errors are contract failures and produce no inventory output. Ordinary directories are traversed, reparse entries remain metadata-only and are not descended, and only non-reparse regular files become `file` entries. Named pipes, sockets, character devices, block devices, and unknown special entries are rejected as unsupported before any content open or hash; they do not introduce another schema entry type and cannot use the reparse or hostile-path external-metadata contract.

HTTP, HTTPS, SSH, and SCP-style remote credentials are removed from generated inventory; local-path remotes become `<local-path>`. Still review the inventory before sharing it.

`gitExecutable` records the caller-selected absolute ordinary Git executable and its SHA-256 digest. The helper rejects relative, missing, reparse, and repository-contained executable paths; it never resolves Git through PATH or an environment override.

## Selection

Paths are repository-relative POSIX paths. Absolute paths, backslashes, `.git`, `..`, missing paths, duplicates, and any ancestor/descendant overlap are invalid. A hostile inventory name may be referenced only as its exact `external` identity; it may not be selected for `include` or `delete`. One Unicode NFKC-normalized, case-folded path tree governs inventory, selection, ZIP payload, and declared deletions; it rejects portable-equal and file/descendant conflicts across and within those categories. Mixed-case or canonically equivalent forms of `.git` are rejected. The helper's `_repo-transfer` archive namespace is reserved under the same identity and must use `external`.

```json
{
  "schemaVersion": 1,
  "inventoryDigest": "<copy from inventory.snapshot.digest>",
  "gitStrategy": {
    "mode": "remote-clone",
    "remote": "origin",
    "expectedHead": "<copy from inventory.repository.head>"
  },
  "items": [
    {
      "path": "notes/local-work.md",
      "disposition": "include",
      "reason": "user-authored untracked work"
    },
    {
      "path": ".scratch/diagnostic.log",
      "disposition": "external",
      "reason": "restricted evidence excluded from ordinary ZIP",
      "receipt": {
        "artifact": "encrypted-media:case-17",
        "setSha256": "<digest of the exact covered inventory-entry set>"
      }
    },
    {
      "path": "node_modules",
      "disposition": "delete",
      "reason": "dependency cache",
      "proof": {
        "kind": "regenerate",
        "command": "npm ci",
        "setSha256": "<digest of the exact covered inventory-entry set>"
      }
    }
  ],
  "restoreCommands": [
    "npm ci",
    "npm test"
  ]
}
```

### Git strategy

| Mode | Use |
| --- | --- |
| `remote-clone` | The required `HEAD` is covered by the selected remote's recorded local-tracking refs. This is offline evidence, not server freshness; run a fresh remote probe when policy requires it. |
| `git-bundle` | Required history is preserved through a separately created and verified standard Git bundle. Record its receipt outside this ordinary overlay schema. |
| `none` | The overlay is being prepared without claiming that Git history is transferable. This never authorizes wiping the source repository. |

An unborn inventory permits only `none`. `remote-clone` and `git-bundle` require committed history, and `git-recoverable` is not a valid delete proof when no verified Git history exists.

### Dispositions

| Value | Required fields | Result |
| --- | --- | --- |
| `include` | `path`, non-empty `reason` | Regular files enter the deterministic ZIP. |
| `external` | `path`, non-empty `reason`, receipt object with `artifact` and content-bound `setSha256` | Content stays out of the ordinary ZIP and is owned by separately verified restricted storage. Required for every reparse or hostile entry. |
| `delete` | `path`, non-empty `reason`, content-bound `proof` | The path enters the preview-only deletion plan after trusted bundle/source verification. |

Allowed delete proof kinds:

- Every proof requires `setSha256`, computed over canonical JSON of the exact covered inventory entries.
- `regenerate`: also requires a non-empty deterministic `command`.
- `git-recoverable`: the exact content or owning source is recoverable from verified Git history.
- `canonical-summary`: an accepted canonical artifact retains every load-bearing observation.

## Bundle contract

The ZIP is a byte-only regular-file overlay. It contains included files at repository-relative paths plus:

- `_repo-transfer/manifest.json`
- `_repo-transfer/git-status.bin`
- `_repo-transfer/git-staged.diff`
- `_repo-transfer/git-unstaged.diff`

The internal manifest strictly requires `schemaVersion` (integer, never Boolean), 64-hex `inventoryDigest`, 64-hex `selectionDigest`, the same conditional `repository.historyState`/`repository.head` contract as the inventory, `payload` list, `metadata` list, and `deletions` list. Existing schema-version-1 committed manifests without `historyState` remain readable. Included tracked deletions are objects in `deletions`; they have no ordinary ZIP member. Receiver payload/source verification requires every listed path to be physically absent, including a dangling link, and rejects every existing reparse/symlink ancestor of either a payload or deletion path.

Git metadata is filtered to included paths with rename/copy detection disabled, so an included rename cannot disclose an external old/new path. Operational Git calls disable executable helpers discovered across effective included local/worktree configuration scopes; their standard output and standard error are streamed into independent 8 MiB bounded captures, and timeout, launch, capture, or cap failures are contract errors. ZIP entries use fixed timestamps, permissions, ordering, and compression settings. Before opening a ZIP, the verifier reads only the bounded end-of-central-directory (EOCD) window and any immediately preceding ZIP64 locator and fixed record; it rejects multi-disk archives, malformed records, more than 10,000 entries, a central directory larger than 8 MiB, and central-directory offsets or sizes outside the archive. Producer and verifier both enforce at most 10,000 entries, 128 MiB per entry, 512 MiB declared uncompressed total, and a 100:1 maximum declared compression ratio. Producer streams source bytes and hashes in chunks; verifier streams ZIP members and source hashes without retaining payload contents. Inventory, selection, and internal manifest JSON are bounded to 8 MiB; producer JSON is encoded incrementally and its complete framing, including the inventory newline, counts toward the limit. File reads request at most the limit plus one byte before parsing, producer output and internal manifests are refused above that limit, and JSON rejects duplicate keys, named non-finite constants, numeric overflow, and nesting deeper than 64. Trusted verification opens the bundle once and uses that same archive handle for internal-manifest validation, payload hashing, and metadata comparison; malformed archives and unsupported compression are contract errors. Trusted verification also binds the manifest history state and conditional head to the inventory. Source-side trusted verification requires `--inventory`, `--selection`, and `--source`; it derives the exact archive set and rejects duplicates, file/descendant and portable path collisions, path escapes, unsafe member types/names, encryption, missing or extra entries, metadata drift, size drift, and hash drift. Standalone verification checks archive structure and internal hashes only. After receiver extraction, `verify --bundle <zip> --source <repo>` checks payload bytes and declared tracked-deletion absence against the restored tree but does not prove original completeness or Git index equivalence. For an unborn inventory, the metadata members preserve status/staged/unstaged evidence; verification does not recreate index equivalence or fabricate a commit. The tool writes only outside the repository so its own output cannot invalidate the audited snapshot.

Bundle production, trusted source verification, and cleanup preview all use the same complete-inventory recensus owner. An unreadable or unsupported source entry therefore fails each path before hashing, ZIP production, successful verification, or cleanup-preview output.

`cleanup` is permanently preview-only. It validates one immutable inventory-plus-selection snapshot and verifies the bundle from that exact in-memory snapshot. Immediately before preview emission it compares the complete current inventory snapshot with that same snapshot; any added, removed, or changed entry fails the preview. Its JSON preview includes `inventoryDigest`, `selectionDigest`, `deletions`, and `deletionProofs` (`path`, proof `kind`, and content-binding `setSha256`). Generic `--apply` is rejected; the repository/lifecycle owner performs any authorized deletion and post-cleanup census. A receiver payload mismatch emits JSON with `verified: false` and a non-zero process status.

## Finalization contract

The inventory and selection bind one source snapshot. Any lifecycle close, receipt, lock, Git change, file change, or new local file invalidates that binding. Quiesce writers, inventory again, update the selection, rebuild the bundle, and verify it again. Only this final bundle is the handoff.

## Local-state categories

Classify by ownership and reproducibility, not by a product-specific directory name.

| State class | Default route |
| --- | --- |
| Global runtime/plugin cache | Reinstall on the receiver; exclude from repository transfer. |
| Regenerable index/cache/log | Exclude only after proving no unique evidence and no live writer. |
| Repository-local tool policy, task memory, or unique evidence | `include`, or `external` when restricted. |
| Tool-generated project memory/config | Activate the owning tool and verify project identity/content currency; exclude cross-project or stale records. |
| Legacy agent workspace or report/plan store | Compare with current canon and Git; preserve unique bytes before retirement. |
| Git recovery payload absent from refs | Stage outside `.git`, hash, preserve, then clean only after bundle proof. |
| Prunable worktree registration | Require a dry-run naming only absent metadata before native Git prune. |

Self-ignored nested workspaces can be absent from root status output. Audit actual filesystem contents. Any recovery staging, prune, cache cleanup, lifecycle receipt, or tool-state change requires a fresh inventory and final bundle rebuild.

## Terms and Abbreviations

- JSON: JavaScript Object Notation.
- POSIX path: forward-slash relative path used inside the portable manifest.
- SHA-256: Secure Hash Algorithm 256-bit digest.
- ZIP: archive format used for the ordinary, non-secret local overlay.
