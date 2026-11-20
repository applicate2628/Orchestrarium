# Orche delivery and later native operations

First qualify and tag the standalone pre-SDK release; integrate optional SDK
execution next, then qualify and migrate native operations separately:

- [Bundled Python and thin delivery channels](npm-distribution-project.md) owns
  one release payload for PowerShell, POSIX and optional npm distribution.
- [Native operations in Rust](https://github.com/applicate2628/Orchestrarium/pull/21)
  remains a later operation-by-operation replacement, not a delivery prerequisite.

The linked delivery document owns the requirements; do not duplicate installation
policy in channel wrappers. [PR18](https://github.com/applicate2628/Orchestrarium/pull/18) records the historical
SDK design; [PR19](https://github.com/applicate2628/Orchestrarium/pull/19) owns
current SDK implementation and qualification. The product release roadmap is in
[PR13](https://github.com/applicate2628/Orchestrarium/pull/13).
This index neither activates a runtime nor claims that those PRs are merged.
The earlier manual-trust documentation/test correction remains unchanged.

## Terms and Abbreviations

- npm: optional package distribution tooling.
- SDK / CLI / PR: software development kit / command-line interface / pull request.
