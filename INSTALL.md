# Installation

This monorepo ships unified entry-point installers at the root (`install.sh` and `install.ps1`). They prompt for Codex, Claude Code, Gemini CLI, or all three, then forward arguments to the matching pack-specific installers in the `scripts/` directory.

## Quick install

Run the router installer from the repository root:

```bash
bash install.sh --global
```

```powershell
.\install.ps1 -Global
```

Or install into a specific project:

```bash
bash install.sh --target /path/to/project
```

```powershell
.\install.ps1 -Target "D:\path\to\project"
```

The router asks which pack to install:

```text
What to install?
  1) Codex pack
  2) Claude Code
  3) Gemini CLI
  4) All three
```

For `All three`, the router reuses the same forwarded arguments for all three pack-specific installers.

## Init-time preset shortcuts

After first-time project bootstrap, the provider init helpers can start from one of these preset shortcuts before writing canonical `agents-mode` keys:

- `default`
- `absolute-balance`
- `external-aggressive`
- `correctness-first`
- `max-speed`

The preset name itself is not persisted; the helper writes the resolved canonical key values instead. Full preset expansion tables live in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md).
If the user wants the preset unchanged, the helper should write the preset-expanded `.agents-mode.yaml` directly; key-by-key fine-tuning is optional rather than mandatory.

Canonical operator-overlay output now uses `.agents-mode.yaml` on every provider line. Legacy extensionless `.agents-mode` files remain compatibility input only: reads should prefer `.agents-mode.yaml`, fall back to the sibling extensionless file only when the canonical file is missing, normalize forward into `.agents-mode.yaml`, and not recreate the legacy path.

## Codex install details

Use `scripts/install-codex.sh` or `scripts/install-codex.ps1` when you want the Codex pack directly.

| Command | Result |
| --- | --- |
| `bash scripts/install-codex.sh --global` | Installs into `~/.codex/` |
| `bash scripts/install-codex.sh --target /path/to/project` | Installs into the target project's `.agents/skills/` and merges root `AGENTS.md` |
| `.\scripts\install-codex.ps1 -Global` | Installs into `~/.codex/` |
| `.\scripts\install-codex.ps1 -Target "D:\path\to\project"` | Installs into the target project's `.agents/skills/` and merges root `AGENTS.md` |

Notes:

- Project-level Codex installs use `.agents/skills/` plus the project root `AGENTS.md`.
- Codex installs also seed built-in subagent overrides into `.codex/agents/default.toml`, `.codex/agents/worker.toml`, and `.codex/agents/explorer.toml` for project installs, or `~/.codex/agents/` for global installs.
- Those shipped override files pin the built-in `default`, `worker`, and `explorer` subagents to `gpt-5.4` with `xhigh` reasoning effort; reinstall preserves any existing custom files at those paths instead of overwriting them.
- Project-level installs ensure `/.reports/` and `/work-items/` are present in the target repo `.gitignore` if they are missing, because session logs and repo-local task memory are local-only runtime output.
- The canonical Codex-line operator file is `.agents/.agents-mode.yaml` for project installs and `~/.codex/.agents-mode.yaml` for global installs.
- First-time creation should write the full default shape with inline comments listing allowed values for each key.
- Decision-driving reads should prefer `.agents/.agents-mode.yaml`, fall back to legacy `.agents/.agents-mode` only if the canonical file is missing, normalize either input forward to the current canonical format in `.agents/.agents-mode.yaml`, and never recreate the legacy file.
- `consultantMode` still controls `$consultant`; `delegationMode: manual` keeps explicit-permission behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation an explicit standing instruction whenever a matching specialist and viable tool path exist; `mcpMode: auto` lets the agent decide when MCP is appropriate while `force` makes MCP usage an explicit standing instruction; the two `preferExternal*` flags let routing prefer `$external-worker` and `$external-reviewer`; `externalProvider` uses the shared provider universe `auto | codex | claude | gemini`; `externalPriorityProfile` selects the active named provider-order profile for `auto`; `externalPriorityProfiles` stores the switchable per-lane provider orders; and `externalOpinionCounts` raises specific lanes above the default single-opinion behavior when one external opinion is not enough. Those counts stay lane-local distinct-opinion requirements; bounded same-provider helper fan-out is handled through the dedicated brigade surfaces.
- `externalProvider: auto` is lane-driven rather than host-pack-driven. It resolves through the active priority profile documented in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md) and must not silently self-bounce into the same provider line.
- `externalModelMode` is the shared cross-provider model policy: `runtime-default` leaves the resolved provider on its runtime default model/profile, while `pinned-top-pro` starts on the strongest documented provider-native model/profile and allows one named same-provider fallback on retryable provider exhaustion.
- Under `externalModelMode: pinned-top-pro`, `externalGeminiFallbackMode` is the Gemini same-provider fallback knob: `disabled` keeps `gemini-3.1-pro` only, `auto` allows one retry on `gemini-3-flash` only after quota, limit, capacity, HTTP `429`, or `RESOURCE_EXHAUSTED`-style Gemini failures, and `force` starts on `gemini-3-flash` immediately.
- `externalClaudeSecretMode` is used whenever the resolved provider is Claude CLI: `auto` keeps the first Claude call plain and allows one SECRET-backed retry only after quota, limit, or reset errors; `force` applies `ANTHROPIC_*` from the local Claude `SECRET.md` to the primary Claude call.
- `externalClaudeApiMode` is the named Claude secondary-transport toggle: `disabled` forbids `claude-api`, `auto` keeps `claude-api` as the fallback after the allowed Claude CLI path is exhausted, and `force` uses `claude-api` as the primary Claude transport immediately. `claude-api` is a Claude transport, not a separate provider.
- `externalClaudeProfile` is Codex-line only and selects or overrides the Claude CLI execution profile: `sonnet-high` maps to Sonnet with `--effort high`, and `opus-max` maps to Opus with `--effort max`.
- Repo-local routing heuristics may still prefer Gemini for image generation, icon work, and decorative visual lanes when that routing remains honest, and the shipped `gemini-crosscheck` profile is the named way to bring Gemini into broader non-visual advisory or review second-opinion sets.
- Full mode tables live in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md).
- After first-time Codex project install, run `$init-project` in Codex to write `## Project policies` to the root `AGENTS.md` and review or update the installed default `.agents/.agents-mode.yaml`.
- Completed lead-managed batches now end with one or more external consultant-checks before closure as required by the active lane policy. Those checks stay advisory-only, but if the required external consultant path is disabled or unavailable the batch stays open and the lead escalates instead of silently downgrading.
- Validation commands: `bash src.codex/skills/lead/scripts/validate-skill-pack.sh` or `.\src.codex\skills\lead\scripts\validate-skill-pack.ps1`.

## Claude Code install details

Use `scripts/install-claude.sh` or `scripts/install-claude.ps1` when you want the Claude Code pack directly.

| Command | Result |
| --- | --- |
| `bash scripts/install-claude.sh --global` | Installs into `~/.claude/` |
| `bash scripts/install-claude.sh --target /path/to/project` | Installs into the target project's `.claude/` |
| `.\scripts\install-claude.ps1 -Global` | Installs into `~/.claude/` |
| `.\scripts\install-claude.ps1 -Target "D:\path\to\project"` | Installs into the target project's `.claude/` |

Notes:

- Project-level Claude installs create or update `.claude/AGENTS.md` and `.claude/CLAUDE.md`.
- Project-level installs ensure `/.reports/` and `/work-items/` are present in the target repo `.gitignore` if they are missing, because session logs and repo-local task memory are local-only runtime output.
- Claude memory is shipped in `src.claude/memory/` and preserved across reinstalls by the existing installer behavior.
- User-side Claude imports such as `@memory/...` are preserved across reinstalls when they live in the installed `.claude/CLAUDE.md` import block alongside `@AGENTS.md`.
- The canonical Claude-line operator file is `.claude/.agents-mode.yaml` for project installs and `~/.claude/.agents-mode.yaml` for global installs.
- First-time creation should write the full default shape with inline comments listing allowed values for each key.
- Decision-driving reads should prefer `.claude/.agents-mode.yaml`, fall back to legacy `.claude/.agents-mode` only if the canonical file is missing, normalize either input forward to the current canonical format in `.claude/.agents-mode.yaml`, and never recreate the legacy file.
- `consultantMode` still controls `$consultant`; `delegationMode: manual` keeps explicit-permission behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation an explicit standing instruction whenever a matching specialist and viable tool path exist; `mcpMode: auto` lets the agent decide when MCP is appropriate while `force` makes MCP usage an explicit standing instruction; the two `preferExternal*` flags let routing prefer `$external-worker` and `$external-reviewer`; `externalProvider` uses the same shared provider universe `auto | codex | claude | gemini`; and the switchable `externalPriorityProfile` / `externalPriorityProfiles` / `externalOpinionCounts` block keeps broader Gemini participation and multi-opinion routing in `agents-mode` instead of hidden host-line defaults. Those counts stay distinct-opinion requirements for one lane, while brigade surfaces cover parallel helper multiplicity.
- Explicit self-provider selection is override-only; ordinary `auto` must not silently resolve back into the same host line.
- If the resolved provider is Claude, `externalClaudeSecretMode` and `externalClaudeApiMode` remain Claude transport knobs. The preferred Claude API transport surface is `.claude/agents/scripts/invoke-claude-api.sh` or `.ps1`, which reads repo-local `.claude/SECRET.md` first and then `~/.claude/SECRET.md`. `externalClaudeProfile` stays Codex-line only.
- Practical launch rules: use the PowerShell Claude wrapper from PowerShell and the bash Claude wrapper from Bash or Git Bash; the PowerShell wrapper accepts both `-PrintSecretPath` and `--print-secret-path`, and the bash wrapper honors `CLAUDE_API_BIN` when the active shell PATH cannot see `claude-api`.
- If a Claude-target external run is obviously unauthenticated on the plain `claude` path, prefer the allowed Claude API transport instead of spending time on repeated plain-CLI retries.
- For Codex commit review, use `codex review --commit <sha>` without a free-form prompt; if custom review instructions are needed, prefer a narrower `codex exec` run on the admitted scope.
- For wide release or parity audits, split the admitted scope by repo, file set, or lane instead of launching one mega neutral-dir prompt across the whole pack family.
- Full mode tables live in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md).
- After first-time Claude project install, run `/agents-init-project` in Claude Code to write `## Project policies` in `.claude/CLAUDE.md` and review or update the installed default `.claude/.agents-mode.yaml`.
- Completed lead-managed batches now end with one or more external consultant-checks before closure as required by the active lane policy. Those checks stay advisory-only, but if the required external consultant path is disabled or unavailable the batch stays open and the lead escalates instead of silently downgrading.
- Validation commands: `bash src.claude/agents/scripts/validate-skill-pack.sh` or `.\src.claude\agents\scripts\validate-skill-pack.ps1`.

## Gemini CLI install details

Use `scripts/install-gemini.sh` or `scripts/install-gemini.ps1` when you want the Gemini pack directly.

| Command | Result |
| --- | --- |
| `bash scripts/install-gemini.sh --global` | Installs into `~/.gemini/` by seeding `GEMINI.md`, `AGENTS.md`, `~/.gemini/.agents-mode.yaml`, and the official extension package at `~/.gemini/extensions/orchestrarium-gemini/` |
| `bash scripts/install-gemini.sh --target /path/to/project` | Installs into the target project's `GEMINI.md`, root `AGENTS.md` when absent, `.gemini/.agents-mode.yaml`, and `.gemini/extensions/orchestrarium-gemini/` |
| `.\scripts\install-gemini.ps1 -Global` | Installs into `~/.gemini/` by seeding `GEMINI.md`, `AGENTS.md`, `~/.gemini/.agents-mode.yaml`, and the official extension package at `~/.gemini/extensions/orchestrarium-gemini/` |
| `.\scripts\install-gemini.ps1 -Target "D:\path\to\project"` | Installs into the target project's `GEMINI.md`, root `AGENTS.md` when absent, `.gemini/.agents-mode.yaml`, and `.gemini/extensions/orchestrarium-gemini/` |

