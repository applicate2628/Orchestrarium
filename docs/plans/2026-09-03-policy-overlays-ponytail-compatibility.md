# Orchestrarium 1.x policy overlays and Ponytail compatibility plan

## Table of contents

- [Goal](#goal)
- [Decision](#decision)
- [Current architecture and discovered risk](#current-architecture-and-discovered-risk)
- [Architecture](#architecture)
- [Implementation](#implementation)
- [Verification](#verification)
- [Out of scope](#out-of-scope)
- [Terms and Abbreviations](#terms-and-abbreviations)

## Goal

Add a backward-compatible Orchestrarium 1.x seam for optional behavior policies, prove Orchestrarium-owned installer coexistence with Ponytail-shaped third-party state, and provide Orchestrarium-native lean implementation and complexity review without embedding Ponytail.

Ponytail upstream: `DietrichGebert/ponytail`. Treat it as an independent MIT-licensed package owned and updated by its own host/plugin installation path.

## Decision

Use one canonical `policy-overlay` skill projected by the existing Codex-to-Claude skill pipeline. Keep user selection explicit and machine state non-authorizing. Project configuration may restrict a user selection but must never enable an overlay by itself. Keep every overlay non-authorizing and resolve it for one exact provider, lane, and target.

Ponytail remains external and host-managed. Compatibility is enforced by ownership-preservation tests, not by copying its JavaScript runtime, lifecycle hooks, or mode tracker into Orchestrarium.

## Current architecture and discovered risk

The existing Orchestrarium hook installer already merges Orchestrarium-owned hooks by marker and preserves unknown third-party entries. The canonical skill projection walks Orchestrarium source skills and does not deliberately reclaim an unrelated target-only `ponytail` skill directory. These are the correct reuse points; do not add a Ponytail-specific manager or a second settings merger.

A focused compatibility regression must verify the complete production install and reinstall paths, not only the low-level hook merger. In particular, inspect `_merge_claude_docs` and the Codex document merge for repeated installation over pre-existing third-party instructions. A current implementation that replaces a previously generated canonical prefix may accidentally discard an unknown Ponytail/user suffix on the second install. Fix that at the shared ownership boundary if the regression reproduces it.

## Architecture

The Version 1 seam consists of:

- one strict catalog;
- one bounded resolver and command-line interface;
- two built-in Orchestrarium policy bodies;
- one skill contract describing composition and propagation;
- one operator/architecture guide;
- focused resolver, prompt-projection, installer, and Ponytail-shaped compatibility regression tests.

Required fixed precedence:

1. hard governance and safety;
2. explicit user requirements;
3. role contract;
4. project policy and restrictions;
5. optional non-authorizing policy overlays;
6. task body.

An overlay must never weaken security, trust-boundary validation, data-loss protection, accessibility, mandatory verification, role authorization, publication gates, or explicit user requirements.

Each resolved projection is bound to one exact:

- provider;
- routing lane;
- target kind (`main-agent`, `internal-subagent`, `external-worker`, `external-reviewer`, or `consultant`);
- ordered overlay set.

Do not permit a projection resolved for one context to be reused for another context.

## Implementation

1. Add the canonical common skill under `src.codex/skills/policy-overlay/`; let the existing installer/projector expose it to Claude rather than creating a parallel provider-specific implementation.
2. Add a machine-readable Version 1 overlay catalog and a strict standard-library-only resolver.
3. Keep Orchestrarium behavior unchanged when no overlay is selected.
4. Add two built-in, independently authored Orchestrarium policies:
   - `lean-implementation`: question new code, reuse the repository, standard library, native platform, and installed dependencies before writing the smallest correct local change;
   - `complexity-review`: a non-authorizing review perspective limited to unnecessary dependencies, hand-rolled platform/standard-library behavior, one-implementation abstractions, speculative configuration, delegating wrappers, dead flexibility, and avoidable boilerplate.
5. Do not copy Ponytail text verbatim. Record upstream provenance and the fact that only ideas and compatibility behavior were studied.
6. Define explicit propagation per provider/lane/target. Lean implementation may reach implementation lanes and workers; complexity review may reach review lanes and reviewers. Neither automatically enters security, formal verification, research, legal/compliance, or publication review.
7. For external workers/reviewers, provide a deterministic framed instruction projection placed after governance and role authority but before the task body. The frame must identify provider, lane, and target and remain non-authorizing.
8. Do not auto-install Ponytail, read its private mode files, synchronize `lite/full/ultra/off`, require Node.js, vendor its hooks, or expose arbitrary executable overlays.
9. Preserve separately installed Ponytail hooks on at least `SessionStart`, `SubagentStart`, and `UserPromptSubmit`; preserve unrelated settings, skills, and instruction text across install, reinstall, update, and Orchestrarium-owned removal.
10. Reuse existing hook and installer ownership primitives. Orchestrarium may replace or remove only proven Orchestrarium-owned stock artifacts.
11. Document the Version 1 limit: declarative built-in instruction overlays and explicit propagation only. Remote registries, executable plugin runtimes, dependency solving, marketplaces, sandboxes, and hot loading belong to a separately reviewed Version 2 design.
12. Update root release notes with the practical effect and preserved behavior.

## Verification

Use test-driven development. Add regressions before the implementation and retain a red/green record in the PR summary.

Minimum focused coverage:

- no selection is an exact no-op;
- unknown, duplicate, malformed, conflicting, linked, escaping, oversized, or mixed-context overlay inputs fail closed;
- project restrictions cannot enable an overlay and cannot silently override an explicit user choice;
- exact provider/lane/target filtering and deterministic ordering;
- Kimi remains restricted to the already admitted non-authorizing review surface;
- rendered overlays cannot claim authorization or suppress higher-precedence governance;
- external prompt composition places the frame at the documented boundary and never duplicates it;
- Codex and Claude hook merge preserves Ponytail-shaped `SessionStart`, `SubagentStart`, and `UserPromptSubmit` entries;
- both install orders (`Orche -> Ponytail` and `Ponytail -> Orche`), repeated Orche install, provider update, and Orche-owned uninstall preserve the other package;
- pre-existing `ponytail` skill directories and unrelated user settings remain byte-stable where Orchestrarium does not own them;
- Codex `AGENTS.md` and Claude `CLAUDE.md`/`AGENTS.md` preserve third-party instruction text after first install and reinstall;
- Orchestrarium has no runtime import or package dependency on Ponytail or Node.js.

Run the affected unit and installer suites, complete Codex and Claude provider-pack validators, agents-mode/document synchronization checks if touched, Python compilation, `git diff --check`, publication-safety review, and the repository publication gate. Do not create or use GitHub Actions workflows.

Perform three explicit review passes:

1. correctness and regression review;
2. installer ownership and third-party coexistence review;
3. complexity review asking whether the same behavior can be achieved with fewer new owners, dependencies, files, and abstractions without weakening tests or safety.

## Out of scope

The task does not add a marketplace, remote download, plugin sandbox, dependency solver, executable overlay lifecycle, automatic Ponytail installation, automatic Ponytail mode synchronization, or benchmark platform.

## Terms and Abbreviations

- **API — Application Programming Interface:** the resolver contract exposed to Orchestrarium roles and adapters.
- **CLI — Command-Line Interface:** the terminal form of the resolver.
- **Overlay:** an optional instruction layer that does not authorize work.
- **Ponytail:** the independent upstream policy package used as the first compatibility case.
- **TDD — Test-Driven Development:** development through a failing regression followed by the implementation and a passing regression.
- **V1 — Version 1:** the bounded implementation targeted at Orchestrarium 1.x.
