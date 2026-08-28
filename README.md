# Orchestrarium

A cross-provider agent orchestration monorepo that keeps the production Codex and Claude Code lines aligned on one shared governance and reference core.

Codex has a native Luna corridor for bounded deterministic mechanical work. Luna has zero decision authority: with the feature enabled and a valid exact caller plan, `resolve_role_dispatch` returns `native-required`; when disabled it returns `E_NATIVE_V2_DISABLED`. Luna uses exact `gpt-5.6-luna` with `high` as the default and minimum; only `high`, `xhigh`, and `max` are valid. The caller supplies the exact tool list, exact root, and terminal oracle; a mechanical worker may apply one exact patch to one existing file only after an executable exact-root, no-follow preflight and matching pre/post hashes. No external, Terra, Sol, runtime-default, or other fallback is allowed; host rejection is the nonauthorizing `E_LUNA_UNAVAILABLE` handoff. Native-role installation accepts hash-pinned prior working or currently-disabled stock payloads, while customized payloads fail closed.

- `src.codex/` — the production Codex provider-pack source
- `src.claude/` — the production Claude Code provider-pack source

The provider lines share one governance model and role vocabulary, while each keeps the runtime structure expected by its own provider. The root router installs Codex, Claude, or both. The removed Gemini and Qwen provider values are retained only as fail-closed migration identifiers; they are not install or execution routes.

Warning: Orchestrarium is optimized for maximum execution effectiveness and low orchestration drag rather than for minimum token spend. On large tasks, multi-opinion review lanes, or aggressive external fan-out, usage can rise quickly and consume a substantial token budget in a short time.

New maintenance sessions should start with [`docs/new-session-guide.md`](docs/new-session-guide.md). It records the source-first rule for this monorepo: tracked Orchestrarium source is canon, while `~/.codex/`, `~/.claude/`, project `.agents/`, and project `.claude/` are installed runtime outputs that should not be patched as the durable fix before the source owner is updated.

For an offline machine move, `$manual-repo-transfer` inventories dirty, ignored, recovery, and local-runtime state; it builds and validates a selected transfer bundle and emits cleanup previews only. Do the actual transfer only after the current tasks and pull-request gates pass.

## WARNING: Claude external authentication

