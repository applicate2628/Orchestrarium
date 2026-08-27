# Installation

This monorepo ships a Python-owned root installer (`install.py`) plus the thin POSIX launcher `install.sh`. They offer the supported Codex and Claude Code packs, then forward arguments to the matching pack-specific installers in the `scripts/` directory.

The Codex installer materializes all 17 manifest native-role TOMLs through the create-only role path and registers each exact name/description/file mapping in `.codex/config.toml`; this includes the Luna corridor roles. Luna has zero decision authority: when its feature is enabled and the caller supplies a valid exact plan, `resolve_role_dispatch` returns `native-required`; disabled state returns `E_NATIVE_V2_DISABLED`. It requires exact `gpt-5.6-luna` with `high` as the default and minimum, allowing only `high`, `xhigh`, or `max`; host rejection is the nonauthorizing `E_LUNA_UNAVAILABLE` handoff. Hash-pinned prior working or currently-disabled stock role payloads are the sole current-role upgrade exception; customized payloads fail closed. An exact pre-existing role or config mapping is retained, while a differing user-owned payload or same-name mapping is preserved and makes the install fail. These roles are native shared-policy corridors, not agents-mode or external-provider settings. Dispatch callers consume the policy-only `resolve_role_dispatch` contract before considering native launch; host outcomes are not replayed and no fallback exists.

## Quick install

Run the router installer from the repository root:

For global installs, POSIX uses `HOME` (or `USERPROFILE` when it is present); Windows requires `USERPROFILE` and does not fall back to `HOME`.

```bash
bash install.sh --global
```

```powershell
python .\install.py --global
```

Or install into a specific project:

```bash
bash install.sh --target /path/to/project
```

```powershell
python .\install.py --target "D:\path\to\project"
```

The router asks which pack to install:

```text
What to install?
Production installs:
  1) Codex pack
  2) Claude Code
  3) Codex + Claude (default production install)
```

Pressing Enter selects the default production install, `Codex + Claude`.

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

Project repositories that use Orchestrarium task-memory closeout should keep `agent-runs.jsonl` beside each active `status.md`. The file is local task memory, not publication content; run `scripts/agent-run-ledger.* --work-item <path> init` for one-time status/ledger migration, `scripts/agent-run-ledger.* --work-item <path> append ...` to append one validated event with rollback on failure, `scripts/validate-work-item-state.* --work-item <path>` before single-item closeout, and `scripts/check-work-items-state.* --root . --stale-hours 24` before broad closeout or interruption recovery to reconcile active work items, subagent execution, artifacts, gates, and evidence. The sole invalid-closure recovery procedure is in [docs/work-item-execution-tracking.md](docs/work-item-execution-tracking.md); this installation guide does not duplicate it.

## Codex install details

Use `python scripts/install-codex.py` or its thin POSIX launcher `scripts/install-codex.sh` when you want the Codex pack directly.

| Command | Result |
| --- | --- |
| `bash scripts/install-codex.sh --global` | Installs into `~/.codex/` |
| `bash scripts/install-codex.sh --target /path/to/project` | Installs into the target project's `.agents/skills/` and merges root `AGENTS.md` |
| `python .\scripts\install-codex.py --global` | Installs into `~/.codex/` |
| `python .\scripts\install-codex.py --target "D:\path\to\project"` | Installs into the target project's `.agents/skills/` and merges root `AGENTS.md` |

Notes:

- Project-level Codex installs use `.agents/skills/` plus the project root `AGENTS.md`.
- The installed Codex `AGENTS.md` is intentionally the compact universal minimum: it carries the shared governance layer plus the thin Codex runtime entrypoint, while detailed installed role behavior lives in the `skills/<role>/SKILL.md` files. Shared/provider reference docs remain source-tree maintainer canon and are not copied into target projects.
- Codex installs create only absent native role TOMLs under `.codex/agents/`; the source manifest validates all 17 current payloads and is never installed as an ownership receipt. Identical regular files are no-ops. Five hash-pinned stock role payload upgrades are the sole current-role exception; customized payloads fail closed, while other changed bytes, type collisions, and reparse points fail without mutation. The same manifest drives `[agents.<name>]` config registration: exact mappings no-op, absent mappings append deterministically, and same-name field/shape collisions fail without changing config. Every unrelated config byte/comment/key and `agents.max_concurrent_threads_per_session` is preserved; an absent config receives `[features] multi_agent_v2 = true` plus every mapping. The exact frozen `agents.luna_mechanical` mapping is the sole other 1.x migration exception: it is removed only with a missing legacy file or the exact hash-pinned `agents/luna-mechanical.toml`; any differing mapping/file fails closed and remains. All config and legacy changes share the installer transaction and rollback. Other adoption, update, deletion, and reclaim remain 2.0 work.
- Codex hook inventory authority is exactly `codex-hook-inventory.json` beside the final ordinary `hooks.json` storage file. An ordinary selected file remains unchanged; a selected file symlink and any directory symlink or junction components in its referent path are preserved and resolved through one bounded component walk. Every supported link/junction identity, kind, and raw target plus the resolved file, real parent, and ordinary inventory are bound against later retargeting or drift. Dangling components, directory leaf targets, link cycles, opaque unsupported reparse points, alternate inventory names or locations, and inventory links remain rejected. Hook-health failures use a strict 4,096-byte internal envelope and the two health-owned failure identifiers, while successful health output is temporary-file-backed and replayed byte-for-byte without a semantic size ceiling. Failed installs continue every independent rollback action, preserve the original typed cause, remove disposable backups after successful restoration, and report a retained recovery directory when snapshot restoration cannot complete.
- Codex installs copy `agent-run-ledger.*`, `validate-work-item-state.*`, and `check-work-items-state.*` into `.agents/skills/lead/scripts/` for project installs or `$HOME/.agents/skills/lead/scripts/` for global installs so task-memory operators can use the helpers without the source checkout.
- On reinstall, Codex native roles remain create-only: absent roles are created, byte-identical files and exact config mappings are no-ops, and five hash-pinned stock role payload upgrades may replace only their exact recognized prior bytes. Customized payloads fail closed; every other differing existing role or same-name mapping is preserved while the install fails. Apart from those five upgrades and the single frozen `luna_mechanical` migration above, there is no installed receipt, historical adoption, update, deletion, or reclaim authority in 1.x.
- Installed Codex validation treats preserved user-added skills as warnings rather than pack metadata-budget failures. The strict metadata budget applies to Orchestrarium-owned roles and utility skills, while extra global skills remain visible as non-blocking orphan warnings.
- The Claude installer treats `agents-` as a RESERVED pack namespace in `commands/` and `skills/`: on reinstall it reclaims (removes) any target `commands/agents-*.md` file or `skills/agents-*/` directory the current pack no longer ships (a renamed/removed flow, or a stale generated skill from an older standalone-branch install — the monorepo path ships flows only as `commands/`). Non-namespaced user files are always preserved; do not author files under the `agents-` prefix. `--dry-run` prints the planned reclaim without deleting.
- Claude installs copy `agent-run-ledger.*`, `validate-work-item-state.*`, and `check-work-items-state.*` into `.claude/agents/scripts/` for project installs or `~/.claude/agents/scripts/` for global installs so task-memory operators can use the helpers without the source checkout.
- Both production installers also copy the pure Version 3 (V3) solution-attempt reducer to `solution_attempt/reducer.py` and the bounded process owner to `process_supervision/process_runner.py` below that provider's installed scripts directory. Process Runner Version 1 (`ProcessRunnerV1`) is active only for provider-prompt operations, skill-pack validator child checks, and detached Slice A validation; all other subprocess paths are unchanged. These three consumer families use bounded output capture and descendant-process-tree settlement. On Windows, Python and Git children require runner-owned, executable-specific, same-run probes; adapters cannot supply their own attestation. Native Codex and Claude launches fail early with a typed unavailable result on Windows, while POSIX Codex and Claude launches are active. Kimi is an explicit-only, policy-admitted read-only exploration, research, planning, or review route through fixed `kimi-code/k3` with no tools or subagents; it is independently verified, nonauthorizing, and never in `auto`. Grok remains unavailable in 1.x. The generic Windows command-line interface remains fail-closed unavailable, and a Rust implementation remains deferred to 2.0. The installers do not copy the source-only durable operation store at `scripts/agent_run_persistence/operation_store.py` or route activation registry at `scripts/process_supervision/route_activation_registry.py`.
- A missing global Windows Kimi binding can be created without reinstalling the pack, and an exact binding can be confirmed without rewriting it: run `python "$HOME\.agents\skills\lead\scripts\invoke-kimi-prompt.py" --enroll-executable`, then check it with the read-only `--verify-enrollment` mode. Both modes stop before provider launch and leave Kimi authentication entirely to Kimi Code CLI. Enrollment uses only the fixed `%USERPROFILE%\.kimi-code\bin\kimi.exe` release identity, writes the path/size/SHA-256 pin atomically, no-ops on an exact replay, and refuses a different existing pin as drift. A missing or malformed binding error prints the exact installed wrapper enrollment command; malformed state or release drift still requires an explicit replacement workflow rather than silently trusting `PATH`, `KIMI_BIN`, or a changed binary.
- The canonical Codex-line operator file is `.agents/.agents-mode.yaml` for project installs and `~/.codex/.agents-mode.yaml` for global installs.
- For this installer monorepo itself, the absence of project-local `.agents/.agents-mode.yaml` inside `Orchestrarium/` is not automatically a bug when the maintainer is working against the global install. Ordinary reads should fall back to `~/.codex/.agents-mode.yaml` before treating the state as missing.
- First-time creation should write the full default shape with inline comments listing allowed values for each key.
- Decision-driving reads should resolve through the Codex read order (highest to lowest precedence, per-key): `.agents/.agents-mode.yaml`, local legacy `.agents/.agents-mode`, pack-local global `~/.codex/.agents-mode.yaml`, pack-local global legacy `~/.codex/.agents-mode`, shared cross-pack global `~/.agents-mode.yaml`, built-in defaults. Normalize whichever file supplied the effective config to the current canonical format in the same scope and never recreate any legacy file or synthesize a local override on read alone.
- `externalProvider: auto` is lane-driven rather than host-pack-driven. It resolves through the active production priority profile documented in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md), stays on the Codex/Claude pair, and must not silently self-bounce into the same provider line. The shipped production profiles are `balanced` for the quiet default and `quality-first` for maximum result quality.
- The external-prompt governance capsule is canon at `shared/external-prompt-governance.md` and is projected to installed wrapper directories as `scripts/external-prompt-governance.md`; do not replace that projection with a raw provider-prompt policy copy.
- `externalModelMode` is the shared production model policy: `runtime-default` leaves the resolved provider on its runtime default model/profile, while `pinned-top-pro` starts on the strongest documented provider-native model/profile and allows one named same-provider fallback on retryable provider exhaustion.
- `externalCodexProfile` is the Codex-specific external profile override with four values: `default` inherits `externalModelMode` after provider resolution, including under `externalProvider: auto`; `gpt-5.6-sol-xhigh` (shipped as the default, symmetric to Claude's `opus-xhigh`) pins model `gpt-5.6-sol` with `model_reasoning_effort = "xhigh"` regardless of `externalModelMode`; `gpt-5.6-sol-max` requests model `gpt-5.6-sol` with `model_reasoning_effort = "max"` for higher-complexity/hard lanes (NOT `gpt-5.6-sol-ultra`, which spawns subagents and must never be shipped on a subagent lane); and `gpt-5.6-terra` selects the balanced Codex model (a distinct model, `model_reasoning_effort = "high"`, not an effort suffix) — a genuine cheaper-and-faster-than-`gpt-5.6-sol-xhigh` reasoning lane, verified against the installed runtime before use and review-gated like any external lane; it replaces the former `gpt-5.5-fast` and `gpt-5.3-codex-spark` values.
- `reserve` is the advisory/review-only supplemental profile candidate after primary `claude`/`codex`. It is symbolic rather than a scalar provider key: `reserveResolver: claude-sonnet | claude-wrapper | wrapper:<command> | disabled` binds it to a concrete read-only resolver. Use `wrapper:<command>` for a PATH-resolved command or repo-relative wrapper path, and keep it out of implementation/editing fallback.
- `externalClaudeProfile` is Codex-line only and selects or overrides the Claude CLI execution profile: `sonnet-high` maps to Sonnet with `--effort high`, `opus-xhigh` (the shipped default) maps to Opus with `--effort xhigh`, `opus-max` maps to Opus with `--effort max` (max-depth escalation for especially hard tasks at caller discretion), and `fable-xhigh` maps to Fable with `--effort xhigh` (the current Claude flagship-family best-effort tier; the `fable` flagship alias as of 2026-07). New Codex installs seed `opus-xhigh` by default unless a preset or explicit operator choice overrides it.
- Full mode tables live in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md).
- After first-time Codex project install, run `$init-project` in Codex to write `## Project policies` to the root `AGENTS.md` and review or update the installed default `.agents/.agents-mode.yaml`.
- If a repo-local lane policy explicitly asks for consultant input at closeout, it follows the configured `consultantMode`. `consultantMode: disabled` waives consultant closeout instead of blocking the batch, and any requested consultant sweep stays advisory-only rather than replacing review or human gates.
- The design-panel technique installs as `$HOME/.agents/skills/design-panel/` (global) or `<project>/.agents/skills/design-panel/` (project), source `src.codex/skills/design-panel/`. No dedicated panel-state validator is installed; the pack validator checks only file presence and invariant markers (`DP1`-`DP8`).
- Validation commands: `python src.codex/skills/lead/scripts/validate-skill-pack.py` or its POSIX launcher `bash src.codex/skills/lead/scripts/validate-skill-pack.sh`.

