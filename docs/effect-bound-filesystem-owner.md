# Effect-bound filesystem owner: contracts and current hold

Status: source design and defensive mitigation, not a qualified mutation backend. This is an Orchestrarium repository contract, not a Codex or Claude provider guarantee. No native qualification is established by the pure tests described here.

## Supported ordinary-writer scope

The accepted ordinary installation scope is cooperating writers serialized by the caller. Selection still identifies intended objects, parents and destinations. Refuse observed foreign replacements, changed targets and occupied destinations; retain recovery material and report uncertain or partial settlement honestly. Caller serialization does not establish operating-system exclusion of unrelated processes.

The stronger namespace/content exclusion requirements below describe a separate adversarial guarantee, not a prerequisite for every ordinary installation. Checked name-based operations may be qualified within the serialized ordinary-writer contract, but are not atomic selected-object deletion or protection against uncooperative concurrent writers. This distinction supersedes blanket readings of the earlier requirements without dismissing historical counterexamples.

Use the existing transaction, mutable-path and platform owners. Qualify acquisition, forward effects, rollback, cleanup, staging and uninstall within the supported scope, including observed drift, collisions and recoverable failures. Keep Linux, macOS and mounted Windows filesystem evidence separate; do not require a privileged storage redesign for an unrequested hostile-writer guarantee.

This clarification does not enable a backend, remove current public/private POSIX holds, establish native receiving or authorize live installation. An implemented and tested owner lifecycle remains necessary; documentation is not runtime acceptance.

## Serialized original-directory retention

When native no-replace is unavailable, the existing transaction owner may retain an original directory into its declared retained slot by exclusively creating an empty destination reservation, recording its creator identity, and verifying the source image, held parents and empty reservation before descriptor-relative rename. The reservation stays present until the rename replaces it. This preserves original identities and existing dependent records; it does not copy/delete the original or overwrite an unverified occupant. The bounded path requires relative descriptor capabilities. It also supports regular-file effect retention and an initial file migration from its old leaf to its declared tombstone, with reservation custody recorded on the owning effect or migration record. A confirmed move advances the existing journal once; a confirmed unchanged failure cleans only the exact owned reservation; ambiguous outcomes preserve recovery material.

This transition relies on the ordinary serialized-writer scope above. It is not atomic no-replace against uncooperative concurrent writers. Prepared replacement construction is permitted only with an empty current target and a verified nonempty retained original; partial new construction and cleanup remain owned by the existing transaction. Component evidence for this path does not remove the public POSIX hold or qualify all migrations, metadata, providers and installer entry points.

Migration reservations are distinct from original-file backups. Settlement validates the owner and original leaf before consuming only the recorded reservation; foreign contents and uncertain cleanup preserve the witness for recovery. A successful retained move clears that witness and advances the existing migration once. Direct rollback, commit and outer transaction settlement use the same reservation cleanup. Recovery reports the verified original leaf rather than an empty reservation as the original. File migration rollback preserves the original inode, including other hardlinks; this does not make reconstructed directory rollback identity-preserving.

## Selected migration parent custody

Forward migration selection binds source and destination parents separately when the retained original is stored in a distinct registered directory. Frozen selection witnesses own the source parent; the existing migration-retention registry owns the retained directory witness. The guard validates selection and retention before acquisition, before yielding and after the effect, reusing a descriptor only for the same parent. Component tests use actual parent descriptors and a relative move, including drift and close failures; they do not qualify the complete migration lifecycle or remove admission holds.

## Existing owner and first implementation

The production installer owns effects through `_InstallTransaction`, `_CreateOnlyMutablePath` and `_WindowsBoundNode`. Extend these owners rather than adding a second filesystem engine. `_require_transaction_disposal_backend` now rejects non-Windows entry to both `_dispose_node` and `_dispose_image`, before input observation, permission changes or transaction updates. The old POSIX name-based deletion branch is removed. The existing Windows branch remains unchanged and still requires its own checks; passing this negative gate grants no authority.