Notes:

- Project-level Gemini installs preserve any user-owned content outside the managed Orchestrarium block inside `GEMINI.md`.
- User-side `@...` imports that live in the installed `GEMINI.md` import block alongside `@./AGENTS.md` are preserved across reinstalls.
- Gemini installs materialize the shared-governance layer as `AGENTS.md`; `GEMINI.md` loads it through the official `@./AGENTS.md` import. Project installs preserve an existing root `AGENTS.md` instead of overwriting it.
- Project-level Gemini installs ensure `/.reports/` and `/work-items/` are present in the target repo `.gitignore` if they are missing, because session logs and repo-local task memory are local-only runtime output.
- Gemini installs materialize the official Gemini extension package under `.gemini/extensions/orchestrarium-gemini/` for project installs and `~/.gemini/extensions/orchestrarium-gemini/` for global installs. That extension is the canonical installed Gemini payload and carries `gemini-extension.json`, `README.md`, `GEMINI.md`, `AGENTS.md`, `skills/`, `agents/`, and `commands/`.
- To avoid precedence conflicts and noisy loader warnings, Orchestrarium does not mirror the same pack into top-level `.gemini/skills/`, `.gemini/agents/`, or `.gemini/commands/`. Those Gemini-native user/workspace tiers remain available for deliberate user overrides only.
- Reinstall cleans legacy Orchestrarium-owned duplicates from `.gemini/skills/`, `.gemini/agents/`, and `.gemini/commands/` when they would shadow the installed extension payload.
- Gemini runtime config and MCP wiring remain owned by `.gemini/settings.json` and `gemini-extension.json`; servers such as Serena, Fetch, or Context7 do not belong inside `AGENTS.md`.
- The Orchestrarium routing overlay file is `.gemini/.agents-mode.yaml` for project installs and `~/.gemini/.agents-mode.yaml` for global installs.
- Decision-driving reads should prefer `.gemini/.agents-mode.yaml`, fall back to legacy `.gemini/.agents-mode` only if the canonical file is missing, normalize either input forward to the current canonical format in `.gemini/.agents-mode.yaml`, and never recreate the legacy file.
- After first-time Gemini project install, run Gemini CLI `/init` if you want Gemini to create or refresh the user-owned portion of `GEMINI.md`, and then use the Orchestrarium Gemini `init-project` helper to review or update the installed default `.gemini/.agents-mode.yaml` when you want project-specific routing choices.
- Validation commands: `bash src.gemini/scripts/validate-pack.sh` or `.\src.gemini\scripts\validate-pack.ps1`.

## Multi-pack setup

To install any combination of packs into the same target project, either choose the matching option in the router or run the pack-specific installers with the same target arguments.

Expected project-level result:

```text
project/
  AGENTS.md
  .codex/
    agents/
  GEMINI.md
  .agents/
    skills/
  .claude/
    AGENTS.md
    CLAUDE.md
  .gemini/
    .agents-mode.yaml
    extensions/
      orchestrarium-gemini/
```

Reference directories are development-only and are not installed:

- `shared/references/`
- `docs/`
- `references-codex/`
- `references-claude/`
- `references-gemini/`

That split is intentional. `shared/references/` holds the canonical shared design cores, `docs/` is the common branch-level docs surface, and `references-codex/`, `references-claude/`, and `references-gemini/` keep only pack-local addenda or compatibility pointers. `subagent-operating-model` is the main example: the installed packs keep their runtime docs, but the monorepo now keeps one shared blueprint core plus one addendum per pack instead of near-duplicate full reference copies.

## Post-install customization

Customize each platform in the place that platform actually reads:

- Codex: append project-specific rules below the installed section in the project root `AGENTS.md`.
- Claude Code: append project-specific rules below the installed section in `.claude/CLAUDE.md`.
- Claude Code: user-side `@...` imports in `.claude/CLAUDE.md` may live in the import block near `@AGENTS.md`; the installer preserves those imports on reinstall.
- Configure consultant and external-dispatch preferences in `.agents/.agents-mode.yaml` for Codex or `.claude/.agents-mode.yaml` for Claude Code.
- Shared design references in `shared/references/` are repository-maintainer documentation only; they are not copied into target projects and should not be treated as installed runtime docs.