The Python-owned `invoke-claude-prompt.py` transport (also exposed through the thin POSIX launcher `invoke-claude-prompt.sh`) runs automated, headless `claude -p`. Subscription sign-in (OAuth), including Claude Pro and Max, is not permitted for these orchestrated runs unless the existing explicit Orchestrarium override is set; use `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, Amazon Bedrock, or Google Vertex AI instead. Orchestrarium 1.x refuses `apiKeyHelper` before prompt capture or provider lookup because a helper-generated credential cannot be bound to the transport's exact output scan. For the secret-backed path, use `invoke-claude-api.py` or its thin `invoke-claude-api.sh` launcher with the credentials documented in `SECRET.md`. See [Anthropic's Claude Code legal and compliance guidance](https://code.claude.com/docs/en/legal-and-compliance).

## Repository layout

```text
shared/             Shared cross-provider governance and canonical reference cores
docs/               Common branch-level docs index and operator/runtime references
src.codex/          Codex provider-pack source
src.claude/         Claude Code provider-pack source
references-codex/   Codex-specific addenda and compatibility pointers
references-claude/  Claude Code-specific addenda and compatibility pointers
RELEASE_NOTES.md    Canonical tracked release log
install.py          Python-owned entry-point installer (asks which pack to install)
install.sh          Thin POSIX launcher for `install.py`
scripts/            Pack-specific installers plus the repo-local publication gate
AGENTS.md           Dev overlay for Codex pack maintenance
CLAUDE.md           Dev overlay for Claude Code pack maintenance
```

## Provider Packs

| Pack | Status in this monorepo | Source | Runtime entrypoint in source | Packaging in this branch | Validation |
| --- | --- | --- | --- | --- | --- |
| Codex | Production | `src.codex/` | assembled installed `AGENTS.md` from `shared/AGENTS.shared.md` + `src.codex/AGENTS.codex.md` | root Python router plus `scripts/install-codex.py` and its POSIX launcher | `validate-skill-pack.py` and its POSIX launcher |
| Claude Code | Production | `src.claude/` | `src.claude/CLAUDE.md` | root Python router plus `scripts/install-claude.py` and its POSIX launcher | `validate-skill-pack.py` and its POSIX launcher |

Shared design references now live in `shared/references/`. Provider-local `references-codex/` and `references-claude/` keep provider-specific addenda plus compatibility pointers where older paths still need to resolve. The clearest example is `subagent-operating-model`: the canonical blueprint core now lives in `shared/references/subagent-operating-model.md`, while each production provider tree keeps only its runtime and repository concretization addendum. Shared governance is maintained across provider lines; the repository-level overlays in `AGENTS.md` and `CLAUDE.md` exist only for maintaining this monorepo.

Dynamic user-interface roles in both live packs consume one neutral installed leaf, `contracts/ui-transition-continuity.md`, sourced from the sole normative English source at `shared/references/ui-transition-continuity.md`. The mandatory Russian file at `shared/references/ru/ui-transition-continuity.md` is a non-authoritative maintainer/operator mirror and is not installed. The full `shared/references/` tree is not installed, and there is no provider-specific semantic copy. This is a pack-structure projection; the root README does not own the continuity semantics.

The maintainer-only [cross-pack reconciliation manifest](shared/references/cross-pack-reconciliation.md) maps shared semantic blocks between provider contracts. It is intentionally excluded from standalone provider branches and packages.

Installed Codex now follows the same compact-entrypoint pattern that Claude already uses: the installed `AGENTS.md` is intentionally the compact universal minimum, while installed runtime guidance lives in the Codex skill bodies under `skills/<role>/SKILL.md`. Shared and provider-specific reference trees remain source-maintainer canon rather than installed target-project docs. Claude keeps a short `CLAUDE.md` entrypoint and leaf-role files under `.claude/agents/`; the deliberate exception is the five curated role-skills — `lead`, `product-manager`, `analyst`, `architect`, `planner` — whose canonical contracts live at `.claude/skills/<role>/SKILL.md`. In `delegationMode: force`, an absent user `settings.json.agent` receives the `lead` default; this main-agent activation uses `agents/lead.md` frontmatter `initialPrompt: /lead`, while a stale dispatched `subagent_type: lead` still fails closed. The other four keep thin delegate wrappers under `.claude/agents/` that load the same-named skill.

Maintainer note: this repository is the installer/source monorepo, not automatically a repo-local Codex install target. When working inside `Orchestrarium/`, it is valid to rely on the global Codex install under `~/.codex/`. A missing local `.agents/` tree in this monorepo does not by itself mean the Codex runtime is misconfigured; create `.agents/` here only by running the installers intentionally.

Installed governance now requires a cited repository-orientation record before the first run, build, or mutation in an unfamiliar repository or subtree. The record names scope, live/archive status, canonical workflow, protected surfaces, and `file:line` evidence; names, file counts, recency, and layout never prove liveness. The production Claude Code and Codex installers also register a warn-only, fail-open process audit that detects a skipped or conflicting record without scanning repository prose or inferring canon from deprecation words.

Cross-provider execution is available through two routing adapters:

- `$external-worker` is the external execution adapter for eligible worker-side roles.
- `$external-reviewer` is the external execution adapter for eligible review and QA roles.
- `$consultant` remains advisory-only and is not reused for implementation or review gates.

## Work-item physical lifecycle

The Codex and Claude production packs use one physical lifecycle owner for
local task memory. Current work is in category roots such as
`work-items/backlog/` and `work-items/active/`; terminal identities exist only
under that category's `archive/YYYY-MM/` directory, selected from explicit
strict UTC terminal evidence. `status.md` is active recovery state and
`closure.md` is final work-item outcome. The generated `work-items/README.md`
and compatibility `index.md` do not authorize transitions. Historical records
without explicit terminal evidence remain unmoved for a human data decision;
the workflow does not infer timestamps, status, or archival targets. Before
closing a work-item, `bug-dispositions.json` must cover exactly all current
bugs whose parsed `context` equals its slug. The lifecycle owner applies each
`terminalize` or `preserve-current` row, archives the item, writes a bound
receipt, and refreshes the derived README as one rollback-safe operation. Two
owner-managed legacy transitions handle the old directory-shaped backlog:
`convert-legacy-candidate` creates one visible flat candidate while preserving
every accepted source text and digest as an appendix, and
`retire-legacy-backlog` records an explicit product rejection directly in the
monthly archive without inventing candidate, active, or closure history.

## Installation

Use the root router installers for the common path:

```bash
bash install.sh --global
```

```powershell
python .\install.py --global
```

Each router asks what to install:

```text
What to install?
Production installs:
  1) Codex pack
  2) Claude Code
  3) Codex + Claude (default production install)