## Claude Code install details

Use `python scripts/install-claude.py` or its thin POSIX launcher `scripts/install-claude.sh` when you want the Claude Code pack directly.

| Command | Result |
| --- | --- |
| `bash scripts/install-claude.sh --global` | Installs into `~/.claude/` |
| `bash scripts/install-claude.sh --target /path/to/project` | Installs into the target project's `.claude/` |
| `python .\scripts\install-claude.py --global` | Installs into `~/.claude/` |
| `python .\scripts\install-claude.py --target "D:\path\to\project"` | Installs into the target project's `.claude/` |

Notes:

- Project-level Claude installs create or update `.claude/AGENTS.md` and `.claude/CLAUDE.md`.
- Claude keeps `.claude/CLAUDE.md` short. Leaf role instructions remain under `.claude/agents/*.md`, with five curated exceptions whose canonical contracts live at `.claude/skills/<role>/SKILL.md`: `lead` is selected as the main agent only when Claude resolves `settings.json.agent: lead` or the operator supplies `--agent lead`; its documented `initialPrompt: /lead` loads the inline Lead contract, while a stale `subagent_type: lead` dispatch still fails closed. The four duals `product-manager`, `analyst`, `architect`, `planner` each keep a thin delegate wrapper that loads the same-named skill.
- User-side Claude imports (for example `@my-notes.md`) are preserved across reinstalls when they live in the installed `.claude/CLAUDE.md` import block alongside `@AGENTS.md`.
- The canonical Claude-line operator file is `.claude/.agents-mode.yaml` for project installs and `~/.claude/.agents-mode.yaml` for global installs.
- First-time creation should write the full default shape with inline comments listing allowed values for each key.
- Decision-driving reads should resolve through the Claude read order (highest to lowest precedence, per-key): `.claude/.agents-mode.yaml`, local legacy `.claude/.agents-mode`, pack-local global `~/.claude/.agents-mode.yaml`, pack-local global legacy `~/.claude/.agents-mode`, shared cross-pack global `~/.agents-mode.yaml`, built-in defaults. Normalize whichever file supplied the effective config to the current canonical format in the same scope and never recreate any legacy file or synthesize a local override on read alone.
- On a Claude install, `delegationMode: force` writes `settings.json.agent: "lead"` only when that scalar is absent. An existing `lead` remains unchanged; an explicit non-Lead scalar remains unchanged and emits `WARN: Claude main agent preserved; force lead binding not installed`. `auto`, `manual`, and unresolved mode preserve the scalar. Managed/project settings and explicit `--agent` are higher-precedence Claude choices and are never rewritten; use a new session or explicit `--agent lead` for an existing session created under another selection.
- Explicit self-provider selection is override-only; ordinary `auto` must not silently resolve back into the same host line.
- `reserveResolver` controls the concrete reserve path. `claude-wrapper` resolves to the Python-owned Claude-line transport `.claude/agents/scripts/invoke-claude-api.py` (also exposed through its thin POSIX launcher), which reads repo-local `.claude/SECRET.md` first and then `~/.claude/SECRET.md`, exports the declared `ANTHROPIC_*` environment, and then runs plain `claude`; `wrapper:<command>` may point to another approved PATH-resolved or repo-relative read-only wrapper — "approved" means exactly the layer-provenance trust gate: the value is defined (or identically confirmed) at a user-global config layer (`~/.claude/.agents-mode.yaml`, its legacy sibling, or `~/.agents-mode.yaml`); a `wrapper:<command>` supplied only by a project-local `.agents-mode.yaml` (which a cloned repository can ship) resolves as `reserveResolverTrust: project-UNCONFIRMED` per `scripts/resolve-agents-mode.py` and must not be launched before explicit first-use user confirmation, recorded durably by writing the approved value into a user-global layer. `externalClaudeProfile` stays Codex-line only for primary Claude CLI runs.
- Practical launch rules: use `python .claude/agents/scripts/invoke-claude-api.py` on every host, or the Bash launcher on POSIX/Git Bash. The Python transport accepts `--print-secret-path`, forwards Claude flags unchanged, preserves the provider exit code, and honors `CLAUDE_BIN` when the active environment cannot see `claude`.
- External provider CLI launches use file-based prompts by default: write substantive task prompts to temporary prompt files and feed them through stdin or a provider-supported file-input mechanism instead of putting the full prompt in argv.
- If a primary Claude external run is obviously unauthenticated on the plain `claude` path, do not silently convert that run to the secret-backed wrapper. Advisory/review lanes may still reach the independent `reserve` candidate later in the profile order; mutating implementation, code-generation, file-editing, or publication work must not use the resolved `reserve` transport.
- For Codex commit review, use `codex review --commit <sha>` without a free-form prompt; if custom review instructions are needed, prefer a narrower `codex exec` run on the admitted scope.
- For wide release or parity audits, split the admitted scope by repo, file set, or lane instead of launching one mega neutral-dir prompt across the whole pack family.
- Full mode tables live in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md).
- After first-time Claude project install, run `/agents-init-project` in Claude Code to write `## Project policies` in `.claude/CLAUDE.md` and review or update the installed default `.claude/.agents-mode.yaml`.
- If a repo-local lane policy explicitly asks for consultant input at closeout, it follows the configured `consultantMode`. `consultantMode: disabled` waives consultant closeout instead of blocking the batch, and any requested consultant sweep stays advisory-only rather than replacing review or human gates.
- The design-panel technique installs as `~/.claude/agents/contracts/design-panel.md` + `~/.claude/commands/agents-design-panel.md` (global) or the `<project>/.claude/` equivalents (project), source `src.claude/agents/contracts/design-panel.md` + `src.claude/commands/agents-design-panel.md`. No dedicated panel-state validator is installed; the pack validator checks only file presence and invariant markers (`DP1`-`DP8`).
- Validation commands: `python src.claude/agents/scripts/validate-skill-pack.py` or its POSIX launcher `bash src.claude/agents/scripts/validate-skill-pack.sh`.

