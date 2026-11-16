# Evidence scope for the pre-SDK backport

The historical checkpoints below were produced on the recovery branch ending at
`7652a203`. They qualify only the recorded inputs and operations, not installation
of the pre-SDK main revision now packaged by this branch. The initial backport
changed application source selection; subsequent bounded installer corrections
are recorded in the pre-SDK checkpoints. Runtime/notice binding remains unchanged.
Do not reuse the recorded installer lifecycle as receiving evidence for changed
application inputs. Publication and attribution limitations remain explicit.

## Pre-SDK native Windows checkpoint: 2026-11-16

Source `f034b843` packages the pre-SDK main layout without importing the SDK installer. Actual Windows assembly passed in 84.56 seconds with the unchanged qualified runtime/notice record `db195ff2a110d7ff83c9ab41744138f04cb2b19676f4574ba631c2d916faa3f1`. Before the role-manifest correction, assembly passed in 196.53 seconds and public create-only retention plus native installer help passed in 86.18 seconds. The correction changed only accepted factory role byte bindings, not assembly or retention logic.

The first installation preview exposed stale role hashes already present in main `d288cf78`: all 18 source TOMLs contained the accepted browser/computer feature changes but the manifest bound their previous bytes. Source-to-bundle comparisons were exact. Each old digest was verified against the parent revision, every parsed difference was confined to the five added false-valued feature flags, and all profession instructions and existing settings were preserved. Only the 18 current byte hashes were updated. Eight source/memory regressions passed, including current factory validation and rejection of unrecorded role drift. Independent review and publication checks passed; this is not a publication result.

With the corrected assembly, the public launcher selected both clients interactively and completed preview in 10.56 seconds. Fresh Codex installation succeeded, installing 54 canonical skill directories and all 18 native roles. The subsequent Claude phase failed with Windows error 1314; the overall two-client operation returned 1 in 81.51 seconds. The Claude target was absent after rollback, while the successful Codex target and user marker remained. Source inspection identifies the unchanged native symbolic-link path as consistent with the privilege failure; this does not establish the exact failing API from a trace.

A separate public-launcher Codex repeat then passed in 22.46 seconds. Its 19 native-role/config files remained byte-identical and the user marker was preserved. No hooks, global profile, model, security setting, GitHub Actions or publication was changed. The supplied runtime evidence remained byte-identical, and the bundled builder, launcher and corrected role manifest matched their current source bytes.

The bounded runtime/notice and Codex receiving result is established. Native Claude installation on this Windows connection is not accepted; no privilege elevation, weakened guard, SDK switch or copy fallback was attempted. Other operating systems, publisher authentication, full attribution and internet release certification remain outside this checkpoint. Historical SDK lifecycle results below do not replace this new result. After recording the result, exclusively owned assembly, retention and project fixtures were moved to the designated trash, with source absence and destination presence verified; original qualified inputs were untouched.

## Pre-SDK local Windows projection receiving: 2026-11-16

This checkpoint supersedes the local Windows Claude privilege limitation in the preceding pre-SDK checkpoint only. Native diagnosis on the unmodified candidate identified error 1314 at `set_reparse_data` during Claude projection creation. The effective token does not contain the symbolic-link privilege: the bounded private-token helper correctly refused with 1300 rather than granting it. Neither the process token nor system policy was changed.

Source `ca5fd4fb` selects the existing native junction representation for OS-resolved local drive directory targets before opening creator handles. Other namespaces retain symbolic-link requirements, without an error-triggered fallback. Both new and replacement directory projections use this shared owner. The independently reproduced dangling-junction rollback defect was also corrected at the shared no-follow capture/disposal boundary: exact object identity, logical target and raw reparse bytes remain mandatory, but cleanup no longer requires the already reclaimed referent to exist.

The focused suite passed 23 tests with three explicit capability skips in 0.59 seconds. Native creation, copying, commit, ordinary rollback and rollback after canonical-target removal passed. Negative cases preserve a changed raw reparse target at the same identity and preserve a replacement user directory/marker. Process and thread token snapshots were unchanged. The three skipped cases require an assigned symbolic-link privilege and are not counted as successful native coverage. Eight adjacent distribution/source tests also passed; independent review and the staged publication gate passed.