```

Pressing Enter selects the default production install, `Codex + Claude`. The router then forwards the same arguments to the selected provider-specific installer in `scripts/`. Use `scripts/install-codex.*` or `scripts/install-claude.*` directly when you want deterministic automation on one line.

Windows Kimi executable enrollment is global-Codex maintenance. Ordinary `--enroll-kimi` remains create-only and refuses any different existing pin. After Kimi Code CLI updates from the accepted rollback release `0.39.0` to the current exact `0.39.1` release, run the provider-specific installer with `--global --replace-kimi-enrollment`; the action validates the fixed executable, atomically rotates only an accepted rollback pin, and never launches Kimi. The installed `invoke-kimi-prompt.py` wrapper exposes the same positive replacement flag for maintenance without a pack reinstall. Launch admission carries the exact enrolled size and SHA-256, so swapping to another accepted release without rotating the pin fails before provider execution. Both launch paths keep `KIMI_CODE_NO_AUTO_UPDATE=1` in the Kimi child environment.

Important: operator preferences live in per-provider `agents-mode` files; both production provider lines may read the lower `~/.agents-mode.yaml` cross-pack global overlay below their pack-local globals.

- Codex reads `.agents/.agents-mode.yaml`.
- Claude Code reads `.claude/.agents-mode.yaml`.
- Legacy extensionless `.agents-mode` files remain compatibility input only. Decision-driving reads should resolve in this order: provider-local `.agents-mode.yaml`, local legacy `.agents-mode`, matching pack-local global `~/.<provider>/.agents-mode.yaml`, matching pack-local global legacy `.agents-mode`, then the shared cross-pack global `~/.agents-mode.yaml`, then built-in defaults. `scripts/resolve-agents-mode.py --provider <provider> --json` is the executable reference for this per-key read order. Normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope without recreating any legacy path or synthesizing a project-local override on read alone.
- Reinstall is expected to do the same maintenance work for installed overlays: if the shipped schema or defaults changed, the installer must rewrite an existing `.agents-mode.yaml` to the current canonical form instead of preserving stale pack-owned structure verbatim.
- `consultantMode` controls `$consultant`.
- `delegationMode: manual` keeps explicit-permission behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation a standing instruction whenever a matching specialist and viable tool path exist. Because the host does not parse `.agents-mode.yaml` natively, the production Claude/Codex installers register an `agents-mode-reminder` `SessionStart` hook that surfaces the active `auto`/`force` posture into the main conversation at session start and after compaction (silent on `manual`), so an init-project run is not required for the posture to take effect.
- `parallelMode: manual` keeps parallel fan-out explicit-by-request, `auto` leaves safe parallelism enabled by routing judgment for any independent internal or external lanes, and `force` makes safe parallel launch a standing instruction whenever scopes are independent and the merge cost is justified.
- `mcpMode: auto` lets the agent decide when MCP is appropriate; `force` means the config itself is an explicit instruction to use relevant available MCP tools instead of treating MCP usage as optional.
- `preferExternalWorker` and `preferExternalReviewer` let routing prefer `$external-worker` on `implement` and `$external-reviewer` on `review` and `QA`.
- `externalProvider` accepts `auto | codex | claude | kimi | grok`. `auto` remains lane-driven, not host-pack-driven, and shipped production profiles stay on the Codex/Claude pair with `reserve` only as a supplemental advisory/review candidate. Kimi is explicit-only, policy-admitted read-only exploration, research, planning, or review through the canonical policy-bound wrapper: fixed `kimi-code/k3`, no tools or subagents, independently verified and nonauthorizing. It never enters `auto`; Grok remains unavailable in 1.x. Legacy Gemini/Qwen scalar values fail closed with `E_EXTERNAL_PROVIDER_REMOVED` and are not rewritten silently.
- `externalPriorityProfile` selects the active named provider-order profile, `reserveResolver` binds the symbolic `reserve` slot to a concrete read-only resolver, `externalPriorityProfiles` stores the switchable per-lane provider orders, and `externalOpinionCounts` raises specific lanes above the default single-opinion behavior when one external opinion is not enough. Those counts are lane-local distinct-opinion requirements, not a cap on how many parallel external helper instances may run overall; `parallelMode` remains the general fan-out rule for any helper lane, while bounded same-provider external helper fan-out lives under the dedicated brigade surfaces.
- `externalModelMode: runtime-default | pinned-top-pro` remains the shared production model policy for the Codex/Claude pair. `runtime-default` leaves the resolved provider on its runtime default model/profile; `pinned-top-pro` starts on the strongest documented provider-native model/profile and allows one named same-provider fallback on limit-style failures.
- `externalCodexProfile: default | gpt-5.6-sol-xhigh | gpt-5.6-sol-max | gpt-5.6-terra` is the Codex-specific external profile override. The shipped value is `gpt-5.6-sol-xhigh`, symmetric to Claude's `opus-xhigh`.
  `default` instead inherits `externalModelMode` after provider resolution; `gpt-5.6-sol-xhigh` pins model `gpt-5.6-sol` with `model_reasoning_effort = "xhigh"` regardless of `externalModelMode`; `gpt-5.6-sol-max` requests model `gpt-5.6-sol` with `model_reasoning_effort = "max"` for higher-complexity/hard lanes; `gpt-5.6-terra` selects the balanced Codex model (a distinct model, `model_reasoning_effort = "high"`, not an effort suffix) and must be verified against the installed Codex runtime — a genuine cheaper-than-flagship reasoning lane, review-gated like any external lane, replacing the former `gpt-5.5-fast` and `gpt-5.3-codex-spark`.
- Explicit self-provider selection is allowed only as an override for isolation, transport, profile, or an intentionally independent rerun.
- `reserve` is a symbolic advisory/review-only profile candidate. It is not a scalar provider, not a worker path, and not a silent fallback from primary `claude` or `codex`; `reserveResolver: claude-sonnet | claude-wrapper | wrapper:<command> | disabled` selects the concrete read-only resolver, where `wrapper:<command>` is a PATH-resolved command or repo-relative wrapper path.
- External provider CLI launches use file-based prompts by default: write substantive task prompts to temporary prompt files and feed them through stdin or a provider-supported file-input mechanism instead of putting the full prompt in argv.
- The external-prompt governance capsule is authored once at `shared/external-prompt-governance.md` and projected for installed wrappers as `scripts/external-prompt-governance.md`; wrappers prefix it in memory rather than treating a raw provider prompt as sufficient governance.
- Codex may additionally use `externalClaudeProfile` to select or override the Claude CLI execution profile: `sonnet-high`, `opus-xhigh` (shipped default), `opus-max` (max-depth escalation for especially hard tasks at caller discretion), or `fable-xhigh` (current Claude flagship-family best-effort tier; the `fable` flagship alias as of 2026-07). New Codex installs seed `opus-xhigh` by default unless a preset or explicit override chooses otherwise.
- Codex installs the 17 manifest roles as create-only TOMLs under `.codex/agents/` and registers every one under `[agents.<name>]` in `.codex/config.toml` with its source description and exact `agents/<relativePath>` file. Hash-pinned recognized prior working or currently-disabled stock role payloads are the only current-role upgrade exception; customized payloads fail closed. Missing mappings are appended deterministically while unrelated config bytes, comments, keys, and `agents.max_concurrent_threads_per_session` remain unchanged; an exact mapping is a no-op and any same-name shape/value collision fails without mutation. An absent config receives `multi_agent_v2 = true` plus all mappings. The sole other 1.x migration exception removes the frozen exact `agents.luna_mechanical` block and its exact hash-pinned `agents/luna-mechanical.toml`; missing legacy files are accepted, while differing legacy mapping/file state is preserved and fails closed. The source manifest remains validation rather than an installed ownership receipt, and all other adoption/update/reclaim work remains reserved for 2.0.
- Provider-specific workdir keys stay separate and default to `neutral`: `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`.
- For first-time Codex project setup, run `$init-project` to write `## Project policies` in the root `AGENTS.md` and review or update the installed default `.agents/.agents-mode.yaml`. If local Codex overlay files are missing but `~/.codex/.agents-mode.yaml` exists, ordinary reads should use that global overlay honestly until you choose to create a project-local override.
- When the current working directory is this installer monorepo itself, a missing local `.agents/.agents-mode.yaml` should fall back to the global Codex install by default. Create a repo-local install only when you explicitly want project-local runtime state; the installer source tree and the installed runtime are different surfaces.
- For first-time Claude Code project setup, run `/agents-init-project` to write `## Project policies` in `.claude/CLAUDE.md` and review or update the installed default `.claude/.agents-mode.yaml`. If local Claude overlay files are missing but `~/.claude/.agents-mode.yaml` exists, ordinary reads should use that global overlay honestly until you choose to create a project-local override.
- Explicit user role requests still override the toggle state in either direction.
- Full value-by-value operator semantics live in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md), including task continuity, continue-by-default execution expectations for initialized projects, and the current init-time preset family: `default`, `absolute-balance`, `external-aggressive`, `correctness-first`, `power-mode`, and `max-speed`. Init helpers can either write the chosen preset as-is or open an optional fine-tune pass before saving `.agents-mode.yaml`.
- Machine-readable `agents-mode` contract sources live in [`shared/agents-mode.schema.json`](shared/agents-mode.schema.json) and [`shared/agents-mode.presets.json`](shared/agents-mode.presets.json). [`scripts/validate-agents-mode-contract.py`](scripts/validate-agents-mode-contract.py) checks those sources against the shared YAML exemplar, the operator reference, and provider init surfaces.

