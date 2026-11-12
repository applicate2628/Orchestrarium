# Runtime evidence and retention contract

The builder requires `--runtime-evidence PATH`. The preparation workflow must issue this expected record only after independently reconciling the selected runtime and notice bytes. The builder never creates an approval record from an arbitrary directory. It checks consistency with the supplied record, not publisher identity, acquisition-channel authenticity, license completeness, or release approval.

## Record format

The JSON object has exactly four fields: `schemaVersion` (integer 1), `target` (the selected layout tuple), `runtime`, and `notices`. The latter two are nonempty objects keyed by exact, case-sensitive, payload-relative paths. Include directories as `["directory"]`, symbolic links as `["link", "exact stored link spelling"]`, and regular files as `["file", "lowercase SHA-256 hex", executable]`, where executable is a JSON boolean indicating whether any executable mode bit is present. Do not normalize path case or resolve link spellings into file contents. Duplicate JSON keys are refused.

`runtime` describes the payload after the builder's documented bytecode, embedded-CLI and target-specific omissions. `notices` describes `scripts/distribution/notices` after historical CLI-only exclusions. Directory entries remain part of the inventory, including empty directories that survive filtering. Both the initial prepared tree and the already-filtered retained tree must match the same record. A new dependency or notice update requires a newly qualified record, not a permanently pinned product version.

## Issuance workflow

1. Retain acquisition bytes, exact platform wheel locks and their source records. Verify their recorded digests without treating a hash as publisher authentication. Preserve the independent preparation report and any acquisition/authentication evidence separately.
2. Extract Linux inputs on a native case-sensitive filesystem, preserving exact file case and symbolic links. Transport the tree in a case-preserving archive if needed. A Windows case-insensitive unpack can lose distinct terminfo entries before a later Linux copy; merely hashing that damaged tree does not qualify it.
3. Install the locked binary wheels in the isolated preparation tree with `--no-index --no-cache-dir --no-deps --no-compile --require-hashes --only-binary=:all:` and a previously verified local wheel directory. Preserve the exact command and lock bytes. Do not invoke SDKs or providers to qualify packaging.
4. Compare all original runtime and wheel members against the retained inputs. Account explicitly for generated RECORD, INSTALLER, REQUESTED and console-script bytes, link transformations and intentional builder omissions. Refuse unexplained missing, changed or extra members. Console-script shebangs may retain preparation paths; packaging verification alone does not qualify those dependency tools for relocation.
5. Reconcile the exact selected notice texts and metadata to the preparation inputs. This includes the upstream-declared subset and SDK notice records; it does not resolve remaining legal-completeness or native-attribution gates.
6. Save the expected record only after these checks, alongside the preparation report and input identities. The low-level inventory helpers can serialize the selected paths, but invoking them on an unqualified directory is not evidence of qualification. Recheck quiescent inputs and verify a real assembly plus repeated retention before using the record in a release workflow.

The checked-in tests deliberately create synthetic records for fake runtime bytes. Their helper is test-only and must not be used to qualify a real runtime. The local recovery evidence demonstrates guarded issuance for reconciled Windows and native Linux inputs; it is not a signing service or general license approval.

## Assembly and compatibility

The builder checks selected runtime and notices before creating output, then checks the copied result before writing `bundle.json`. Schema-2 manifests retain the unchanged record at `runtime-evidence.json` and bind its SHA-256. The launcher verifies the record's identity; retention supplies that same record to the one existing builder. Normal launch does not rehash every payload file. Inputs must remain quiescent under the existing local ownership contract; no new hostile concurrent-writer protection is claimed.

The new launcher explicitly refuses schema-1 manifests. Existing schema-1 bundles keep their original launcher and remain untouched. Do not replace an old launch.py in place or infer that upgrading its manifest qualifies its runtime. To reassemble a legacy payload, independently reconcile it and supply an explicit record. Initial build callers now require the record; retention callers do not invent one.

An interrupted copy remains for diagnosis and has no completed manifest. Existing outputs, runtimes, profiles and tags are never overwritten or upgraded by this contract. Distribution authentication, supported-platform acceptance, native attribution and release approval remain separate gates.