Actual Windows assembly passed in 97.97 seconds. Through the public bundled launcher, interactive Claude selection completed fresh installation in 52.19 seconds, and interactive selection of both clients completed repeat installation in 66.49 seconds. All commands exited 0. Readback found 54 Claude junctions, each with native mount-point tag and the same file identity as its corresponding canonical skill directory; the user marker was preserved. The bundled installer, builder, launcher and role manifest matched current source bytes. Installer SHA-256 was `54a7b45ef1f95235b60e9db090e1f10362c0bafce6f317d4658b92583025f5bf`; runtime evidence remained `db195ff2a110d7ff83c9ab41744138f04cb2b19676f4574ba631c2d916faa3f1`.

This establishes local Windows project installation/repeat receiving without hooks or global profiles, not cross-volume/network receiving, other operating systems, positive privileged-symlink execution, publisher authentication or internet-release certification. No model, GitHub Actions, system security setting, elevation or denied publication operation was used. After independent evidence readback, the exclusively owned receiving workspace was returned to designated trash, with source absence verified; original qualified inputs remained untouched.

## Current-main reconciliation checkpoint: 2026-11-16

The candidate now integrates published main `b6217d74` with the earlier pre-SDK candidate `781d0fcc`. The shared projection owner retains target-dependent Windows representation selection and exact no-follow rollback, including raw reparse bytes and identity. Current-main changes outside these three conflict regions are preserved. Independent review accepted the production reconciliation.

The main-branch inert projection fixtures required alignment with the shared owner rather than restoring an obsolete unconditional junction default or live-referent rollback prerequisite. These are source-method checks, not native filesystem acceptance. The eight distribution/layout tests passed. Native bundle assembly and installation recorded above qualify their earlier source only; they must not be reported as acceptance of this changed installer. Current combined native receiving and publication remain pending. No model, Actions, live-profile installation or previously refused publication was attempted.

## Caller-project receiving correction: 2026-11-16

Merged source `597cae7d` assembled successfully in 177.93 seconds. Public preview, fresh and repeat returned zero, but independent readback rejected the intended project acceptance: `install.py` reset the child working directory to its own source root, so both clients were installed into the disposable bundle application tree, not the caller project. The marker-only project snapshot could not prove installed-state repeat safety. Those successful process exits are not a passed caller-project lifecycle.

The root dispatcher now inherits the caller working directory while retaining its absolute client-script path. Source ownership, global-home selection and explicit-target safeguards stay unchanged; no unsafe-target override was added. The new source-method regression reproduced the reset for both clients under ordinary, explicit relative target, global and preview argument sets before the correction. A fresh assembly and independent actual-target readback are required before claiming corrected native acceptance. All affected installation outputs were confined to the disposable receiving workspace; live profiles were not modified.

## Corrected caller-project native receiving: 2026-11-16

Committed source `fa89cb15` was rebuilt from the unchanged qualified runtime/notice inputs: assembly exited zero in 83.34 seconds. Through the public bundled launcher and its ordinary interactive choice of both clients, preview passed in 9.90 seconds, fresh installation in 72.68 seconds and repeat in 66.64 seconds. All returned zero. HOME, application-data and temporary directories were confined to the isolated receiving workspace; no unsafe-target override, hook-enabled mode, global installation or model was used.

Independent readback verified the actual caller-project Codex and Claude targets, not just process exit codes. Fresh, repeat and live no-follow snapshots match exactly: 337 files and 54 links. Every Claude skill junction has native mount-point tag and the same file identity as its corresponding canonical skill directory. The user marker and ownership receipt bytes were preserved, and the bundle application tree was not used as the installation target.

Bundled entry SHA-256 is `b0fbcc1e1554eae47e525b614616d306b34a653ed3a7a79d5cb818e924afa3e3`; installer SHA-256 is `f22c05f45c631fb146f6d859574bc655477b9b79ba77df4c19cf28019dfbd44a`. Both match committed source bytes. The independently qualified runtime evidence remains `db195ff2a110d7ff83c9ab41744138f04cb2b19676f4574ba631c2d916faa3f1`. The completed repeat process was independently confirmed settled.

This supersedes the failed caller-project acceptance of `597cae7d`, while preserving that failure record above. It establishes bounded isolated Windows installation/repeat receiving, not native pytest-suite coverage, global/hooks-enabled installation, other operating systems, publisher authentication, complete attribution or internet release. No prior publication refusal was retried or bypassed; publication remains pending.

# Runtime evidence recovery scope