Shipped production provider-order profiles:

These are the persisted production `externalPriorityProfile` choices shipped from the root surfaces, not the init-time preset shortcuts. Example integrations may define their own provider-local examples, but root production profiles stay on Codex plus Claude provider families only. `reserve` may appear only as a supplemental read-only candidate after primary Claude and Codex on advisory/review lanes.

| Lane | Balanced priority | Quality-first priority |
|---|---|---|
| `advisory.repo-understanding` | `claude > codex > reserve` | `codex > claude > reserve` |
| `advisory.design-adr` | `claude > codex > reserve` | `codex > claude > reserve` |
| `design.ui-ux-structure` | `codex > claude` | `codex > claude` |
| `worker.reasoning-constraints` | `claude > codex` | `claude > codex` |
| `worker.default-implementation` | `codex > claude` | `codex > claude` |
| `worker.systems-performance-implementation` | `claude > codex` | `codex > claude` |
| `worker.ui-implementation` | `claude > codex` | `claude > codex` |
| `worker.visual-graphics-visualization` | `claude > codex` | `claude > codex` |
| `review.pre-pr` | `claude > codex > reserve` | `codex > claude > reserve` |
| `review.security` | `claude > codex > reserve` | `codex > claude > reserve` |
| `review.performance-architecture` | `codex > claude > reserve` | `codex > claude > reserve` |
| `review.ui-visual-correctness` | `codex > claude > reserve` | `codex > claude > reserve` |

