# Provider Runtime Layouts

This document records the installed runtime layout for the provider lines used by Orchestrarium today, including provider source trees that already exist in the monorepo. It is an install/runtime reference, not a source-layout reference.

## Codex native mechanical roles

Codex installs the exact role set in the validated Native role manifest as create-only TOML payloads under the target `.codex/agents/` directory and registers each manifest name under `[agents.<name>]` in `.codex/config.toml`; `mechanical-scout` and `mechanical-worker` are the two Luna members. The factory name, description and `agents/<relativePath>` mapping come from the validated Source TOML; compatible user descriptions and extra native registration settings are preserved. The factory `default` role does not pin a model or effort. Ordinary named/skill-only selection uses `describe_ordinary_native_role_options` then `resolve_ordinary_native_dispatch`. Native policy uses the capability tier `mechanical` and exactly one live Luna profile, `luna-high`; `micro-low`, `fast-medium`, and `fast-high` are removed historical names, not aliases. The verified policy's current `luna-high` binding requires exact `gpt-6-luna` with `high` as default and minimum reasoning effort; only `high`, `xhigh`, and `max` are valid. The profile carries model and reasoning effort only. It does not select execution speed, `RoleDispatchPolicyV1` emits no requested-speed or service-tier field, and Luna callers retain standard service without fast, priority, or ultrafast injection. Its shared eligibility is native policy rather than an agents-mode model option. `RoleDispatchPolicyV1` is resolved only when considering `mechanical-scout` or `mechanical-worker` and accepts no host/provider result or result file: enabled plus a valid exact plan is `native-required`, while disabled is `E_NATIVE_V2_DISABLED`. Luna has zero decision authority; the caller owns exact tools, root, plan/facts oracle, and the worker's one existing-file exact patch with pre/post hashes and an executable exact-root/no-follow preflight. No external, Terra, Sol, runtime-default, or other fallback is permitted; host rejection is nonauthorizing `E_LUNA_UNAVAILABLE`. A Codex reinstall may replace the prior stock policy and its exactly matching stock manifest only as one rollback-safe pair; either customized file or any one-byte drift fails before target mutation, and native role TOMLs plus config mappings remain unchanged.

Repository policy tests use inline requests and consume no tracked provider-result or runtime-result fixture. `scripts/validate-slice-a-detached.py` applies only the explicitly admitted overlay to one real detached candidate worktree, supervises every focused child, settles worktree cleanup, and only then publishes an always-nonauthorizing bounded manifest. Attempt logs and receipts are local evidence only.

Production auto-routing in the root integration contract is limited to Codex plus Claude Code. Kimi Code is explicit-only through the canonical fixed `kimi-code/k3` wrapper for policy-admitted read-only exploration/research/planning/review or mapped `external-worker` engineering. Omitting the capability file keeps tools, Model Context Protocol servers, and subagents empty with permission `reject`; a validated file may select admitted read tools/servers or scoped worker tools. Every result remains independently verified and nonauthorizing. Capability-file reads compare descriptor and pathname metadata before and after acquisition and reject drift. Selected Model Context Protocol (MCP) environment and header values are private by default; the existing public environment controls `PATH`, `LANG`, `TIMEOUT` and headers `Accept-Language`, `X-Region`, `X-Timeout` retain their behavior. Structured authorization/cookie payloads, values carried by credential-named Model Context Protocol command options, and URL user-info, non-service path segments, fragments, and query values, including URLs in environment values and arguments, are also checked. Raw and JSON-escaped echoes cannot enter public results or receipts; public endpoint text and ordinary non-credential command arguments remain public controls. This does not read provider authentication storage or change tool permissions. Grok remains unavailable in 1.x. `resolve_external_dispatch` must not use either in `auto`.

Supported authentication transports may attempt a task without known exact credential values; selecting a mode proves neither login success nor detector availability. The provider-prompt owner resolves one ordinary-local output context and checks both complete settled streams with all known injected and selected private values, credential classes and machine paths. Bare credential assignments under the existing label family use colon or equals delimiters with line-local empty/null/template semantics. Quoted JSON labels retain JSON whitespace, multiline values and visible required-parse failures, including actual nested JSON strings. Unknown context, unavailable detectors, invalid decoding and incomplete acquisition withhold child text and remain visible failures. These checks provide limited coverage even when exact values are known: arbitrary opaque, refreshed or transformed secrets are not proved absent, and local output supplies no retention/export/publication credit.

