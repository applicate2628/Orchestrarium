# Orchestrarium

A cross-provider agent orchestration monorepo that keeps the Codex, Claude Code, and Gemini provider trees aligned on one shared governance and reference core:

- `src.codex/` — the Codex provider pack source
- `src.claude/` — the Claude Code provider pack source
- `src.gemini/` — the Gemini provider-pack source tree with `GEMINI.md` as its runtime entrypoint, a pack-local `AGENTS.shared.md` import module, the stable skill catalog, and the preview specialist-agent surface

The provider lines share one governance model and role vocabulary, while each keeps the runtime structure expected by its own provider. In this branch, the root router installers now cover Codex, Claude Code, and Gemini CLI while still keeping each provider line honest through its own source-surface checks.

Warning: Orchestrarium is optimized for maximum execution effectiveness and low orchestration drag rather than for minimum token spend. On large tasks, multi-opinion review lanes, or aggressive external fan-out, usage can rise quickly and consume a substantial token budget in a short time.

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
  1) Codex pack
  2) Claude Code
  3) Gemini CLI
  4) All three
```

Then it forwards the same arguments to the provider-specific installer in `scripts/`. Use `scripts/install-codex.*`, `scripts/install-claude.*`, or `scripts/install-gemini.*` directly when you want deterministic single-provider automation.

Important: operator preferences now live only in pack-local `agents-mode` files.

- Codex reads `.agents/.agents-mode.yaml`.
- Claude Code reads `.claude/.agents-mode.yaml`.
- Gemini reads `.gemini/.agents-mode.yaml`.
- Legacy extensionless `.agents-mode` files remain compatibility input only. Reads should prefer `.agents-mode.yaml`, fall back to the sibling extensionless file only if the canonical file is missing, then normalize forward into `.agents-mode.yaml` without recreating the legacy path.
- `consultantMode` controls `$consultant`.
- `delegationMode: manual` keeps explicit-permission behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation a standing instruction whenever a matching specialist and viable tool path exist.
- `mcpMode: auto` lets the agent decide when MCP is appropriate; `force` means the config itself is an explicit instruction to use relevant available MCP tools instead of treating MCP usage as optional.
- `preferExternalWorker` and `preferExternalReviewer` let routing prefer `$external-worker` on `implement` and `$external-reviewer` on `review` and `QA`.
- `externalProvider` now uses one shared provider universe across all three lines: `auto | codex | claude | gemini`.
- `externalProvider: auto` is lane-driven, not host-pack-driven. It resolves through the active `externalPriorityProfile` and must not silently self-bounce into the same provider line.
- `externalPriorityProfile` selects the active named provider-order profile, `externalPriorityProfiles` stores the switchable per-lane provider orders, and `externalOpinionCounts` raises specific lanes above the default single-opinion behavior when one external opinion is not enough. Those counts are lane-local distinct-opinion requirements, not a cap on how many parallel external helper instances may run overall; bounded same-provider helper fan-out now lives under the dedicated brigade surfaces.
- `externalModelMode: runtime-default | pinned-top-pro` is the shared cross-provider model policy. `runtime-default` leaves the resolved provider on its runtime default model/profile; `pinned-top-pro` starts on the strongest documented provider-native model/profile and allows one named same-provider fallback on limit-style failures.
- Explicit self-provider selection is allowed only as an override for isolation, transport, profile, or an intentionally independent rerun.
- `externalGeminiFallbackMode: disabled | auto | force` stays under the `gemini` provider. When the model policy is pinned, `auto` keeps `gemini-3.1-pro` first and allows one fallback retry on `gemini-3-flash` only for limit, quota, or capacity-style Gemini failures.
- `externalClaudeApiMode: disabled | auto | force` stays under the `claude` provider. The named Claude API path is the repo-local secret-backed wrapper that runs plain `claude` with `ANTHROPIC_*` from `SECRET.md`; it is a Claude wrapper transport, not a fourth provider.
- Codex may additionally use `externalClaudeProfile` to select or override the Claude CLI execution profile: `sonnet-high` or `opus-max`. New Codex installs seed `opus-max` by default unless a preset or explicit override chooses otherwise.
- Codex install also seeds `.codex/agents/default.toml`, `worker.toml`, and `explorer.toml` so the built-in Codex subagents run as `gpt-5.4` with `xhigh` by default unless the user has already customized those files.
- Provider-specific workdir keys stay separate and default to `neutral`: `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, `externalGeminiWorkdirMode`.
- For first-time Codex project setup, run `$init-project` to write `## Project policies` in the root `AGENTS.md` and review or update the installed default `.agents/.agents-mode.yaml`. If only legacy `.agents/.agents-mode` exists, normalize it forward into the canonical `.yaml` file.
- When the current working directory is this installer monorepo itself, decide explicitly whether to use the global Codex install or to create a repo-local install before treating missing `.agents/.agents-mode.yaml` as a blocker. The installer source tree and the installed runtime are different surfaces.
- For first-time Claude Code project setup, run `/agents-init-project` to write `## Project policies` in `.claude/CLAUDE.md` and review or update the installed default `.claude/.agents-mode.yaml`. If only legacy `.claude/.agents-mode` exists, normalize it forward into the canonical `.yaml` file.
- For Gemini project setup, use Gemini's built-in `/init` to generate or tailor `GEMINI.md`. Official Gemini runtime config and MCP wiring stay in `.gemini/settings.json` or extension manifests, while Orchestrarium-specific shared governance is brought in through `GEMINI.md` importing project-root `AGENTS.md`, the canonical installed Gemini payload lives under `.gemini/extensions/orchestrarium-gemini/`, and shared routing semantics live in the Orchestrarium overlay `.gemini/.agents-mode.yaml`, which install seeds by default and the Gemini `init-project` helper reviews or updates after `/init`. If only legacy `.gemini/.agents-mode` exists, normalize it forward into the canonical `.yaml` file. Top-level `.gemini/skills/`, `.gemini/agents/`, and `.gemini/commands/` stay available for deliberate user overrides instead of carrying a second mirrored Orchestrarium install, because Gemini gives those tiers precedence over extension content.
- Explicit user role requests still override the toggle state in either direction.
- Full value-by-value operator semantics live in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md), including task continuity, continue-by-default execution expectations for initialized projects, and the current init-time preset family: `default`, `absolute-balance`, `external-aggressive`, `correctness-first`, and `max-speed`. Init helpers can either write the chosen preset as-is or open an optional fine-tune pass before saving `.agents-mode.yaml`.