If a repo-local lane policy explicitly asks for consultant input at closeout, it should follow the configured `consultantMode`; `consultantMode: disabled` waives consultant closeout instead of blocking the batch. `parallelMode` is the general rule for whether any helper lanes are parallelized by judgment or only by explicit request, while `externalOpinionCounts` may still raise advisory or review lanes above `1` when the active policy wants multiple independent external opinions before advancing.

See [INSTALL.md](INSTALL.md) for quick install, pack-specific install details, dual-platform setup, and post-install customization.

Publication scan-derived push credit now requires one gate-owned Version 3 range receipt over the complete unpublished Git commit/tree/blob graph. Version 2 and manual/default/path scan output remain diagnostic only and cannot authorize a push.

## Orchestration utilities

Two independence techniques ship on the Claude and Codex production lines:

| Technique | Stage | Claude | Codex |
| --- | --- | --- | --- |
| Review-loop | Independence at **verification** of one already-written artifact, across autonomous rounds | `/agents-review-loop` (`.claude/agents/contracts/review-loop.md`) | `$review-loop` (`skills/review-loop/`) |
| Design-panel | Independence at **generation**: N independently-framed candidate designs on one pinned problem, converged through one mandatory synthesis, before a single design exists | `/agents-design-panel` (`.claude/agents/contracts/design-panel.md`) | `$design-panel` (`skills/design-panel/`) |