The same negative gate also runs before enabled transaction snapshot acquisition and before any direct-operation scope yields to a writer, including nested or enabled scopes. It therefore refuses those private entry paths before their scoped effects. A disabled transaction context without an operation remains a no-op; construction is unchanged. Direct writer scopes refuse even when the requested writer might later discover an exact no-op or dry-run path: no writer is entered to make that determination. Disabled transaction mode is not permission to bypass cleanup preconditions. This deliberately narrows private non-Windows use; it does not narrow the already-held public POSIX interface further. This is a cleanup-precondition check, not a new mutation capability. Unwrapped low-level methods and work performed before these entries are not covered.

The public POSIX installer hold, including dry run, is unchanged. A private caller may have performed earlier operations before reaching this new refusal. Such a refusal does not undo them: preserve recovery material and surface incomplete settlement through the existing caller. Never record a refused deletion as consumed, absent or successfully rolled back. This guard covers these two transaction disposal entry points, not every staging cleanup, legacy tree remover, private writer or uninstall path.

Five additional mutable-path entry points use the same preflight directly: directory preparation, anchor bootstrap, exact-file migration, projection creation and migrated-file rollback. They refuse non-Windows calls before observing inputs, including dry-run or potential no-op requests. Rollback does not enter a fresh writer context: refusal preserves its existing custody and propagates to the established incomplete-settlement owner. This finite entry set does not claim that every internal primitive, staging remover or uninstall route is covered; expansion beyond it requires a complete effect/caller inventory rather than repeated local guards.

## Bounded ordinary POSIX leaf reconstruction

`_InstallTransaction._dispose_posix_node` is the first reconstructed primitive for the supported caller-serialized scope. It requires a sealed ordinary leaf witness, compares current identity and content, holds a no-follow parent descriptor, and performs relative unlink or empty-directory removal. It does not change permissions, recurse into unknown children, or adopt a replacement. Close failures retain the primary exception by identity, including interruptions and false-valued exceptions.

The existing `_dispose_node` admission gate still runs before dispatch. Public installation, transaction acquisition and direct-operation holds are unchanged. Native isolated leaf tests qualify only this primitive, not whole-tree settlement, ancestor lifetime, staging, update, uninstall or fresh-directory publication. This is not hostile concurrent-writer exclusion. The caller remains responsible for ancestor selection, serialization and journal advancement. Reconstruct and qualify those remaining owners before enabling POSIX transactions.

The subsequent native tree-component tests invoke the existing image/journal owner with explicit test-only admission and leaf dispatch. They cover completed tree consumption, foreign membership and payload drift, pending migration, partial progress, late foreign children, and descriptor-close failure after a leaf effect. Uncertain completion retains unconsumed journal state; a retry refuses a missing expected member instead of inferring ownership from absence. Effect and backup images are checked separately. These tests do not enable public transactions or qualify acquisition, staging, crash recovery, update or uninstall.

The snapshot component suite now exercises actual file/tree acquisition, backup creation, owned disposal, snapshot restoration, commit cleanup and partial-copy failure cleanup. Foreign payload and backup membership changes preserve recovery data. Rollback selects a primary exception by presence, never its truth value, including when exception truthiness raises. POSIX admission is substituted only in these isolated tests; declared replacements, migration, scalar effects, uninstall and the complete public installer lifecycle remain separate qualification obligations.

The same primary-by-presence rule now applies to the remaining copy-close, scalar-parent-close, descriptor-read-reset, scalar-close, payload-close, tree-construction and prepared-image cleanup boundaries. Extracted production-expression checks cover absent, ordinary, false-valued and raising-truthiness causes; a real payload producer/descriptor-close test verifies retained bytes and recovery location. Expression checks establish diagnostic selection only, not complete native lifecycle qualification.

## Capability-probe failure receiving

The existing directory-move capability probe chooses its primary exception by
presence (`is None`), never truthiness. If both its body and disposal fail, the
existing typed settlement failure retains the original body cause, cleanup
exception context and recovery locator. A false-valued exception must not replace
the original cause, and an exception's `__bool__` must not run during this choice.
When only disposal fails, disposal remains the selected cause. That diagnostic
correction alone added no backend admission and did not change the public or
private POSIX holds. The later selected-tree retention qualification below
updates the probed owner without changing those diagnostic guarantees.