Selected private values are checked unchanged in raw provider streams. For the final terminal envelope, the builder owns validated field provenance: caller/provider-derived data is checked recursively for exact known echoes, while proved fixed protocol values and capture metadata computed from actual runner observations receive contextual treatment only for that exact check. Generic credential checks visit the complete actual serialized result and all parsed/nested strings; only validated control slots interpret closed protocol tokens as control metadata. Machine-path checks inspect the entire actual line, parsed/nested strings and stderr with no provenance exemption. Unknown fields or invalid source claims fail visibly. The actual checked line is committed/read back before identical stdout, and replacement lines receive the same checks. This distinction is not a minimum-secret-length exemption.

For a positively established pre-child setup failure, finalization scans explicit empty streams and preserves the stable setup-failure identifier. An attempted process with missing observations is an acquisition failure, never a pre-child failure. This does not waive scanner availability or permit unverified post-launch output; actual child/capture failures and cleanup uncertainty remain visible. Default and configured prompt captures share one creator-owned namespace: safe automatic roots and protected workspaces remain useful; unsafe or unestablished bindings fail before disk capture. Pending acquisition and interrupted promotion retain one cleanup owner, and native prompt/child handles close before capture removal. Windows prompt creation records its original native opening and file identity before verification or descriptor conversion. A positively stored descriptor becomes the sole close owner; its transferred raw alias is retired before descriptor closure. An unobserved conversion outcome retains its original association and nonclean settlement without guessing whether to close a native handle or descriptor. An interrupted close with unknown effect retains its original association and a nonclean cached result; its numeric handle is never retried as proved ownership. A bookkeeping interruption after positively observed closure retains the closed effect separately and never repeats the native close. Independently safe resources still close, the first interruption remains primary, and reserved-context exit always attempts receipt closure after capture settlement without replacing an earlier body failure.

Do not confuse these runtime surfaces with the monorepo authoring trees `src.codex/` and `src.claude/`.

Native role manifest version 2 retains exact factory hashes and adds `developerInstructionsSha256`, calculated from the exact UTF-8 parsed instruction string. Runtime settings are parsed from one captured snapshot and owned name/instructions are checked separately from model/effort policy. No setting allowlist or TOML rewrite is introduced. All 18 factory role TOMLs ship `[features] apps=false` and `plugins=false`; compatible user tuning remains supported, main-session settings stay unchanged, and these flags do not establish selective MCP-server startup isolation. V1 accepts exact stock bytes only; configured V1 inputs require the exact-stock manifest upgrade. The existing installer preserves compatible role and registration bytes, including user guidance and extra settings, and verifies them through the same transaction. A configured tuple is a candidate, not observed native execution; role-file sandbox, approval, provider and MCP settings cannot enlarge the parent scope. Missing target-host metadata stays unobserved. Use the existing public describe/resolve operation again at the last pre-launch check; serialized descriptions retain known carrier conflicts but do not carry a live filesystem binding.

Architecture note: on the Codex line, the installed `AGENTS.md` is intentionally the compact universal minimum. Detailed installed role contracts and runtime guidance belong in the installed `skills/<role>/SKILL.md` files; the Native role manifest binds exact factory provenance and the owned parsed instruction contract, while role TOMLs remain create-only, configuration-preserving targets without a general adoption/update/reclaim authority in 1.x. The installer appends missing manifest mappings without reserializing `.codex/config.toml`, preserves unrelated bytes and the thread limit, rejects same-name mapping collisions, and gives an absent config `multi_agent_v2 = true` plus all mappings. It accepts exactly five hash-pinned stock-role upgrades, while the frozen legacy `luna_mechanical` config/file pair is a separate bounded mapping migration; legacy fixture bytes remain historical migration inputs. Codex and Claude compose one identical complete canonical `.agents/skills/lead` tree before its single create-only publication or receipt-bound replacement, in either installation order, and Claude receives only create-only discovery projections. Codex hook inventory is mutable evidence outside that tree and is authoritative only beside the final resolved ordinary `hooks.json`. Shared/provider reference trees are source-maintainer canon, not target-project install payload. Claude uses a short `CLAUDE.md` entrypoint plus `.claude/agents/*.md` role files. Its four Claude-owned curated role bodies are `lead`, `product-manager`, `analyst`, and `planner`; Architect instead uses the universal `.agents/skills/architect/SKILL.md` body through the existing `.claude/skills/architect` projection. Claude main-agent `lead` activation uses the documented `initialPrompt: /lead`; the same definition retains a fail-closed stale-dispatch branch, while the other three Claude-owned roles and Architect keep thin `.claude/agents/<role>.md` wrappers that load their respective body.