Both are conditional, deliberate-cost techniques with narrow explicit triggers — neither auto-invokes on plain "design" or "review". Composition is sequential: design-panel generates and synthesizes once, then optionally hands its output to review-loop for verification. See `shared/references/design-panel-methodology.md` and `shared/references/review-loop-methodology.md` for the provider-neutral design.

## Common skills

In addition to roles, the pack ships **common skills** — workflow-focused capabilities that any role or the main conversation can invoke when the skill's description matches the current task. They package reusable methodology, gates, and evidence requirements without owning delivery.

Two archetypes:
- **Knowledge-style** — loaded into the caller's current context to inform how the caller performs the work.
- **Delegate-style** — additionally spawnable as a fresh-context subagent that executes the workflow and returns one self-contained artifact.

The governance index and runtime layout are defined in [`shared/AGENTS.shared.md`](shared/AGENTS.shared.md) under `## Common skills`. Each provider source tree carries its native form under `src.<provider>/skills/<name>/`, and Claude delegate-style skills additionally register a thin Agent-tool wrapper at `src.claude/agents/<name>.md`.

Currently shipped:
- `$windows-gui-manual-testing` — delegate-style; Windows desktop GUI manual visual verification with screen capture, hard crop validation, and theme/state evidence across toolkit/runtime variants.
- `$analyzing-video-bugs` — knowledge-style; frame extraction, scene-change detection, and dense sampling for any UI/animation/layout bug video.
- `$bug-hunting` — knowledge-style; systematic runtime-bug investigation via diagnostic logging.
- `$mathtype-book-page` — knowledge-style; bring translated technical-book DOCX pages to accepted MathType format.
- `$manual-repo-transfer` — knowledge-style; inventory local state, create and validate a selected transfer bundle, and emit preview-only cleanup evidence.
- `$github-pr-review-bot` — knowledge-style; drive a GitHub pull-request review loop with the Codex review bot to a terminal result on the current remote head.
- `$explain-simply` — knowledge-style; reader-tailored plain-language explanations for concepts, code paths, results, decisions, and learner notes.
- `$vak-dissertation-review` — knowledge-style; review of a Russian dissertation (диссертация) and autoreferat for a кандидат/доктор наук defense — нормоконтроль, novelty, ВАК compliance, borrowings, references, ВАК-list publications.

## References and maintenance

- `shared/references/` contains the shared cross-provider design core that current and future provider packs can reuse.
- `shared/agents-mode.defaults.yaml` is the single editable YAML exemplar for provider default overlays in the monorepo. Keep it aligned with the machine-readable contract files, `shared/agents-mode.schema.json` and `shared/agents-mode.presets.json`; the pack validators call the shared contract check so docs, init helpers, defaults, and provider-order policy do not drift silently, and the normalizer reads the schema for provider/lane policy instead of carrying a second hardcoded provider universe. Main installers seed provider-local or global `agents-mode` files directly from that shared exemplar, with any provider-only additions applied at install time. Standalone pack repositories keep one shipped pack-root default for self-contained install seeding.
- `docs/README.md` is the common branch-level docs entrypoint for operator semantics and runtime-layout references.
- [`docs/provider-runtime-layouts.md`](docs/provider-runtime-layouts.md) records the installed production runtime layout for Codex and Claude Code, with `global` and `local` scopes split explicitly so install/runtime paths are not confused with repo source trees.
- `references-codex/` contains Codex-specific addenda plus compatibility pointers for older reference paths.
- `references-claude/` contains Claude-specific addenda plus compatibility pointers for older reference paths.
- `subagent-operating-model` is no longer duplicated per provider pack: use the shared core for the canonical blueprint and the provider-local file only for runtime and repository concretization.
- `AGENTS.md` is the root development overlay for Codex provider-pack maintenance.
- `CLAUDE.md` is the root development overlay for Claude Code provider-pack maintenance.