The focused tests execute the extracted probe control flow and real diagnostic
declarations against inert paths and a synthetic transaction. They include the
actual POSIX refusal helper but no installer import or filesystem effects. This
is not native probe, creation, move, cleanup or recovery qualification. Acquisition
and initial observation before the probe's existing try boundary remain open
lifetime issues; this correction does not claim to settle them.

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


### Verified unrequested copy timestamps

A successful timestamp setter may return a full same-operation observation that differs only in the requested times. If all other metadata and the retained identity match the projected state, and the subsequent complete observation exactly matches that operation result, the copy owner journals the actual image before rejecting the unfulfilled exact assignment. This is factual rollback custody, not acceptance of filesystem rounding. Missing observations, setter errors, changed non-time metadata, identity changes and later timestamp drift retain the unknown-effect path.

The assembled POSIX regression substitutes only the internal admission boundaries and injects an unexpected timestamp result on a real held descriptor. It checks the full remaining target tree and empty staging, not just regular files. This qualifies failed-install rollback, not public POSIX installation, timestamp representability, successful upgrade/removal or native macOS acceptance.

### Fresh-copy timestamp representability

Forward copies may use measured representable times only when the copy owner proves both destination absence and an absent original metadata participant. Restoration remains exact; a missing original cannot be inferred from a generic forward-operation flag. Existing originals require the separate pre-mutation qualification below.

When the real successful setter differs only in time, the journal first retains its verified actual image. The owner then creates an exclusive empty sibling through the existing prepared-file owner, measures the specific requested pair with the same descriptor-based setter, changes each time independently to a contrasting value, and repeats the request. Each field must change and reproduce exactly; observations must not exceed the requested values. No filesystem name, inferred global quantum, tolerance or cross-mount cache grants acceptance. The probe is disposed through the existing checked image owner, with original and cleanup failures retained together on failure.

Before accepting the measured pair, target bytes, identity and pathname binding are revalidated. Since validation reads can change access time, the same progress owner repeats timestamp assignment against the measured exact image; this second assignment cannot initiate another normalization attempt. Subsequent observations remain exact. The new file's bytes and all non-time metadata retain their existing constraints. This fresh-copy permission does not authorize existing originals by itself or admit public POSIX installation.

A file can be copied again after being created earlier in the same transaction. The copy participant therefore retains its actual exclusive-creator identity from the shared file producer or ordinary copy producer. Repeated forward copies may use measured times only while the current inode/native proof still matches that creator and original beforeimages remain absent. Moving a user original into an initially absent logical path does not create this witness; neither a later pathname census nor optional receipt tracking grants it.

### Original-file restoration qualification

Before changing an existing POSIX copy participant, independently measure its original timestamp pair through the owned probe. Both values must reproduce exactly. Revalidate the original stable metadata and descriptor contents after the probe, before the first byte or metadata write. Only this invocation may then qualify representable forward timestamps for that same original inode; inverse restoration still requires the full exact original times and metadata.

If the current full metadata image and requested mode already match exactly, perform no setter. In particular, refusing a preflight must not round an unchanged original merely while trying to restore an already-satisfied state. Changed mode or any metadata difference still follows the ordinary verified path. Unrestorable originals refuse before writing; foreign changes during qualification are preserved rather than overwritten.

Native isolated Codex qualification has completed fresh and repeat installation with only the public POSIX admission/disposal holds substituted, without models or hooks. This is not public POSIX admission, native macOS qualification, or hook health acceptance. The pack installer has no uninstall command; a rejected unsupported removal option is not an uninstall result.

## Selected-tree retention capability

Selected whole-tree replacement qualifies the same retained-object owner used by
the real transition. Its isolated source and destination are explicitly bound to
one owner effect, so supported native no-replace or the existing verified empty
reservation can carry the original identity. The probe is not admission authority
and does not change public POSIX holds or production ownership checks.

