# Evidence scope for the pre-SDK backport

The historical checkpoints below were produced on the recovery branch ending at
`7652a203`. They qualify only the recorded inputs and operations, not installation
of the pre-SDK main revision now packaged by this branch. This backport changes
application source selection only; runtime/notice binding remains unchanged.
Do not reuse the recorded installer lifecycle as receiving evidence for changed
application inputs. Publication and attribution limitations remain explicit.

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