Installer tree identity uses the versioned `orchestrarium.tree-manifest.sha256.v2` member manifest: relative paths retain their directory or file-content identity. New Lead receipts use `orchestrarium.canonical-lead-install.v2`; newly written non-Lead managed-member records contain complete members, while compatible legacy string entries remain preserved. When replacement relies on a legacy digest, that digest is a lookup key rather than structural ownership proof and requires an independently materialized factory witness; independently qualified Lead-v2 receipts or non-Lead member evidence do not require that legacy witness. The authenticated 1560 factory bridge is supported; other selected historical generations without a witness refuse with `E_LEGACY_TREE_WITNESS_UNAVAILABLE`, preserving that target. Existing 64-character backup names remain lookup-only and are checked against the selected source structure; new names use `tree-v2-`, and explicit strong adoption uses `tree-v2:<sha256>`. Rollback restores original receipt bytes. Native identity preservation depends on the selected recovery path; file reconstruction can restore bytes with a new identity. Downgrading requires a coherent older code/receipt pair; an old reader is not promised new receipt compatibility.

Read the tables with three layers in mind:

- `Official provider behavior` means the provider's own documented runtime surface or configuration model.
- `Orchestrarium runtime contract` means the install shape and conventions introduced by this repository.
- `Observed installed behavior` means the result verified in an installed target.

Do not collapse those layers into one claim. When a row is Orchestrarium-owned rather than provider-native, the notes call that out explicitly.

## Scope legend

| Scope | Meaning |
| --- | --- |
| `Global` | User-level installed runtime surface, usually under the provider's home directory |
| `Local` | Project-level installed runtime surface inside the current repository or target project |

## Codex

Both installer entrypoints use one canonical Lead receipt lifecycle for repository,
explicit-target and global materialization. The existing compact receipt binds the
actual final authored tree after verification and declared reclamation; it grants
no historical producer, signer, native hook trust or publication claim.

A supported predecessor transport generation is admitted through its scoped
receipt, complete authored canonical tree, ordered manifest codec and matching
ordinary peer members. Its captured old digests drive the existing exact migration
owner. Both provider entrypoints converge an already owned scoped Claude transport
peer in the same transaction.

Current installed Claude transport selects the ledger writer, validator, lifecycle owner and schema from its same-scope canonical Lead tree. Historical peer ledger files can remain present but cannot shadow that owner. Missing or changed canonical scope refuses the operation; working-directory helpers supply no fallback. An absent unselected peer is not created; an unknown,
customized or unsupported unselected peer remains preserved and unclaimed, while
explicit unknown overwrite still refuses. Historical example hashes are not the
general ownership rule, and independently valid safe and frozen legacy routes keep
their controls.

File and tree replacements retain their actual beforeimages and register performed
effects with the existing transaction owner. Directory recovery stays in the same
actual parent and uses one atomic no-overwrite move capability. An unsupported
required move refuses that operation before live effects. Owned staging records
actual created identities and partial bytes separately from the desired source.
Enclosing moves relocate current child and recovery addresses while preserving
their original proof and logical restoration destinations.

Rollback checks physical membership, identities, bytes, untouched snapshot
witnesses and retained recovery before restoration. It reverses actual destructive
dependencies and consumes each owned image once. Commit settles an admitted child
migration before disposing its containing image; failed children protect both the
current file and prior recovery. A direct writer preserves an image needed by an
explicitly deferred migration until that migration's owner commits or rolls back.
Foreign drift blocks affected parent snapshots, preserves current state and reports
the original failure plus settlement evidence. Installer Python children retain
their verification and trust checks with bytecode writes disabled.

Snapshot backups bind their empty creator root before copying and record each
created member and partial write. Final observation verifies that composition;
unclaimed siblings remain preserved with visible recovery. Moving a prepared
object consumes its staging role and grants no cleanup authority over a later
occupant of the vacated name.

On the tested Windows NTFS target, cleanup verifies native identity, content and
complete link metadata through one object handle before disposition. Observation
can coexist with the declared creator; mutation and disposal retain restrictive
sharing. Tested Linux cleanup uses declared member checks, parent-relative native
operations and result verification. It does not provide atomic inode-conditioned
removal against an intentional same-user replacement in the final syscall
interval. Remote and long-path Windows variants have no new verification claim.

### Global

