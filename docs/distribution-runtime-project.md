# Orche delivery and later native operations

The [current product plan](https://github.com/applicate2628/Orchestrarium/blob/debdf7b9cf8f0078b62dd5d40f45318655572677/docs/orchestrarium-2.0-plan.md#current-delivery-order-and-completed-work) starts from the
standalone tagged baseline. The selected independent Rust scanner release comes
before software development kit (SDK) delivery. SDK qualification can run in
parallel, and channel qualification has its own acceptance evidence.

- [Bundled Python and thin delivery channels](npm-distribution-project.md) owns
  one release payload for PowerShell, POSIX and optional npm distribution.
- [Native operations in Rust](https://github.com/applicate2628/Orchestrarium/pull/21)
  owns the selected scanner release and later qualified operation-by-operation
  migration.

The linked delivery document owns the requirements; do not duplicate installation
policy in channel wrappers. [PR18](https://github.com/applicate2628/Orchestrarium/pull/18) records the historical
SDK design; [PR19](https://github.com/applicate2628/Orchestrarium/pull/19) owns
current SDK implementation and qualification. The
[installer guide](../INSTALL.md) governs manual hook trust.

## Terms and Abbreviations

- npm: optional package distribution tooling.
- SDK / CLI / PR: software development kit / command-line interface / pull request.
