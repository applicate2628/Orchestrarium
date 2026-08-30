# vcpkg Overlay Upstream-Sync Reference

## Source authority

| Surface | Permitted role |
|---|---|
| Port's canonical project repository or official vendor release channel | Source/version/ref authority |
| Immutable release tag or commit/checkin from that upstream | Selected revision |
| Archive fetched from that upstream with recorded digest | Build input |
| Builtin vcpkg checkout and `microsoft/vcpkg` history | Comparison, packaging ideas, absorbed-fix evidence only |
| Mirrors, forks, copied builtin ports | Never source authority unless the repository explicitly records an exception |

Probe the external checkout before use. A read-only comparison may fetch remote metadata without changing its worktree when the repository permits it. Pull/bootstrap/update are separate mutations and require explicit admission.

## Port and delta disposition

| Port class | Update rule |
|---|---|
| `CUSTOM_UPSTREAM` | Preserve complete overlay ownership; absence from builtin is expected. |
| `INTENTIONAL_SHADOW` | Preserve priority and documented divergence; builtin equality alone never deletes it. |
| `COMPATIBILITY_OVERLAY` | Rebase packaging onto the selected project upstream and retain only proved compatibility deltas. |
| `PLATFORM_OR_TOOLCHAIN_OWNED` | Extend the existing owner seam and remove duplicated port logic only after equivalent runtime proof. |
| `AUXILIARY_OR_OUT_OF_SCOPE` | Do not update/remove until an accepted scope record admits it. |

Every pre-existing local patch, replacement, option, feature, version field, and platform guard receives exactly one disposition: `RETAIN`, `ABSORBED`, `STALE`, or `UNKNOWN`. Record the owner and falsifying probe for `RETAIN`; `UNKNOWN` is non-mutating.

## Version and source update

- Preserve the port's established version field and scheme unless an accepted migration says otherwise.
- Pin an immutable upstream identity; moving branches and symbolic `latest` paths are comparison inputs, not build pins.
- Record the selected archive digest from the actual source channel.
- Prove the new manifest version is strictly ordered above the previous overlay version under vcpkg semantics.
- Keep manifest features/default-features/supports/license contracts unless the upstream change and admitted scope require a named revision.

## Patch and anchor validation

- Apply `PATCHES` sequentially in manifest order to one clean extracted source tree. Later patches may depend on earlier context.
- Verify each retained patch changes the intended source/contract and no rejected hunk or fuzz hides drift.
- Verify every text replacement anchor occurs at the expected cardinality before replacement and the intended result afterward.
- For configure-time/project-include fixes, prove the include reaches the actual configure invocation and the target anchor exists in the selected source.
- Remove a fix only when upstream absorption is present in the selected source and the affected receiving-side gate still passes.

## Validation by blast radius

| Change owner | Minimum evidence |
|---|---|
| Manifest/source-only, no local compatibility delta | Parse/schema, source digest, version ordering, overlay resolution, smallest targeted build when admitted |
| One compiler/platform-specific delta | Static contract plus targeted affected lane and installed/receiver oracle |
| Common portfile/helper or feature contract | Every affected compiler/platform family named by repository ownership; do not extrapolate one lane |
| Patch/anchor refresh | Ordered clean-tree application plus actual configure/build evidence that the fix executed |
| Overlay removal or owner move | Resolution proves the intended replacement wins; prior consumers and affected lanes remain valid |

An exit-zero already-installed/no-op result is not proof of the new source. Runtime freshness and cleanup follow `vcpkg-builder`.

## Stop conditions

Return `REVISE` without widening scope when official-upstream identity is ambiguous, digest/version ordering is unproved, a patch/anchor drifts, a local delta is `UNKNOWN`, overlay resolution chooses the wrong owner, or an affected runtime oracle fails. Return `BLOCKED` only for an external prerequisite or unresolved authority conflict.
