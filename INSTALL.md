# Installation

This monorepo ships unified entry-point installers at the root (`install.sh` and `install.ps1`). They separate the production Codex/Claude path from explicit example integrations, then forward arguments to the matching pack-specific installers in the `scripts/` directory.

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
Production installs:
  1) Codex pack
  2) Claude Code
  3) Codex + Claude (production pair)
Example integrations:
  4) Gemini CLI (WEAK MODEL / NOT RECOMMENDED)
  5) Qwen (WEAK MODEL / NOT RECOMMENDED)
  6) All available root installs
```

For `All available root installs`, the router reuses the same forwarded arguments for every root-visible installer on the current platform. In the current checkout, that includes the Qwen example path because matching `scripts/install-qwen.*` entrypoints are present; if a future checkout lacks them, the router hides the dedicated Qwen slot.

Maintainer note for this monorepo: `Orchestrarium/` is the installer/source tree, not automatically a repo-local installed Codex runtime. When you are editing this repository itself, a missing local `.agents/` tree can be perfectly valid if you are using the global install under `~/.codex/`. If you want this repository to behave as a repo-local install target, create that state intentionally through `scripts/install-codex.*` or the root router instead of hand-writing `.agents/` files.

## Init-time preset shortcuts

After first-time project bootstrap, the provider init helpers can start from one of these preset shortcuts before writing canonical `agents-mode` keys:

- `default`
- `absolute-balance`
- `external-aggressive`
- `correctness-first`
- `max-speed`

The preset name itself is not persisted; the helper writes the resolved canonical key values instead. Full preset expansion tables live in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md).
If the user wants the preset unchanged, the helper should write the preset-expanded `.agents-mode.yaml` directly; key-by-key fine-tuning is optional rather than mandatory.

Canonical operator-overlay output now uses `.agents-mode.yaml` on every provider line. Legacy extensionless `.agents-mode` files remain compatibility input only: decision-driving reads should resolve provider overlays in this order — local `.agents-mode.yaml`, local legacy `.agents-mode`, matching global `~/.<provider>/.agents-mode.yaml`, then matching global legacy `.agents-mode` — normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope, and not recreate any legacy path.
The same rule now applies to reinstall: if an existing `.agents-mode.yaml` is older than the current shipped schema or defaults, the installer must normalize it to the current canonical form instead of preserving stale pack-owned structure verbatim.

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
- Installed Codex validation treats preserved user-added skills as warnings rather than pack metadata-budget failures. The strict metadata budget applies to Orchestrarium-owned roles and utility skills, while extra global skills remain visible as non-blocking orphan warnings.
- Project-level installs ensure `/.reports/` and `/work-items/` are present in the target repo `.gitignore` if they are missing, because session logs and repo-local task memory are local-only runtime output.
- The canonical Codex-line operator file is `.agents/.agents-mode.yaml` for project installs and `~/.codex/.agents-mode.yaml` for global installs.
- For this installer monorepo itself, the absence of project-local `.agents/.agents-mode.yaml` inside `Orchestrarium/` is not automatically a bug when the maintainer is working against the global install. Ordinary reads should fall back to `~/.codex/.agents-mode.yaml` before treating the state as missing.
- First-time creation should write the full default shape with inline comments listing allowed values for each key.
- Decision-driving reads should prefer `.agents/.agents-mode.yaml`, then local legacy `.agents/.agents-mode`, then `~/.codex/.agents-mode.yaml`, then global legacy `~/.codex/.agents-mode`; normalize whichever file supplied the effective config to the current canonical format in the same scope and never recreate any legacy file or synthesize a local override on read alone.
- `consultantMode` still controls `$consultant`; `delegationMode: manual` keeps explicit-permission behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation an explicit standing instruction whenever a matching specialist and viable tool path exist; `parallelMode: manual` keeps parallel fan-out explicit-by-request, `auto` leaves safe parallelism enabled by routing judgment for any independent internal or external lanes, and `force` makes safe parallel launch a standing instruction whenever scopes are independent and the merge cost is justified; `mcpMode: auto` lets the agent decide when MCP is appropriate while `force` makes MCP usage an explicit standing instruction; the two `preferExternal*` flags let routing prefer `$external-worker` and `$external-reviewer`; production `externalProvider` uses `auto | codex | claude`; `externalPriorityProfile` selects the active named provider-order profile for `auto`; `externalPriorityProfiles` stores the switchable per-lane provider orders; and `externalOpinionCounts` raises specific lanes above the default single-opinion behavior when one external opinion is not enough. Those counts stay lane-local distinct-opinion requirements; `parallelMode` remains the general helper fan-out rule, while bounded same-provider external helper fan-out is handled through the dedicated brigade surfaces.
- `externalProvider: auto` is lane-driven rather than host-pack-driven. It resolves through the active production priority profile documented in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md), stays on the Codex/Claude pair, and must not silently self-bounce into the same provider line.
- `externalModelMode` is the shared production model policy: `runtime-default` leaves the resolved provider on its runtime default model/profile, while `pinned-top-pro` starts on the strongest documented provider-native model/profile and allows one named same-provider fallback on retryable provider exhaustion.
- `externalClaudeApiMode` controls the advisory/review-only `claude-secret` supplemental candidate: `disabled` forbids the secret-backed Claude API path, `auto` allows it when an advisory or review profile order reaches `claude-secret` after primary `claude`/`codex`, and `force` keeps that supplemental candidate available for advisory/review even when plain Claude is unavailable. It remains a weaker Claude transport, not a scalar provider and not an implementation/editing fallback.
- `externalClaudeProfile` is Codex-line only and selects or overrides the Claude CLI execution profile: `sonnet-high` maps to Sonnet with `--effort high`, and `opus-max` maps to Opus with `--effort max`. New Codex installs seed `opus-max` by default unless a preset or explicit operator choice overrides it.
- Gemini and Qwen remain explicit example-only integrations in this repository. They are `WEAK MODEL / NOT RECOMMENDED`, do not participate in the shipped production `auto` profiles, and should be treated as manual example or compatibility paths rather than production defaults.
- Full mode tables live in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md).
- After first-time Codex project install, run `$init-project` in Codex to write `## Project policies` to the root `AGENTS.md` and review or update the installed default `.agents/.agents-mode.yaml`.
- If a repo-local lane policy explicitly asks for consultant input at closeout, it follows the configured `consultantMode`. `consultantMode: disabled` waives consultant closeout instead of blocking the batch, and any requested consultant sweep stays advisory-only rather than replacing review or human gates.
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
- Decision-driving reads should prefer `.claude/.agents-mode.yaml`, then local legacy `.claude/.agents-mode`, then `~/.claude/.agents-mode.yaml`, then global legacy `~/.claude/.agents-mode`; normalize whichever file supplied the effective config to the current canonical format in the same scope and never recreate any legacy file or synthesize a local override on read alone.
- `consultantMode` still controls `$consultant`; `delegationMode: manual` keeps explicit-permission behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation an explicit standing instruction whenever a matching specialist and viable tool path exist; `parallelMode: manual` keeps parallel fan-out explicit-by-request, `auto` leaves safe parallelism enabled by routing judgment for any independent internal or external lanes, and `force` makes safe parallel launch a standing instruction whenever scopes are independent and the merge cost is justified; `mcpMode: auto` lets the agent decide when MCP is appropriate while `force` makes MCP usage an explicit standing instruction; the two `preferExternal*` flags let routing prefer `$external-worker` and `$external-reviewer`; production `externalProvider` uses `auto | codex | claude`; and the switchable `externalPriorityProfile` / `externalPriorityProfiles` / `externalOpinionCounts` block keeps production auto-routing on Codex plus Claude instead of hidden host-line defaults. Those counts stay distinct-opinion requirements for one lane, while brigade surfaces cover parallel external helper multiplicity on top of the general `parallelMode` rule.
- Explicit self-provider selection is override-only; ordinary `auto` must not silently resolve back into the same host line.
- `externalClaudeApiMode` controls only the advisory/review `claude-secret` candidate. When that candidate is reached, the wrapper surface is `.claude/agents/scripts/invoke-claude-api.sh` or `.ps1`, which reads repo-local `.claude/SECRET.md` first and then `~/.claude/SECRET.md`, exports the declared `ANTHROPIC_*` environment, and then runs plain `claude`. `externalClaudeProfile` stays Codex-line only for primary Claude CLI runs.
- Practical launch rules: use the PowerShell Claude wrapper from PowerShell and the bash Claude wrapper from Bash or Git Bash; the PowerShell wrapper accepts both `-PrintSecretPath` and `--print-secret-path`, requires `--%` before forwarded Claude flags, and the bash wrapper honors `CLAUDE_BIN` when the active shell PATH cannot see `claude`.
- External provider CLI launches use file-based prompts by default: write substantive task prompts to temporary prompt files and feed them through stdin or a provider-supported file-input mechanism instead of putting the full prompt in argv.
- If a primary Claude external run is obviously unauthenticated on the plain `claude` path, do not silently convert that run to the secret-backed wrapper. Advisory/review lanes may still reach the independent `claude-secret` candidate later in the profile order when enabled; mutating implementation, code-generation, file-editing, or publication work must not use the secret-backed transport.
- For Codex commit review, use `codex review --commit <sha>` without a free-form prompt; if custom review instructions are needed, prefer a narrower `codex exec` run on the admitted scope.
- For wide release or parity audits, split the admitted scope by repo, file set, or lane instead of launching one mega neutral-dir prompt across the whole pack family.
- Full mode tables live in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md).
- After first-time Claude project install, run `/agents-init-project` in Claude Code to write `## Project policies` in `.claude/CLAUDE.md` and review or update the installed default `.claude/.agents-mode.yaml`.
- If a repo-local lane policy explicitly asks for consultant input at closeout, it follows the configured `consultantMode`. `consultantMode: disabled` waives consultant closeout instead of blocking the batch, and any requested consultant sweep stays advisory-only rather than replacing review or human gates.
- Validation commands: `bash src.claude/agents/scripts/validate-skill-pack.sh` or `.\src.claude\agents\scripts\validate-skill-pack.ps1`.

