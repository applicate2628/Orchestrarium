# Orchestrarium

A cross-provider agent orchestration monorepo that keeps the production Codex and Claude Code lines aligned on one shared governance and reference core, while also carrying explicit example integrations for Gemini and Qwen:

- `src.codex/` — the production Codex provider-pack source
- `src.claude/` — the production Claude Code provider-pack source
- `src.gemini/` — the Gemini example-integration source tree around `GEMINI.md`; repository status: `WEAK MODEL / NOT RECOMMENDED`
- `src.qwen/` — the Qwen native example-integration source tree around `QWEN.md`; repository status: `WEAK MODEL / NOT RECOMMENDED`

The provider lines share one governance model and role vocabulary, while each keeps the runtime structure expected by its own provider. The root router install surface is production-first: Codex plus Claude are the shipped production path, while Gemini and Qwen are explicit example integrations. In the current checkout, matching root `scripts/install-qwen.*` entrypoints exist, so the router exposes both example slots directly.

Warning: Orchestrarium is optimized for maximum execution effectiveness and low orchestration drag rather than for minimum token spend. On large tasks, multi-opinion review lanes, or aggressive external fan-out, usage can rise quickly and consume a substantial token budget in a short time.

## Repository layout

```text
shared/             Shared cross-provider governance and canonical reference cores
docs/               Common branch-level docs index and operator/runtime references
src.codex/          Codex provider-pack source
src.claude/         Claude Code provider-pack source
src.gemini/         Gemini example-provider source tree with `GEMINI.md`,
                    `AGENTS.shared.md`, stable `skills/`, and preview `agents/`
src.qwen/           Qwen example-pack source tree with `QWEN.md`,
                    `AGENTS.shared.md`, stable `skills/`, and preview `agents/`
references-codex/   Codex-specific addenda and compatibility pointers
references-claude/  Claude Code-specific addenda and compatibility pointers
references-gemini/  Gemini-specific addenda and compatibility pointers
references-qwen/    Qwen-specific addenda and compatibility pointers
RELEASE_NOTES.md    Canonical tracked release log
install.sh          Entry-point installer (asks which pack to install)
install.ps1         Entry-point installer (asks which pack to install)
scripts/            Pack-specific installers plus the repo-local publication gate
AGENTS.md           Dev overlay for Codex pack maintenance
CLAUDE.md           Dev overlay for Claude Code pack maintenance
```

## Provider Packs

| Pack | Status in this monorepo | Source | Runtime entrypoint in source | Packaging in this branch | Validation |
| --- | --- | --- | --- | --- | --- |
| Codex | Production | `src.codex/` | assembled installed `AGENTS.md` from `shared/AGENTS.shared.md` + `src.codex/AGENTS.codex.md` | root router installers plus `scripts/install-codex.*` | `validate-skill-pack.sh` and `validate-skill-pack.ps1` |
| Claude Code | Production | `src.claude/` | `src.claude/CLAUDE.md` | root router installers plus `scripts/install-claude.*` | `validate-skill-pack.sh` and `validate-skill-pack.ps1` |
| Gemini CLI | Explicit example integration (`WEAK MODEL / NOT RECOMMENDED`) | `src.gemini/` | `src.gemini/GEMINI.md` importing `src.gemini/AGENTS.shared.md` | root router installers plus `scripts/install-gemini.*` | `validate-pack.sh` and `validate-pack.ps1` |
| Qwen | Native explicit example integration (`WEAK MODEL / NOT RECOMMENDED`) | `src.qwen/` | `src.qwen/QWEN.md` importing `src.qwen/AGENTS.shared.md` | root router installers plus `scripts/install-qwen.*` | `validate-pack.sh` and `validate-pack.ps1` |

Shared design references now live in `shared/references/`. Provider-local `references-codex/`, `references-claude/`, `references-gemini/`, and `references-qwen/` keep provider-specific addenda plus compatibility pointers where older paths still need to resolve. The clearest example is `subagent-operating-model`: the canonical blueprint core now lives in `shared/references/subagent-operating-model.md`, while each provider-local tree keeps only its runtime and repository concretization addendum. Shared governance is maintained across provider lines; the repository-level overlays in `AGENTS.md` and `CLAUDE.md` exist only for maintaining this monorepo.

Maintainer note: this repository is the installer/source monorepo, not automatically a repo-local Codex install target. When working inside `Orchestrarium/`, it is valid to rely on the global Codex install under `~/.codex/`. A missing local `.agents/` tree in this monorepo does not by itself mean the Codex runtime is misconfigured; create `.agents/` here only by running the installers intentionally.

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
Production installs:
  1) Codex pack
  2) Claude Code
  3) Codex + Claude (production pair)
Example integrations:
  4) Gemini CLI (WEAK MODEL / NOT RECOMMENDED)
  5) Qwen (WEAK MODEL / NOT RECOMMENDED)
  6) All available root installs