This branch restores the bounded runtime/notice consistency contract on the committed SDK baseline. It is not the later combined candidate, a release, or authorization to install. The final combined archive has not been recovered. Later hook projection, packaging omissions and provider changes are not recreated from guesses.

The builder requires an independently qualified expected record before copying. Both selected input trees and the copied runtime/notice trees must match. Only then are the identical record and schema-2 manifest written. The launcher verifies record identity; retention passes the same record to the same builder. Existing schema-1 bundles remain untouched and are not silently qualified or upgraded.

Records contain exactly schemaVersion (integer 1), target, runtime and notices. Inventory values represent directories, exact link spellings, or SHA-256 and executable-bit state for regular files. This baseline retains its original payload selection. Do not reuse a record prepared for different omissions: independently reconcile acquisition inputs, transformations and notice bytes for the selected build first.

Matching bytes proves consistency only. It does not authenticate an issuer or archive, prove complete dependency attribution, establish license clearance, protect against hostile concurrent writers, or establish native receiving. Synthetic tests never execute fake interpreters. Publication, real-input qualification and live receiving remain pending.

## Verification checkpoint

Recovery was prepared on SDK commit 5f0515ac, then rebased onto published SDK commit 8dfe53eb to exclude an unrelated instruction-scope change. Product and test bytes were verified unchanged by that rebase. Inventory/read/verify helpers were recovered from the retained builder whose SHA-256 is 72aefb95713d9c5ec4329993349e6ed9d879d0ebcbb45e77300a4559fad0257c. Payload selection remains the baseline policy rather than importing unrelated later hook or dependency changes. The two post-copy receiving suites preserve their accepted November 11 test bytes; the launcher and existing caller tests are explicitly migrated to the new record contract.

ASUS Windows verification: CPython 3.15.2 ran four record-syntax cases and 18 receiving cases (12 passed, six explicit POSIX-only skips). CPython 3.14.10 with pytest 9.2.0 passed 33 builder/launcher compatibility cases, with ten link/native-child cases excluded. The cache-provider-disabled run emitted the pre-existing unknown cache_dir option warning. In-memory omission of only final receiving produced ten expected negative failures, two passing controls, six skips and zero errors. This is sensitivity evidence, not additional product failures or native acceptance.

At that initial checkpoint, the full repository suite, omitted link/native-child cases, current real-runtime qualification and the unavailable later combined candidate were not verified. Subsequent checkpoints below qualify the omitted cases within their stated platform boundaries. No interpreter payload, live profile or global installation was changed.

The new launcher intentionally rejects schema 1; this is an explicit compatibility boundary, not an in-place backward-compatible upgrade. Normal launch validates record identity but does not rehash the runtime inventory. Inventory consistency is checked during build and retention, not as per-launch tamper protection.


## Native Linux receiving checkpoint: 2026-11-14

The same recovery code at commit `3b8c851b` was verified on Debian under Windows Subsystem for Linux (WSL), using CPython 3.13.5. All 18 runtime/notice receiving tests passed in 0.554 seconds, with no skips; all four evidence-record syntax tests passed in 0.048 seconds. This includes the six link-target and executable-bit cases previously skipped on Windows. Source files remained unchanged.

Reproduce from the repository root with bytecode writes disabled and `TMPDIR` plus `ORCHE_TEST_TMPDIR` set to an approved disposable directory that supports POSIX links and modes. The observed run used a memory-backed temporary filesystem; fixture directories were absent after test cleanup.

```sh
python3 -B -m unittest discover -s tests -p 'test_bundle_*receiving.py' -v
python3 -B -m unittest discover -s tests -p test_bundle_evidence_record.py -v
```

This checkpoint supersedes the earlier missing Linux receiving coverage only. It does not run the remaining omitted builder/launcher cases, execute an interpreter payload, qualify real acquisition inputs, authenticate provenance, or establish installation/release acceptance. Publication and real-input qualification remain pending.

## Linux link-boundary checkpoint: 2026-11-14

On the unchanged recovery code, six previously excluded builder/launcher link cases passed on Debian with real POSIX symlinks, in 38.05 seconds, with no skips. They cover an escaping runtime link, a source link swap before copy, a linked output parent, an escaping interpreter link, an escaping manifest link and a dangling retention destination. The synthetic interpreter bytes were never executed. The existing pytest 9.2.0 library was reused without installation; disabling its cache emitted the known cache_dir warning.