## Gemini CLI example integration

Use `scripts/install-gemini.sh` or `scripts/install-gemini.ps1` when you want the Gemini pack directly.

| Command | Result |
| --- | --- |
| `bash scripts/install-gemini.sh --global` | Installs into `~/.gemini/` by seeding `GEMINI.md`, `AGENTS.md`, `~/.gemini/.agents-mode.yaml`, and the official extension package at `~/.gemini/extensions/orchestrarium-gemini/` |
| `bash scripts/install-gemini.sh --target /path/to/project` | Installs into the target project's `GEMINI.md`, root `AGENTS.md` when absent, `.gemini/.agents-mode.yaml`, and `.gemini/extensions/orchestrarium-gemini/` |
| `.\scripts\install-gemini.ps1 -Global` | Installs into `~/.gemini/` by seeding `GEMINI.md`, `AGENTS.md`, `~/.gemini/.agents-mode.yaml`, and the official extension package at `~/.gemini/extensions/orchestrarium-gemini/` |
| `.\scripts\install-gemini.ps1 -Target "D:\path\to\project"` | Installs into the target project's `GEMINI.md`, root `AGENTS.md` when absent, `.gemini/.agents-mode.yaml`, and `.gemini/extensions/orchestrarium-gemini/` |

Notes:

- Repository classification: `WEAK MODEL / NOT RECOMMENDED`. Gemini stays installable here as an explicit example or compatibility path, while shipped production `externalProvider: auto` routing stays on `codex | claude`.
- Project-level Gemini installs preserve any user-owned content outside the managed Orchestrarium block inside `GEMINI.md`.
- User-side `@...` imports that live in the installed `GEMINI.md` import block alongside `@./AGENTS.md` are preserved across reinstalls.
- Gemini installs materialize the shared-governance layer as `AGENTS.md`; `GEMINI.md` loads it through the official `@./AGENTS.md` import. Project installs preserve an existing root `AGENTS.md` instead of overwriting it.
- Project-level Gemini installs ensure `/.reports/` and `/work-items/` are present in the target repo `.gitignore` if they are missing, because session logs and repo-local task memory are local-only runtime output.
- Gemini installs materialize the official Gemini extension package under `.gemini/extensions/orchestrarium-gemini/` for project installs and `~/.gemini/extensions/orchestrarium-gemini/` for global installs. That extension is the canonical installed Gemini payload and carries `gemini-extension.json`, `README.md`, `GEMINI.md`, `AGENTS.md`, `skills/`, `agents/`, and `commands/`.
- To avoid precedence conflicts and noisy loader warnings, Orchestrarium does not mirror the same pack into top-level `.gemini/skills/`, `.gemini/agents/`, or `.gemini/commands/`. Those Gemini-native user/workspace tiers remain available for deliberate user overrides only.
- Reinstall cleans legacy Orchestrarium-owned duplicates from `.gemini/skills/`, `.gemini/agents/`, and `.gemini/commands/` when they would shadow the installed extension payload.
- Gemini runtime config and MCP wiring remain owned by `.gemini/settings.json` and `gemini-extension.json`; servers such as Serena, Fetch, or Context7 do not belong inside `AGENTS.md`.
- The Orchestrarium routing overlay file is `.gemini/.agents-mode.yaml` for project installs and `~/.gemini/.agents-mode.yaml` for global installs.
- Decision-driving reads should prefer `.gemini/.agents-mode.yaml`, then local legacy `.gemini/.agents-mode`, then `~/.gemini/.agents-mode.yaml`, then global legacy `~/.gemini/.agents-mode`; normalize whichever file supplied the effective config to the current canonical format in the same scope and never recreate any legacy file or synthesize a local override on read alone.
- After first-time Gemini project install, run Gemini CLI `/init` if you want Gemini to create or refresh the user-owned portion of `GEMINI.md`, and then use the Orchestrarium Gemini `init-project` helper to review or update the installed default `.gemini/.agents-mode.yaml` when you want project-specific routing choices. Keep that overlay on the example path; it is not part of the shipped production root schema.
- Validation commands: `bash src.gemini/scripts/validate-pack.sh` or `.\src.gemini\scripts\validate-pack.ps1`.