| Installed pack root | `~/.codex/` | Global Codex pack install target |
| Governance entrypoint | `~/.codex/AGENTS.md` | Installed Codex runtime entrypoint; intentionally the compact universal minimum rather than the full role/runtime manual |
| Skill tree | `$HOME/.agents/skills/<role>/SKILL.md` | Orchestrarium Codex runtime organizes each role as a skill directory |
| Legacy skill compatibility | `~/.codex/skills/<role>` | Global Codex installs preserve the `.codex/skills` root and unrelated entries, then project each absent Orchestrarium-owned name to the canonical `$HOME/.agents/skills/<role>` tree. An ordinary same-name tree is preserved and migrated only with repeatable `--migrate-legacy-skill <role>` authority; project installs remain `.agents`-only. |
| Design-panel binding | `$HOME/.agents/skills/design-panel/SKILL.md` + `agents/openai.yaml` | Independent multi-lane design generation on one pinned problem, converged through one mandatory synthesis; no panel-state validator is installed |
| Native roles | `~/.codex/agents/<role>.toml` | Absent roles are created and identical files are no-ops. Manifest v2 preserves compatible user runtime settings and descriptions byte-for-byte while binding owned profession instructions. Incompatible instructions, names, registration shapes or file types refuse without mutation; only explicitly pinned stock migrations may replace existing role payloads. The source manifest is not installed as an ownership receipt. |
| Validation script | `$HOME/.agents/skills/lead/scripts/validate-skill-pack.sh` | Same lead script tree as the repo source |
| Publication-safety scan | `$HOME/.agents/skills/lead/scripts/check-publication-safety.sh` | PowerShell runs the sibling `.py` entrypoint with Python |
| Global operator overlay | `~/.codex/.agents-mode.yaml` | Orchestrarium-owned default operator file seeded on first global install and preserved on reinstall; legacy sibling `~/.codex/.agents-mode` is compatibility input only |

### Local

| Item | Path or shape | Notes |
| --- | --- | --- |
| Installed pack root | `<project>/.agents/skills/` | Role skills are copied here |
| Governance entrypoint | `<project>/AGENTS.md` | Codex pack section is merged into the project-root `AGENTS.md`; the installed Codex section stays intentionally compact and defers detailed installed role/runtime guidance to the skill tree |
| Skill tree | `<project>/.agents/skills/<role>/SKILL.md` | Mirrors the global `skills/` structure |
| Design-panel binding | `<project>/.agents/skills/design-panel/SKILL.md` + `agents/openai.yaml` | Project-level mirror of the global design-panel binding; no panel-state validator is installed |
| Native roles | `<project>/.codex/agents/<role>.toml` | Absent roles are created and identical files are no-ops. Manifest v2 preserves compatible user runtime settings and descriptions byte-for-byte while binding owned profession instructions. Incompatible instructions, names, registration shapes or file types refuse without mutation; only explicitly pinned stock migrations may replace existing role payloads. The source manifest is not installed as an ownership receipt. |
| Local config | `<project>/.agents/.agents-mode.yaml` | Canonical Orchestrarium local state file; local install seeds the default and `$init-project` reviews or updates it, while legacy sibling `<project>/.agents/.agents-mode` remains compatibility input only. Decision-driving reads use this local scope first, then fall back to the global Codex overlay when the local scope is absent. |
| Validation script | `<project>/.agents/skills/lead/scripts/validate-skill-pack.sh` | Run from the target project root after install |
| Publication-safety scan | `<project>/.agents/skills/lead/scripts/check-publication-safety.sh` | PowerShell runs the sibling `.py` entrypoint with Python |

## Claude Code

### Global

| Item | Path or shape | Notes |
| --- | --- | --- |
| Global context file | `~/.claude/CLAUDE.md` | Official user-level Claude Code instruction file; intentionally short while detailed role behavior lives under `~/.claude/agents/`. The four Claude-owned curated role bodies (`lead`, `product-manager`, `analyst`, `planner`) are under `~/.claude/skills/<role>/SKILL.md`; Architect uses the universal `~/.agents/skills/architect/SKILL.md` body through the existing `~/.claude/skills/architect` projection. `~/.claude/agents/lead.md` activates `/lead` through its main-agent `initialPrompt` and rejects stale dispatch; the other wrappers retain dispatch authority. |
| Global personal skills | `~/.claude/skills/<skill-name>/SKILL.md` | Official preferred user-level extension surface |
| Global personal subagents | `~/.claude/agents/*.md` | Official user-level custom subagent surface |
| Design-panel binding | `~/.claude/agents/contracts/design-panel.md` + `~/.claude/commands/agents-design-panel.md` | Independent multi-lane design generation on one pinned problem, converged through one mandatory synthesis; no panel-state validator is installed |
| Global legacy commands | `~/.claude/commands/*.md` | Still supported, but Claude docs now recommend skills as the preferred model |
| Global operator overlay | `~/.claude/.agents-mode.yaml` | Orchestrarium-owned default operator file seeded on first global install and preserved on reinstall; not a Claude-native file from official docs, and legacy sibling `~/.claude/.agents-mode` is compatibility input only |