## Multi-pack setup

To install both supported packs into the same target project, select the default `Codex + Claude` router option or run the two pack-specific installers with the same target arguments.

Expected default project-level result:

```text
project/
  AGENTS.md
  .codex/
    agents/
    hooks.json             ← hook entries (PreToolUse + Stop + SessionStart) merged here
  .agents/
    .agents-mode.yaml
    skills/                ← role skills + common skills (e.g. windows-gui-manual-testing/, mathtype-book-page/, explain-simply/)
  .claude/
    .agents-mode.yaml
    AGENTS.md
    CLAUDE.md
    settings.json          ← hook entries plus conditional force-mode `agent: lead` default merged here
    agents/                ← leaf-role subagents + dual-safe Lead main-agent definition + delegate-style common-skill wrappers
    commands/
    skills/                ← inline /lead orchestration skill + common skills reachable from main conv and subagents
```

Reference directories are development-only and are not installed:

- `shared/references/`
- `docs/`
- `references-codex/`
- `references-claude/`


## Post-install customization

Customize each platform in the place that platform actually reads:

- Codex: append project-specific rules below the installed section in the project root `AGENTS.md`.
- Claude Code: append project-specific rules below the installed section in `.claude/CLAUDE.md`.
- Claude Code: user-side `@...` imports in `.claude/CLAUDE.md` may live in the import block near `@AGENTS.md`; the installer preserves those imports on reinstall.
- Configure consultant and external-dispatch preferences in `.agents/.agents-mode.yaml` for Codex or `.claude/.agents-mode.yaml` for Claude Code.
- Shared design references in `shared/references/` are repository-maintainer documentation only; they are not copied into target projects and should not be treated as installed runtime docs.

### Structural enforcement hooks (auto-installed)

Both Claude Code and Codex CLI expose hook surfaces. The archival Stop adapter is retired and is neither registered nor installed. The retained production surfaces contain twelve Codex entries and thirteen Claude entries (the same twelve plus Claude-only typed routing); upgrade removes only the obsolete adapter/registration and preserves every retained registration identity.

The production hook runtime is direct Python on every platform. During installation, `resolve_hook_target` obtains the absolute interpreter path from that installer process's `sys.executable`. Before any registration mutation, the installer checks every owned hook: the interpreter and `.py` target must be absolute regular files; on Windows the interpreter must be a non-reparse `.exe`, and on POSIX it must have execute permission. The later health gate actually launches every registered hook. A missing or invalid interpreter or target therefore fails the install loudly instead of leaving a registration that never fires. The serialized Claude Code entry is an executable plus argument array; the Codex Windows entry is the verified `cmd.exe`/PowerShell-compatible unquoted absolute interpreter followed by the unquoted absolute `.py` path. Windows paths containing whitespace or command metacharacters are rejected rather than registered in an unverified shape.

Upgrade ordering is fixed: **SYNC → REGISTER → VERIFY → RECLAIM**. Reclaim cannot run unless `scripts/check-hook-health.py` first verifies every registered executable and target. Its hash-gated retired-file manifest removes only exact last-pack-owned hook shell or PowerShell files; customized copies are preserved. Reclaim is last, idempotent, and dry-run-visible.

For a later global upgrade, a lead runs Claude Code first, verifies the direct-Python registration, then installs and checks hook health:

#### Claude Code Python workflow

```powershell
python .\scripts\install-claude.py --global --dry-run
python .\scripts\install-claude.py --global
python scripts/check-hook-health.py --verify-fires
```

Then run Codex and verify its direct-Python registration:

#### Codex Python workflow

```powershell
python .\scripts\install-codex.py --global --dry-run
python .\scripts\install-codex.py --global
codex
python scripts/check-hook-health.py --verify-fires
```

#### Codex Bash workflow

The equivalent Bash or Git Bash Codex workflow is:

```bash
bash scripts/install-codex.sh --global --dry-run
bash scripts/install-codex.sh --global
codex
python scripts/check-hook-health.py --verify-fires
```

#### Codex manual trust step

After reinstall, start interactive `codex` — not `codex exec` — and choose **Trust all and continue** for all 12 affected entries.
Do not press Esc and do not choose **`Continue without trusting`**, because all hooks and guards remain installed but inactive.
`codex exec` silently skips untrusted hook entries instead of showing the trust prompt, so interactive `codex` must run first.
The trust modal does not time out and the operator must review all 12 entries before making the explicit choice.

#### Hook implementation

Production installers accept only the direct-Python hook runtime. The retained `.sh` files are manual POSIX launchers for source and installed non-hook commands; they are not a second hook-registration profile.

The production Codex and Claude Code installs also project the sole normative English source `shared/references/ui-transition-continuity.md` into one neutral leaf, `contracts/ui-transition-continuity.md`, at the effective pack root. Codex global installs use `$HOME/.agents/contracts/`, and Codex project installs use `<repo>/.agents/contracts/`; installed `skills/<role>/SKILL.md` files refer to it as `../../contracts/ui-transition-continuity.md`. Claude global installs use `~/.claude/contracts/`, and Claude project installs use `<repo>/.claude/contracts/`; installed `agents/<role>.md` files refer to it as `../contracts/ui-transition-continuity.md`.

Runtime installation is English-only. `shared/references/ru/ui-transition-continuity.md` is a required non-authoritative maintainer/operator mirror and is not installed. The full `shared/references/` tree is not installed, and there is no provider-specific semantic copy. This uses the existing install commands and transaction; it introduces no new install command or workflow.

The git-push marker now registers `check-git-push-gate-runner.py`, a minimal cached-import entry point for the fixed sibling `hook_common.py` and policy `check-git-push-gate.py`. Any load or delegation failure denies without raw detail. This changes the Codex command identity, so the next install requires the documented interactive trust review.

