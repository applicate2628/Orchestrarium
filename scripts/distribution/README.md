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

### Optional Windows x64 publication matcher

An independently built and qualified Windows x64 matcher can be selected with
both --publication-matcher FILE and --publication-matcher-sha256 SHA256.
The pack contains only the named executable at
native/orche-publication-match.exe; the Rust toolchain and source tree are not
packaged and no build runs during installation. This is an application
component rather than a Python module or an SDK.

The builder checks its image type and SHA-256 before and after copy. A bundle
with no selection remains manifest version 3. Version 4 adds only
publicationMatcher with the fixed relative path and expected SHA-256.
Predecessor manifests remain readable without opening the old matcher;
active launch and retention reject a declared member that is absent, linked,
or different. Retention passes the original identity to the same builder.

A passing package check is not build provenance, publisher authentication,
dependency license evidence, or actual activation. Release qualification must
establish the executable and its applicable notices independently. The
existing stock hook registration and Python runtime lifetime do not change.

## Shared Codex hook file

Use this only when multiple global Codex profiles already link to a synchronized
`hooks.json`. Keep the bundle local, in the same absolute directory on each host
of the same platform. Select an ordinary, permanent directory managed by the
local installation owner, not a synchronized folder or an arbitrary workspace.
On Windows the selected directory must satisfy the installer’s direct-command
path grammar. No interpreter is found through `PATH`.

Run the bundle launcher with `--retain-only ABSOLUTE_DIRECTORY` on every host
first. This stages the checked release without changing any provider profile.
For a registration-only update, preview from the existing retained bundle with
`--permanent-runtime --global --shared-hook-runtime --hooks-only --dry-run`.
For an upgrade from a different retained bundle, supply
--previous-retained-release ABSOLUTE_DIRECTORY with the already trusted bundle
that owns the current registrations. Use the same selection for preview and apply;
the previous bundle is inspected, never launched. Repeating the same update
cannot rewrite an already matched registration. An unchanged registration is
not evidence of Codex trust; complete any pending approval natively before
expecting a successful health check on a repeat run.
On the host owning publication of the common file, remove only `--dry-run` to
apply. This requires the current shared file and its neighboring installer
inventory to agree with the current retained release or with a receipt-verified
ordinary installation. The older interpreter may be missing, but its complete
owned registration and script paths must still be independently identifiable.
Each retained release supplies its own hook catalog. The installer can add,
update or retire its own entries without moving unrelated native handler slots.
Only those registrations and the generated portable inventory can change.
The installer preserves the Codex profile link, unrelated hooks, skills,
roles, documents, settings and trust. Legacy commands outside the qualified
inventory are not part of this operation.


Omit `--hooks-only` for the existing full Codex pack installation with shared
hook registration. It selects Codex without the provider menu. The shared
registrations point at the selected retained Python and script paths; the
portable inventory carries the expected commands across different local
sync and profile paths.

Do not run the apply step before all consumers have the same verified retained
release. Review changed definitions in Codex’s native `/hooks` interface on
each applicable host; the package does not transfer hook trust. To verify the
retained route explicitly, pass its `app/src.codex/skills/lead` directory as the
health checker’s `--installed-root`. Retain the release as long as any hook
references it. This mode initially migrates the installer’s ordinary installed
hooks; re-running the same release is supported. Changing to a different
retained root requires requalifying the predecessor, not editing the shared file.

Earlier distribution assets and qualification records are preserved only in the
[original Git checkpoint](https://github.com/applicate2628/Orchestrarium/tree/082d46cd83324117abcb965842005d3c15ab99ed/scripts/distribution).
They are not current build inputs and must not be applied to new runtimes.
Do not relabel earlier records or rewrite historical releases.

### Shared upgrade contract

The installer owns the transition: the verified previous release identifies
which existing registrations may be changed; the desired release supplies the
replacement. Preview and apply evaluate the same selection. An already matched
registration needs no rewrite. Hook trust is separate and remains owned by
Codex; an unchanged registration does not establish that trust.

The regression probe runs the normal entry point for A-to-B upgrade, wrong
predecessor, and repeat. Check the shared files and unrelated profile state,
not just the exit code. Keep product-native health distinct from fixture
results; a repeat while Codex approval is pending is not proof of readiness.

For design background, see [Effective ML Revisited](https://blog.janestreet.com/effective-ml-revisited/#make-illegal-states-unrepresentable),
[Parse, Don't Validate](https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/),
and [Applying Design by Contract](https://www.kth.se/social/files/59526bfb56be5b4f17000807/meyer-92-contracts.pdf).
[Hypothesis stateful testing](https://hypothesis.readthedocs.io/en/latest/stateful.html)
describes a way to explore longer operation sequences if focused probes cease
to cover the risk; it is not a dependency of this installer.

## Terms and abbreviations

- CPython: the reference implementation of the Python interpreter.