## Qwen example integration

`src.qwen/` is the native Qwen example line in this monorepo.

- Repository classification: `WEAK MODEL / NOT RECOMMENDED`. Qwen is installable for explicit example, inspection, or compatibility use, while shipped production `externalProvider: auto` routing stays on `codex | claude`.
- The root router currently exposes Qwen because matching root `scripts/install-qwen.sh` and `scripts/install-qwen.ps1` entrypoints are present in this checkout.
- If a future checkout lacks those root entrypoints, fall back to the Qwen source tree directly: `src.qwen/QWEN.md`, `src.qwen/README.md`, and `src.qwen/scripts/validate-pack.sh` or `.\src.qwen\scripts\validate-pack.ps1`.

## Multi-pack setup

To install any combination of packs into the same target project, either choose the matching option in the router or run the pack-specific installers with the same target arguments.

The current root router covers the production Codex/Claude pair plus both example integrations, Gemini and Qwen. If a future checkout lacks root `scripts/install-qwen.*`, the router drops back to the Codex/Claude production path plus Gemini only.

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
- `references-qwen/`

That split is intentional. `shared/references/` holds the canonical shared design cores, `docs/` is the common branch-level docs surface, and `references-codex/`, `references-claude/`, `references-gemini/`, and `references-qwen/` keep only pack-local addenda or compatibility pointers. `subagent-operating-model` is the main example: the installed packs keep their runtime docs, but the monorepo now keeps one shared blueprint core plus one addendum per pack instead of near-duplicate full reference copies.