- **PreToolUse bugfix-discipline hook** (`check-bugfix-discipline.py`): catches the model about to make a code-mutating tool call (`Edit`/`Write`/`NotebookEdit`/`apply_patch`) in response to a bug-report or change-request signal (`fix`, `change`, `broken`, `не работает`, `исправь`, `пофикси`, traceback, `Error:`), without first invoking `/agents-bugfix` or otherwise capturing diagnostic data. It reads the PreToolUse envelope's `transcript_path`, checks the current turn for discipline signals, and emits a structured deny payload when the pre-fix gate was skipped. It skips subagent contexts (envelope `agent_id` present) and exempts writes to non-code artifact paths (`.reports/`, `.scratch/`, `.plans/`, `work-items/`, `docs/`), so a report/plan/doc write under a bug-vocabulary prompt is never falsely blocked (proven on a real transcript).
- **PreToolUse git-push publication-gate hook** (`check-git-push-gate.py`; registered on a `Bash` matcher): a **blocking** structural backstop for the publication-safety rule "human review before `git push` must include a leak-check of staged changes". Default/tracked and explicit-path modes are manual pre-commit checks and never authorize a later push. After one generic or strict pull-request route freezes remote, destination, resolved source, and current `HEAD`, the gate captures the verified `hook_common.py` + machine-path-classifier + canonical scanner closure through bounded open handles and directly executes those bytes with its current trusted interpreter and no shell or path lookup. Only the exact pending invocation's bounded, reaped, non-empty version-3 result covering the complete unpublished commit/tree/blob graph, with matching receipt tip and complete message/object/blob/subject/path coverage digests, can provide scan-derived credit. Transcript/manual and version-2/v1/tracked/path/zero-commit, malformed, finding, refusal, incomplete-acquisition, correlation, provenance, execution, identity-drift, or reused results deny. The solitary positive long `--dry-run` and genuine-user `[approve-publication]` route remain. The result does not claim repository identity, remote URL/server freshness, or Git metadata outside the selected unpublished object graph.
- **Stop passive-polling hook** (`check-passive-polling-stop.py`): catches the model about to end its turn by saying it is waiting for an async external source (bot/review/CI/job/notification/reply) without a relevant current-turn state check. It reads `last_assistant_message` from the Stop envelope, respects `stop_hook_active=true`, exempts user handoffs like `waiting for your response` / `жду твоего подтверждения`, supports the per-stop `[acknowledge-passive-stop]` override, and otherwise requires a relevant probe such as `date`, `Get-Date`, `gh pr view`, `gh run list`, `gh api`, `curl`, process/task output, or reading an output/log/task file.
- **Work-item lifecycle.** No archival Stop adapter is installed or registered. The installed lifecycle owner moves and reconciles records; only physical archive placement makes a record terminal. Status and closure text supply required evidence but do not substitute for the move.
- **PreToolUse machine-local-path hook** (`check-machine-local-path.py`; lives in the typed `agents/hooks/` (Claude) / `skills/lead/hooks/` (Codex) dir and imports `hook_common` from the sibling `scripts/`): a **warn-only AUDIT** hook that flags a machine-local absolute path (a concrete user home or workstation dev root; placeholders like `<you>`, `%USERPROFILE%`, `${CLAUDE_PROJECT_DIR}` are allowed) written into a non-`.scratch/` tracked file. It matches the edit's own `tool_input`, writes a UTF-8 stderr warning, and ALLOWS — it never blocks (promotion to a blocking `deny` is a separate reviewed step once the false-positive rate is measured). On a hit it exits 1 (never 2) so the warning surfaces as a non-blocking `<hook name> hook error` transcript notice instead of being silently swallowed into the debug log the way exit 0 is; it exits 0 when there is nothing to flag, and fails open on any internal error.
- **PreToolUse no-trash-in-repo hook** (`check-no-trash-in-repo.py`; same typed `hooks/` dir, registered with a `Bash`/`PowerShell`-inclusive matcher so it sees the `git worktree add` command from either shell tool): a **warn-only AUDIT** hook — the stray-artifact guard (filename and install-marker retained for install continuity; a rename to `check-stray-artifact` is a tracked follow-up) — that warns on four things. It warns on every confidently parsed `git worktree add` except one add whose command ends with the exact `# orchestrarium:requested-isolation-worktree` marker required by the installed parallel-isolation protocol; missing, near-match, quoted, reused, or batch markers do not suppress the audit. `git worktree list/remove/prune`, `git add` (not `git worktree add`), `git` inside a quoted string, and non-git commands never warn; the parser is shell-aware (shlex tokenization, command-position tracking across `&&`/`;`/`|`/`(`, env-assignment-prefix and git-global-option skipping) and fails open on any tokenizer error. This replaced a name-based version that warned only on new dirs named `kosyaks`/`mistake-log` — useless, because those are the *user's* personal-process vocabulary, not names the *agent* (the actor a PreToolUse hook guards) ever creates, so it never fired; the real reported problem was the agent creating stray artifacts, chiefly unrequested worktrees, so the guard now keys on the OPERATION. (2) A **mangled Windows redirect target** — a drive-letter prefix carrying no path separator (`> r:Tempxbuild.log`), the signature of a shell eating the backslashes of `r:\Temp\x\build.log` and silently creating one file named after the whole mangled path while the command reports success; always a mistake, so this trigger is not gated on where the process is running. (3) A **build/log artifact redirected into the repository ROOT** (`> build.log`, `> probe.obj`) — a target with no directory component lands in the process working directory, which for a tool-run command is the repo root. (4) A **compiler invocation whose output lands in the repository root** — `ifx`/`ifort`/`icx`/`gfortran`/`cl`/`gcc` with at least one source operand and no output-directing flag, which is how a recorded cleanup of 54 untracked build artifacts (16 MB, 47 of them in two days) accumulated in a consuming repo's root. Triggers (3) and (4) fire only when the process CWD is CONFIRMED to be a repository root (`cwd/.git` exists — directory for a clone, file for a worktree/submodule) **and** the command contains no `cd`/`pushd`/`popd`; a directory change makes the destination undecidable, so the guard stays silent (running a tool from inside its own `.scratch/` output dir is the correct pattern, not a defect). Redirect destinations are judged from the RAW command text because posix tokenization eats backslashes — `> r:\Temp\x\build.log` and `> r:Tempxbuild.log` tokenize identically, and a legitimate `> .scratch\t\build.log` would otherwise collapse to a bare name and look root-destined. Deferred: the Claude `Agent` tool's `isolation: "worktree"` form. Dropped: outside-repo writes (allow-list FP-floods) and arbitrary in-repo trash (no reliable non-name signal) — note triggers (2)-(4) do NOT repeat that mistake: "writes outside the repo" is an OPEN set needing an unenumerable allow-list, whereas an artifact extension written to the ROOT is CLOSED on both axes (enumerable extensions, one destination directory), so no allow-list is required. Matches its own `tool_input`, and (like the sibling audit hooks above) delivers its warning to the MODEL as one line of `hookSpecificOutput.additionalContext` JSON on stdout with exit 0 — never a stderr-plus-exit-1 form, which was measured to reach nobody on either provider line — never blocks (never exit 2), and fails open on any tokenizer or internal error.
- **PreToolUse stale-relation-residue hook** (`check-stale-relation-residue.py`; same typed `hooks/` dir): a **warn-only AUDIT** hook — the structural backstop for architecture law C6 ("a superseding change leaves only the correct current state") — that flags an `Edit`/`Write` ADDING a stale-relation residue phrase (`deprecated alias`, `former alias`/`former name`, `(was X)`/`(formerly X)` parentheticals, `misregistered as`, arrow+alias, "is wrong, the correct is") into a LIVE-tree file. For diff/apply_patch payloads it scans ONLY added lines (erasing residue never warns). Exempt: provenance surfaces (`work-items/`, changelogs/release notes, `/archive/`+`/legacy/` trees, `.scratch/`, `.git/`) where recording a superseded relation IS the point. The stale-vs-live discriminator is review-bound, so it never blocks (never exit 2); it exits 1 on a hit / 0 otherwise so the warning is visible instead of debug-log-only, and fails open.
- **PreToolUse repository-orientation hook** (`check-repository-orientation.py`; same typed `hooks/` dir, registered on the full edit/shell matcher including `PowerShell`): a **warn-only AUDIT** hook that checks for exactly one assistant-authored `REPOSITORY ORIENTATION:` record before risky repository mutation or repository-local run/build/test actions. It validates `scope`, `status`, `workflow`, `protected`, `evidence`, a `path:line` citation, non-conflict status, and scope ancestry; skips discovery-only commands, local artifact writes, and subagent envelopes; and adds a stronger path-segment warning for `archive`, `deprecated`, `superseded`, or `frozen` unless the record states the matching non-live status plus explicit user-approved historical scope. It never scans repository prose or infers canon from deprecation words, never blocks (never exit 2); it exits 1 on a hit (either warning) / 0 otherwise so the warning is visible instead of debug-log-only, and fails open.
- **PreToolUse mcp-momentum hook** (`check-mcp-momentum.py`; registered on the exact `Grep|Bash|PowerShell|shell_command|exec_command` matcher): a consumer of the shared three-event [MCP continuity policy](shared/references/mcp-continuity.md). It recognizes native `Grep`; shell-shaped inputs using default-recursive `rg`/`ag`/`ack` or explicit-recursive `grep`; source scopes, source selectors, symbol patterns, and `rg --files`; and it stays silent only when every explicit scope resolves from the raw envelope `cwd` to `work-items/`, `.reports/`, `.plans/`, or `.scratch/` at the nearest repository root. A matching segment at any other depth is not exempt, and mixed source/exempt scopes still fire. Codex remains a warn-only audit in `skills/lead/hooks/`. Claude installs a provider-specific adapter in `agents/scripts/`: `mcpMode: auto` and subagents remain advisory, while a root `mcpMode: force` search is denied with `[MCP-FORCE-1]` whenever a configured code-intelligence server is present. Exact `[approve-mcp-fallback:v1]` in the bounded host-projected `user`-role record allows one recovery turn; assistant/tool injection cannot mint it, but this projection is not authenticated authorization and a forged host-shaped user record can satisfy it. No-server and unresolved-mode cases allow with stable diagnostics so enforcement cannot loop. Output contains only safe matched MCP server names (at most three plus a count), never commands, environment values, prompts, or tokens; internal errors fail open.
- **PreToolUse typed-routing hook** (`check-typed-routing.py`; **Claude-only**, same typed `agents/hooks/` dir, registered on the `Agent` subagent-dispatch matcher): a **warn-only AUDIT** hook that nudges when the orchestrator dispatches the built-in catch-all `subagent_type: general-purpose` for work that looks like typed specialist work (an implementation/review/design/security/performance/toolchain signal in the dispatch prompt), so the routing smell surfaces at the dispatch decision — the one moment it is observable. It skips subagent contexts (`agent_id`), keys on the Phase-0-captured dispatch shape (`tool_name` `Agent`, `tool_input.subagent_type`) and is INERT if that shape is absent (a mismatch makes it fire nothing, never a false block), exits 1 on a hit (never 2) so the nudge is visible, exits 0 otherwise, and fails open. It has no Codex mirror — Codex CLI exposes no analogous subagent-dispatch tool, so the Codex pack's hook count is unchanged.
- **SessionStart MCP-usage reminder** (`mcp-usage-reminder.py`): informational context injection at startup/resume/compaction. It does not block, but it makes MCP/tool-discovery a visible checkpoint for codebase, architecture, API/docs, search, browser, debugger, profiler, and repository-understanding tasks; under `mcpMode: force`, relevant MCP use remains a standing instruction.
- **SessionStart delegation-posture reminder** (`agents-mode-reminder.py`): informational context injection at startup/resume/compaction. It reads the effective `delegationMode` from a self-contained first-match walk of the documented `.agents-mode.yaml` read-order and, ONLY when that mode is `force` or `auto`, emits an imperative directive telling the main conversation to adopt the `$lead` orchestration role in-session and route non-trivial tasks to the matching specialist role (spawned via the Agent tool on Claude; activated as a skill on Codex), and maintain `work-items/` recovery state; it is SILENT on `manual` and on the no-file/unresolved state (fail-safe). Because the shipped default is now `auto`, a default install surfaces the auto delegation directive automatically, without an `/agents-init-project` run. It exists because `delegationMode` is pack governance the host never parses on its own — without it the main conversation never sees `force` and never applies it. Generic and fail-open (any error emits nothing and exits 0).
- **SessionStart scratch-valuables watchdog** (`check-scratch-valuables.py`): informational, CONDITIONAL context injection at startup/resume/compaction — a read-only detector for `.scratch/` (the pack's own local-scratch convention) that surfaces valuable-looking data before the operator accidentally overwrites it, instead of a command someone has to remember to run. It NEVER deletes, moves, quarantines, or otherwise mutates anything; its only filesystem/process calls are directory reads, stats, junction detection, and two READ-ONLY git subprocesses. The PRIMARY signal is git-content-uniqueness: a candidate is a non-empty, non-junk file whose exact bytes are not already recoverable from the local repository's git object database (checked via `git hash-object` — never with `-w` — plus `git cat-file --batch-check`); age is a severity/sort key (newest-modified first), not a filter. When `.scratch/` is not inside a git repository, git is unavailable, or any git call fails, it falls back to the prior age-gated behavior (older than 7 days) rather than going silent or noisy. A narrow junk denylist (editor/OS litter, cache and dependency directories, known external-CLI prompt-capture shapes) is applied as a secondary filter on top of the uniqueness check, biased to over-warn rather than hide real data. It is SILENT when nothing is found; when the candidate count is large it summarizes by top-level `.scratch/` subdirectory and lists a short window led by the longest-lingering files plus the newest-modified, instead of a flat dump. Fail-open (any error emits nothing and exits 0).
- **UserPromptSubmit turn-anchor reminder** (`turn-anchor-reminder.py`): informational context injection at the START OF EVERY TURN, not just SessionStart/compaction. It re-anchors two turn-boundary postures ("a passed slice is not completion, keep going until blocked" and "delegate at the first decision point via `$lead`") because their failure moment is the turn boundary itself, which a once-per-session reminder cannot reach once a long turn's own momentum takes over (measured in-session: ~100 consecutive successful tool calls with the reminder still in context, never consulted). Deliberately short — this text is paid for on every turn, so detail stays in the SessionStart reminders and the spine. Always emits; fail-open (never exit 2, which would erase the user's prompt per the hooks reference).

