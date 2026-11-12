# Portable distribution on the published layout

This builder packages the current installer and existing Codex/Claude provider trees, without migrating them to the experimental SDK adapters layout. It preserves src.claude/skills, existing projection policy and current installer behavior. It does not enable a model adapter, download software or activate a host.

The runtime input must already have qualified provenance and notices. Existing exact runtime evidence is checked before and after copying. The bundle contains Python and required dependencies, not a Codex CLI. Launcher paths are relative to their own bundle directory. Windows uses orche.ps1; POSIX uses orche. Neither searches system Python. Windows reports E_BUNDLE_RUNTIME_MISSING for an absent Python payload.

Use the builder with explicit --source, --runtime, --runtime-evidence, --output, --target and --release. Existing outputs are not replaced. The source and destination ancestry must remain quiescent and controlled during assembly; this is not a hostile-writer sandbox or publisher authentication.

Invoke the launcher with --permanent-runtime only when this is a retained location, or --retain-to an absolute new permanent directory. Registered hooks may depend on that runtime, so do not remove it while they reference it. All remaining flags pass to the existing interactive root installer, which selects Codex, Claude or both. SDK-only --clients and --list-clients are not added by this subset.

Both provider trees are copied in full. Existing canonical mirror parity and registered hook artifact presence are checked before and after assembly; these checks do not claim full Python import closure or native provider activation. Actual model-free receiving remains necessary.

The locks, notices and runtime-evidence research accompany the original qualified runtime; they are not proof of a new qualification or a general platform guarantee. No interpreter binary is tracked. Distribution must authenticate the complete release before executing it.

## Terms and Abbreviations
- SDK: software development kit.
- CLI: command-line interface.
- POSIX: portable operating-system interface.
