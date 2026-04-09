# Orchestrarium

One monorepo for two agent skill packs:

- `src.codex/` — Orchestrarium, the Codex skill pack
- `src.claude/` — Claudestrator, the Claude Code skill pack

Both packs share the same governance model and role vocabulary, but each ships in the structure and runtime format expected by its platform.

## Repository layout

```text
shared/             Shared governance (AGENTS.shared.md)
src.codex/          Codex skill pack source
src.claude/         Claude Code skill pack source
references-codex/   Codex reference docs and blueprints
references-claude/  Claude Code reference docs and blueprints
install.sh          Entry-point installer (asks which pack to install)
install.ps1         Entry-point installer (asks which pack to install)
scripts/            Pack-specific installers (called by entry points)
AGENTS.md           Dev overlay for Codex pack maintenance
CLAUDE.md           Dev overlay for Claude pack maintenance
```

## Skill packs

| Pack | Source | Installs into | Runtime governance | Validation |
| --- | --- | --- | --- | --- |
| Codex | `src.codex/` | `~/.codex/` or project `.agents/skills/` | `src.codex/AGENTS.md` | `bash src.codex/skills/lead/scripts/validate-skill-pack.sh` |
| Claude Code | `src.claude/` | `~/.claude/` or project `.claude/` | `src.claude/CLAUDE.md` | `bash src.claude/agents/scripts/validate-skill-pack.sh` |

Shared development references live in `references-codex/` and `references-claude/`. Shared governance is maintained across both packs; the repository-level overlays in `AGENTS.md` and `CLAUDE.md` exist only for maintaining this monorepo.

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
  1) Codex (Orchestrarium)
  2) Claude Code (Claudestrator)
  3) Both
```

Then it forwards the same arguments to the pack-specific installer in `scripts/`. Use `scripts/install-codex.*` or `scripts/install-claude.*` directly when you want deterministic single-pack automation.

Important: if you want the assistant to actually start a team or delegate to subagents, give explicit delegation permission in your prompt. Naming a role such as `$lead` or clearly asking for delegation is the safe default; without that permission, the assistant may remain in the main conversation instead of launching the team.

See [INSTALL.md](INSTALL.md) for quick install, pack-specific install details, dual-platform setup, and post-install customization.

## References and maintenance

- `references-codex/` contains the Codex-side design docs, operating model, and translations.
- `references-claude/` contains the Claude-side design docs, operating model, and translations.
- `AGENTS.md` is the root development overlay for Codex pack maintenance.
- `CLAUDE.md` is the root development overlay for Claude pack maintenance.

Before publishing maintenance changes, validate both packs:

```bash
bash src.codex/skills/lead/scripts/validate-skill-pack.sh
bash src.claude/agents/scripts/validate-skill-pack.sh
```

## License

This repository is licensed under the Apache License 2.0. See [LICENSE](LICENSE).
