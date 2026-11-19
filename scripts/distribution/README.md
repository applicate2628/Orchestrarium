# Local Orchestrarium distribution

The optional builder packages the existing installers and an independently
qualified standalone CPython runtime. It does not fetch Python, run a package
manager, activate a provider, or install either client. The ordinary source
installer is unchanged and does not require this bundle.

## Runtime profile and evidence

Use the cpython-stdlib-only profile: a standalone CPython 3.15 runtime with its
standard library, no installed third-party packages or startup extension files,
and the matching target notices. The builder rejects populated package locations,
linked package locations, installed package metadata, path extensions and virtual
environments before creating output. It does not filter particular model
providers or automatically remove software from the supplied runtime. A stock
standard-library component such as _dbm is not omitted: decide its admission
and required notices during independent target qualification.

Supply the independent qualification result as --runtime-evidence. The new
record has exactly these top-level fields:

- schemaVersion: 2
- target: the selected operating system and architecture
- runtimeProfile: cpython-stdlib-only
- runtime: exact relative-path inventory of the selected Python runtime
- notices: exact relative-path inventory of the selected CPython notice tree

Both inventories use the existing directory, link-string and file digest/mode
records. Relative paths for notices start below the distribution notices
directory. As with the prior builder, disposable cache entries are not packaged.
Record bytes are carried unchanged and bound by the bundle manifest. Compare
the runtime with its authenticated upstream source, verify the import/runtime
layout and applicable notices independently, and use a new record for the new
profile. A matching inventory alone does not authenticate its producer or
establish license completeness. The builder's layout checks are not a sandbox
against a malicious interpreter or concurrent writer.

The repository currently has target-specific CPython notice trees for Linux
x64 and Windows x64. For other targets, matching target notices and independently
qualified runtime bytes are required before the builder can assemble a bundle.
Ordinary source installs do not use these notice trees.

## Assembly and use

Invoke the local builder with --runtime, --runtime-evidence, --target, --release,
and --output. Prepare all inputs independently before assembly. The destination
must be new, and no operation changes the existing source or runtime inputs.

Launch the bundle with its generated shell or PowerShell entry. The launcher
checks bundle-relative identity and evidence consistency before passing arguments
to the existing installer. Applying an installation requires explicit
--retain-to ABSOLUTE_DIRECTORY or --permanent-runtime; retain the selected
interpreter while installed hooks reference it.

Earlier distribution assets and qualification records are preserved only in the
[original Git checkpoint](https://github.com/applicate2628/Orchestrarium/tree/082d46cd83324117abcb965842005d3c15ab99ed/scripts/distribution).
They are not current build inputs and must not be applied to new runtimes.
Do not relabel earlier records or rewrite historical releases.

## Terms and abbreviations

- CPython: the reference implementation of the Python interpreter.