## Post-install customization

Customize each platform in the place that platform actually reads:

- Codex: append project-specific rules below the installed section in the project root `AGENTS.md`.
- Claude Code: append project-specific rules below the installed section in `.claude/CLAUDE.md`.
- Claude Code: user-side `@...` imports in `.claude/CLAUDE.md` may live in the import block near `@AGENTS.md`; the installer preserves those imports on reinstall.
- Configure consultant and external-dispatch preferences in `.agents/.agents-mode.yaml` for Codex or `.claude/.agents-mode.yaml` for Claude Code.
- Shared design references in `shared/references/` are repository-maintainer documentation only; they are not copied into target projects and should not be treated as installed runtime docs.

When both packs are installed, keep shared project policies aligned across both files. The repository's dev overlays, `AGENTS.md` and `CLAUDE.md`, are for maintaining this monorepo and are not copied into target projects by the install scripts.

## Gemini example source tree in the monorepo

The monorepo still keeps the full Gemini line as a validated example source tree in addition to the root-router example path:

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

It intentionally keeps the full Gemini payload in `src.gemini/` while materializing the installed runtime as one official extension package plus the adjacent Gemini-native context files and `.agents-mode.yaml` overlay. Use Gemini's built-in `/init` for the official `GEMINI.md` bootstrap first. Orchestrarium install seeds `.gemini/.agents-mode.yaml` with the current default overlay in either the project target or `~/.gemini/`, and it materializes the canonical runtime payload under `.gemini/extensions/orchestrarium-gemini/` or `~/.gemini/extensions/orchestrarium-gemini/`; use the Orchestrarium Gemini init helper to review or update that installed default rather than replacing Gemini's official `.gemini/settings.json`. Top-level `.gemini/skills/`, `.gemini/agents/`, and `.gemini/commands/` stay reserved for deliberate user overrides and are not used as a second mirrored install target, because Gemini gives user/workspace tiers precedence over extension content. MCP wiring for servers such as Serena, Fetch, or Context7 remains a `settings.json` or `gemini-extension.json` concern. In the root integration contract, Gemini stays an explicit example path: shipped production `externalProvider: auto` routing remains on `codex | claude`, while any broader Gemini routing behavior belongs to provider-local example documentation instead of the root production schema. Full operator semantics, including task continuity and continue-by-default execution expectations, live in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md).