After movement, the exact relocated original image and source absence must match.
A second source cannot replace the occupied destination. If publication completed
before a later accounting or close error, cleanup considers only the original
witnesses, their exact relocation and an already-recorded owned reservation.
Unknown or foreign members are never adopted from a new census; failed complete
image checks preserve them and retain the primary and cleanup failures.


## Native macOS receiving boundary

On source revision `0ff5a46e`, isolated macOS x86_64 receiving with CPython
3.13.18 completed the Claude project fresh/repeat and global fresh/repeat/selected
nonlead upgrade cases. Codex global fresh/repeat without hooks also completed.
Only the two existing POSIX admission checks were substituted in the receiving
harness; filesystem effects and hook health subprocesses were real. Public
POSIX admission is unchanged.

The four-case provider matrix was not green: three cases passed and Codex
hook-enabled fresh installation failed with `E_HOOK_HEALTH_FAILED` caused by
`PSV1-TREE-NOT-EMPTY`; its repeat was never reached. Rollback reported
`E_ROLLBACK_RESTORE_BLOCKED_BY_IDENTITY` and preserved recovery state. Native
Codex hook inventory had created runtime databases, shared-memory/write-ahead
files and an installation identifier in the isolated provider directory outside
the installer's journal. Those files are not disposable installer payload merely
because this health invocation produced them. The next correction must address
the host-query process lifecycle and ownership boundary, not weaken rollback
identity checks or reinterpret the failed run as acceptance.

Focused native lifecycle checks ran 18 cases: 16 passed and two existing
representability-probe cases skipped because native timestamp representation was
exact. Probe-settlement diagnostics passed nine cases; the public-hold tests
passed five. The separate leaf/tree disposal test modules could not load because
pytest was absent in that interpreter; they are unverified, not passing. These
results do not establish race freedom or release admission.

A bounded follow-up probe using native Codex 0.166.0 identified live Git and
HTTPS-transport descendants in the query's private process group after the
app-server direct process had been terminated and waited. The first remaining
Git process was reparented to the system parent. The query helper's direct-PID
cleanup therefore does not settle the native host's complete process lifecycle.
Its zero-item inventory result was not evidence of process completion. The probe
used the existing group owner for cleanup; its five-second settlement reported
absence unconfirmed, and a subsequent process census observed no remaining group.
Do not reinterpret the earlier incomplete closure as successful settlement or
remove the outer health process-tree guard to make this scenario pass.

At revision `328d46e2`, the query owns and settles its private group, with
EOF-first host shutdown and interrupted-binding reconciliation. The bounded native
query returned its inventory and the group was independently observed absent.
Native Codex global hook-enabled fresh installation then returned success with
`PENDING_MANUAL_TRUST`. Repeat before that manual trust was granted refused with
`CODEX_HOOK_TRUST_PREEXISTING_DRIFT`, as required by the current trust policy;
there was no process-tree or rollback-settlement failure. Staging was empty and
the unrelated marker and installed configuration remained. This is fresh-install
receiving plus an observed trust boundary, not trusted-repeat acceptance or a
solution for ownership of native host runtime files. Nine query-custody unit
checks passed on both Windows and macOS; the pytest-based suite remains unrun.


### Native Codex selected-upgrade receiving
- Added the missing Codex global selected non-lead upgrade scenario with hooks explicitly disabled for both fresh install and upgrade. Native macOS CPython 3.13.18 executed one test in 21.041s: PASS; fresh 11.82s and selected upgrade 8.90s both returned zero.
- Assertions verified selected source bytes restored, neighboring analyst tree unchanged, receipt schema/member manifest correct, source bytes unchanged, user marker preserved, staging empty and no retained/probe/upgrade leftovers. This is additional acceptance coverage, not red-before-fix regression evidence or trusted-hook acceptance.
- ASUS and Mac test blob identities matched. Independent test-only review PASS and release-notes-exempt. Native hook trust and runtime-state ownership remain outside this check; public POSIX admission unchanged.
