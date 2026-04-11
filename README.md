# Orchestrarium

A cross-provider agent orchestration monorepo that keeps the Codex, Claude Code, and Gemini provider trees aligned on one shared governance and reference core:

- `src.codex/` — the Codex provider pack source
- `src.claude/` — the Claude Code provider pack source
- `src.gemini/` — the Gemini provider-pack source tree with `GEMINI.md` as its runtime entrypoint, a pack-local `AGENTS.shared.md` import module, the stable skill catalog, and the preview specialist-agent surface

The provider lines share one governance model and role vocabulary, while each keeps the runtime structure expected by its own provider. In this branch, the root router installers now cover Codex, Claude Code, and Gemini CLI while still keeping each provider line honest through its own source-surface checks.

## Repository layout

```text
shared/             Shared cross-provider governance and canonical reference cores
docs/               Common branch-level docs index and operator/runtime references
src.codex/          Codex provider-pack source
src.claude/         Claude Code provider-pack source
src.gemini/         Gemini provider-pack source tree with `GEMINI.md`,
                    `AGENTS.shared.md`, stable `skills/`, and preview `agents/`
references-codex/   Codex-specific addenda and compatibility pointers
references-claude/  Claude Code-specific addenda and compatibility pointers
references-gemini/  Gemini-specific addenda and compatibility pointers
RELEASE_NOTES.md    Canonical tracked release log
install.sh          Entry-point installer (asks which pack to install)
install.ps1         Entry-point installer (asks which pack to install)
scripts/            Pack-specific installers plus the repo-local publication gate
AGENTS.md           Dev overlay for Codex pack maintenance
CLAUDE.md           Dev overlay for Claude Code pack maintenance
```

## Provider Packs

| Pack | Source | Runtime entrypoint in source | Packaging in this branch | Validation |
| --- | --- | --- | --- | --- |
| Codex | `src.codex/` | assembled installed `AGENTS.md` from `shared/AGENTS.shared.md` + `src.codex/AGENTS.codex.md` | root router installers plus `scripts/install-codex.*` | `validate-skill-pack.sh` and `validate-skill-pack.ps1` |
| Claude Code | `src.claude/` | `src.claude/CLAUDE.md` | root router installers plus `scripts/install-claude.*` | `validate-skill-pack.sh` and `validate-skill-pack.ps1` |
| Gemini CLI | `src.gemini/` | `src.gemini/GEMINI.md` importing `src.gemini/AGENTS.shared.md` | root router installers plus `scripts/install-gemini.*` | `validate-pack.sh` and `validate-pack.ps1` |

Shared design references now live in `shared/references/`. Provider-local `references-codex/`, `references-claude/`, and `references-gemini/` keep provider-specific addenda plus compatibility pointers where older paths still need to resolve. The clearest example is `subagent-operating-model`: the canonical blueprint core now lives in `shared/references/subagent-operating-model.md`, while each provider-local tree keeps only its runtime and repository concretization addendum. Shared governance is maintained across provider lines; the repository-level overlays in `AGENTS.md` and `CLAUDE.md` exist only for maintaining this monorepo.

Cross-provider execution is available through two routing adapters:

- `$external-worker` is the external execution adapter for eligible worker-side roles.
- `$external-reviewer` is the external execution adapter for eligible review and QA roles.
- `$consultant` remains advisory-only and is not reused for implementation or review gates.

## Installation

Use the root router installers for the common path:

```bash
bash install.sh --global
```

```powershell
.\install.ps1 -Global
```

Each router asks what to install:

```text
What to install?
  1) Codex pack
  2) Claude Code
  3) Gemini CLI
  4) All three
```

Then it forwards the same arguments to the provider-specific installer in `scripts/`. Use `scripts/install-codex.*`, `scripts/install-claude.*`, or `scripts/install-gemini.*` directly when you want deterministic single-provider automation.

Important: operator preferences now live only in pack-local `agents-mode` files.

