# Orche delivery and later native operations

The delivery sequence is SDK integration and bundled Python first, followed by
separately qualified native-operation migration:

- [Bundled Python and thin delivery channels](npm-distribution-project.md) owns
  one release payload for PowerShell, POSIX and optional npm distribution.
- [Native operations in Rust](https://github.com/applicate2628/Orchestrarium/pull/21)
  remains a later operation-by-operation replacement, not a delivery prerequisite.

The linked delivery document owns the requirements; do not duplicate installation
policy in channel wrappers. SDK design/status belongs to
[PR18](https://github.com/applicate2628/Orchestrarium/pull/18), implementation to
[PR19](https://github.com/applicate2628/Orchestrarium/pull/19), and the remaining
roadmap to [PR13](https://github.com/applicate2628/Orchestrarium/pull/13).
This index neither activates a runtime nor claims that those PRs are merged.
The earlier manual-trust documentation/test correction remains unchanged.

## Terms and Abbreviations

- npm: optional package distribution tooling.
- SDK / CLI / PR: software development kit / command-line interface / pull request.
