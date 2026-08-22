# Codex Pack Source

This directory contains the Codex-provider source tree inside the Orchestrarium monorepo.

It includes two standalone native Luna mechanical roles: read-only `mechanical-scout` and bounded-write `mechanical-worker`. They are create-only install payloads and admit only the shared fast-high mechanical corridor. `scripts/resolve-agents-mode.py::resolve_role_dispatch` is the policy-only caller-neutral owner; disabled native roles return typed unavailability, admitted calls require the exact native attempt, and no host result, external route, Terra, or Sol fallback enters policy.

Use it together with:

- [../docs/README.md](../docs/README.md) for the common branch-level docs surface
- [../shared/references/README.md](../shared/references/README.md) for the shared design core
- [../references-codex/README.md](../references-codex/README.md) for the Codex-side provider addendum

Source surface:

- `../shared/AGENTS.shared.md` + `AGENTS.codex.md` assemble the installed Codex `AGENTS.md`
- `agents/*.toml` are create-only native role payloads and `agents/orchestrarium-role-manifest.json` is source-only current-inventory validation; no installed receipt, historical digest, adoption, update, reclaim, or delete authority exists in 1.x
- `skills/<role>/SKILL.md` and `skills/<role>/agents/openai.yaml` define the role catalog
- `skills/lead/` carries operating-model notes, handoff contracts, and validation/publication-safety scripts
- `skills/consultant/` and `skills/second-opinion/` carry the advisory and explicit consultant routing surfaces
- `skills/external-brigade/` carries the bounded parallel external-helper orchestration surface
- `skills/design-panel/` carries the design-panel technique — independent multi-lane design generation on one pinned problem, converged through one mandatory synthesis; the generation-side analog of `skills/review-loop/`

Architecture decision: the installed Codex `AGENTS.md` is intentionally the compact universal minimum, not the place for the full role catalog or long runtime manuals. Keep the universal entrypoint thin and put detailed role contracts in `skills/<role>/SKILL.md`, shared methodology in `../shared/references/`, and Codex-specific addenda in `../references-codex/`. The source `agents/*.toml` files are policy-resolved native role payloads created only when their targets are absent; any existing operator role collision fails closed. An absent config receives `multi_agent_v2 = true`; an existing ordinary config is preserved byte-exact and accepted only when TOML is valid and the feature is absent or Boolean. Codex and Claude compose the same complete canonical `lead` payload before either host publishes it. This mirrors the Claude-side pattern where `CLAUDE.md` stays short and `.claude/agents/*.md` carries the detailed role files.

Keep `SKILL.md` frontmatter `description:` values compact because Codex loads them as startup metadata before any one skill body is selected. Put detailed trigger logic, scope, and gate rules in the body of the skill instead; `skills/lead/scripts/validate-skill-pack.*` enforces the Codex metadata budget.

This subtree is the Codex runtime source owned by the monorepo. Shared governance and shared references stay one level up; only the provider-specific runtime source lives here.

## Terms and Abbreviations

- `AGENTS.md`: Codex governance entrypoint assembled from shared and Codex-specific source files.
- `Codex`: OpenAI Codex runtime and production provider line.
- `frontmatter`: YAML metadata block at the top of a skill or agent file.
- `runtime`: installed provider-facing files used by Codex outside the source tree.
- `SKILL.md`: Codex skill entrypoint containing role instructions, scope, artifact, and gate rules.
- `startup metadata`: compact metadata Codex reads before loading a specific skill body.