Before publishing maintenance changes, validate the active provider surfaces:

```bash
bash src.codex/skills/lead/scripts/validate-skill-pack.sh
bash src.claude/agents/scripts/validate-skill-pack.sh
python scripts/sync-agents-mode-docs.py --root . --check
python scripts/validate-agents-mode-installers.py --root .
```

```powershell
python .\src.codex\skills\lead\scripts\validate-skill-pack.py
python .\src.claude\agents\scripts\validate-skill-pack.py
python .\scripts\sync-agents-mode-docs.py --root . --check
python .\scripts\validate-agents-mode-installers.py --root .
```

The docs sync command checks generated `agents-mode` tables, raised-count lists, and canonical YAML snippets against the JSON contract; use `--write` to refresh those generated blocks after intentional schema or preset edits.

The installer regression command creates disposable targets under `/.scratch/`, runs the Python production installers and the retained example-provider launchers, and verifies that stale `agents-mode` overlays are normalized to the current schema-backed contract. It also verifies manifest-owned Codex native-role installation and that upgrades preserve customized user roles.

Work-item execution tracking uses `agent-runs.jsonl` beside `status.md` for machine-readable agent state. Use `scripts/agent-run-ledger.* --work-item <path> init` for one-time migration of missing status sections and ledger files, `scripts/agent-run-ledger.* --work-item <path> append ...` to append one validated event with rollback on failure, `scripts/validate-work-item-state.* --work-item <path>` before single-item closeout, and `scripts/check-work-items-state.* --root . --stale-hours 24` before broad closeout or interruption recovery. The helpers catch stale agents, duplicate run IDs, missing evidence, inconsistent gates, or accepted artifacts that were never verified. `scripts/agent-run-ledger.* rollup --root .` (or `--work-item <path>` for one item) aggregates ledger events — runs by role, execution-role, gate, and status, evidence coverage, and a malformed-line count. `scripts/check-work-items-state.* --root . --max-age-days <N>` additionally reports (informational, never a failure) active items older than N days plus any open `Depends-on` blockers or dangling dependency targets.