Reproduce with the same temporary-directory and bytecode conditions as above, in an environment where pytest 9.2.0 is available. The observed native Python process loaded an existing pure-Python pytest library through PYTHONPATH; no system-wide pytest installation is implied.

```sh
python3 -B -m pytest -p no:cacheprovider tests/test_bundle_build.py::test_escaping_runtime_symlink_refused tests/test_bundle_build.py::test_source_link_swap_before_copy_call_is_rejected tests/test_bundle_build.py::test_output_parent_symlink_is_refused tests/test_bundled_launcher.py::test_symlink_escape_refused tests/test_bundled_launcher.py::test_manifest_symlink_outside_bundle_refused tests/test_bundled_launcher.py::test_dangling_retention_name_is_not_followed -q
```

This narrows the earlier excluded-case gap only. The remaining omitted builder/launcher cases, native interpreter execution, real inputs, publication and installed receiving are still unqualified.

## Native Windows child-boundary checkpoint: 2026-11-14

On the unchanged recovery source at `16b905f7`, three launcher child-boundary tests passed on Windows in 0.20 seconds with no skips. The real child test invokes the existing Python interpreter with isolated mode and verifies an exit status of 23 plus exact arguments containing spaces, Unicode, a literal ampersand, an embedded quote and an empty string. The other two tests substitute the process boundary and check Windows wait/exit propagation and POSIX exec-replacement dispatch; they are not native POSIX execution evidence. The known disabled-cache configuration warning remains.

Reproduce from the repository root with an existing pytest environment, bytecode disabled, and temporary variables plus `--basetemp` pointing to a fresh approved disposable directory:

```sh
python -B -m pytest -p no:cacheprovider tests/test_bundled_launcher.py::test_windows_child_preserves_real_argument_boundaries tests/test_bundled_launcher.py::test_windows_child_waits_and_propagates_failure tests/test_bundled_launcher.py::test_posix_child_keeps_exec_replacement -q
```

This validates launcher argument/exit handling with the test environment interpreter, not the shipped interpreter payload or an installed bundle. Real acquisition inputs, publication and installed receiving remain pending. No production source or admission policy changed.

## Native Git notice-byte checkpoint: 2026-11-14

On unchanged recovery source at `c18498eb`, the remaining excluded notice-checkout case passed on Windows in 0.98 seconds. The test creates a local synthetic Git repository, commits the actual tracked notice bytes with `core.autocrlf=false`, then clones locally with `core.autocrlf=true` and compares every notice file byte-for-byte. It performs no network access or publication and executes no interpreter payload. The known disabled-cache warning remains.

Reproduce from the repository root with an existing pytest environment, bytecode disabled and temporary variables plus `--basetemp` selecting a fresh approved disposable directory:

```sh
python -B -m pytest -p no:cacheprovider tests/test_bundle_build.py::test_vendor_notices_keep_exact_bytes_in_autocrlf_checkout -q
```

Together with the six Linux link cases and three Windows child-boundary cases above, this accounts for the ten cases excluded from the original 33-case compatibility run. These are separate platform-specific checkpoints, not a full-suite run or release acceptance. Real acquisition inputs, publication and installed receiving remain pending.

## Retained real-input recovery checkpoint: 2026-11-14

On recovery source `8e4442d3`, the retained Windows runtime was re-inventoried using the current builder. All 6,374 entries match the independently qualified Windows record whose SHA-256 is `db195ff2a110d7ff83c9ab41744138f04cb2b19676f4574ba631c2d916faa3f1`. The retained bundle's record is byte-identical to that original record, and its complete notice inventory matches. This is a fresh real-input integrity check, not another synthetic runtime test or publisher authentication.

Restored 35 missing supplemental files under `notices/cffi`, `notices/cryptography` and `notices/python-rust` from that intact retained bundle. Each subtree was checked against the original qualified record before and after copying. Existing recovery files were not overwritten. The original qualification describes partial component/source attribution; it does not claim complete legal clearance.

Full assembly remains open: the qualified runtime uses the Python SDK with an external Codex CLI, while the recovered baseline locks still include `openai-codex-cli-bin` and its notice metadata describes a bundled CLI. Existing native CLI notice files remain preserved. Resolving that distribution-owner discrepancy requires the corresponding source/lock/adapter contract, not changing the evidence record to bless mismatched inputs or suppressing notice checks. No real bundle was assembled, retained or installed by this checkpoint, and no publication occurred.

