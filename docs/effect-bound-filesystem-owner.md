# Effect-bound filesystem owner: contracts and current hold

Status: source design and defensive mitigation, not a qualified mutation backend. This is an Orchestrarium repository contract, not a Codex or Claude provider guarantee. No native qualification is established by the pure tests described here.

## Existing owner and first implementation

The production installer owns effects through `_InstallTransaction`, `_CreateOnlyMutablePath` and `_WindowsBoundNode`. Extend these owners rather than adding a second filesystem engine. `_require_transaction_disposal_backend` now rejects non-Windows entry to both `_dispose_node` and `_dispose_image`, before input observation, permission changes or transaction updates. The old POSIX name-based deletion branch is removed. The existing Windows branch remains unchanged and still requires its own checks; passing this negative gate grants no authority.

The same negative gate also runs before enabled transaction snapshot acquisition and before any direct-operation scope yields to a writer, including nested or enabled scopes. It therefore refuses those private entry paths before their scoped effects. A disabled transaction context without an operation remains a no-op; construction is unchanged. Direct writer scopes refuse even when the requested writer might later discover an exact no-op or dry-run path: no writer is entered to make that determination. Disabled transaction mode is not permission to bypass cleanup preconditions. This deliberately narrows private non-Windows use; it does not narrow the already-held public POSIX interface further. This is a cleanup-precondition check, not a new mutation capability. Unwrapped low-level methods and work performed before these entries are not covered.

The public POSIX installer hold, including dry run, is unchanged. A private caller may have performed earlier operations before reaching this new refusal. Such a refusal does not undo them: preserve recovery material and surface incomplete settlement through the existing caller. Never record a refused deletion as consumed, absent or successfully rolled back. This guard covers these two transaction disposal entry points, not every staging cleanup, legacy tree remover, private writer or uninstall path.

## Required effect contract

For every operation, identify the selected source object, authorized parent and ancestor chain, exact entry name, expected current content/metadata and permitted destination. Separate these guarantees:

- Object binding: the effect consumes the same live object acquired and verified by the owner, not a fresh lookup with matching historical identifiers.
- Namespace binding: all effects remain within the authorized chain. A live parent descriptor alone can continue addressing a directory moved outside that chain.
- Mutation stability: content and relevant metadata cannot change between verification and the effect under the supported threat model. A hash followed by a write or delete does not provide this guarantee.
- Destination exclusion: publication cannot overwrite an unselected occupant. This does not bind a selected source name to its object.
- Custody and settlement: acquisition, staging, publish, failure, rollback, cleanup and close have explicit ownership outcomes. An uncertain effect is reconciled before retry; cleanup never adopts a replacement occupant.

A trusted backend must establish these properties for the actual filesystem, operation and current acquisition, not accept caller booleans, a platform label, a historical receipt or a successful capability probe as permission. Reject unsupported effects before they begin. Readback detects drift but cannot retroactively authorize a wrong effect.

## Platform contracts

### Windows

Existing `NtCreateFile` creation relative to `RootDirectory` binds the new child to the held parent object and obtains creator custody. Existing handle-based disposition binds deletion to an opened object. Neither alone establishes namespace continuity or the full lifecycle. Current parent handles share delete access, so ancestors may move; current `os.rename(source, target)` is source-name based. A future backend must retain and validate the complete selected chain with enforceable sharing/access semantics, bind source rename/disposition to the selected handle, reject reparse traversal, ensure content stability, and account for sharing violations and pending deletion. Handle closure is not proof that the selected name is now absent. Keep existing behavior unqualified until these conditions and recovery exits are physically demonstrated.

### Linux and other POSIX systems

`openat` with a retained directory descriptor constrains lookup to that parent object; no-follow controls must cover every component, not only the leaf. Keeping a live object reference avoids some identifier-reuse cases but does not freeze names or content. `unlinkat`/`rmdir` and `renameat2` still select replaceable leaf names. A final `stat` comparison followed by these calls has a substitution gap. No generic compare-and-delete-by-inode contract is supplied by these interfaces.

Before enabling effects, establish an enforceable namespace/content exclusion model for the actual selected objects, or use an operation that directly binds the selected object while satisfying all other guarantees. Advisory locks and declared quiescence do not exclude uncooperative writers. Do not emulate missing atomic semantics with check-then-delete, copy-and-delete or overwrite fallbacks.

A historical Linux experiment with anonymous temporary files and linking from a live descriptor is only evidence for one primitive on that tested filesystem. It does not qualify directory creation, selected replacement, ancestor continuity, disposal, rollback or uninstall, and is not integrated here.

### Windows Subsystem for Linux and DrvFS

Treat each mounted filesystem as a separate backend, not as Linux capability inheritance. Prior observations include unsupported anonymous-file/no-replace-directory operations and coarse metadata timestamps. Reject unsupported primitives without a pathname fallback; timestamp equality is not identity or content authority. Cross-volume operations, mount changes, junction/reparse substitution and both Windows/Linux writers require explicit coverage. This document does not add a filesystem probe or remove any hold.

## Whole lifecycle and qualification

The admission plan must cover creation (including temporary names), exact replacement, metadata changes, selected object retention, commit disposal, rollback restoration, staging cleanup and uninstall. A successful create primitive cannot admit a transaction whose required inverse or cleanup is unsafe. On incomplete settlement, retain recoverable objects and the original failure plus cleanup failure; do not silently convert preservation into success.

Required physical qualification, not run by this change: component and leaf substitution before every effect, identifier reuse, parent movement, content mutation through another handle/hard link, reparse changes, destination collisions, unsupported filesystem results, interruption after effect before journaling, pending deletion, close failures and retry after uncertain outcome. Exercise native Windows, Linux and supported DrvFS configurations separately, including actual public and private callers. Fixtures or mocked native effects cannot establish this qualification.

The current tests execute only the negative gate and extracted refusal paths, inspect source ordering and compare unchanged source portions. Existing public POSIX hold tests remain relevant. Full installation, rollback, race freedom, historical ownership, automatic migration and release acceptance remain open.

## Terms and Abbreviations

- Effect-bound: an operating-system effect addresses the acquired authorized object and namespace throughout the operation.
- POSIX: Portable Operating System Interface family of operating-system contracts.
- ABA: an object or name changes away and back to an apparently equal observed state.
- WSL: Windows Subsystem for Linux.
- DrvFS: the WSL filesystem interface exposing Windows drives.
- Native qualification: actual platform lifecycle verification, not a source or mocked test result.
