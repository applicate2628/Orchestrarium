# Codex Pack Source

This directory contains the Codex-provider source tree inside the Orchestrarium monorepo.

It includes 17 manifest-driven native roles. Both Luna roles are unavailable in 1.x: `mechanical-scout` returns `E_LUNA_EXECUTION_CONTAINMENT_UNAVAILABLE` until host-enforced execution containment and attestation exist; `mechanical-worker` returns `E_LUNA_WRITE_CONTAINMENT_UNAVAILABLE` until host-enforced per-agent tool and filesystem containment is proven. `LunaExecutionContractV1` and `ScoutFactsV1` validation are dormant future re-admission prerequisites, not a current native attempt. Role TOMLs are create-only install payloads except for five hash-pinned stock role payload upgrades; customized payloads fail closed. Every current role is registered in `.codex/config.toml` from its validated name, description, and relative file. `scripts/resolve-agents-mode.py::resolve_role_dispatch` is the policy-only caller-neutral owner; no host result, external route, Terra, or Sol fallback enters policy.

Use it together with:

- [../docs/README.md](../docs/README.md) for the common branch-level docs surface
- [../shared/references/README.md](../shared/references/README.md) for the shared design core
- [../references-codex/README.md](../references-codex/README.md) for the Codex-side provider addendum

Source surface:

- `../shared/AGENTS.shared.md` + `AGENTS.codex.md` assemble the installed Codex `AGENTS.md`
- `agents/*.toml` are create-only native role payloads and `agents/orchestrarium-role-manifest.json` is source-only current-inventory and config-registration validation; five hash-pinned stock role payload upgrades are the only current-role exception, customized payloads fail closed, and no installed receipt or general historical adoption, update, reclaim, or delete authority exists in 1.x apart from those upgrades and the exact frozen `luna_mechanical` migration
- `skills/<role>/SKILL.md` and `skills/<role>/agents/openai.yaml` define the role catalog
- `skills/lead/` carries operating-model notes, handoff contracts, and validation/publication-safety scripts
- `skills/consultant/` and `skills/second-opinion/` carry the advisory and explicit consultant routing surfaces
- `skills/external-brigade/` carries the bounded parallel external-helper orchestration surface
- `skills/design-panel/` carries the design-panel technique — independent multi-lane design generation on one pinned problem, converged through one mandatory synthesis; the generation-side analog of `skills/review-loop/`

Architecture decision: the installed Codex `AGENTS.md` is intentionally the compact universal minimum, not the place for the full role catalog or long runtime manuals. Keep the universal entrypoint thin and put detailed role contracts in `skills/<role>/SKILL.md`, shared methodology in `../shared/references/`, and Codex-specific addenda in `../references-codex/`. The source `agents/*.toml` files are policy-resolved native role payloads created only when their targets are absent, except for five hash-pinned stock role payload upgrades; customized payloads fail closed. Manifest mappings are appended to valid config text without reserializing unrelated bytes; exact mappings no-op and collisions fail. An absent config receives `multi_agent_v2 = true` plus all mappings, and only the exact frozen `luna_mechanical` state may otherwise be migrated away. Codex and Claude compose the same complete canonical `lead` payload before either host publishes it. This mirrors the Claude-side pattern where `CLAUDE.md` stays short and `.claude/agents/*.md` carries the detailed role files.

Keep `SKILL.md` frontmatter `description:` values compact because Codex loads them as startup metadata before any one skill body is selected. Put detailed trigger logic, scope, and gate rules in the body of the skill instead; `skills/lead/scripts/validate-skill-pack.*` enforces the Codex metadata budget.

This subtree is the Codex runtime source owned by the monorepo. Shared governance and shared references stay one level up; only the provider-specific runtime source lives here.

## Terms and Abbreviations

- `AGENTS.md`: Codex governance entrypoint assembled from shared and Codex-specific source files.
- `Codex`: OpenAI Codex runtime and production provider line.
- `frontmatter`: YAML metadata block at the top of a skill or agent file.
- `runtime`: installed provider-facing files used by Codex outside the source tree.
- `SKILL.md`: Codex skill entrypoint containing role instructions, scope, artifact, and gate rules.
- `startup metadata`: compact metadata Codex reads before loading a specific skill body.
