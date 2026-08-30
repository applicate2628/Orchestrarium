# External Dispatch Contract

This contract defines the shared Claude-line routing semantics for the consultant toggle file and the external adapters.

## Shared config file

- Canonical path: `.claude/.agents-mode.yaml`
- Legacy `.claude/.agents-mode` is compatibility input only. Resolve Claude overlay state in this read order (highest to lowest precedence, per-key resolution): local `.claude/.agents-mode.yaml`, local legacy `.claude/.agents-mode`, pack-local global `~/.claude/.agents-mode.yaml`, pack-local global legacy `~/.claude/.agents-mode`, shared cross-pack global `~/.agents-mode.yaml` (alongside `~/.claude.json`), then built-in defaults. Each key resolves to the highest layer that defines it; layers compose, they do not replace each other wholesale. Normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope, do not recreate any legacy file, and do not synthesize a local override on read alone.
- Full value-by-value operator semantics live in `docs/agents-mode-reference.md` in the source repository (maintainer reference; not installed at runtime).

Supported canonical keys:

```yaml
consultantMode: external  # allowed: external | internal | disabled; default: disabled
delegationMode: auto  # allowed: manual | auto | force; default: auto
parallelMode: auto  # allowed: manual | auto | force; default: auto
mcpMode: auto  # allowed: auto | force; default: auto
preferExternalWorker: true  # allowed: false | true; default: false
preferExternalReviewer: true  # allowed: false | true; default: false
externalProvider: auto  # allowed here: auto | codex | claude | kimi | grok; default: auto; kimi is explicit read-only/nonauthorizing; grok is unavailable in 1.x
externalPriorityProfile: balanced  # allowed: balanced | quality-first | <repo-local production profile>; default: balanced
reserveResolver: claude-sonnet  # allowed: disabled | claude-sonnet | claude-wrapper | wrapper:<command>; default: claude-sonnet
externalPriorityProfiles: {}  # allowed: structured profile map
externalOpinionCounts: {}  # allowed: structured lane-count map
externalCodexWorkdirMode: neutral  # allowed: neutral | project
externalClaudeWorkdirMode: neutral  # allowed: neutral | project
externalModelMode: runtime-default  # allowed: runtime-default | pinned-top-pro; default: runtime-default
externalCodexProfile: gpt-5.6-sol-xhigh  # allowed: default | gpt-5.6-sol-xhigh | gpt-5.6-sol-max | gpt-5.6-terra; default: gpt-5.6-sol-xhigh
```

Semantics:

- `consultantMode` continues to govern `$consultant`.
- `delegationMode: manual` keeps explicit user-request behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation a standing instruction whenever a matching specialist and viable tool path exist.
- `parallelMode: manual` keeps ordinary parallel fan-out explicit-only, `auto` parallelizes safe independent lanes by routing judgment, and `force` makes safe parallel launch a standing instruction whenever scopes are independent and the merge cost is justified.
- `mcpMode: auto` lets the agent decide when available MCP tools are appropriate; `force` makes relevant MCP usage a standing explicit instruction.
- `preferExternalWorker` and `preferExternalReviewer` are routing preferences for eligible external adapter substitutions.
- `externalProvider` uses the shared provider universe `auto | codex | claude | kimi | grok`.
- `externalProvider: auto` resolves by lane type through the active named production priority profile instead of by host-pack identity. Shipped `auto` profiles use the Codex/Claude pair only and do not select explicit-only providers.
- `externalPriorityProfile` selects the named provider-order map used only when `externalProvider: auto`; missing means `balanced`.
- `reserveResolver` binds the symbolic `reserve` candidate to one concrete read-only resolver: `disabled`, `claude-sonnet`, `claude-wrapper`, or `wrapper:<command>`. `wrapper:<command>` is a PATH-resolved command or repo-relative wrapper path, not an argv prompt channel.
- **Layer-provenance trust gate for executable-bearing values (binding).** `wrapper:<command>` names an arbitrary executable, and the highest-precedence project-local `.claude/.agents-mode.yaml` can arrive inside a cloned repository — an untrusted source that must never silently select code the agent then executes. An executable-bearing value is honored without further confirmation only when a user-global layer (`~/.claude/.agents-mode.yaml`, legacy `~/.claude/.agents-mode`, or `~/.agents-mode.yaml`) defines it or defines the identical value. A project-local `wrapper:<command>` absent from every user-global layer resolves as `reserveResolverTrust: project-UNCONFIRMED` (the machine-readable flag emitted by `scripts/resolve-agents-mode.py`, the executable reference in the source repository) and MUST NOT be launched until the user explicitly confirms it on first use (`AskUserQuestion`). Record the approval durably by writing the approved value into a user-global layer — that write is what flips subsequent resolutions to `reserveResolverTrust: user-global`. "Approved" wrapper anywhere in this pack's guidance means exactly this mechanism: defined or confirmed at a user-global layer, never a repo-supplied value alone.
- `externalPriorityProfiles` stores the ordered provider lists per lane for each named profile; the shipped profiles live in the shared operator reference.
- `externalOpinionCounts` stores how many distinct external opinions to collect per lane; missing entries mean `1`.
- `externalCodexWorkdirMode` and `externalClaudeWorkdirMode` choose whether each production-provider external run starts in a fresh neutral empty directory or in the current project/worktree. The ordinary default is `neutral`.
- `externalModelMode` is the shared cross-provider model policy. `runtime-default` must be resolved to the installed runtime's observed supported model/effort and passed as explicit launch flags before launch — it does NOT leave the provider on an ambient config default. `pinned-top-pro` starts on the strongest documented provider-native model/profile and allows one named same-provider fallback on retryable provider exhaustion.
- `externalCodexProfile` is the Codex-specific external profile override after provider resolution. `default` inherits `externalModelMode`, including when `externalProvider: auto` resolves to Codex. `gpt-5.6-sol-max` requests model `gpt-5.6-sol` with `model_reasoning_effort = "max"` for higher-complexity/hard lanes (NOT `gpt-5.6-sol-ultra`, which spawns subagents and must never be shipped on a subagent lane). `gpt-5.6-terra` selects the balanced Codex model (a distinct model, `model_reasoning_effort = "high"`, not an effort downgrade of `gpt-5.6-sol-xhigh`) — it must still be verified against the installed runtime before it is reported as used. `gpt-5.6-sol-xhigh` (shipped as the default; symmetric to `externalClaudeProfile: opus-xhigh`) explicitly requests model `gpt-5.6-sol` with `model_reasoning_effort = "xhigh"` via `-c model_reasoning_effort=xhigh` regardless of `externalModelMode`. The advisory/consultant lane runs at HIGH effort by default — Codex `gpt-5.6-sol` + `model_reasoning_effort=xhigh`, Claude `--model opus --effort xhigh` — overriding the operator-set effort knob. `xhigh` is the default for both providers; for especially heavy / complex tasks that genuinely need more depth, the orchestrator may escalate the consultant to the provider's deepest tier (Claude `--effort max`). Never downshift a consultant lane below `xhigh`.
- `reserve` is a symbolic supplemental read-only candidate that may appear only in advisory and review profile orders after primary `claude`/`codex`. It is independent of the primary `claude` candidate, not a scalar provider key, not a primary-provider retry, and not an implementation or editing fallback. The concrete resolver comes from `reserveResolver` and must be recorded in the execution artifact.
- Treat named fallback paths as alternate limit or budget pools only when runtime observation shows they exhaust independently. That remains repo-local operator policy rather than an official provider guarantee.
- Every provider-backed run MUST carry the resolved model/profile and effort as explicit launch flags in that invocation, even when they equal configured defaults; never rely on provider config defaults. Resolve `runtime-default` to the installed runtime's observed supported model/effort before launch, or report the route unavailable if it cannot be made explicit. Record the exact flags in the execution artifact.
- Claude-line does not use `externalClaudeProfile` as part of the canonical schema and should not write it into `.agents-mode.yaml`.
- Any tool that updates the file must preserve unknown keys in the canonical output and must not rewrite the file back to a consultant-only shape.
- Any read of the effective Claude overlay that influences routing must normalize that file to the current canonical format before trusting the flags. Comment-free or older-layout files are valid input, not valid output.
- If local `.claude/.agents-mode.yaml` is missing, read local legacy `.claude/.agents-mode` as compatibility input only; if both local files are missing, fall back through pack-local global `~/.claude/.agents-mode.yaml`, pack-local global legacy `~/.claude/.agents-mode`, then the shared cross-pack global `~/.agents-mode.yaml`, before applying built-in defaults. Normalize whichever file supplied the effective config in place before trusting the flags.
- When writing `.claude/.agents-mode.yaml`, keep each key on its own line and add an inline YAML comment that enumerates the allowed values for that key.
- Normalization preserves effective known values and unknown keys, fills missing canonical keys with current defaults, removes retired canonical keys, refreshes inline comments plus the shipped profile/count blocks, and restores canonical key order.

## Claude-line provider