### Local

| Item | Path or shape | Notes |
| --- | --- | --- |
| Project context file | `<project>/.claude/CLAUDE.md` or `<project>/CLAUDE.md` | Official project-level Claude instruction entrypoints; keep the entrypoint short and the detailed role files under `.claude/agents/`. The four Claude-owned curated role bodies (`lead`, `product-manager`, `analyst`, `planner`) are under `.claude/skills/<role>/SKILL.md`; Architect uses the universal `.agents/skills/architect/SKILL.md` body through the existing `.claude/skills/architect` projection. `.claude/agents/lead.md` activates `/lead` through its main-agent `initialPrompt` and rejects stale dispatch; the other wrappers retain dispatch authority. |
| Local personal override | `<project>/CLAUDE.local.md` | Official personal, uncommitted project override layer |
| Project skills | `<project>/.claude/skills/<skill-name>/SKILL.md` | Official preferred project-level extension surface |
| Project subagents | `<project>/.claude/agents/*.md` | Official project-level custom subagent surface |
| Design-panel binding | `<project>/.claude/agents/contracts/design-panel.md` + `<project>/.claude/commands/agents-design-panel.md` | Project-level mirror of the global design-panel binding; no panel-state validator is installed |
| Legacy commands | `<project>/.claude/commands/*.md` | Still work, but lose precedence to a skill with the same name |
| Orchestrarium shared governance copy | `<project>/.claude/AGENTS.md` | Repo-local overlay copied by Orchestrarium install scripts; not a Claude-native runtime requirement |
| Orchestrarium local config | `<project>/.claude/.agents-mode.yaml` | Canonical Orchestrarium local state file; local install seeds the default and `/agents-init-project` reviews or updates it, while legacy sibling `<project>/.claude/.agents-mode` remains compatibility input only. Decision-driving reads use this local scope first, then fall back to the global Claude overlay when the local scope is absent. |

## Quick comparison

| Provider | Global runtime root | Local runtime root | Native instruction entrypoint |
| --- | --- | --- | --- |
| Codex | `~/.codex/` | `<project>/.agents/` plus root `AGENTS.md` | `AGENTS.md` |
| Claude Code | `~/.claude/` | `<project>/.claude/` and optional root `CLAUDE.md` | `CLAUDE.md` |

## Sources

- Orchestrarium install and runtime contracts: `INSTALL.md`, `docs/agents-mode-reference.md`, `install.py`, `install.sh`, `src.codex/AGENTS.codex.md`, `src.codex/skills/consultant/SKILL.md`, `src.claude/CLAUDE.md`, `src.claude/agents/consultant.md`, `scripts/install-codex.py`, `scripts/install-codex.sh`, `scripts/install-claude.py`, `scripts/install-claude.sh`
- Claude Code documentation:
  - Memory and `CLAUDE.md` locations: <https://code.claude.com/docs/en/memory>
  - Skills and legacy commands: <https://code.claude.com/docs/en/slash-commands>
  - Subagents: <https://code.claude.com/docs/en/sub-agents>

## Terms and Abbreviations

- `AGENTS.md`: agent governance file used directly by Codex and installed as a shared-governance module for supported packs.
- `agents-mode`: Orchestrarium routing and operator overlay file for provider preferences and execution policy.
- `CLI`: Command-Line Interface, a terminal command surface for a provider runtime.
- `Codex`: OpenAI Codex runtime and production provider line.
- `Claude Code`: Anthropic's Claude runtime and production provider line.
- `extension`: provider-supported package directory that can bundle context, skills, agents, commands, or manifests.
- `local`: project-level install scope under a target repository.
- `MCP`: Model Context Protocol; a mechanism for exposing tool and resource servers to agent runtimes.
- `runtime root`: provider-facing directory where installed context, skills, agents, commands, or overlays live.
