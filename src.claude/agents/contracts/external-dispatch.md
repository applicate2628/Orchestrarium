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
externalProvider: auto  # allowed here: auto | codex | claude | gemini | qwen; default: auto; gemini/qwen are explicit example-only and not recommended for shipped auto
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
- `externalProvider` uses the shared provider universe `auto | codex | claude | gemini | qwen`.
- `externalProvider: auto` resolves by lane type through the active named production priority profile instead of by host-pack identity. Shipped `auto` profiles use `codex | claude` only and do not select example-only providers.
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
- Explicit user override or documented repo-local task-domain heuristics may still choose an explicit example-only provider route such as Qwen, or the weaker/not-recommended Gemini path, over the ordinary `auto` result for demonstration or compatibility work.

## Claude-line provider

- `externalProvider: auto` resolves by lane type through the active named production priority profile instead of by host-pack identity.
- When the resolved provider is Codex, honor `externalCodexWorkdirMode`; when it is Claude, honor `externalClaudeWorkdirMode`.
- When the resolved provider is Codex, `externalCodexProfile: default` inherits `externalModelMode`; `externalCodexProfile: gpt-5.6-sol-max` requests model `gpt-5.6-sol` with `model_reasoning_effort = "max"` for higher-complexity/hard lanes; `externalCodexProfile: gpt-5.6-terra` selects the balanced Codex model tier (a distinct model, `model_reasoning_effort = "high"`, not an effort downgrade) and must record unavailable or deviated if that model cannot be verified against the installed runtime; `externalCodexProfile: gpt-5.6-sol-xhigh` (shipped as default) requests model `gpt-5.6-sol` with `model_reasoning_effort = "xhigh"` regardless of `externalModelMode`, and is the best-effort sibling of Claude's `opus-xhigh`.
- Explicit `externalProvider: claude` is a self-provider override only. Ordinary `auto` must not silently self-bounce into the current host line's own provider (the host-line-relative self-bounce rule).
- `reserve` is considered only when an advisory or review profile order reaches it after primary `claude`/`codex`; it does not skip earlier primary profile candidates.
- Treat `reserve` as a supplemental advisory/review candidate only. It never grants permission to run implementation, worker-side execution, or editing work through the resolved transport.
- When an advisory or review route resolves to `reserve`, bind it through `reserveResolver`. `claude-sonnet` means the approved Sonnet-style read-only reserve path; `claude-wrapper` means the installed wrapper under `.claude/agents/scripts/invoke-claude-api.sh` or `.claude/agents/scripts/invoke-claude-api.ps1`; `wrapper:<command>` means a PATH-resolved command or repo-relative wrapper path, subject to the layer-provenance trust gate above (a `project-UNCONFIRMED` value must not be launched before first-use user confirmation). The Claude wrapper reads `ANTHROPIC_*` from repo-local `.claude/SECRET.md` first and then from `~/.claude/SECRET.md`, then launches plain `claude`.
- If the chosen `reserve` resolver is unavailable, disclose that as a dependency/config failure.
- If the plain Claude CLI is selected and fails, do not silently convert that same primary `claude` run to the wrapper. Advisory/review lanes may later collect `reserve` as a separate profile candidate when enabled; worker or mutating routes must report Claude unavailable or reroute honestly.
- Use `.claude/agents/scripts/invoke-claude-api.ps1` from PowerShell and `.claude/agents/scripts/invoke-claude-api.sh` from Bash or Git Bash only when that wrapper is the approved resolver for a resolved `reserve` advisory/review candidate. The PowerShell wrapper must stay compatible with Windows PowerShell 5.1 and PowerShell 7+, forwarded Claude flags should be passed after `--%`, and the Bash wrapper must honor `CLAUDE_BIN` when the shell PATH differs from PowerShell PATH.
- On Windows, keep the ordinary external launch path unchanged and try the native Windows shell first. If that native shell path fails because of shell bootstrap, execution-policy, or environment-policy problems, retry once through Git-for-Windows Bash / MSYS when available. Do not use the WSL `bash.exe` stub as a fallback, and do not reinterpret ordinary provider auth, quota, or model failures as shell-fallback triggers.
- Use `gpt-5.6-terra` as the balanced cheaper-than-flagship Codex reasoning lane when full `gpt-5.6-sol` depth is not required; a genuine reasoning model whose output stays review-gated like any external lane. Gemini and Qwen routes stay manual `WEAK MODEL / NOT RECOMMENDED` example-only paths and do not add separate production fallback keys to this schema.
- External CLI launches that carry a substantive task prompt must use file-based prompt delivery: write the prompt to a temporary prompt file and feed it through the provider's stdin or supported file-input mechanism. Keep command-line arguments limited to launcher flags, model/profile options, and file paths; inline prompt argv is allowed only for tiny smoke checks or a documented provider limitation, and record that deviation in the execution artifact.
- The canonical Claude-pack transports for primary runs are `.claude/agents/scripts/invoke-codex-prompt.sh` / `.ps1` and `.claude/agents/scripts/invoke-claude-prompt.sh` / `.ps1`; use their persisted prompt plus sibling `.out` / `.err` capture path. A transport-neutral inline chain that performs the same probe, capture, and explicit-flag recording is the fallback, not an argv prompt.
- **WARNING — automated Claude authentication:** the `invoke-claude-prompt.sh` / `.ps1` transport requires commercial API-key authentication for automated `claude -p` and fails closed under subscription sign-in (OAuth). Use `invoke-claude-api.sh` / `.ps1` as the key-backed path; it loads `ANTHROPIC_AUTH_TOKEN` and `ANTHROPIC_BASE_URL` from `SECRET.md`. Other accepted commercial paths are `ANTHROPIC_API_KEY`, `apiKeyHelper`, Amazon Bedrock, and Google Vertex AI. See [Anthropic's Claude Code legal and compliance guidance](https://code.claude.com/docs/en/legal-and-compliance).
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

- Include the complete handoff template verbatim from the owning `contracts/subagent-contracts.md`, including its mandatory pre-dispatch fill rule and defect-class completeness trigger; this contract cites that owner and does not reproduce its field list.
- State the assigned role's gate vocabulary and one-artifact requirement.
- Include a provenance-header echo instruction using this contract's header fields.
- Include the evidence-citation discipline verbatim from the owning `Evidence discipline:` handoff field; this contract does not create a second copy.
- For an adversarial review strategy, use an artifact-only prompt: include the artifact and review scope, but exclude builder claims and self-review.
- Immediately before an approved non-interactive Codex launch, `provider_prompt.py::launch` runs the installed Codex hook-health helper in `require` mode. A nonzero trust/liveness verdict prevents `codex exec`; this gate does not apply to Claude launches.

## Run-completion oracle

- A provider run is complete only when its exit code is recorded, its `.out` artifact exists and is non-empty with the requested artifact shape (provenance header plus gate line), and its `.err` artifact is free of authentication, quota, usage-limit, and mid-stream-truncation markers.
- Every run admitted by `provider_prompt.py::launch` also has one sibling `<slug>.verdict` file. The wrapper atomically writes `LAUNCHED` before an optional ledger launch event and before starting the provider, then atomically replaces it after an ordinary child return. The file is newline-terminated and contains exactly one token: `COMPLETE:PASS`, `COMPLETE:REVISE`, `UNVERIFIED:empty`, `UNVERIFIED:no-gate-line`, `UNVERIFIED:err-markers`, or `FAILED:nonzero-exit`. An interrupted run deliberately remains `LAUNCHED`; the wrapper still terminates and, when needed, kills and waits for the child before returning `130`.
- The `.verdict` token is the durable wrapper classification, not a substitute for the raw `.out`, `.err`, and Codex `.lastmsg` evidence. `COMPLETE:PASS` and `COMPLETE:REVISE` mean the corresponding anchored final gate line was observed; each `UNVERIFIED:*` token names the failed oracle condition; `FAILED:nonzero-exit` means the provider or admitted pre-child bookkeeping path returned nonzero.
- Verdict persistence is mandatory and fail-loud. Failure to create `LAUNCHED` prevents the provider from starting. Failure to replace a terminal verdict turns an otherwise-zero wrapper result into an infrastructure failure; an already-nonzero provider exit remains nonzero. The work-item ledger remains optional and, when enabled, consumes the same terminal classification without changing its event shape.
- A failed oracle check makes the run `UNVERIFIED`: re-dispatch it or return `BLOCKED:dependency`. Never summarize a truncated or partial `.out` into an artifact or render it as `PASS`.
- A completion notification — a harness background-task signal, a wrapper exit message, a task callback — or its absence, is never this oracle. Verify the `.out` artifact shape and `.err` cleanliness directly before counting a run done, regardless of any notification.
- For a Claude-line Codex dispatch launched in the background, `await-codex-dispatch` is the shipped active-polling mechanism. `invoke-codex-prompt` prints a copy-pasteable command wired to that dispatch's `.out`, `.err`, `.lastmsg`, and `.pid` paths before the provider child starts; launch that watcher with `run_in_background: true` so it polls until one terminal status line is emitted.
- The watcher's `.out`-non-empty terminal condition assumes `codex exec` does not stream interim agent messages to stdout; `.lastmsg` has precedence, and a CLI upgrade must re-check this assumption.

## Direct liveness probe (PID handoff)

Artifact timestamps alone can prove a run finished; they cannot prove a silent run is still alive versus gone — the live incident this half of the contract closes was eight of sixteen provider runs producing zero-byte output, indistinguishable from "still working" for the entire stall/timeout window. The watcher's terminal statuses therefore include a fourth outcome, `DEAD` (exit `69`, `EX_UNAVAILABLE`), reached only when a **direct probe of the recorded process** — never an artifact or a notification — confirms it gone.

- **What is recorded, where, by whom.** `invoke-codex-prompt.sh`/`.ps1` and `invoke-claude-prompt.sh`/`.ps1` each write a sidecar `<slug>.pid` file alongside `.out`/`.err`/`.lastmsg`, before the provider call blocks, containing `pid=<PID>` and, when the platform exposes one, `start=<opaque marker>`. On Bash/POSIX (Git Bash/MSYS included) the recorded PID is the **actual provider child process** — bash always forks to exec a background command, so `$!` is a real, separate OS process regardless of what the provider binary turns out to be — and the start marker is `/proc/<pid>/stat` field 22 (`starttime`, in clock ticks since boot). On PowerShell the recorded PID is **this wrapper's own process**, not necessarily a distinct provider child: PowerShell's call operator (`&`) does not always spawn a separate process — an npm-style `.ps1` shim (the common shape; e.g. `codex` commonly resolves to `codex.ps1`) runs in-process, in a new scope, with no child PID to capture — so the wrapper's own PID is the accurate direct-probe answer on that platform, not a fallback proxy: it is the OS-level unit that owns prompt persistence, the provider call, and output capture end-to-end for that dispatch. The start marker there is the recorded process's `StartTime.Ticks`. This is a disclosed platform asymmetry, not a silent weakening: Bash gets true child-process precision, PowerShell gets wrapper-process precision, and the known residual gap (an `.exe`/`.cmd` child on PowerShell surviving orphaned if something kills only the parent wrapper) is named in the wrapper's own comments rather than hidden.
- **PID reuse.** A process identifier alone goes stale the instant the process exits, and an OS may hand that same identifier to an unrelated later process — a real hazard, not a theoretical one. The recorded start marker exists solely to catch this: the watcher re-reads the CURRENT start marker for the recorded PID and compares it for equality against the recorded one; a mismatch (a different process now holds that PID) is treated as `DEAD`, never as alive. No start marker recorded (an older host with no `/proc`, or a process that exited before the marker could be read) falls back to existence-only trust in the PID — weaker, but still a genuine direct probe, never inferred from artifacts.
- **The combined rule ("not running" is ambiguous on its own).** A finished-successfully run and a died-silently run are both "not running" from a bare liveness probe. The watcher therefore always evaluates its pre-existing DONE conditions (non-empty `.lastmsg`/`.out`, or a changed `HEAD` when `--commit-base` was supplied) FIRST, every poll; only when none of them fired that same iteration does a confirmed-dead probe result produce `DEAD`. A process that exits normally immediately after writing its completion artifact is therefore still `DONE` (exit `0`) even though the same poll would also see its PID gone — the artifact wins. Only a gone process with **no** completion artifact yet reaches `DEAD`.
- **Missing handoff (the common case, not the edge).** `--pid-file`/`-PidFile` is OPTIONAL and purely additive. An older `invoke-*-prompt`, a hand-rolled background launch, or any run started outside the wrapper entirely — the live incident's own loop was hand-rolled, so this is the ordinary case this contract must cover, not a rare corner — simply never produces a `.pid` file (or the flag is omitted). The watcher resolves this as "unknown" liveness and degrades to EXACTLY the pre-existing artifact-only behavior (DONE/STALL/TIMEOUT), byte-for-byte identical to before this half of the fix landed. A missing, unreadable, or malformed `.pid` file (no parseable `pid=` line) degrades the same way — never treated as `DEAD`. `DEAD` is reachable ONLY when a handoff was actually supplied and actively confirms the process gone.

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

- Actively poll the `.out` / `.err` artifacts and process status. The shipped `await-codex-dispatch` helper is the canonical Claude-line Codex poller: it stops on non-empty `.lastmsg`/`.out` (exit `0`, `DONE`), a changed `HEAD` when `--commit-base` is supplied (also `DONE`), a confirmed-dead recorded process with no completion artifact yet when `--pid-file` was supplied (exit `69`, `DEAD` — see "Direct liveness probe" above), a provider cybersecurity content-filter marker in `.err`'s tail with empty completion artifacts (exit `77`, `FILTERED` — see "Cybersecurity content-filter detection" above; re-dispatch on a different model, never reword the prompt), an idle `.err` beyond `--stall-secs` (exit `75`, `STALL`), or `--max-secs` (exit `124`, `TIMEOUT`). Terminal exit codes are pairwise distinct and machine-readable without parsing stdout. Its shipped default is 2700 seconds (45 minutes), matching the earliest valid `xhigh`/`max` review window; callers may set a shorter threshold only when the resolved lane's policy permits it. A stall declaration before the applicable window without process evidence violates this contract — a `DEAD` declaration is not subject to that window because it rests on a direct process probe, not an elapsed-time inference. Dispatched Claude and Codex children set `ORCHESTRARIUM_DISPATCHED_REVIEW=1` only for the provider process, so the main-conversation Stop-hook guards cannot contaminate their verdicts; ordinary main-conversation Stop-hook behavior is unchanged.
- **Whether a completion notification arrives depends on HOW the run was launched; its presence is not proof and its absence is not a stall.** A harness completion notification fires only when the run is (1) launched by the MAIN orchestrating loop — a dispatched subagent is never re-invoked when a background child it launched finishes (see the no-spawn-and-wait rule in `subagent-contracts.md`), (2) as a harness-tracked background run (Claude Bash `run_in_background: true`), and (3) whose tracked process stays attached until the provider exits — a foreground launch that forks, `&`-detaches, or `nohup`s the provider notifies on the shell's exit, not the provider's. The canonical wrapper is the recommended way to satisfy (3) plus the transport contract; it is not itself the notifier. An improvised or untracked launch delivers no notification, so ending a turn "waiting to be notified" after one strands the run — actively poll regardless of whether a notification is expected.
- If the shell times out, do not relaunch: identify the running process first and stop it only if it is orphaned or no longer needed.
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
| Owner roles such as `$product-manager` or `$lead` | unsupported | Fail fast before provider resolution. There is no generic external owner adapter on the Claude line. |

Rules:

- An explicit request for `external` does not create a new adapter type.
- Unsupported external role requests must stop with an unsupported-route explanation and an honest reroute suggestion instead of probing Codex, Claude, Gemini, or Qwen availability as if a missing adapter might exist.
- Worker-side specialist lanes such as `analyst`, `architect`, `planner`, `knowledge-archivist`, `algorithm-scientist`, `computational-scientist`, `security-engineer`, `performance-engineer`, and `reliability-engineer` remain eligible for `$external-worker` when routing selects external substitution.
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
- `Requested provider: <internal | codex | claude | gemini | qwen>`
- `Resolved provider: <Codex CLI | Claude CLI | Gemini CLI | Qwen Code | none>`
- `Requested consultant mode: <external | internal | disabled>` when consultant routing is relevant; otherwise `not-applicable`
- `Actual execution path: <internal consultant | external CLI (Codex CLI) | external CLI (Claude CLI) | external CLI (Gemini CLI) | external CLI (Qwen Code) | role disabled>`
- `Model / profile used: <actual profile or model when known | runtime default | unspecified by runtime>`
- `Launch flags: <exact argv model / effort / sandbox flags>`
- `Run record: <started and finished timestamps or duration; prompt / .out / .err paths>`
- `Deviation reason: <none | external unavailable: [reason] | explicit override>`

Rules:

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
- `WEAK MODEL / NOT RECOMMENDED`: repository classification for example-only providers excluded from production `auto` routing.
- `PID handoff`: the sidecar `<slug>.pid` file `invoke-codex-prompt`/`invoke-claude-prompt` write at launch so `await-codex-dispatch` can directly probe the dispatched process instead of inferring from artifact timestamps alone.
- `verdict`: the one-token sibling `<slug>.verdict` file written atomically by `provider_prompt.py`; it exposes the wrapper's durable launch or terminal classification independently of optional work-item ledger bookkeeping.
- `DEAD`: `await-codex-dispatch` terminal status (exit `69`, `EX_UNAVAILABLE`) for a `--pid-file`-confirmed-gone process with no completion artifact yet; distinct from `STALL` (a temporary, still-possibly-alive condition).
- `FILTERED`: `await-codex-dispatch` terminal status (exit `77`, `EX_NOPERM`) for empty completion artifacts plus a provider cybersecurity content-filter marker in `.err`'s tail; model-specific, remedied by re-dispatching the same lane on a different model, never by rewording the prompt.