The runtime helper surface is installed with production Codex and Claude packs as well: Codex gets the scripts under `$HOME/.agents/skills/lead/scripts/` or `<repo>/.agents/skills/lead/scripts/`, while Claude Code gets them under `~/.claude/agents/scripts/` or `<repo>/.claude/agents/scripts/`. That payload includes the pure Version 3 (V3) solution-attempt reducer at `solution_attempt/reducer.py` and the bounded process owner at `process_supervision/process_runner.py`. Process Runner Version 1 (`ProcessRunnerV1`) now owns subprocess execution for exactly three migrated consumer families: provider-prompt operations, skill-pack validator child checks, and detached Slice A validation. Other subprocess paths are unchanged. Each migrated path uses bounded output capture and descendant-process-tree settlement. On Windows, Python and Git child processes are admitted only through runner-owned, executable-specific probes performed for the same run; adapters cannot self-attest. Native Codex and Claude launches fail early with a typed unavailable result on Windows, while Linux Codex and Claude launches are active; no macOS/Darwin backend is shipped. Kimi is an explicit-only, policy-admitted read-only exploration, research, planning, or review route through fixed `kimi-code/k3` with no tools or subagents; it is independently verified, nonauthorizing, and never in `auto`. Grok remains unavailable in 1.x. The generic Windows command-line interface remains fail-closed unavailable, and a Rust implementation remains deferred to 2.0. The source-only durable operation store at `scripts/agent_run_persistence/operation_store.py` and route activation registry at `scripts/process_supervision/route_activation_registry.py` are not installed. See [docs/work-item-execution-tracking.md](docs/work-item-execution-tracking.md) for the sole operator runbook, including invalid-closure recovery. To group several work-items under one goal or milestone, see [docs/epics.md](docs/epics.md) (the epic -> work-item -> phase hierarchy). For durable cross-item architecture decisions see [docs/decisions.md](docs/decisions.md) (the ADR registry), and for standing cross-work-item dependencies see [docs/dependencies.md](docs/dependencies.md) (`Depends-on` edges + blocked/ready derivation). For the in-repo delivery-lessons registry see [docs/lessons.md](docs/lessons.md) (capture lessons learned so they survive a work-item's archival), and for the DoR/DoD vocabulary map onto existing admission and close gates see [docs/definition-of-ready-done.md](docs/definition-of-ready-done.md).

For release-relevant tracked changes, update `RELEASE_NOTES.md` in the same change before publication and explain the practical effect of the change, not just its title. Keep release notes in reverse-chronological `## YYYY-MM-DD` sections instead of one long-lived `## Unreleased` bucket, and run the repo-local gate before publication:

```bash
bash scripts/check-publication-gate.sh
```

```powershell
python .\scripts\check-publication-gate.py
```

## License

This repository is licensed under the Mozilla Public License 2.0. See [LICENSE](LICENSE).

## Terms and Abbreviations

- `AGENTS.md`: agent governance entrypoint assembled or read by Codex-compatible runtimes.
- `agent-run-ledger.*`: helper script family that initializes legacy work-item ledger files and appends validated `agent-runs.jsonl` events.
- `agents-mode`: Orchestrarium operator configuration overlay for delegation, provider routing, MCP use, and parallelism.
- `agent-runs.jsonl`: JSONL execution ledger stored beside `status.md` for machine-readable work-item state.
- `check-work-items-state.*`: helper script family that checks every active work item under a repository root.
- `reserve`: symbolic supplemental read-only candidate for advisory/review lanes; it runs after primary `claude` and `codex` and is not a worker or editing path.
- `reserveResolver`: scalar `agents-mode` key that binds `reserve` to `claude-sonnet`, `claude-wrapper`, a `wrapper:<command>` resolver, or `disabled`.
- `CLI`: Command-Line Interface, a terminal command surface such as `codex`, `claude`, or `kimi`.
- `Codex`: the OpenAI Codex runtime and production provider line in this repository.
- `Claude Code`: Anthropic's Claude Code runtime and production provider line in this repository.
- `externalProvider: auto`: Orchestrarium routing mode that uses only production-recommended providers, currently Codex and Claude.
- `externalPriorityProfile`: the active named provider-order profile used when `externalProvider: auto`.
- `externalPriorityProfiles`: the map of named routing profiles to lane-specific provider priority lists.
- `evidence`: concrete verification data such as a command result, artifact path, review result, log summary, or observed output supporting a gate.
- `Gemini`: a removed provider identifier retained only for fail-closed migration diagnostics.
- `JSON`: JavaScript Object Notation; structured data format used here for machine-readable contract files.
- `JSONL`: JSON Lines; one JSON object per line, used here for append-only execution events.
- `ledger`: append-only record of agent runs, gates, artifacts, and evidence for a work item.
- `MCP`: Model Context Protocol; a protocol for exposing tools and resources to agent runtimes.
- `power-mode`: init-time preset for hardest tasks where maximum useful result matters more than latency; starts from the `quality-first` provider-order profile.
- `quality-first`: production provider-order profile that biases near-tie advisory, source-bound, and review lanes toward Codex while preserving Claude-first lanes where the benchmark evidence gives Claude a clearer compact or visual-worker edge.
- `Qwen`: a removed provider identifier retained only for fail-closed migration diagnostics.
- `runtime`: installed provider-facing files and directories used by an agent tool outside the source tree.
- `schema`: structured contract describing allowed keys, values, defaults, provider sets, and routing shapes.
- `status.md`: human-readable recovery summary for the active work item.
