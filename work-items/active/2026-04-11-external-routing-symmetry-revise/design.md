# Design Package

## Canonical model

| Item | Decision |
|---|---|
| External provider universe | One shared universe for all three packs: `auto | codex | claude | gemini` |
| Workdir policy | Provider-specific workdir keys stay separate; all default to `neutral` |
| Claude transport | `claude-api` is a Claude secondary transport, not a fourth provider |
| Parallelism | Eligible external lanes may run in parallel regardless of internal slot pressure |
| Visual routing | Gemini is first for image/icon/decorative visual worker and visual-review lanes |
| Truthfulness | Docs and init surfaces must describe only real runtime behavior |

## Shared routing rules

| Layer | Canonical rule |
|---|---|
| Provider selection | All packs expose the same provider universe: `auto | codex | claude | gemini` |
| `auto` semantics | `auto` resolves by lane type, not by host pack |
| Lane routing | One common lane-priority matrix for all packs |
| Transport | Provider-local transport knobs remain separate from provider selection |
| Workdir | `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, `externalGeminiWorkdirMode` remain provider-specific and default `neutral` |
| Self-provider | Allowed only as explicit override for isolation, profile, transport, or independent rerun; never as ordinary `auto` result |
| Failure behavior | Fail fast on unsupported owner-role externalization, unavailable provider, or illegal self-recursion |

## Lane-priority matrix

| Lane | Priority |
|---|---|
| `advisory.repo-understanding` | `claude > gemini > codex` |
| `advisory.design-adr` | `claude > codex > gemini` |
| `review.pre-pr` | `claude > codex > gemini` |
| `worker.default-implementation` | `codex > claude > gemini` |
| `worker.long-autonomous` | `claude > codex > gemini` |
| `worker.visual-icon-decorative` | `gemini > claude > codex` |
| `review.visual` | `gemini > claude > codex` |

## Self-provider rule

| Case | Rule |
|---|---|
| Ordinary `auto` routing | Must not resolve to the same provider as the current host line |
| Explicit self-provider request | Allowed if the user explicitly asks, or if routing needs profile, transport, or isolation differences |
| Silent self-bounce | Forbidden |
| Owner roles | Still unsupported for generic externalization |
| Claude transport | `externalClaudeSecretMode` and `externalClaudeApiMode` apply only after provider already resolved to `claude` |

## Accepted alternatives

| Option | Verdict | Why |
|---|---|---|
| Keep line-specific provider universes | Reject | Preserves current asymmetry and keeps docs/init/live overlays fighting each other |
| Make one global winner provider | Reject | Conflicts with lane-specific strengths and accepted external comparative research |
| Add `claude-api` as a top-level provider | Reject | It is transport under `claude`, not a separate execution family |

## Required change boundary

| Must change now | Why |
|---|---|
| `Orchestrarium/docs/agents-mode-reference.md` | Canonical provider universe, lane matrix, self-provider rule, Claude transport semantics |
| `Orchestrarium/src.codex/skills/lead/external-dispatch.md` | Replace host-pack-specific provider scope with common universe and common resolution rules |
| `Orchestrarium/src.claude/agents/contracts/external-dispatch.md` | Same |
| `Orchestrarium/src.gemini/skills/lead/external-dispatch.md` | Same |
| `Orchestrarium/src.codex/skills/init-project/SKILL.md` | Generated `.agents-mode` must use the new canonical universe |
| `Orchestrarium/src.claude/commands/agents-init-project.md` | Same |
| `Orchestrarium/src.gemini/skills/init-project/SKILL.md` | Same |
| `Orchestrarium/README.md` | Root truthfulness about shared provider universe |
| `Orchestrarium/INSTALL.md` | Same |
| `Orchestrarium/src.gemini/commands/agents/help.toml` | Help text must match the shared routing model |
| Standalone mirrors in `codex/`, `claude/`, and `gemini/` | Keep standalone packs truthful and symmetric with `main` |

## Deferred surfaces

| Surface | Why deferred |
|---|---|
| Codex `team-templates` materialization gap | Separate structural parity project |
| Claude helper-vs-agent normalization | Separate role-surface normalization project |
| Gemini dual `skills/` + `agents/` shape | Routing canon can be fixed without replatforming Gemini surfaces |
| Command-surface parity across all three packs | Separate UX/control-plane follow-up |

## Acceptance checks

| Check | Expected result |
|---|---|
| All four `agents-mode-reference.md` files | identical provider-universe semantics and lane matrix |
| All three init surfaces in `main` plus standalone mirrors | write same provider universe and provider-specific workdir defaults |
| All three external-dispatch contracts in `main` plus standalone mirrors | same provider resolution, same self-provider rule, same Claude transport semantics |
| Live overlays `.agents/.agents-mode`, `.claude/.agents-mode`, `.gemini/.agents-mode` | materialize the documented keys, including Claude transport keys where Claude is selectable |
| Root docs | no remaining line-specific lie about provider universe |
| Validators | Codex, Claude, Gemini validators all pass |
| Deep diff audit | no remaining mismatch where docs say one provider universe and overlays/init files say another |
