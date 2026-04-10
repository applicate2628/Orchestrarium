# Orchestrarium

A cross-provider agent orchestration monorepo for provider-specific agent packs:

- `src.codex/` — the Codex provider pack
- `src.claude/` — the Claude Code provider pack
- `src.gemini/` — the Gemini CLI provider-pack scaffold

Current provider packs share the same governance model and role vocabulary, while each ships in the structure and runtime format expected by its own provider line. The Gemini line currently enters as a lean source scaffold on the same cross-provider core rather than as a third independent methodology tree.

## Repository layout

```text
shared/             Shared cross-provider governance and canonical reference cores
src.codex/          Codex provider-pack source
src.claude/         Claude Code provider-pack source
src.gemini/         Gemini CLI provider-pack scaffold
references-codex/   Codex-specific addenda and compatibility pointers
references-claude/  Claude Code-specific addenda and compatibility pointers
RELEASE_NOTES.md    Canonical tracked release log
install.sh          Entry-point installer (asks which pack to install)
install.ps1         Entry-point installer (asks which pack to install)
scripts/            Pack-specific installers (called by entry points)
AGENTS.md           Dev overlay for Codex pack maintenance
CLAUDE.md           Dev overlay for Claude Code pack maintenance
```

## Provider Packs

| Pack | Source | Installs into | Runtime governance | Validation |
| --- | --- | --- | --- | --- |
| Codex | `src.codex/` | `~/.codex/` or project `.agents/skills/` | `src.codex/AGENTS.md` | `bash src.codex/skills/lead/scripts/validate-skill-pack.sh` |
| Claude Code | `src.claude/` | `~/.claude/` or project `.claude/` | `src.claude/CLAUDE.md` | `bash src.claude/agents/scripts/validate-skill-pack.sh` |
| Gemini CLI | `src.gemini/` | scaffold only for now | `src.gemini/GEMINI.md` | `bash src.gemini/scripts/validate-pack.sh` |

Shared design references now live in `shared/references/`. Provider-local `references-codex/` and `references-claude/` now keep only provider-specific addenda plus compatibility pointers where older paths still need to resolve. The clearest example is `subagent-operating-model`: the canonical blueprint core now lives in `shared/references/subagent-operating-model.md`, while each provider-local tree keeps only its runtime and repository concretization addendum. Shared governance is maintained across provider lines; the repository-level overlays in `AGENTS.md` and `CLAUDE.md` exist only for maintaining this monorepo.

Cross-provider execution is available through two routing adapters:

- `$external-worker` is the external execution adapter for eligible implementer roles.
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
  3) Both
```

Then it forwards the same arguments to the provider-specific installer in `scripts/`. Use `scripts/install-codex.*` or `scripts/install-claude.*` directly when you want deterministic single-provider automation.

Important: operator preferences now live in pack-local `agents-mode` files; legacy `consultant-mode` files remain fallback-only during migration.

- Codex reads `.agents/.agents-mode`.
- Claude Code reads `.claude/.agents-mode`.
- `consultantMode` controls `$consultant`.
- `delegationMode` supports `manual | auto | force`: `manual` keeps explicit delegation, `auto` leaves ordinary delegation to routing judgment, and `force` means delegate whenever a matching role and working tool path are available.
- `mcpMode: auto | force` controls MCP usage: `auto` leaves MCP choice to routing judgment, while `force` means the config itself is an explicit instruction to use relevant available MCP tools instead of treating them as optional.
- `preferExternalWorker` and `preferExternalReviewer` let routing prefer `$external-worker` on `implement` and `$external-reviewer` on `review` and `QA`.
- Codex may additionally use `externalClaudeProfile` to select the Claude CLI execution profile: `sonnet-high` or `opus-max`.
- Claude Code does not use `externalClaudeProfile` in its canonical config because Claude-line external dispatch goes to Codex CLI.
- For Gemini project setup, use Gemini's built-in `/init` to generate or tailor `GEMINI.md`. Official Gemini runtime config stays in `.gemini/settings.json`; the Orchestrarium Gemini `init-project` helper only bootstraps the optional `.gemini/.agents-mode` overlay after `/init`.
- Explicit user role requests still override the toggle state in either direction.

See [INSTALL.md](INSTALL.md) for quick install, pack-specific install details, dual-platform setup, and post-install customization.

## References and maintenance

- `shared/references/` contains the shared cross-provider design core that current and future provider packs can reuse.
- `references-codex/` contains Codex-specific addenda plus compatibility pointers for older reference paths.
- `references-claude/` contains Claude-specific addenda plus compatibility pointers for older reference paths.
- `subagent-operating-model` is no longer duplicated per provider pack: use the shared core for the canonical blueprint and the provider-local file only for runtime and repository concretization.
- `AGENTS.md` is the root development overlay for Codex provider-pack maintenance.
- `CLAUDE.md` is the root development overlay for Claude Code provider-pack maintenance.

Before publishing maintenance changes, validate the active provider surfaces:

```bash
bash src.codex/skills/lead/scripts/validate-skill-pack.sh
bash src.claude/agents/scripts/validate-skill-pack.sh
bash src.gemini/scripts/validate-pack.sh
```

For release-relevant tracked changes, update `RELEASE_NOTES.md` in the same change before publication and explain the practical effect of the change, not just its title.

## License

This repository is licensed under the Apache License 2.0. See [LICENSE](LICENSE).