- `externalProvider: auto` resolves by lane type through the active named production priority profile instead of by host-pack identity.
- When the resolved provider is Codex, honor `externalCodexWorkdirMode`; when it is Claude, honor `externalClaudeWorkdirMode`.
- When the resolved provider is Codex, `externalCodexProfile: default` inherits `externalModelMode`; `externalCodexProfile: gpt-5.6-sol-max` requests model `gpt-5.6-sol` with `model_reasoning_effort = "max"` for higher-complexity/hard lanes; `externalCodexProfile: gpt-5.6-terra` selects the balanced Codex model tier (a distinct model, `model_reasoning_effort = "high"`, not an effort downgrade) and must record unavailable or deviated if that model cannot be verified against the installed runtime; `externalCodexProfile: gpt-5.6-sol-xhigh` (shipped as default) requests model `gpt-5.6-sol` with `model_reasoning_effort = "xhigh"` regardless of `externalModelMode`, and is the best-effort sibling of Claude's `opus-xhigh`.
- Explicit `externalProvider: claude` is a self-provider override only. Ordinary `auto` must not silently self-bounce into the current host line's own provider (the host-line-relative self-bounce rule).
- `reserve` is considered only when an advisory or review profile order reaches it after primary `claude`/`codex`; it does not skip earlier primary profile candidates.
- Treat `reserve` as a supplemental advisory/review candidate only. It never grants permission to run implementation, worker-side execution, or editing work through the resolved transport.
- When an advisory or review route resolves to `reserve`, bind it through `reserveResolver`. `claude-sonnet` means the approved Sonnet-style read-only reserve path; `claude-wrapper` means the installed wrapper under `.claude/agents/scripts/invoke-claude-api.py` or `.sh`; `wrapper:<command>` means a PATH-resolved command or repo-relative wrapper path, subject to the layer-provenance trust gate above (a `project-UNCONFIRMED` value must not be launched before first-use user confirmation). The Claude wrapper reads `ANTHROPIC_*` from repo-local `.claude/SECRET.md` first and then from `~/.claude/SECRET.md`, then launches plain `claude`.
- If the chosen `reserve` resolver is unavailable, disclose that as a dependency/config failure.
- If the plain Claude CLI is selected and fails, do not silently convert that same primary `claude` run to the wrapper. Advisory/review lanes may later collect `reserve` as a separate profile candidate when enabled; worker or mutating routes must report Claude unavailable or reroute honestly.
- Use `.claude/agents/scripts/invoke-claude-api.py` from PowerShell or `.claude/agents/scripts/invoke-claude-api.sh` from Bash or Git Bash only when that wrapper is the approved resolver for a resolved `reserve` advisory/review candidate. The Python entrypoint is the canonical implementation; the Bash launcher must honor `CLAUDE_BIN` when the shell PATH differs from PowerShell PATH.
- On Windows, keep the ordinary external launch path unchanged and try the native Windows shell first. If that native shell path fails because of shell bootstrap, execution-policy, or environment-policy problems, retry once through Git-for-Windows Bash / MSYS when available. Do not use the WSL `bash.exe` stub as a fallback, and do not reinterpret ordinary provider auth, quota, or model failures as shell-fallback triggers.
- Use `gpt-5.6-terra` as the balanced cheaper-than-flagship Codex reasoning lane when full `gpt-5.6-sol` depth is not required; a genuine reasoning model whose output stays review-gated like any external lane.
- Every substantive external task prompt must use an approved thin wrapper and file/stdin delivery. Command-line arguments are limited to launcher flags, model/profile options, and paths; inline argv is permitted only for a fixed synthetic non-substantive smoke token, never a provider limitation or real task.
- The canonical Claude-pack transports for primary runs are `.claude/agents/scripts/invoke-codex-prompt.py` / `.sh` and `.claude/agents/scripts/invoke-claude-prompt.py` / `.sh`; invoke the approved thin wrapper synchronously with one caller-owned absolute `--terminal-receipt <path>`. Consume the single V2 `ORCHESTRARIUM_PROVIDER_RESULT_V2` envelope through the strict V2 parser, using its complete untrusted/potentially-sensitive resultText, full external-nonauthorizing tuple, combined outcome, cleanup status, and wrapper process exit. If a caller-side wait loses stdout, read that exact line from the reserved receipt after the wrapper settles. For tracked runs, read the path-free terminal ledger back separately after return. The caller owns receipt retention/deletion; wrapper-private prompt, stdout, stderr, and process paths are not consumer surfaces. No transport-neutral raw provider chain is an approved substantive prompt path; fail or reroute when an approved wrapper is unavailable.
- Kimi is an explicit read-only route for policy-admitted broad research and review. On Windows it requires an installer enrollment pin and invokes fixed `kimi-code/k3` text output with a no-tools/no-subagents sealed agent bundle under an OS-temp private run directory; it has no native effort selector, remains independently verified and nonauthorizing, and never enters shipped `auto`. Grok remains an unavailable policy name in 1.x: do not launch or probe it.
- For Kimi, `invoke-kimi-prompt` is the only approved Kimi launch surface. The wrapper alone owns every Kimi provider argument. Callers pass the unchanged task prompt file to the wrapper and must not invoke `kimi`, `kimi.exe`, `kimi --prompt`, or compose `--auto`.
- **WARNING — automated Claude authentication:** the `invoke-claude-prompt.py` / `.sh` transport selects and conflict-checks explicit `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, Amazon Bedrock, Google Vertex AI, and the existing subscription override before any user-settings lookup; these modes do not require `HOME` or `CLAUDE_CONFIG_DIR`. A supplied `CLAUDE_CONFIG_DIR` is validated only when actually forwarded or inspected. With no explicit mode, any user-settings `apiKeyHelper` key is refused as `E_EXTERNAL_PROVIDER_API_KEY_HELPER_UNSUPPORTED` before prompt capture or provider lookup and is never executed or interposed. Use `invoke-claude-api.py` / `.sh` as the key-backed path; it loads `ANTHROPIC_AUTH_TOKEN` and `ANTHROPIC_BASE_URL` from `SECRET.md`. See [Anthropic's Claude Code legal and compliance guidance](https://code.claude.com/docs/en/legal-and-compliance).
- For wide release or parity audits, split the admitted scope by repo, file set, or lane instead of launching one mega neutral-dir prompt across the whole pack family.
- Provider-backed consultant execution in `external` mode plus `$external-worker` and `$external-reviewer` must use direct external launch from the orchestrating runtime or an approved transport wrapper script. Do not proxy them through an internal agent/helper/subagent host.
- The adapter does not change the team template JSON.
- The adapter replaces an eligible internal role at routing time and keeps the replaced role label in provenance.
- If the external CLI is unavailable, the adapter is disabled and the orchestrator may reroute the work to another eligible path.
- The adapter itself must not silently fall back to an internal specialist.
- `parallelMode` is the general orchestrator rule for whether independent helper lanes should be parallelized by judgment at all; external adapter fan-out is one overlay on top of that rule.
- Multiple external adapters may run in parallel when their scopes are independent, `parallelMode` permits ordinary parallel fan-out, and the selected provider runtimes support concurrent non-interactive execution.
- Do not cap that fan-out at one instance per helper or provider: the same external helper and the same resolved provider may be launched multiple times concurrently when each run owns a different admitted artifact or disjoint slice.
- `externalOpinionCounts` governs distinct-provider opinions for one lane; it does not replace the general `parallelMode` rule or forbid brigade-style reuse of the same provider across different independent lanes or slices.
- Same-provider external helper reuse is allowed when each run owns a different admitted artifact or disjoint slice.
- If internal native slot limits would otherwise block more independent eligible lanes, prefer available external adapters instead of silently serializing or dropping them.
- When multiple independent external lanes should launch together, prefer the operator surface `/agents-external-brigade` so the batch has one explicit brigade plan and one aggregated result surface. This is the dedicated brigade surface.

## Prompt-content contract

The prompt file is the only governance an external Command-Line Interface (CLI) inherits. Before launch it must:

- Remain a raw, caller-authored handoff. The provider-neutral `provider_prompt.py::launch` wrapper seam snapshots and prefixes the installed `scripts/external-prompt-governance.md` projection in memory; its sole authored source is `shared/external-prompt-governance.md`. Role and provider documents must reference this seam and must not copy its policy text. Substantive raw provider Command-Line Interface (CLI) prompt routes are unsupported: use an approved thin `invoke-<provider>-prompt` wrapper.
- Include the complete handoff template verbatim from the owning `contracts/subagent-contracts.md`, including its mandatory pre-dispatch fill rule and defect-class completeness trigger; this contract cites that owner and does not reproduce its field list.
- State the assigned role's gate vocabulary and one-artifact requirement.
- Include a provenance-header echo instruction using this contract's header fields.
- Include the evidence-citation discipline verbatim from the owning `Evidence discipline:` handoff field; this contract does not create a second copy.
- For an adversarial review strategy, use an artifact-only prompt: include the artifact and review scope, but exclude builder claims and self-review.
- Immediately before an approved non-interactive Codex launch, `provider_prompt.py::launch` runs the installed Codex hook-health helper in `require` mode. A nonzero trust/liveness verdict prevents `codex exec`; this gate does not apply to Claude launches.

## Run-completion oracle

- A prompt-wrapper run is complete only after the provider reaches a terminal state and the wrapper performs this order: enforce one live combined raw-byte quota across supervisor-owned stdout/stderr pipes; settle the process tree; extract one complete bounded result and primary outcome; dispose of the exact private run directory through validated same-parent tombstoning; build one V2 line; run the existing credential and machine-path detectors over the full serialized line for every provider; durably commit and exactly read back the caller-owned terminal receipt; write and flush the identical line to stdout exactly once; append exactly one optional path-free terminal ledger event; return. A detector finding or unavailable detector commits only a minimal blocked envelope with empty `resultText` and no dynamic detail. Codex runs as `exec --json` and `resultText` is the last strict UTF-8, newline-complete `item.completed` record whose `item.type=agent_message`; Claude uses its bounded stdout. Raw stdout and raw stderr are never duplicated into public output.
- The V2 envelope carries bounded `primaryOutcome` metadata plus the combined `exitCode`, `token`, `status`, `gate`, `note`, `cleanupStatus`, `cleanupIssueCount`, `captureRecoveryRetained`, `cancelled`, `timedOut`, and `stderrMarkerCount`, provider/model/effort identity, and the mandatory `authorizing=false`, `closesRunIds=[]`, `independentVerificationRequired=true`, `terminalClass=external-nonauthorizing`, `actualExecutionPath=direct-external-cli` tuple. Parsed provider `PASS`/`REVISE` retains its original token/status/gate/note in `primaryOutcome` but emits `COMPLETE:EXTERNAL_NONAUTHORIZING`; failures retain their failure token. Credential echo or scan-unavailable produces empty result text and a nonzero `UNVERIFIED:E_EXTERNAL_PROVIDER_CREDENTIAL_*` result. A V1 prefix/schema or incomplete/nonempty authority tuple fails closed. `resultText` remains direct provider output, untrusted and potentially sensitive: callers must not persist or re-prompt it. A terminal-ledger failure after a successful flush is reported by stderr and a nonzero wrapper exit, never by a speculative envelope field. Any failed combined check remains non-PASS: re-dispatch it or return `BLOCKED:dependency`.
- `provider_prompt.py::launch` owns its timeout through `--timeout-secs` (default `3600`) and delegates streaming supervision to `supervise_provider_io`: the supervisor computes a monotonic deadline and polls `process.wait(timeout=0.05)` until the child exits, a stream failure/overflow occurs, or the deadline expires. A real timeout terminates and reaps the provider, sets `timedOut=true`, and returns `124`; cancellation terminates and reaps it, sets `cancelled=true`, and returns `130`. Success, provider failure, timeout, cancellation, and post-launch errors converge on the same terminal finalizer.
- Prompt, stdout, stderr, and process files are fixed children of one randomized private `RunCaptureLifecycle` directory below an absolute configured root. Immediately after `mkdtemp`, acquisition is provisional: hardening/metadata/initialization failure authorizes only `os.rmdir` while empty; nonempty or unremovable state is preserved as non-PASS evidence. After ownership is established, terminal cleanup revalidates identity and same parent, atomically tombstones the exact directory, rejects link/junction/reparse content, and removes it. `--capture-max-bytes` defaults to 16 MiB (hard maximum 256 MiB); `--result-max-bytes` defaults to 1 MiB (hard maximum 16 MiB) and must not exceed the capture limit. Overflow is typed, terminates/reaps the child, safely cleans established captures, and emits only bounded counts, issue count, and a per-run salted digest whose salt is never emitted. Below-cap parse/materialization failure preserves secure recovery evidence.
- A completion notification — a harness background-task signal, wrapper exit message, or task callback — is not a substitute for the envelope oracle. Consumers validate `resultText` and its terminal metadata; they never poll or retain the wrapper's transient capture paths.
- `await-codex-dispatch` remains an independent watcher for caller-managed background launches that create and retain their own `.out`, `.err`, optional `.lastmsg`, and optional `.pid` inputs. The prompt wrappers neither print a watcher command nor hand their private capture paths to it. For independently managed captures, `.lastmsg` has precedence over `.out`, and a CLI upgrade must re-check the assumption that `.out` contains only terminal provider output.

## Direct liveness probe for the standalone watcher

For a caller-managed background launch, artifact timestamps alone cannot prove whether a silent run is still alive. The independent watcher's terminal statuses therefore include `DEAD` (exit `69`, `EX_UNAVAILABLE`), reached only when a **direct probe of the caller-recorded process** — never an artifact or a notification — confirms it gone. This interface does not apply to synchronous prompt-wrapper calls, whose timeout and process cleanup are owned inside `provider_prompt.py`.

- **What the caller supplies.** `--pid-file` points to a caller-owned sidecar containing `pid=<PID>` and, when available, `start=<opaque marker>`. The caller that created the background process owns the accuracy, lifetime, and cleanup of this file. Prompt-wrapper `.pid` captures are private receipts and are never watcher handoffs.
- **PID reuse.** A process identifier alone goes stale the instant the process exits, and an OS may hand that same identifier to an unrelated later process — a real hazard, not a theoretical one. The recorded start marker exists solely to catch this: the watcher re-reads the CURRENT start marker for the recorded PID and compares it for equality against the recorded one; a mismatch (a different process now holds that PID) is treated as `DEAD`, never as alive. No start marker recorded (an older host with no `/proc`, or a process that exited before the marker could be read) falls back to existence-only trust in the PID — weaker, but still a genuine direct probe, never inferred from artifacts.
- **The combined rule ("not running" is ambiguous on its own).** A finished-successfully run and a died-silently run are both "not running" from a bare liveness probe. The watcher therefore always evaluates its pre-existing DONE conditions (non-empty `.lastmsg`/`.out`, or a changed `HEAD` when `--commit-base` was supplied) FIRST, every poll; only when none of them fired that same iteration does a confirmed-dead probe result produce `DEAD`. A process that exits normally immediately after writing its completion artifact is therefore still `DONE` (exit `0`) even though the same poll would also see its PID gone — the artifact wins. Only a gone process with **no** completion artifact yet reaches `DEAD`.
- **Missing handoff.** `--pid-file`/`-PidFile` is optional. When a caller-managed launch omits it, or supplies a missing, unreadable, or malformed file, the watcher treats liveness as unknown and uses its artifact-only outcomes (`DONE`, `STALL`, or `TIMEOUT`); it never infers `DEAD`. `DEAD` is reachable only when a supplied handoff actively confirms the process is gone.

## Cybersecurity content-filter detection

A second silent-success shape, distinct from `DEAD`: a provider's own content-policy filter fires mid-run, the child process exits `0` having spent its whole token budget, and both completion artifacts (`.out`, `.lastmsg`) stay empty forever — indistinguishable from "still working" for the entire stall/timeout window (observed live: 0-byte `.out`, absent `.lastmsg`, exit `0`, 229k tokens spent, reported as `STALL` — the wrong cause — only after the full 2700s wait). The watcher's terminal statuses therefore include a fifth outcome, `FILTERED` (exit `77`, `EX_NOPERM`), reached the same poll the conjunction below holds — never subject to `--stall-secs`.

- **The conjunction.** `FILTERED` requires BOTH legs, never either alone: (1) none of the pre-existing DONE conditions fired that same poll (a completed run is never overridden even if its `.err` happens to contain the phrase), AND (2) the LAST few KB of `.err` — never the whole file — carry the filter marker. Scanning only the tail is deliberate: a real dispatch's `.err` is a full transcript that starts by echoing the prompt itself, so a whole-file scan risks matching an early, unrelated mention (this very detection being discussed in a dispatched prompt, for instance) while the run is still genuinely alive; the real marker sits in the last ~15 lines of a 4000+ line transcript.
- **Marker matching is loose by design.** The marker string is provider prose that will drift in wording. The match requires both the "flag" concept and the "cybersecurity" concept (case-insensitively, either order) to appear in the tail window, rather than pinning the exact sentence — loose enough to survive rewording, but two independent words rather than one common word, so a healthy run's unrelated chatter cannot misfire this status.
- **The remedy is model-specific, and is never a prompt reword.** The filter is a property of the dispatched model, not the task. The correct response to `FILTERED` is to re-dispatch the SAME lane on a DIFFERENT model, unchanged. Rewording the prompt to appease the filter changes what was asked — a worse outcome than a model swap — and the watcher's own status line names this remedy explicitly so the decision does not depend on a human noticing an empty file.

## Stall and timeout policy

| Effort tier and lane | Earliest valid stall window |
| --- | --- |
| Ordinary advisory | 5-15 minutes |
| `xhigh` / `max` worker or review | 45-60 minutes |

- Synchronous prompt-wrapper calls use the wrapper-owned `--timeout-secs` limit and consume the returned result envelope; they are never actively polled through transient sidecars. For a separately implemented caller-managed background launch, `await-codex-dispatch` remains the Claude-line Codex poller: it stops on non-empty `.lastmsg`/`.out` (exit `0`, `DONE`), a changed `HEAD` when `--commit-base` is supplied (also `DONE`), a confirmed-dead recorded process with no completion artifact when `--pid-file` was supplied (exit `69`, `DEAD`), a provider cybersecurity content-filter marker in `.err`'s tail with empty completion artifacts (exit `77`, `FILTERED`), an idle `.err` beyond `--stall-secs` (exit `75`, `STALL`), or `--max-secs` (exit `124`, `TIMEOUT`). Its default stall threshold is 2700 seconds (45 minutes); callers may shorten it only when lane policy permits. A stall declaration before the applicable window without process evidence violates this contract.
- **Whether a completion notification arrives depends on how an independently managed background run was launched; its presence is not proof and its absence is not a stall.** A harness completion notification fires only when the MAIN orchestrating loop owns a harness-tracked background process through provider exit. A dispatched subagent is never re-invoked when its own background child finishes. Prompt wrappers are synchronous terminal-result transports, not watcher or notification handoffs.
- If an independently managed background shell times out, do not relaunch: identify the running process first and stop it only if it is orphaned or no longer needed. A prompt-wrapper timeout is already terminal: the wrapper terminates and reaps the child, returns `124`, and marks the result envelope `timedOut=true`.
- A run declared stalled is `UNVERIFIED`; any re-dispatch cites the failed attempt and never duplicates a still-running process.

## Write capability by lane type

- Review, Quality Assurance (QA), and advisory lanes launch with the provider's read-only or sandboxed mode wherever the resolved CLI supports one, and record those permission flags in `Launch flags`.
- A worker lane producing edits from a neutral workdir returns a reviewable edit payload as either a unified diff or a full-file set with repo-relative target paths; the worker artifact names which payload format it used.
- In-place worker editing requires project workdir mode plus the marker-declared isolation worktree defined by decision `2026-07-10-worktree-isolation-canonical-path`; never grant a worker write access to the user's dirty primary tree.

## External worker

- `$external-worker` is the external worker-side adapter.
- It may stand in for any eligible non-owner, non-review role.
- The `Assigned role` provenance label names the internal worker role being replaced.
- Worker-side tasks stay worker-side; the adapter does not take review or QA ownership.

## External reviewer

- `$external-reviewer` is the external review-side adapter.
- It may stand in for any eligible review or QA-side role.
- The `Assigned role` provenance label names the internal review-side role being replaced.
- Review-side tasks stay review-side; the adapter does not take implementation ownership.

## Eligibility gate

Resolve external dispatch in this order: `role eligibility -> provider selection -> CLI availability`.

| Requested role family | External path | Required result |
| --- | --- | --- |
| Advisory second opinion | `$consultant` | Advisory-only. Never becomes a worker or review lane. |
| Eligible worker-side role | `$external-worker` | Valid only after routing has already classified the work as non-owner, non-review work. This includes research, design, planning, scientist or constraint, implementation, and repository-hygiene roles. |
| Eligible review or QA-side role | `$external-reviewer` | Valid only after routing has already classified the work as review or QA. |
| Roles mapped to `none` by `external-role-taxonomy.v1.json` | unsupported | Fail fast before provider resolution. The current mapping includes `$product-manager`, `$lead`, `$knowledge-archivist`, `$external-worker`, and `$external-reviewer`; the taxonomy, not this example list, owns policy. |

Rules:

- An explicit request for `external` does not create a new adapter type.
- Unsupported external role requests must stop with an unsupported-route explanation and an honest reroute suggestion instead of probing provider availability as if a missing adapter might exist.
- Worker-side specialist lanes such as `analyst`, `architect`, `planner`, `algorithm-scientist`, `computational-scientist`, `security-engineer`, `performance-engineer`, and `reliability-engineer` remain eligible for `$external-worker` when routing selects external substitution. Do not remap `$knowledge-archivist`; its current taxonomy disposition is `none`.
- Before honoring `reserve`, classify the selected lane name. Only `advisory.*` and `review.*` profile lanes may retain `reserve`; worker, implementation, repository-hygiene, installer, publication, or other lanes must strip or ignore it.

## Named priority profiles

- `externalPriorityProfile` selects the named provider-order map used only when `externalProvider: auto`.
- `balanced` is the shipped default profile and must always exist.
- `quality-first` is the shipped alternate production profile for maximum result quality; it biases near-tie advisory, source-bound, and review lanes toward Codex while preserving Claude-first lanes where the benchmark evidence gives Claude a clearer compact or visual-worker edge.
- The shipped `balanced` and `quality-first` profiles follow the release-backed `12 + 1` routing read in `docs/routing/full-v2-hard-r2-routing-evidence-2026-05-01.md` (maintainer reference; not installed at runtime); the `L00 owner/control` line is not an external profile lane because owner roles have no generic external adapter. Currency: `ASSUMPTION (UNVERIFIED — lane priorities carried over from the gpt-5.5/opus-4.7 release, pending re-benchmark)`; the benchmarked models are retired and the lane orders have not been re-validated on the current families.
- Model-family migration invalidates routing evidence (standing rule): whenever a migration of `externalCodexProfile` or `externalClaudeProfile` retires, renames, or replaces the model family behind any routed lane, the routing-evidence `PASS` is invalidated in the same change — the shipped lane priorities become `ASSUMPTION (UNVERIFIED)`, carried over from the last benchmarked release, until the routing evidence is re-benchmarked or explicitly re-affirmed on the current model families. This is the routing-evidence form of the material-upstream-revision rule: a materially revised accepted upstream artifact marks its dependent downstream artifacts for re-review.
- Repo-local heuristics may refine lane classification, but they must not invent a different provider universe.
- Ordinary `auto` must not resolve to the same provider as the current host line.

## Provenance header

Every external or consultant artifact should include one explicit execution record with these separate fields:

- `Execution role: <consultant | external-worker | external-reviewer>`
- `Assigned / replaced internal role: <eligible internal role label | none>`
- `Requested provider: <internal | auto | codex | claude | kimi | grok>`
- `Resolved provider: <Codex CLI | Claude CLI | Kimi CLI | none>`
- `Requested consultant mode: <external | internal | disabled>` when consultant routing is relevant; otherwise `not-applicable`
- `Actual execution path: <internal consultant | external CLI (Codex CLI) | external CLI (Claude CLI) | external CLI (Kimi CLI) | role disabled>`
- `Model / profile used: <actual profile or model when known | runtime default | unspecified by runtime>`
- `Launch flags: <exact argv model / effort / sandbox flags>`
- `Run record: <started and finished timestamps or duration; wrapper exit; terminal ledger runId when tracked>`
- `Deviation reason: <none | external unavailable: [reason] | explicit override>`

Rules:

- Kimi may be selected only for policy-admitted read-only research/review and must be recorded truthfully as a nonauthorizing provider with independent verification; Grok remains unavailable and must never be selected, executed, or recorded as a realized provider in 1.x.
- Before declaring a route unavailable, run `command -v` or `Get-Command` for the resolved CLI in the current session and record the availability-probe output in the execution artifact; a route change requires the probe result plus a populated `Deviation reason`. A missing wrapper, older failed run, or empty `.out` is indirect evidence and does not prove unavailability.
- Keep `Execution role` and `Assigned / replaced internal role` on separate lines. Do not merge them into one ambiguous label.
- `Requested provider: internal` means no explicit external provider was requested by the caller and routing/default resolution picked the provider. It must not be rendered as `auto` in the artifact.
- `internal consultant` is valid only for the consultant role when `consultantMode: internal`.
- Provider-backed consultant execution in `external` mode plus `$external-worker` and `$external-reviewer` must show a direct external transport path. An internal agent/helper/subagent host means the route failed the contract and must be reported as disabled or rerouted.
- The adapter may replace an internal role for provenance, but the artifact must still show which role actually ran and which role was replaced.

## Terms and Abbreviations

- `agents-mode`: Orchestrarium operator configuration overlay for delegation, external provider routing, MCP use, and parallelism.
- `reserve`: symbolic supplemental read-only candidate for advisory/review lanes only; it is separate from primary providers and not valid for worker or mutating routes.
- `reserveResolver`: scalar `agents-mode` key that binds symbolic `reserve` to a concrete read-only resolver such as `claude-sonnet`, `claude-wrapper`, or `wrapper:<command>`.
- `CLI`: Command-Line Interface; a provider or tool invoked from a shell.
- `L00`: owner/control routing line in the release-backed `12 + 1` read; it is documented evidence but not an external provider profile lane.
- `MCP`: Model Context Protocol; protocol for exposing tools and resources to agent runtimes.
- `QA`: Quality Assurance; verification work for tests, regressions, and acceptance criteria.
- `12 + 1`: twelve external routing lines plus one owner/control line from the release-backed RF12 interpretation.
- `PID handoff`: an optional caller-owned sidecar supplied to the standalone `await-codex-dispatch` watcher so it can directly probe a caller-managed background process; prompt-wrapper `.pid` captures are private and transient.
- `result envelope`: the single strict-prefix V2 `ORCHESTRARIUM_PROVIDER_RESULT_V2=<json>` line committed to the caller-owned terminal receipt after settlement, materialization, cleanup, and full-line safety scanning; one identical stdout write/flush precedes the optional terminal ledger append. It is always external-nonauthorizing.
- `terminal receipt`: the mandatory caller-declared, exclusively reserved durable file containing the exact V2 result line. The wrapper commits it before stdout write/flush and the optional terminal ledger append, while the caller owns retention and deletion.
- `run capture`: one randomized private directory and its fixed prompt, output, error, and process children, written only by supervisor-owned streams and disposed of only by `RunCaptureLifecycle` after ownership is established.
- `DEAD`: `await-codex-dispatch` terminal status (exit `69`, `EX_UNAVAILABLE`) for a `--pid-file`-confirmed-gone process with no completion artifact yet; distinct from `STALL` (a temporary, still-possibly-alive condition).
- `FILTERED`: `await-codex-dispatch` terminal status (exit `77`, `EX_NOPERM`) for empty completion artifacts plus a provider cybersecurity content-filter marker in `.err`'s tail; model-specific, remedied by re-dispatching the same lane on a different model, never by rewording the prompt.
