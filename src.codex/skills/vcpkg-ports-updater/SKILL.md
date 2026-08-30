---
name: vcpkg-ports-updater
description: "Use when vcpkg overlay ports need upstream source/version synchronization, patch refresh, intentional-shadow reconciliation, or stale-overlay removal."
---

# vcpkg Ports Updater

Act as a leaf overlay-maintenance specialist under the root `$lead`. Update only the admitted ports and return one upstream-sync package. Do not own roadmap priority, aggregate builds, general toolchain refactors, or publication.

Use this skill only where repository instructions define vcpkg overlay tiers and validation entry points. Use `vcpkg-builder` for an admitted runtime build after the update is accepted.

## Core principle

Each port's canonical project repository or official vendor release channel owns its source revision and version. A builtin vcpkg checkout is comparison evidence only: never copy its revision, source archive, or patch as the overlay's upstream authority.

## Required inputs

Before editing, require:

- an admitted overlay-maintenance objective whose scope is either an exact port
  set or named overlay roots/tiers whose current members are to be inventoried;
- repository orientation, overlay priority/ownership map, and status of any scope decision;
- external vcpkg-root mutation policy and any separately authorized refresh command;
- intended upstream policy (`HEAD`, release, or pinned revision), version scheme, retained local fixes, and validation matrix;
- protected roots, scratch/evidence boundary, cleanup rule, and next reviewer.

Missing or conflicting ownership is `BLOCKED:CONTRACT`. Do not resolve it by copying builtin material or creating a new overlay tier.

## Classify before editing

Classify every admitted port by current evidence:

- `CUSTOM_UPSTREAM`: no builtin peer; overlay owns the complete port.
- `INTENTIONAL_SHADOW`: deliberately wins over builtin and tracks its own upstream.
- `COMPATIBILITY_OVERLAY`: builtin-adjacent packaging with still-required local compatibility deltas.
- `PLATFORM_OR_TOOLCHAIN_OWNED`: behavior belongs in an existing triplet/toolchain/shared-helper seam, not another port copy.
- `AUXILIARY_OR_OUT_OF_SCOPE`: not authorized by the current catalog/scope decision.

Then classify each local delta as `RETAIN`, `ABSORBED`, `STALE`, or `UNKNOWN`. `UNKNOWN` stops mutation until its owner and falsifying probe are known.

## Full overlay sweep

A user-authorized sweep of named overlay roots is a valid read-only inventory
scope; discover the exact port set from those roots instead of demanding that
the user enumerate it. Keep inventory admission separate from update admission:
the sweep may classify every current port, but it does not authorize version
bumps, removals, or rebuilding every candidate.

For each port, first recover its existing source policy from the live port:
release/tag tracking, pinned branch HEAD, custom vendor archive, or compatibility
delegation to another port definition. Report one evidence state:

- `current`: the selected source satisfies its declared policy;
- `update-candidate`: official upstream advertises a different source allowed by
  that policy, with patch/delta validation still open;
- `unknown`: the available evidence cannot establish freshness or identity;
- `stale-overlay-candidate`: the overlay may have been absorbed or fallen out of
  admitted scope, but deletion still requires exact delta and ownership proof.

A pinned commit differing from an advertised branch tip is not by itself
"behind"; establish ancestry when that distinction matters, otherwise keep the
verdict at `update-candidate` or `unknown`. It is valid for a completed sweep to
find no safe automatic updates when local patches or retained deltas remain
unverified.

For a compatibility overlay that delegates implementation while owning its own
manifest, verify the manifest and delegated portfile form one source contract.
Compare the effective version/ref/hash inputs after subtracting only explicitly
retained manifest deltas. On an archive hash mismatch, first rule out a
manifest/portfile version split and verify the requested upstream identity;
never accept the observed hash merely because repeated downloads agree.

## Workflow

1. Read the repository contract, canonical catalog/scope records, target portfiles/manifests/patches, and overlay-resolution order. Use CodeGraph and vcpkg MCP where available; confirm index freshness after edits.
2. Resolve the external vcpkg checkout and probe its policy. Refresh or pull it only when that exact mutation is authorized; otherwise use read-only local/remote comparison.
3. Resolve each port's own official upstream. Select an immutable revision, obtain the archive digest, and preserve the port's established version scheme while proving the new manifest version sorts above the previous one.
4. Rebase the existing port onto that source. Reapply only `RETAIN` deltas at their owning seam; remove `ABSORBED`/`STALE` material and superseded files in the same change.
5. Validate manifest/feature/source shape, overlay precedence, sequential patch application, fail-open text anchors, and the smallest affected compiler/platform matrix. Runtime builds require their own admitted `vcpkg-builder` gate.
6. Return one sync package: port classifications, official-upstream identities, old/new immutable revisions and digests, delta dispositions, changed files, validation evidence, cleanup, and `PASS|REVISE|BLOCKED`.

## Non-negotiable invariants

- Never mutate an external vcpkg checkout merely to compare it.
- Never infer liveness or deletion from directory name, recency, builtin equality, or an unaccepted scope proposal.
- Apply patch stacks in declared order to one accumulating extracted tree; a standalone patch check is not an acceptance oracle.
- Re-verify every `vcpkg_replace_string`, patch context, and post-extract/project-include anchor against the selected source. A missing anchor is `REVISE`, not a silent no-op.
- Preserve feature contracts, platform guards, version ordering, and intentional shadows. Remove an overlay directory only when its current owner is proven unnecessary and no custom/shadow contract remains.
- Keep raw downloads, extracted trees, and logs in the repository's scratch/transient boundary. Clean only exact inactive task-owned artifacts after evidence is accepted.

## Gate

`PASS` requires official-upstream provenance, immutable revision plus digest, valid version ordering, explicit disposition of every prior local delta, current overlay-resolution evidence, required patch/anchor checks, affected-surface validation, protected-root compliance, and no stale live-tree residue.

Read `references/upstream-sync.md` for source-authority, patch-stack, anchor, version, and validation matrices.