```

Then it forwards the same arguments to the provider-specific installer in `scripts/`. Use `scripts/install-codex.*`, `scripts/install-claude.*`, `scripts/install-gemini.*`, or `scripts/install-qwen.*` directly when you want deterministic automation on one line. If a future checkout lacks the root `scripts/install-qwen.*` entrypoints, the router hides the dedicated Qwen slot and you should fall back to the Qwen source tree and provider-local docs directly.

Important: operator preferences now live only in pack-local `agents-mode` files.

- Codex reads `.agents/.agents-mode.yaml`.
- Claude Code reads `.claude/.agents-mode.yaml`.
- Gemini reads `.gemini/.agents-mode.yaml`.
- Legacy extensionless `.agents-mode` files remain compatibility input only. Decision-driving reads should resolve in this order: provider-local `.agents-mode.yaml`, local legacy `.agents-mode`, matching global `~/.<provider>/.agents-mode.yaml`, then matching global legacy `.agents-mode`. Normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope without recreating any legacy path or synthesizing a project-local override on read alone.
- Reinstall is expected to do the same maintenance work for installed overlays: if the shipped schema or defaults changed, the installer must rewrite an existing `.agents-mode.yaml` to the current canonical form instead of preserving stale pack-owned structure verbatim.
- `consultantMode` controls `$consultant`.
- `delegationMode: manual` keeps explicit-permission behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation a standing instruction whenever a matching specialist and viable tool path exist.
- `parallelMode: manual` keeps parallel fan-out explicit-by-request, `auto` leaves safe parallelism enabled by routing judgment for any independent internal or external lanes, and `force` makes safe parallel launch a standing instruction whenever scopes are independent and the merge cost is justified.
- `mcpMode: auto` lets the agent decide when MCP is appropriate; `force` means the config itself is an explicit instruction to use relevant available MCP tools instead of treating MCP usage as optional.
- `preferExternalWorker` and `preferExternalReviewer` let routing prefer `$external-worker` on `implement` and `$external-reviewer` on `review` and `QA`.
- Production `externalProvider` routing now uses `auto | codex | claude`. `externalProvider: auto` is lane-driven, not host-pack-driven, and the shipped production profiles stay on the Codex/Claude pair only.
- Gemini and Qwen remain explicit example-only integrations in this repository. They are `WEAK MODEL / NOT RECOMMENDED`, do not participate in the shipped production `auto` profiles, and should be treated as manual example or compatibility paths rather than production defaults.
- `externalPriorityProfile` selects the active named provider-order profile, `externalPriorityProfiles` stores the switchable per-lane provider orders, and `externalOpinionCounts` raises specific lanes above the default single-opinion behavior when one external opinion is not enough. Those counts are lane-local distinct-opinion requirements, not a cap on how many parallel external helper instances may run overall; `parallelMode` remains the general fan-out rule for any helper lane, while bounded same-provider external helper fan-out lives under the dedicated brigade surfaces.
- `externalModelMode: runtime-default | pinned-top-pro` remains the shared production model policy for the Codex/Claude pair. `runtime-default` leaves the resolved provider on its runtime default model/profile; `pinned-top-pro` starts on the strongest documented provider-native model/profile and allows one named same-provider fallback on limit-style failures.
- Explicit self-provider selection is allowed only as an override for isolation, transport, profile, or an intentionally independent rerun.
- `externalClaudeApiMode: disabled | auto | force` controls the advisory/review-only `claude-secret` supplemental candidate. The named Claude API path is the repo-local secret-backed wrapper that runs plain `claude` with `ANTHROPIC_*` from `SECRET.md`; it is weaker than primary Claude, appears only after primary `claude`/`codex` in advisory and review profile orders, and is not a scalar provider or an implementation/editing fallback.
- External provider CLI launches use file-based prompts by default: write substantive task prompts to temporary prompt files and feed them through stdin or a provider-supported file-input mechanism instead of putting the full prompt in argv.
- Codex may additionally use `externalClaudeProfile` to select or override the Claude CLI execution profile: `sonnet-high` or `opus-max`. New Codex installs seed `opus-max` by default unless a preset or explicit override chooses otherwise.
- Codex install also seeds `.codex/agents/default.toml`, `worker.toml`, and `explorer.toml` so the built-in Codex subagents run as `gpt-5.4` with `xhigh` by default unless the user has already customized those files.
- Provider-specific workdir keys stay separate and default to `neutral`: `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`.
- For first-time Codex project setup, run `$init-project` to write `## Project policies` in the root `AGENTS.md` and review or update the installed default `.agents/.agents-mode.yaml`. If local Codex overlay files are missing but `~/.codex/.agents-mode.yaml` exists, ordinary reads should use that global overlay honestly until you choose to create a project-local override.
- When the current working directory is this installer monorepo itself, a missing local `.agents/.agents-mode.yaml` should fall back to the global Codex install by default. Create a repo-local install only when you explicitly want project-local runtime state; the installer source tree and the installed runtime are different surfaces.
- For first-time Claude Code project setup, run `/agents-init-project` to write `## Project policies` in `.claude/CLAUDE.md` and review or update the installed default `.claude/.agents-mode.yaml`. If local Claude overlay files are missing but `~/.claude/.agents-mode.yaml` exists, ordinary reads should use that global overlay honestly until you choose to create a project-local override.
- Gemini remains an explicit example integration. Use Gemini's built-in `/init` to generate or tailor `GEMINI.md`, keep official runtime config and MCP wiring in `.gemini/settings.json` or extension manifests, and treat the Orchestrarium overlay `.gemini/.agents-mode.yaml` as example-path routing state rather than part of the shipped production `auto` contract. If local Gemini overlay files are missing but `~/.gemini/.agents-mode.yaml` exists, ordinary reads should use that global overlay honestly until you choose to create a project-local override.
- Qwen remains a native explicit example integration. Use Qwen's built-in `/init` to generate or tailor `QWEN.md`, keep official runtime config and MCP wiring in `.qwen/settings.json` or extension manifests, and treat Qwen routing as manual example or compatibility work rather than part of the shipped production `auto` contract. The current checkout exposes Qwen through root `scripts/install-qwen.*`, while checkouts without those entrypoints should fall back to the Qwen source tree directly.
- Explicit user role requests still override the toggle state in either direction.
- Full value-by-value operator semantics live in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md), including task continuity, continue-by-default execution expectations for initialized projects, and the current init-time preset family: `default`, `absolute-balance`, `external-aggressive`, `correctness-first`, and `max-speed`. Init helpers can either write the chosen preset as-is or open an optional fine-tune pass before saving `.agents-mode.yaml`.