Shipped named provider-order profiles:

These are persisted `externalPriorityProfile` choices, not the init-time preset shortcuts.

| Profile | Lane | Priority |
|---|---|---|
| `balanced` | `advisory.repo-understanding` | `claude > codex > gemini` |
|  | `advisory.design-adr` | `claude > codex > gemini` |
|  | `review.pre-pr` | `claude > codex > gemini` |
|  | `review.performance-architecture` | `claude > codex > gemini` |
|  | `worker.default-implementation` | `codex > claude > gemini` |
|  | `worker.systems-performance-implementation` | `codex > claude > gemini` |
|  | `worker.long-autonomous` | `claude > codex > gemini` |
|  | `worker.ui-structural-modernization` | `codex > claude > gemini` |
|  | `worker.ui-surgical-patch-cleanup` | `codex > claude > gemini` |
|  | `worker.visual-icon-decorative` | `codex > claude > gemini` |
|  | `review.visual` | `claude > codex > gemini` |
| `gemini-crosscheck` | `advisory.repo-understanding` | `claude > gemini > codex` |
|  | `advisory.design-adr` | `claude > gemini > codex` |
|  | `review.pre-pr` | `claude > gemini > codex` |
|  | `review.performance-architecture` | `claude > codex > gemini` |
|  | `worker.default-implementation` | `codex > claude > gemini` |
|  | `worker.systems-performance-implementation` | `codex > claude > gemini` |
|  | `worker.long-autonomous` | `claude > codex > gemini` |
|  | `worker.ui-structural-modernization` | `codex > claude > gemini` |
|  | `worker.ui-surgical-patch-cleanup` | `codex > claude > gemini` |
|  | `worker.visual-icon-decorative` | `codex > claude > gemini` |
|  | `review.visual` | `claude > codex > gemini` |

If a repo-local lane policy explicitly asks for consultant input at closeout, it should follow the configured `consultantMode`; `consultantMode: disabled` waives consultant closeout instead of blocking the batch. `externalOpinionCounts` may raise advisory or review lanes above `1` when the active policy wants multiple independent external opinions before advancing, but it does not prevent the lead from launching multiple same-provider external helpers in parallel on different disjoint brigade items.

See [INSTALL.md](INSTALL.md) for quick install, pack-specific install details, dual-platform setup, and post-install customization.

## References and maintenance

- `shared/references/` contains the shared cross-provider design core that current and future provider packs can reuse.
- `shared/agents-mode.defaults.yaml` is the single editable exemplar for provider default overlays in the monorepo. Main installers seed provider-local or global `agents-mode` files directly from that shared exemplar, with any provider-only additions applied at install time. Standalone pack repositories keep one shipped pack-root default for self-contained install seeding.
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