- Codex reads `.agents/.agents-mode`.
- Claude Code reads `.claude/.agents-mode`.
- `consultantMode` controls `$consultant`.
- `delegationMode: manual` keeps explicit-permission behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation a standing instruction whenever a matching specialist and viable tool path exist.
- `mcpMode: auto` lets the agent decide when MCP is appropriate; `force` means the config itself is an explicit instruction to use relevant available MCP tools instead of treating MCP usage as optional.
- `preferExternalWorker` and `preferExternalReviewer` let routing prefer `$external-worker` on `implement` and `$external-reviewer` on `review` and `QA`.
- `externalProvider` now uses one shared provider universe across all three lines: `auto | codex | claude | gemini`.
- `externalProvider: auto` is lane-driven, not host-pack-driven. It resolves through the active `externalPriorityProfile` and must not silently self-bounce into the same provider line.
- `externalPriorityProfile` selects the active named provider-order profile, `externalPriorityProfiles` stores the switchable per-lane provider orders, and `externalOpinionCounts` raises specific lanes above the default single-opinion behavior when one external opinion is not enough. Those counts are lane-local distinct-opinion requirements, not a cap on how many parallel external helper instances may run overall; bounded same-provider helper fan-out now lives under the dedicated brigade surfaces.
- Explicit self-provider selection is allowed only as an override for isolation, transport, profile, or an intentionally independent rerun.
- `externalClaudeSecretMode: auto | force` and `externalClaudeApiMode: disabled | auto | force` stay under the `claude` provider. `claude-api` is a secondary Claude transport, not a fourth provider.
- Codex may additionally use `externalClaudeProfile` to select the Claude CLI execution profile: `sonnet-high` or `opus-max`.
- Provider-specific workdir keys stay separate and default to `neutral`: `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, `externalGeminiWorkdirMode`.
- For first-time Codex project setup, run `$init-project` to write `## Project policies` in the root `AGENTS.md` and create `.agents/.agents-mode`.
- For first-time Claude Code project setup, run `/agents-init-project` to write `## Project policies` in `.claude/CLAUDE.md` and initialize `.claude/.agents-mode`.
- For Gemini project setup, use Gemini's built-in `/init` to generate or tailor `GEMINI.md`. Official Gemini runtime config and MCP wiring stay in `.gemini/settings.json` or extension manifests, while Orchestrarium-specific shared governance is brought in through `GEMINI.md` importing project-root `AGENTS.md`, the stable role catalog lives in `.gemini/skills/`, the preview specialist-team layer lives in `.gemini/agents/`, and shared routing semantics may additionally live in `.gemini/.agents-mode`, which the Gemini `init-project` helper bootstraps separately after `/init`. In that preview layer, every top-level `.gemini/agents/*.md` file must be a real agent definition with YAML frontmatter.
- Explicit user role requests still override the toggle state in either direction.
- Full value-by-value operator semantics live in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md), including task continuity and continue-by-default execution expectations for initialized projects.

Shipped named profiles:

| Profile | Lane | Priority |
|---|---|---|
| `balanced` | `advisory.repo-understanding` | `claude > gemini > codex` |
|  | `advisory.design-adr` | `claude > codex > gemini` |
|  | `review.pre-pr` | `claude > codex > gemini` |
|  | `worker.default-implementation` | `codex > claude > gemini` |
|  | `worker.long-autonomous` | `claude > codex > gemini` |
|  | `worker.visual-icon-decorative` | `gemini > claude > codex` |
|  | `review.visual` | `gemini > claude > codex` |
| `gemini-crosscheck` | `advisory.repo-understanding` | `claude > gemini > codex` |
|  | `advisory.design-adr` | `claude > gemini > codex` |
|  | `review.pre-pr` | `claude > gemini > codex` |
|  | `worker.default-implementation` | `codex > claude > gemini` |
|  | `worker.long-autonomous` | `claude > gemini > codex` |
|  | `worker.visual-icon-decorative` | `gemini > claude > codex` |
|  | `review.visual` | `gemini > claude > codex` |

The default closeout path follows the active lane policy's external consultant-check count. `externalOpinionCounts` may raise advisory or review lanes above `1` when the active policy wants multiple independent external opinions before advancing, but it does not prevent the lead from launching multiple same-provider external helpers in parallel on different disjoint brigade items.

See [INSTALL.md](INSTALL.md) for quick install, pack-specific install details, dual-platform setup, and post-install customization.

## References and maintenance

- `shared/references/` contains the shared cross-provider design core that current and future provider packs can reuse.
- `docs/README.md` is the common branch-level docs entrypoint for operator semantics and runtime-layout references.
- [`docs/provider-runtime-layouts.md`](docs/provider-runtime-layouts.md) records the exact installed runtime layout for Codex, Claude Code, and Gemini, with `global` and `local` scopes split explicitly so install/runtime paths are not confused with repo source trees.
- `references-codex/` contains Codex-specific addenda plus compatibility pointers for older reference paths.
- `references-claude/` contains Claude-specific addenda plus compatibility pointers for older reference paths.
- `references-gemini/` contains Gemini-specific addenda plus compatibility pointers for older reference paths.
- `subagent-operating-model` is no longer duplicated per provider pack: use the shared core for the canonical blueprint and the provider-local file only for runtime and repository concretization.
- `AGENTS.md` is the root development overlay for Codex provider-pack maintenance.
- `CLAUDE.md` is the root development overlay for Claude Code provider-pack maintenance.

Before publishing maintenance changes, validate the active provider surfaces:

```bash
bash src.codex/skills/lead/scripts/validate-skill-pack.sh
bash src.claude/agents/scripts/validate-skill-pack.sh
bash src.gemini/scripts/validate-pack.sh
```

```powershell
.\src.codex\skills\lead\scripts\validate-skill-pack.ps1
.\src.claude\agents\scripts\validate-skill-pack.ps1
.\src.gemini\scripts\validate-pack.ps1
```

For release-relevant tracked changes, update `RELEASE_NOTES.md` in the same change before publication and explain the practical effect of the change, not just its title. Keep release notes in reverse-chronological `## YYYY-MM-DD` sections instead of one long-lived `## Unreleased` bucket, and run the repo-local gate before publication:

```bash
bash scripts/check-publication-gate.sh
```

```powershell
.\scripts\check-publication-gate.ps1
```

## License

This repository is licensed under the Apache License 2.0. See [LICENSE](LICENSE).