When both packs are installed, keep shared project policies aligned across both files. The repository's dev overlays, `AGENTS.md` and `CLAUDE.md`, are for maintaining this monorepo and are not copied into target projects by the install scripts.

## Gemini source tree in the monorepo

The monorepo still keeps the full Gemini line as a validated source tree in addition to the new root-router install path:

- runtime entrypoint: `src.gemini/GEMINI.md`
- shared-governance import module: `src.gemini/AGENTS.shared.md`
- branch-level docs entrypoint: `docs/README.md`
- built-in initialization: Gemini CLI `/init` writes or tailors the project `GEMINI.md`
- expertise layer: `src.gemini/skills/<name>/SKILL.md`
- preview specialist-team layer: `src.gemini/agents/*.md` (agent definitions only; YAML frontmatter required)
- repo-local team templates: `src.gemini/agents/team-templates/*.json`
- custom commands: `src.gemini/commands/**/*.toml`
- official runtime config: project `.gemini/settings.json`
- Orchestrarium operator overlay: project `.gemini/.agents-mode.yaml`
- installed extension manifest source: `src.gemini/extension/gemini-extension.json`
- provider-local reference tree: `references-gemini/`
- validation commands: `bash src.gemini/scripts/validate-pack.sh` or `.\src.gemini\scripts\validate-pack.ps1`
- Orchestrarium overlay bootstrap: `src.gemini/commands/agents/init-project.toml` and `src.gemini/skills/init-project/SKILL.md`

It intentionally keeps the full Gemini payload in `src.gemini/` while materializing the installed runtime as one official extension package plus the adjacent Gemini-native context files and `.agents-mode.yaml` overlay. Use Gemini's built-in `/init` for the official `GEMINI.md` bootstrap first. Orchestrarium install seeds `.gemini/.agents-mode.yaml` with the current default overlay in either the project target or `~/.gemini/`, and it materializes the canonical runtime payload under `.gemini/extensions/orchestrarium-gemini/` or `~/.gemini/extensions/orchestrarium-gemini/`; use the Orchestrarium Gemini init helper to review or update that installed default rather than replacing Gemini's official `.gemini/settings.json`. Top-level `.gemini/skills/`, `.gemini/agents/`, and `.gemini/commands/` stay reserved for deliberate user overrides and are not used as a second mirrored install target, because Gemini gives user/workspace tiers precedence over extension content. MCP wiring for servers such as Serena, Fetch, or Context7 remains a `settings.json` or `gemini-extension.json` concern. Gemini shares the same external provider universe `auto | codex | claude | gemini`; ordinary `auto` resolves by lane through the active priority profile, while explicit `gemini` is self-provider override only. The overlay may also carry `externalPriorityProfile`, `externalPriorityProfiles`, and `externalOpinionCounts` so Gemini can participate in broader advisory or review second-opinion sets when the active policy requests more than one external opinion. Those counts stay same-lane distinct-opinion requirements rather than a cap on helper multiplicity; bounded same-provider helper fan-out now routes through `external-brigade`. When the resolved provider is Gemini, that overlay may also carry `externalModelMode: runtime-default | pinned-top-pro` plus `externalGeminiFallbackMode: disabled | auto | force`, where pinned `auto` means `gemini-3.1-pro` first and one fallback retry on `gemini-3-flash` only for limit-style Gemini failures. When the resolved provider is Claude, that overlay may also carry the same shared `externalModelMode` plus `externalClaudeSecretMode: auto | force` and `externalClaudeApiMode: disabled | auto | force`. Repo-local routing heuristics may still prefer Gemini itself for image generation, icon work, and decorative visual lanes, and `gemini-crosscheck` is the named broader-Gemini profile. Full operator semantics, including task continuity and continue-by-default execution expectations, live in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md).