**The production installers auto-register all retained entries by default** (thirteen for Claude Code — including the Claude-only `check-typed-routing` audit — and twelve for Codex CLI) in both `--global` and `--target <project>` modes via an idempotent JSON merge that preserves all your other settings and hooks. Upgrade reclaims the obsolete archival Stop registration only after synchronization and health verification:

- Claude Code installer merges the hook entry into `~/.claude/settings.json` (`--global`) or `<project>/.claude/settings.json` (`--target`).
- Codex CLI installer merges the hook entry into `~/.codex/hooks.json` (`--global`) or `<project>/.codex/hooks.json` (`--target`).
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
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-marker check-git-push-gate --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.codex/hooks.json --platform codex --script-marker check-git-push-gate --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-marker check-machine-local-path --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.codex/hooks.json --platform codex --script-marker check-machine-local-path --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-marker check-no-trash-in-repo --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.codex/hooks.json --platform codex --script-marker check-no-trash-in-repo --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-marker check-repository-orientation --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.codex/hooks.json --platform codex --script-marker check-repository-orientation --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-marker check-mcp-momentum --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.codex/hooks.json --platform codex --script-marker check-mcp-momentum --script-path "" --remove
# check-typed-routing is Claude-only (no Codex mirror):
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --script-marker check-typed-routing --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --hook-event Stop --script-marker check-passive-polling-stop --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.codex/hooks.json --platform codex --hook-event Stop --script-marker check-passive-polling-stop --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --hook-event SessionStart --script-marker mcp-usage-reminder --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.codex/hooks.json --platform codex --hook-event SessionStart --script-marker mcp-usage-reminder --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --hook-event SessionStart --script-marker agents-mode-reminder --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.codex/hooks.json --platform codex --hook-event SessionStart --script-marker agents-mode-reminder --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --hook-event SessionStart --script-marker check-scratch-valuables --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.codex/hooks.json --platform codex --hook-event SessionStart --script-marker check-scratch-valuables --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.claude/settings.json --platform claude --hook-event UserPromptSubmit --script-marker turn-anchor-reminder --script-path "" --remove
python scripts/install-hypothesis-hook.py --target ~/.codex/hooks.json --platform codex --hook-event UserPromptSubmit --script-marker turn-anchor-reminder --script-path "" --remove
```

Entries are identified independently by script marker: `check-bugfix-discipline`, `check-git-push-gate`, `check-machine-local-path`, `check-no-trash-in-repo`, `check-stale-relation-residue`, `check-repository-orientation`, `check-mcp-momentum`, and (Claude-only) `check-typed-routing` for `PreToolUse`, `check-passive-polling-stop` for `Stop`, `mcp-usage-reminder` + `agents-mode-reminder` + `check-scratch-valuables` for `SessionStart`, and `turn-anchor-reminder` for `UserPromptSubmit`. Re-running the installer is idempotent: it finds each entry by marker and updates it in place rather than appending duplicates. **Scope of preservation:** the merge preserves every part of the file outside our entries — your other hooks and top-level user keys (env, attribution, permissions, enabledPlugins, model, theme) survive. **Scope of overwrite:** the merge does NOT preserve hand-edits inside our entries' `command`/`args` fields; reinstall normalizes matched entries back to canonical form. To preserve manual overrides, pass `--no-hypothesis-hook` (PowerShell: `-NoHypothesisHook`) on every future install or set `ORCHESTRARIUM_NO_HYPOTHESIS_HOOK=1`; the opt-out does not block `--remove`.

**Per-event overrides (no install change).** For a non-bug code edit whose user message happens to contain a bug-trigger word (e.g. "fix this typo" — really a docs edit), put `[skip-bugfix-discipline]` in your assistant message acknowledging the override; the PreToolUse guard pulls back for the next turn only. For an approved publication, the USER includes `[approve-publication]` in their own message; the git-push gate opens for that turn only (this marker is never honored from assistant prose or tool output). For a legitimate Stop handoff that uses waiting language, include `[acknowledge-passive-stop]` in that final assistant message; the passive-polling Stop guard pulls back for that stop only. Status or closure text never moves a work-item: use the installed lifecycle owner for terminalization and reconciliation.

**Codex-specific note: manual trust step required after install.** Codex marks every newly-installed or modified hook as "untrusted" by design; the twelve retained entries are written to `hooks.json` but do not fire until you run `codex` interactively and trust them via the TUI. This is Codex's security model, not a limitation of the installer — Codex does not currently expose a programmatic trust API. The archival adapter retirement preserves the remaining registration identities, so it alone does not create a new trust requirement. Claude Code does not require this step — Claude hooks fire immediately after install.

**Cross-platform hook command shape.** The only supported hook runtime registers the absolute interpreter reported by `sys.executable` followed by the absolute `.py` target path. The same direct-Python target resolution is used on Windows and POSIX; only the provider schema differs (Claude Code uses `command` plus `args`, while Codex stores one shell-form command string). Windows Codex commands deliberately leave both absolute paths unquoted, the form verified under both `cmd.exe` and PowerShell; a single-quoted command word is not portable to `cmd.exe`. Retained `.sh` files are manual launchers for non-hook commands only.

When both packs are installed, keep shared project policies aligned across both files. The repository's dev overlays, `AGENTS.md` and `CLAUDE.md`, are for maintaining this monorepo and are not copied into target projects by the install scripts.

## Terms and Abbreviations

- `AGENTS.md`: agent governance file installed for Codex and materialized as a shared-governance module for example providers.
- `agent-run-ledger.*`: helper script family that initializes legacy work-item ledger files and appends validated `agent-runs.jsonl` events.
- `agents-mode`: Orchestrarium YAML overlay that records delegation, provider, consultant, parallelism, MCP, and workdir preferences.
- `agent-runs.jsonl`: JSONL execution ledger stored beside `status.md` for machine-readable work-item state.
- `check-work-items-state.*`: helper script family that checks every active work item under a repository root.
- `Claude Code`: Anthropic's Claude runtime and production provider line.
- `Codex`: OpenAI Codex runtime and production provider line.
- `externalProvider: auto`: production routing mode that stays on the Codex/Claude pair in shipped defaults.
- `evidence`: concrete verification data such as a command result, artifact path, review result, log summary, or observed output supporting a gate.
- `global install`: install into a user-level provider runtime root such as `~/.codex/` or `~/.claude/`.
- `JSON`: JavaScript Object Notation; structured data format used here for machine-readable contract files.
- `JSONL`: JSON Lines; one JSON object per line, used here for append-only execution events.
- `ledger`: append-only record of agent runs, gates, artifacts, and evidence for a work item.
- `MCP`: Model Context Protocol; provider/runtime mechanism for tool and resource servers.
- `power-mode`: init-time preset for hardest tasks where maximum useful result matters more than latency; starts from the `quality-first` provider-order profile.
- `runtime`: installed provider-facing files and directories read by the provider tool.
- `schema`: structured contract describing allowed keys, values, defaults, provider sets, and routing shapes.
- `stdin`: standard input stream used by CLIs and wrappers.
- `status.md`: human-readable recovery summary for the active work item.