## SDK-only selection and real assembly checkpoint: 2026-11-14

This bounded follow-up supersedes the baseline-selection hold above. The existing SDK adapter already requires an explicitly selected external Codex executable. Builder selection, both platform wheel locks and upstream notice metadata now agree: retain the Python SDK, exclude its separate CLI package/metadata/entrypoints, and preserve historical CLI notices in source but not the SDK-only output. No later hook payload changes, launcher changes or Windows header/library omissions were imported.

Three layout/neighbor regression cases first failed on the baseline and then passed. Independent review found a relative entry-directory alias that defeated exclusion; the regression reproduced that failure before correction. The shared validator now rejects linked package, entry, package-directory and entry-directory inputs containing the excluded CLI, while preserving unrelated internal directory links. Native Debian/WSL ran four negative alias cases and one positive control: all five passed. These cases are explicitly POSIX-only; Windows reparse refusal has separate coverage.

The final Windows bundle-focused regression passed 56 tests and 10 subtests, with 17 platform/privilege skips and the known disabled-cache configuration warning. This is not a full-repository result. Both independent reviews accepted the bounded change after the alias and documentation corrections.

Final real Windows assembly completed with exit 0 in 81.82 seconds, followed by create-only retention through the same builder and native retained interpreter execution of installer help, exit 0 in 77.74 seconds. Both receiving boundaries verified the unchanged independently qualified record `db195ff2a110d7ff83c9ab41744138f04cb2b19676f4574ba631c2d916faa3f1`. The final builder SHA-256 is `f77c153252297c9d5c2766ff82ec328ef45e4e326061d183eaa05b8f69c99d45`. Readback confirmed byte-identical builder, distribution README, notice metadata and four lock files between the final source and assembled application. This evidence paragraph was recorded after assembly; test files are not bundle inputs.

This establishes real build/retention consistency and native help startup, not live-profile installation, hook execution, Linux/macOS runtime acceptance, complete dependency attribution, publisher authentication or internet release readiness. No model call, global installation or publication occurred. Identified disposable test fixtures and superseded pre-review bundles were moved to the designated trash; final assembled/retained artifacts remain available.

## Native project lifecycle checkpoint: 2026-11-15

The retained real Windows bundle from source `ab0f428d` completed public-launcher preview and fresh project installation for Codex and Claude, then repeat installation and uninstall. This extends the assembly/help evidence above to the bounded project lifecycle, without hooks or a global profile. Fresh installation took 143.91 seconds, repeat installation 101.02 seconds, and uninstall 134.98 seconds; each client returned COMPLETE (0) in each apply phase.

Both installed clients had 54 skill directories and ownership records. The user marker and both ownership records remained byte-identical across repeat installation. Uninstall removed 199 Codex and 352 Claude owned files plus three configuration entries per client. Independent post-action readback confirmed the user marker unchanged, both skill trees absent, empty residual ownership records, and the retained interpreter and original evidence record preserved. An initial postcheck incorrectly expected ownership-record deletion; inspection of the uninstall owner established that empty residual records are the intended output, and the check was corrected without changing product code.

The exact original installation fixture was reused for uninstall only after its marker and ownership-record hashes matched the preceding checkpoint. It was returned to the designated trash after verification. No already-passed installation was repeated during this evidence reconciliation. Global or hook-enabled installation, other operating systems, publication, full attribution and publisher provenance remain unverified; this checkpoint does not qualify internet release. No model, live-profile or security-setting change occurred.


## Published-main integration checkpoint: 2026-11-16

Reconciled delivery source `07f6b7ba` with published main `891f61a1`, retaining
its Claude uninstall and admitted POSIX backend changes. The production merge
was conflict-free; the duplicated release-date heading was consolidated without
dropping any release entries. The existing caller-directory fix and Windows
projection selection/no-follow rollback remain in the combined source.

On Windows, distribution/layout checks passed 9 tests, selected-current uninstall
passed 21 tests, and inert Windows projection checks passed 17 tests. Universal
hook mirror parity, staged publication checks and diff hygiene passed. These are
focused integration checks, not a new native bundle assembly or full-repository
result. Earlier bundle acceptance continues to describe only its recorded source.

No native push was repeated: the prior complete-history scan refusal remains
unresolved under the unchanged deadline. No scanner, supervisor, access policy,
model, Actions or live profile was changed. Publication and archival remain open.
