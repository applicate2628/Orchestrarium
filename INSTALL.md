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
  3) Codex + Claude (default production install)
Example integrations:
  4) Gemini CLI (WEAK MODEL / NOT RECOMMENDED)
  5) Qwen (WEAK MODEL / NOT RECOMMENDED)
```

Pressing Enter selects the default production install, `Codex + Claude`. Gemini and Qwen stay explicit example-only choices and are never included in the default root install. In the current checkout, the router exposes the Qwen example slot because matching `scripts/install-qwen.*` entrypoints are present; if a future checkout lacks them, the router hides the dedicated Qwen slot.

Maintainer note for this monorepo: `Orchestrarium/` is the installer/source tree, not automatically a repo-local installed Codex runtime. When you are editing this repository itself, a missing local `.agents/` tree can be perfectly valid if you are using the global install under `~/.codex/`. If you want this repository to behave as a repo-local install target, create that state intentionally through `scripts/install-codex.*` or the root router instead of hand-writing `.agents/` files.

## Init-time preset shortcuts

After first-time project bootstrap, the provider init helpers can start from one of these preset shortcuts before writing canonical `agents-mode` keys:

- `default`
- `absolute-balance`
- `external-aggressive`
- `correctness-first`
- `power-mode`
- `max-speed`

The preset name itself is not persisted; the helper writes the resolved canonical key values instead. Full preset expansion tables live in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md), with machine-readable copies in `shared/agents-mode.presets.json`.
If the user wants the preset unchanged, the helper should write the preset-expanded `.agents-mode.yaml` directly; key-by-key fine-tuning is optional rather than mandatory.

Canonical operator-overlay output now uses `.agents-mode.yaml` on every provider line. Legacy extensionless `.agents-mode` files remain compatibility input only: decision-driving reads should resolve provider overlays in this read order (highest to lowest precedence, per-key resolution) — local `.agents-mode.yaml`, local legacy `.agents-mode`, matching pack-local global `~/.<provider>/.agents-mode.yaml`, matching pack-local global legacy `.agents-mode`, shared cross-pack global `~/.agents-mode.yaml` (alongside `~/.claude.json`, created during default global install), then built-in defaults — each key resolves to the highest layer that defines it; layers compose, they do not replace each other wholesale; normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope, and not recreate any legacy path.

**Migration semantic when shared global is introduced.** When the shared cross-pack global `~/.agents-mode.yaml` is created for the first time on an existing setup that already has pack-local globals (`~/.claude/.agents-mode.yaml`, `~/.codex/.agents-mode.yaml`), the installer fills the new shared file from `shared/agents-mode.defaults.yaml` and does **not** copy values from pre-existing pack-local globals. This is the safe default — no user customizations are destroyed — but it means operators who want to consolidate shared settings between Claude and Codex must hand-migrate common values from pack-local files into `~/.agents-mode.yaml` themselves. Subsequent `--global` installs are normalize-not-overwrite, preserving whatever values you place in the shared file.
The same rule now applies to reinstall: if an existing `.agents-mode.yaml` is older than the current shipped schema or defaults, the installer must normalize it to the current canonical form instead of preserving stale pack-owned structure verbatim.
Maintainers changing scalar keys, provider sets, priority profiles, opinion counts, or preset expansions must keep `shared/agents-mode.defaults.yaml`, `shared/agents-mode.schema.json`, `shared/agents-mode.presets.json`, and the provider init surfaces aligned; `python scripts/validate-agents-mode-contract.py --root .` checks that contract directly, the pack validators invoke it in source-mode validation, and runtime normalization reads the schema for provider/lane policy while preserving the YAML exemplar as emitted install shape. Run `python scripts/sync-agents-mode-docs.py --root . --write` to refresh generated reference/init tables and snippets after intentional schema or preset edits. For installer-path regression coverage, run `python scripts/validate-agents-mode-installers.py --root .`; it creates disposable targets under `/.scratch/`, runs the Bash installers, and verifies the emitted provider overlays.

Project repositories that use Orchestrarium task-memory closeout should keep `agent-runs.jsonl` beside each active `status.md`. The file is local task memory, not publication content; run `scripts/agent-run-ledger.* --work-item <path> init` for one-time status/ledger migration, `scripts/agent-run-ledger.* --work-item <path> append ...` to append one validated event with rollback on failure, `scripts/validate-work-item-state.* --work-item <path>` before single-item closeout, and `scripts/check-work-items-state.* --root . --stale-hours 24` before broad closeout or interruption recovery to reconcile active work items, subagent execution, artifacts, gates, and evidence.

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
- The installed Codex `AGENTS.md` is intentionally the compact universal minimum: it carries the shared governance layer plus the thin Codex runtime entrypoint, while detailed installed role behavior lives in the `skills/<role>/SKILL.md` files and the `.codex/agents/*.toml` built-in override files. Shared/provider reference docs remain source-tree maintainer canon and are not copied into target projects.
- Codex installs also seed built-in subagent overrides into `.codex/agents/default.toml`, `.codex/agents/worker.toml`, and `.codex/agents/explorer.toml` for project installs, or `~/.codex/agents/` for global installs.
- Codex installs copy `agent-run-ledger.*`, `validate-work-item-state.*`, and `check-work-items-state.*` into `.agents/skills/lead/scripts/` for project installs or `~/.codex/skills/lead/scripts/` for global installs so task-memory operators can use the helpers without the source checkout.
- Those shipped override files pin the built-in `default`, `worker`, and `explorer` subagents to `gpt-5.5` with `xhigh` reasoning effort. Reinstall refreshes stale Orchestrarium-owned templates at those paths, even when the stale model string is not the current one, but preserves files whose prompt or structure was actually customized by the user. A model-only edit in one of those pack-owned template filenames is treated as stale template drift rather than a preserved custom override; use a structurally customized file or a user-added override path when the model-only choice itself must be preserved.
- Installed Codex validation treats preserved user-added skills as warnings rather than pack metadata-budget failures. The strict metadata budget applies to Orchestrarium-owned roles and utility skills, while extra global skills remain visible as non-blocking orphan warnings.
- Project-level installs ensure `/.reports/`, `/.plans/`, and `/work-items/` are present in the target repo `.gitignore` if they are missing, because session logs and repo-local task memory are local-only runtime output.
- The Claude installer treats `agents-` as a RESERVED pack namespace in `commands/` and `skills/`: on reinstall it reclaims (removes) any target `commands/agents-*.md` file or `skills/agents-*/` directory the current pack no longer ships (a renamed/removed flow, or a stale generated skill from an older standalone-branch install — the monorepo path ships flows only as `commands/`). Non-namespaced user files are always preserved; do not author files under the `agents-` prefix. `--dry-run` prints the planned reclaim without deleting.
- Claude installs copy `agent-run-ledger.*`, `validate-work-item-state.*`, and `check-work-items-state.*` into `.claude/agents/scripts/` for project installs or `~/.claude/agents/scripts/` for global installs so task-memory operators can use the helpers without the source checkout.
- The canonical Codex-line operator file is `.agents/.agents-mode.yaml` for project installs and `~/.codex/.agents-mode.yaml` for global installs.
- For this installer monorepo itself, the absence of project-local `.agents/.agents-mode.yaml` inside `Orchestrarium/` is not automatically a bug when the maintainer is working against the global install. Ordinary reads should fall back to `~/.codex/.agents-mode.yaml` before treating the state as missing.
- First-time creation should write the full default shape with inline comments listing allowed values for each key.
- Decision-driving reads should resolve through the Codex read order (highest to lowest precedence, per-key): `.agents/.agents-mode.yaml`, local legacy `.agents/.agents-mode`, pack-local global `~/.codex/.agents-mode.yaml`, pack-local global legacy `~/.codex/.agents-mode`, shared cross-pack global `~/.agents-mode.yaml`, built-in defaults. Normalize whichever file supplied the effective config to the current canonical format in the same scope and never recreate any legacy file or synthesize a local override on read alone.
- `consultantMode` still controls `$consultant`; `delegationMode: manual` keeps explicit-permission behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation an explicit standing instruction whenever a matching specialist and viable tool path exist; `parallelMode: manual` keeps parallel fan-out explicit-by-request, `auto` leaves safe parallelism enabled by routing judgment for any independent internal or external lanes, and `force` makes safe parallel launch a standing instruction whenever scopes are independent and the merge cost is justified; `mcpMode: auto` lets the agent decide when MCP is appropriate while `force` makes MCP usage an explicit standing instruction; the two `preferExternal*` flags let routing prefer `$external-worker` and `$external-reviewer`; production `externalProvider` uses `auto | codex | claude`; `externalPriorityProfile` selects the active named provider-order profile for `auto`; `reserveResolver` binds the symbolic `reserve` slot to a concrete read-only resolver; `externalPriorityProfiles` stores the switchable per-lane provider orders; and `externalOpinionCounts` raises specific lanes above the default single-opinion behavior when one external opinion is not enough. Those counts stay lane-local distinct-opinion requirements; `parallelMode` remains the general helper fan-out rule, while bounded same-provider external helper fan-out is handled through the dedicated brigade surfaces.
- `externalProvider: auto` is lane-driven rather than host-pack-driven. It resolves through the active production priority profile documented in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md), stays on the Codex/Claude pair, and must not silently self-bounce into the same provider line. The shipped production profiles are `balanced` for the quiet default and `quality-first` for maximum result quality.
- `externalModelMode` is the shared production model policy: `runtime-default` leaves the resolved provider on its runtime default model/profile, while `pinned-top-pro` starts on the strongest documented provider-native model/profile and allows one named same-provider fallback on retryable provider exhaustion.
- `externalCodexProfile` is the Codex-specific external profile override with four values: `default` inherits `externalModelMode` after provider resolution, including under `externalProvider: auto`; `gpt-5.5-fast` selects the fast Codex model tier (model variant only — reasoning_effort still stays `xhigh`, this is not an effort downgrade) when the installed runtime supports it; `gpt-5.5-xhigh` (shipped as the default, symmetric to Claude's `opus-xhigh`) pins model `gpt-5.5` with `model_reasoning_effort = "xhigh"` regardless of `externalModelMode`; and `gpt-5.3-codex-spark` is a bounded mechanical overflow path — a fast low-reasoning Codex tier reserved for strictly-scoped fully-autonomous worker lanes to retry once after usage-limit or quota exhaustion on the primary path, never the ordinary cheaper mode for reasoning-heavy work.
- `reserve` is the advisory/review-only supplemental profile candidate after primary `claude`/`codex`. It is symbolic rather than a scalar provider key: `reserveResolver: claude-sonnet | claude-wrapper | wrapper:<command> | disabled` binds it to a concrete read-only resolver. Use `wrapper:<command>` for a PATH-resolved command or repo-relative wrapper path, and keep it out of implementation/editing fallback.
- `externalClaudeProfile` is Codex-line only and selects or overrides the Claude CLI execution profile: `sonnet-high` maps to Sonnet with `--effort high`, `opus-xhigh` (the shipped default) maps to Opus with `--effort xhigh`, and `opus-max` maps to Opus with `--effort max` (max-depth escalation for especially hard tasks at caller discretion). New Codex installs seed `opus-xhigh` by default unless a preset or explicit operator choice overrides it.
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
- Claude already uses the same split in its native shape: keep `.claude/CLAUDE.md` short and let `.claude/agents/*.md` hold the detailed role instructions and team-template routing.
- Project-level installs ensure `/.reports/`, `/.plans/`, and `/work-items/` are present in the target repo `.gitignore` if they are missing, because session logs and repo-local task memory are local-only runtime output.
- Claude memory is shipped in `src.claude/memory/` and preserved across reinstalls by the existing installer behavior.
- User-side Claude imports such as `@memory/...` are preserved across reinstalls when they live in the installed `.claude/CLAUDE.md` import block alongside `@AGENTS.md`.
- The canonical Claude-line operator file is `.claude/.agents-mode.yaml` for project installs and `~/.claude/.agents-mode.yaml` for global installs.
- First-time creation should write the full default shape with inline comments listing allowed values for each key.
- Decision-driving reads should resolve through the Claude read order (highest to lowest precedence, per-key): `.claude/.agents-mode.yaml`, local legacy `.claude/.agents-mode`, pack-local global `~/.claude/.agents-mode.yaml`, pack-local global legacy `~/.claude/.agents-mode`, shared cross-pack global `~/.agents-mode.yaml`, built-in defaults. Normalize whichever file supplied the effective config to the current canonical format in the same scope and never recreate any legacy file or synthesize a local override on read alone.
- `consultantMode` still controls `$consultant`; `delegationMode: manual` keeps explicit-permission behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation an explicit standing instruction whenever a matching specialist and viable tool path exist; `parallelMode: manual` keeps parallel fan-out explicit-by-request, `auto` leaves safe parallelism enabled by routing judgment for any independent internal or external lanes, and `force` makes safe parallel launch a standing instruction whenever scopes are independent and the merge cost is justified; `mcpMode: auto` lets the agent decide when MCP is appropriate while `force` makes MCP usage an explicit standing instruction; the two `preferExternal*` flags let routing prefer `$external-worker` and `$external-reviewer`; production `externalProvider` uses `auto | codex | claude`; and the switchable `externalPriorityProfile` / `reserveResolver` / `externalPriorityProfiles` / `externalOpinionCounts` block keeps production auto-routing on Codex plus Claude instead of hidden host-line defaults. Shipped profiles are `balanced` and `quality-first`. Those counts stay distinct-opinion requirements for one lane, while brigade surfaces cover parallel external helper multiplicity on top of the general `parallelMode` rule.
- Explicit self-provider selection is override-only; ordinary `auto` must not silently resolve back into the same host line.
- `reserveResolver` controls the concrete reserve path. `claude-wrapper` may resolve to the Claude-line wrapper surface `.claude/agents/scripts/invoke-claude-api.sh` or `.ps1`, which reads repo-local `.claude/SECRET.md` first and then `~/.claude/SECRET.md`, exports the declared `ANTHROPIC_*` environment, and then runs plain `claude`; `wrapper:<command>` may point to another approved PATH-resolved or repo-relative read-only wrapper. `externalClaudeProfile` stays Codex-line only for primary Claude CLI runs.
- Practical launch rules: use the PowerShell Claude wrapper from PowerShell and the bash Claude wrapper from Bash or Git Bash; the PowerShell wrapper accepts both `-PrintSecretPath` and `--print-secret-path`, requires `--%` before forwarded Claude flags, and the bash wrapper honors `CLAUDE_BIN` when the active shell PATH cannot see `claude`.
- External provider CLI launches use file-based prompts by default: write substantive task prompts to temporary prompt files and feed them through stdin or a provider-supported file-input mechanism instead of putting the full prompt in argv.
- If a primary Claude external run is obviously unauthenticated on the plain `claude` path, do not silently convert that run to the secret-backed wrapper. Advisory/review lanes may still reach the independent `reserve` candidate later in the profile order; mutating implementation, code-generation, file-editing, or publication work must not use the resolved `reserve` transport.
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
- Project-level Gemini installs ensure `/.reports/`, `/.plans/`, and `/work-items/` are present in the target repo `.gitignore` if they are missing, because session logs and repo-local task memory are local-only runtime output.
- Gemini installs materialize the official Gemini extension package under `.gemini/extensions/orchestrarium-gemini/` for project installs and `~/.gemini/extensions/orchestrarium-gemini/` for global installs. That extension is the canonical installed Gemini payload and carries `gemini-extension.json`, `README.md`, `GEMINI.md`, `AGENTS.md`, `skills/`, and `commands/`.
- To avoid precedence conflicts and noisy loader warnings, Orchestrarium does not mirror the same pack into top-level `.gemini/skills/`, `.gemini/agents/`, or `.gemini/commands/`. Those Gemini-native user/workspace tiers remain available for deliberate user overrides only.
- Reinstall cleans legacy Orchestrarium-owned duplicates from `.gemini/skills/`, `.gemini/agents/`, and `.gemini/commands/` when they would shadow the installed extension payload.
- Gemini runtime config and MCP wiring remain owned by `.gemini/settings.json` and `gemini-extension.json`; servers such as Serena, Fetch, or Context7 do not belong inside `AGENTS.md`.
- The Orchestrarium routing overlay file is `.gemini/.agents-mode.yaml` for project installs and `~/.gemini/.agents-mode.yaml` for global installs.
- Decision-driving reads should prefer `.gemini/.agents-mode.yaml`, then local legacy `.gemini/.agents-mode`, then `~/.gemini/.agents-mode.yaml`, then global legacy `~/.gemini/.agents-mode`, then the shared cross-pack global `~/.agents-mode.yaml`; normalize whichever file supplied the effective config to the current canonical format in the same scope and never recreate any legacy file or synthesize a local override on read alone.
- After first-time Gemini project install, run Gemini CLI `/init` if you want Gemini to create or refresh the user-owned portion of `GEMINI.md`, and then use the Orchestrarium Gemini `init-project` helper to review or update the installed default `.gemini/.agents-mode.yaml` when you want project-specific routing choices. Keep that overlay on the example path; it is not part of the shipped production root schema.
- Validation commands: `bash src.gemini/scripts/validate-pack.sh` or `.\src.gemini\scripts\validate-pack.ps1`.

## Qwen example integration

`src.qwen/` is the native Qwen example line in this monorepo.

- Repository classification: `WEAK MODEL / NOT RECOMMENDED`. Qwen is installable for explicit example, inspection, or compatibility use, while shipped production `externalProvider: auto` routing stays on `codex | claude`.
- The root router currently exposes Qwen because matching root `scripts/install-qwen.sh` and `scripts/install-qwen.ps1` entrypoints are present in this checkout.
- If a future checkout lacks those root entrypoints, fall back to the Qwen source tree directly: `src.qwen/QWEN.md`, `src.qwen/README.md`, and `src.qwen/scripts/validate-pack.sh` or `.\src.qwen\scripts\validate-pack.ps1`.
- Decision-driving reads should prefer `.qwen/.agents-mode.yaml`, then local legacy `.qwen/.agents-mode`, then `~/.qwen/.agents-mode.yaml`, then global legacy `~/.qwen/.agents-mode`, then the shared cross-pack global `~/.agents-mode.yaml`; normalize whichever file supplied the effective config to the current canonical format in the same scope and never recreate any legacy file or synthesize a local override on read alone.

## Multi-pack setup

To install any combination of packs into the same target project, either choose one explicit router option at a time or run the pack-specific installers with the same target arguments.

The current root router defaults to the production Codex/Claude pair and exposes Gemini and Qwen only as explicit example integration choices. It does not provide an "all available root installs" default because `WEAK MODEL / NOT RECOMMENDED` example providers must not be installed by default. If a future checkout lacks root `scripts/install-qwen.*`, the router drops the Qwen example choice and keeps the Codex/Claude default plus Gemini as the remaining explicit example.

Expected default project-level result:

```text
project/
  AGENTS.md
  .codex/
    agents/
    hooks.json             ← structural hook entries (PreToolUse + Stop) merged here
  .agents/
    .agents-mode.yaml
    skills/                ← role skills + common skills (e.g. windows-gui-manual-testing/, mathtype-book-page/, explain-simply/)
  .claude/
    .agents-mode.yaml
    AGENTS.md
    CLAUDE.md
    settings.json          ← structural hook entries (PreToolUse + Stop) merged here
    agents/                ← role subagent definitions + delegate-style common-skill wrappers
    commands/
    skills/                ← common skills reachable via the Skill tool from main conv and subagents
```

Explicit Gemini or Qwen example installs add their provider-native files and extension directories on top of that production baseline. Their common-skill payload is materialized under `.gemini/extensions/orchestrarium-gemini/skills/` and the equivalent Qwen extension path.

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

### Structural enforcement hooks (auto-installed)

Both Claude Code and Codex CLI expose hook surfaces; both production packs auto-install six structural hooks — three blocking backstops and three warn-only audit hooks — plus one informational `SessionStart` reminder (seven entries total):

- **PreToolUse bugfix-discipline hook** (`check-bugfix-discipline.py` plus thin `.sh`/`.ps1` wrappers): catches the model about to make a code-mutating tool call (`Edit`/`Write`/`NotebookEdit`/`apply_patch`) in response to a bug-report or change-request signal (`fix`, `change`, `broken`, `не работает`, `исправь`, `пофикси`, traceback, `Error:`), without first invoking `/agents-bugfix` or otherwise capturing diagnostic data. It reads the PreToolUse envelope's `transcript_path`, checks the current turn for discipline signals, and emits a structured deny payload when the pre-fix gate was skipped. It skips subagent contexts (envelope `agent_id` present) and exempts writes to non-code artifact paths (`.reports/`, `.scratch/`, `.plans/`, `work-items/`, `docs/`), so a report/plan/doc write under a bug-vocabulary prompt is never falsely blocked (proven on a real transcript).
- **Stop passive-polling hook** (`check-passive-polling-stop.py` plus thin `.sh`/`.ps1` wrappers): catches the model about to end its turn by saying it is waiting for an async external source (bot/review/CI/job/notification/reply) without a relevant current-turn state check. It reads `last_assistant_message` from the Stop envelope, respects `stop_hook_active=true`, exempts user handoffs like `waiting for your response` / `жду твоего подтверждения`, supports the per-stop `[acknowledge-passive-stop]` override, and otherwise requires a relevant probe such as `date`, `Get-Date`, `gh pr view`, `gh run list`, `gh api`, `curl`, process/task output, or reading an output/log/task file.
- **Stop work-items-archival hook** (`check-work-items-archival-stop.py` plus thin `.sh`/`.ps1` wrappers): catches the systemic create-but-never-close failure — a delivered or closed work-item left in `work-items/active/` instead of being archived. It reads the Stop envelope and **exits immediately when the envelope carries `agent_id`** (a subagent context — work-item lifecycle is the MAIN conversation's job, so a subagent is never blocked), respects `stop_hook_active=true`, walks up from the session cwd to the nearest `work-items/active/`, and treats an item as an orphan when it has a `closure.md`, or its `status.md` has a state/status/stage/outcome line whose value begins with a done/closed word (`closed`/`done`/`complete`/`archived`) — anchored to the state-key line (not free prose), so chatty active-item text like `nothing pending` or `phase 1 shipped + pushed` never trips it. On an orphan it emits a block payload telling the model to close the item (write `closure.md`, move to `work-items/archive/<YYYY-MM>/<slug>/`, update `index.md`) or use the per-stop `[acknowledge-open-work-items]` override. Registered ONLY on `Stop` (never `SubagentStop`); fails open. The same `agent_id` subagent-safety skip is retrofitted onto the passive-polling Stop hook so neither blocking Stop guard interferes with subagents.
- **PreToolUse machine-local-path hook** (`check-machine-local-path.py` plus thin `.sh`/`.ps1` wrappers; lives in the typed `agents/hooks/` (Claude) / `skills/lead/hooks/` (Codex) dir and imports `hook_common` from the sibling `scripts/`): a **warn-only AUDIT** hook that flags a machine-local absolute path (a concrete user home or workstation dev root; placeholders like `<you>`, `%USERPROFILE%`, `${CLAUDE_PROJECT_DIR}` are allowed) written into a non-`.scratch/` tracked file. It matches the edit's own `tool_input`, writes a UTF-8 stderr warning, and ALWAYS allows — it never blocks (promotion to a blocking `deny` is a separate reviewed step once the false-positive rate is measured), and fails open.
- **PreToolUse no-trash-in-repo hook** (`check-no-trash-in-repo.py` plus thin `.sh`/`.ps1` wrappers; same typed `hooks/` dir, registered with a `Bash`-inclusive matcher so it sees the `git worktree add` command): a **warn-only AUDIT** hook — the stray-artifact guard (filename and install-marker retained for install continuity; a rename to `check-stray-artifact` is a tracked follow-up) — that flags a Bash command confidently running `git worktree add`, the unrequested-worktree side effect. `git worktree list/remove/prune`, `git add` (not `git worktree add`), `git` inside a quoted string, and non-git commands never warn; the parser is shell-aware (shlex tokenization, command-position tracking across `&&`/`;`/`|`/`(`, env-assignment-prefix and git-global-option skipping) and fails open on any tokenizer error. This replaced a name-based version that warned only on new dirs named `kosyaks`/`mistake-log` — useless, because those are the *user's* personal-process vocabulary, not names the *agent* (the actor a PreToolUse hook guards) ever creates, so it never fired; the real reported problem was the agent creating stray artifacts, chiefly unrequested worktrees, so the guard now keys on the OPERATION. Deferred: the Claude `Agent` tool's `isolation: "worktree"` form. Dropped: outside-repo writes (allow-list FP-floods) and arbitrary in-repo trash (no reliable non-name signal). Matches its own `tool_input`, writes a UTF-8 stderr warning, ALWAYS allows, and fails open.
- **PreToolUse stale-relation-residue hook** (`check-stale-relation-residue.py` plus thin `.sh`/`.ps1` wrappers; same typed `hooks/` dir): a **warn-only AUDIT** hook — the structural backstop for architecture law C6 ("a superseding change leaves only the correct current state") — that flags an `Edit`/`Write` ADDING a stale-relation residue phrase (`deprecated alias`, `former alias`/`former name`, `(was X)`/`(formerly X)` parentheticals, `misregistered as`, arrow+alias, "is wrong, the correct is") into a LIVE-tree file. For diff/apply_patch payloads it scans ONLY added lines (erasing residue never warns). Exempt: provenance surfaces (`work-items/`, changelogs/release notes, `/archive/`+`/legacy/` trees, `.scratch/`, `.git/`) where recording a superseded relation IS the point. The stale-vs-live discriminator is review-bound, so it ALWAYS allows and fails open.
- **SessionStart MCP-usage reminder** (`mcp-usage-reminder.sh` / `.ps1`): informational context injection at startup/resume/compaction. It does not block, but it makes MCP/tool-discovery a visible checkpoint for codebase, architecture, API/docs, search, browser, debugger, profiler, and repository-understanding tasks; under `mcpMode: force`, relevant MCP use remains a standing instruction.

**The production installers auto-register all six entries by default** in both `--global` and `--target <project>` modes via an idempotent JSON merge that preserves all your other settings and hooks:

- Claude Code installer merges the hook entry into `~/.claude/settings.json` (`--global`) or `<project>/.claude/settings.json` (`--target`).
- Codex CLI installer merges the hook entry into `~/.codex/hooks.json` (`--global`) or `<project>/.codex/hooks.json` (`--target`).
- Gemini and Qwen example installers copy the same universal hook/helper scripts into their installed extension roots (`<install-root>/extensions/<pack>/scripts/` and `hooks/`). If the provider runtime exposes compatible native hook wiring, those scripts are the canonical backstop payload; otherwise they remain installed helper surfaces for manual or wrapper-driven checks instead of disappearing from the pack.
- Compatible non-Codex/Claude wrappers can use `scripts/install-hypothesis-hook.py --platform generic` to emit the provider-neutral exec-form JSON entry; runtimes with a different native schema should adapt from the installed universal hook/helper payload rather than forking the hook logic.

Opt out at install time with:

- `bash scripts/install-claude.sh --global --no-hypothesis-hook` (or `-NoHypothesisHook` on PowerShell)
- `bash scripts/install-codex.sh --global --no-hypothesis-hook` (or `-NoHypothesisHook` on PowerShell)
- Set `ORCHESTRARIUM_NO_HYPOTHESIS_HOOK=1` in the environment before running any installer

(The flag and env-var names retain the legacy "hypothesis-hook" prefix for back-compat with operators who already scripted them; the hook itself is now the bugfix-discipline guard.)

To remove already-installed hook entries without uninstalling the pack:

```bash
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.codex/hooks.json --platform codex --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-marker check-machine-local-path --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.codex/hooks.json --platform codex --script-marker check-machine-local-path --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-marker check-no-trash-in-repo --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.codex/hooks.json --platform codex --script-marker check-no-trash-in-repo --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --hook-event Stop --script-marker check-passive-polling-stop --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.codex/hooks.json --platform codex --hook-event Stop --script-marker check-passive-polling-stop --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --hook-event Stop --script-marker check-work-items-archival-stop --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.codex/hooks.json --platform codex --hook-event Stop --script-marker check-work-items-archival-stop --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --hook-event SessionStart --script-marker mcp-usage-reminder --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.codex/hooks.json --platform codex --hook-event SessionStart --script-marker mcp-usage-reminder --script-path "" --remove
```

Entries are identified independently by script marker: `check-bugfix-discipline`, `check-machine-local-path`, and `check-no-trash-in-repo` for `PreToolUse`, `check-passive-polling-stop` and `check-work-items-archival-stop` for `Stop`, and `mcp-usage-reminder` for `SessionStart`. Re-running the installer is idempotent: it finds each entry by marker and updates it in place rather than appending duplicates. **Scope of preservation:** the merge preserves every part of the file outside our entries — your other hooks and top-level user keys (env, attribution, permissions, enabledPlugins, model, theme) survive. **Scope of overwrite:** the merge does NOT preserve hand-edits inside our entries' `command`/`args` fields; reinstall normalizes matched entries back to canonical form. To preserve manual overrides, pass `--no-hypothesis-hook` (PowerShell: `-NoHypothesisHook`) on every future install or set `ORCHESTRARIUM_NO_HYPOTHESIS_HOOK=1`; the opt-out does not block `--remove`.

**Per-event overrides (no install change).** For a non-bug code edit whose user message happens to contain a bug-trigger word (e.g. "fix this typo" — really a docs edit), put `[skip-bugfix-discipline]` in your assistant message acknowledging the override; the PreToolUse guard pulls back for the next turn only. For a legitimate Stop handoff that uses waiting language, include `[acknowledge-passive-stop]` in that final assistant message; the passive-polling Stop guard pulls back for that stop only. For an intentionally-left-open closed work-item (e.g. `closure.md` written but the archive move deferred for a stated reason), include `[acknowledge-open-work-items]` in that final assistant message; the work-items-archival Stop guard pulls back for that stop only.

**Codex-specific note: manual trust step required after install.** Codex marks every newly-installed or modified hook as "untrusted" by design; all six entries are written to `hooks.json` but do not fire until you run `codex` interactively and trust them via the TUI. This is Codex's security model, not a limitation of the installer — Codex does not currently expose a programmatic trust API. After install: run `codex` once, open the hook browser (typically via the keystroke shown next to "Trust to view hooks; to trust"), and trust all six entries: the five structural/audit entries plus `mcp-usage-reminder`. Claude Code does not require this step — Claude hooks fire immediately after install.

**Codex+Windows note: PowerShell shell form.** Codex hook entries on Windows use `powershell.exe -NoProfile -ExecutionPolicy Bypass -File '<abs-path>\<script>.ps1'`. Explicit `powershell.exe` avoids a Windows PATH gotcha: on machines with WSL installed alongside Git Bash, `bash` may resolve to `C:\Windows\System32\bash.exe` (the WSL launcher) instead of Git Bash; WSL bash cannot resolve `C:\Users\...` paths and the entry silently failed on every Bash tool call. PowerShell.exe is unambiguous.

Gemini and Qwen remain example-only provider lines, but the universal hook/helper payload is still installed with them. The Bootstrap text rule in the merged `AGENTS.md` remains binding on all platforms regardless of whether a provider runtime can auto-trigger the installed scripts.

When both packs are installed, keep shared project policies aligned across both files. The repository's dev overlays, `AGENTS.md` and `CLAUDE.md`, are for maintaining this monorepo and are not copied into target projects by the install scripts.

## Gemini example source tree in the monorepo

The monorepo still keeps the full Gemini line as a validated example source tree in addition to the root-router example path:

- runtime entrypoint: `src.gemini/GEMINI.md`
- shared-governance source: `shared/AGENTS.shared.md`
- branch-level docs entrypoint: `docs/README.md`
- built-in initialization: Gemini CLI `/init` writes or tailors the project `GEMINI.md`
- expertise layer: `src.gemini/skills/<name>/SKILL.md`
- repo-local team templates: `src.gemini/skills/lead/team-templates/*.json`
- custom commands: `src.gemini/commands/**/*.toml`
- official runtime config: project `.gemini/settings.json`
- Orchestrarium operator overlay: project `.gemini/.agents-mode.yaml`
- installed extension manifest source: `src.gemini/extension/gemini-extension.json`
- provider-local reference tree: `references-gemini/`
- validation commands: `bash src.gemini/scripts/validate-pack.sh` or `.\src.gemini\scripts\validate-pack.ps1`
- Orchestrarium overlay bootstrap: `src.gemini/commands/agents/init-project.toml` and `src.gemini/skills/init-project/SKILL.md`

It intentionally keeps the full Gemini payload in `src.gemini/` while materializing the installed runtime as one official extension package plus the adjacent Gemini-native context files and `.agents-mode.yaml` overlay. Use Gemini's built-in `/init` for the official `GEMINI.md` bootstrap first. Orchestrarium install seeds `.gemini/.agents-mode.yaml` with the current default overlay in either the project target or `~/.gemini/`, and it materializes the canonical runtime payload under `.gemini/extensions/orchestrarium-gemini/` or `~/.gemini/extensions/orchestrarium-gemini/`; use the Orchestrarium Gemini init helper to review or update that installed default rather than replacing Gemini's official `.gemini/settings.json`. Top-level `.gemini/skills/`, `.gemini/agents/`, and `.gemini/commands/` stay reserved for deliberate user overrides and are not used as a second mirrored install target, because Gemini gives user/workspace tiers precedence over extension content. MCP wiring for servers such as Serena, Fetch, or Context7 remains a `settings.json` or `gemini-extension.json` concern. In the root integration contract, Gemini stays an explicit example path: shipped production `externalProvider: auto` routing remains on `codex | claude`, while any broader Gemini routing behavior belongs to provider-local example documentation instead of the root production schema. Full operator semantics, including task continuity and continue-by-default execution expectations, live in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md).

## Terms and Abbreviations

- `AGENTS.md`: agent governance file installed for Codex and materialized as a shared-governance module for example providers.
- `agent-run-ledger.*`: helper script family that initializes legacy work-item ledger files and appends validated `agent-runs.jsonl` events.
- `agents-mode`: Orchestrarium YAML overlay that records delegation, provider, consultant, parallelism, MCP, and workdir preferences.
- `agent-runs.jsonl`: JSONL execution ledger stored beside `status.md` for machine-readable work-item state.
- `check-work-items-state.*`: helper script family that checks every active work item under a repository root.
- `Claude Code`: Anthropic's Claude runtime and production provider line.
- `Codex`: OpenAI Codex runtime and production provider line.
- `externalProvider: auto`: production routing mode that stays on `codex | claude` in shipped defaults.
- `evidence`: concrete verification data such as a command result, artifact path, review result, log summary, or observed output supporting a gate.
- `Gemini`: Google Gemini CLI provider line, installable here only as an explicit example or compatibility path.
- `global install`: install into a user-level provider runtime root such as `~/.codex/` or `~/.claude/`.
- `JSON`: JavaScript Object Notation; structured data format used here for machine-readable contract files.
- `JSONL`: JSON Lines; one JSON object per line, used here for append-only execution events.
- `ledger`: append-only record of agent runs, gates, artifacts, and evidence for a work item.
- `MCP`: Model Context Protocol; provider/runtime mechanism for tool and resource servers.
- `power-mode`: init-time preset for hardest tasks where maximum useful result matters more than latency; starts from the `quality-first` provider-order profile.
- `Qwen`: Qwen provider line, installable here only as an explicit example or compatibility path.
- `runtime`: installed provider-facing files and directories read by the provider tool.
- `schema`: structured contract describing allowed keys, values, defaults, provider sets, and routing shapes.
- `stdin`: standard input stream used by CLIs and wrappers.
- `status.md`: human-readable recovery summary for the active work item.
- `WEAK MODEL / NOT RECOMMENDED`: repository classification for example-only provider integrations that are excluded from default installs and production `auto` routing.