Shipped production provider-order profile:

This is the persisted production `externalPriorityProfile` shipped from the root surfaces, not the init-time preset shortcuts. Example integrations may define their own provider-local examples, but the root production profile stays on Codex plus Claude only.

| Profile | Lane | Priority |
|---|---|---|
| `balanced` | `advisory.repo-understanding` | `claude > codex` |
|  | `advisory.design-adr` | `claude > codex` |
|  | `review.pre-pr` | `claude > codex` |
|  | `review.performance-architecture` | `claude > codex` |
|  | `worker.default-implementation` | `codex > claude` |
|  | `worker.systems-performance-implementation` | `codex > claude` |
|  | `worker.long-autonomous` | `claude > codex` |
|  | `worker.ui-structural-modernization` | `codex > claude` |
|  | `worker.ui-surgical-patch-cleanup` | `codex > claude` |
|  | `worker.visual-icon-decorative` | `codex > claude` |
|  | `review.visual` | `claude > codex` |

If a repo-local lane policy explicitly asks for consultant input at closeout, it should follow the configured `consultantMode`; `consultantMode: disabled` waives consultant closeout instead of blocking the batch. `parallelMode` is the general rule for whether any helper lanes are parallelized by judgment or only by explicit request, while `externalOpinionCounts` may still raise advisory or review lanes above `1` when the active policy wants multiple independent external opinions before advancing.

See [INSTALL.md](INSTALL.md) for quick install, pack-specific install details, dual-platform setup, and post-install customization.

## References and maintenance

- `shared/references/` contains the shared cross-provider design core that current and future provider packs can reuse.
- `shared/agents-mode.defaults.yaml` is the single editable exemplar for provider default overlays in the monorepo. Main installers seed provider-local or global `agents-mode` files directly from that shared exemplar, with any provider-only additions applied at install time. Standalone pack repositories keep one shipped pack-root default for self-contained install seeding.
- `docs/README.md` is the common branch-level docs entrypoint for operator semantics and runtime-layout references.
- [`docs/provider-runtime-layouts.md`](docs/provider-runtime-layouts.md) records the installed production runtime layout for Codex and Claude Code, plus the current example-integration status for Gemini and Qwen, with `global` and `local` scopes split explicitly so install/runtime paths are not confused with repo source trees.
- `references-codex/` contains Codex-specific addenda plus compatibility pointers for older reference paths.
- `references-claude/` contains Claude-specific addenda plus compatibility pointers for older reference paths.
- `references-gemini/` contains Gemini-specific addenda plus compatibility pointers for older reference paths.
- `references-qwen/` contains Qwen-specific addenda plus compatibility pointers for older reference paths.
- `subagent-operating-model` is no longer duplicated per provider pack: use the shared core for the canonical blueprint and the provider-local file only for runtime and repository concretization.
- `AGENTS.md` is the root development overlay for Codex provider-pack maintenance.
- `CLAUDE.md` is the root development overlay for Claude Code provider-pack maintenance.

Before publishing maintenance changes, validate the active provider surfaces:

```bash
bash src.codex/skills/lead/scripts/validate-skill-pack.sh
bash src.claude/agents/scripts/validate-skill-pack.sh
bash src.gemini/scripts/validate-pack.sh
bash src.qwen/scripts/validate-pack.sh
```

```powershell
.\src.codex\skills\lead\scripts\validate-skill-pack.ps1
.\src.claude\agents\scripts\validate-skill-pack.ps1
.\src.gemini\scripts\validate-pack.ps1
.\src.qwen\scripts\validate-pack.ps1
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
