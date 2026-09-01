# V2.1 Provider-Harness Equivalence Ledger

Date: 2026-07-12
Scope: `R-OPUS`, `R-SONNET`, `R-SOL`, and `R-TERRA` in `run-v21-cohort-batch.ps1`

This ledger records the harness knobs that affect cross-provider interpretation. `EQUALIZED` means the runner pins the same measurement intent on both provider paths. `LABELED-CONFOUND` means the provider interfaces cannot be made identical without inventing or using an unverified control.

| Knob | Status | Codex path | Claude path | Evidence / consequence |
|---|---|---|---|---|
| Prompt text | EQUALIZED | Reads `meta/prompt.txt` and pipes it to standard input. | Reads the same `meta/prompt.txt` and pipes it to standard input. | One `New-V21WorkerPrompt` result is written once per repeat; no model, row, or scenario hint is injected. |
| Prompt delivery | EQUALIZED | File-backed standard-input pipe; no prompt argument. | File-backed standard-input pipe; no prompt argument. | The substantive prompt is absent from process arguments on both paths. |
| Candidate working directory | EQUALIZED | `caseRoot/<runIndex>/provider/`. | `caseRoot/<runIndex>/provider/`. | The staged provider root is the only candidate-writable benchmark tree. |
| Oracle and verifier visibility | EQUALIZED | `stage_provider_root.py` allowlist plus structural sentinel. | Same staging command and sentinel. | Production mode stages no `oracle/`, `verifiers/`, or `discrimination.yaml`. |
| Model Context Protocol (MCP) surface | EQUALIZED | Enumerates configured MCP servers and passes `-c mcp_servers.<name>.enabled=false` for each. | Passes `--strict-mcp-config --mcp-config meta/claude-empty-mcp.json`, whose content is `{"mcpServers":{}}`. | Both profile paths expose an empty MCP surface. |
| Sandbox / permission intent | EQUALIZED | Pins `--dangerously-bypass-approvals-and-sandbox` and `--ephemeral`. | Pins `--permission-mode bypassPermissions`. | Both paths are explicitly unrestricted inside the disposable staged root; neither inherits an approval default. |
| Provider transport | LABELED-CONFOUND | `codex exec` JSON Lines transport. | `claude -p --output-format json` print transport. | Provider-native transports differ and cannot be collapsed into one command protocol. |
| Network access | LABELED-CONFOUND | Provider CLI behavior; no probe-confirmed offline flag is applied. | Provider CLI behavior; no probe-confirmed offline flag is applied. | Network policy is not proven equivalent. Treat cross-provider deltas as carrying this harness confound. |
| Model identifier | EQUALIZED | `-m <model>` is built from `Instrument/profiles.yaml`. | `--model <model>` is built from the same registry. | New profile rows contain no hardcoded model identifier. |
| Reasoning effort | LABELED-CONFOUND | `-c model_reasoning_effort=<effort>` is built from the registry (`xhigh`). | The registry value is resolved and recorded, but the approved probe-confirmed Claude command has no corresponding `xhigh` flag. | Do not claim a numerically identical effort control across providers. An additional Claude CLI probe is required before translating the registry token. |
| Sampling temperature | EQUALIZED | No temperature override; provider/model default. | No temperature override; provider/model default. | Equal absence is pinned, but provider defaults need not be numerically identical. |
| Raw provider envelope | EQUALIZED | Standard output only to `meta/provider-envelope.jsonl`; standard error is separate. | Standard output only to `meta/provider-envelope.json`; standard error is separate. | Raw machine output is preserved without mixing diagnostic text into the envelope. |
| Budget surface | EQUALIZED | `meta/worker-output.txt` is copied from `-o meta/last-message.txt`. | `meta/worker-output.txt` is the final event's `result` text. | Operator-budget checks measure final-answer text on both paths, not a Codex transcript versus a Claude answer. |
| Runner latency | EQUALIZED | One `Stopwatch` around the provider call. | The same `Stopwatch` boundary. | `telemetry.wallClockMs` is always runner-measured; unavailable provider values are JSON `null`, not zero. |
| Token and cost schema | LABELED-CONFOUND | Parser accepts the expected JSONL `usage` aliases; cost remains unavailable without a price table. | Parser accepts the expected final-result event fields, including provider-reported cost. | Exact live envelope field names are not verified because this task forbids provider calls. See the resolving probes below. |
| Legacy X4 transport | LABELED-CONFOUND | Not applicable. | The retained X4 anchor row still uses the frozen secret-backed wrapper. | X4 remains available for anchor comparison but is not evidence of four-profile transport equivalence. |

## Uncertainty-Resolving Probes

Do not run these during the stage-only acceptance pass; each invokes a provider.

| Uncertainty | Resolving probe | Required observation |
|---|---|---|
| Claude event-array and usage field shape | Pipe a file containing `say ok` to `claude -p --output-format json --permission-mode bypassPermissions --model claude-sonnet-5` with the same strict empty MCP arguments as the runner. | Confirm whether the top level is an event array and record the final `result`, `usage`, `total_cost_usd`, `duration_ms`, `duration_api_ms`, `num_turns`, and model fields. |
| Codex JSONL usage event shape | Pipe the same file to `codex exec --ephemeral --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox --json -o <last-message> -m gpt-5.6-terra -c model_reasoning_effort=xhigh`, with all configured MCP servers disabled. | Record the event type carrying usage and the exact token/model field names; verify `last-message` equals the intended budget surface. |
| Claude effort translation | Run `claude --help` for the installed version, then a trivial print probe only if help exposes a compatible effort flag. | Establish an official accepted value corresponding to registry token `xhigh`; otherwise keep the confound label. |

## Terms and Abbreviations

- `MCP`: Model Context Protocol.
- `JSONL`: JSON Lines, one JSON object per line.
- `EQUALIZED`: the runner pins the same measurement intent on both provider paths.
- `LABELED-CONFOUND`: a known, explicitly carried source of cross-provider measurement uncertainty.

## Known limitations & LABELED-CONFOUNDs (Terra H1 audit, 2026-07-12)

- **Terra CRITICAL-2 — host-filesystem isolation. RELATIVE-traversal hole CLOSED; absolute-path is the
  documented (canary-validated non-threat) escalation.** The provider runs with `--dangerously-bypass-
  approvals-and-sandbox` and `--cd provider/`. Layered defenses now:
  1. Oracle is never staged into `provider/` (H2/H3) and candidate CODE runs in the oracle-free
     `exec-fixed/` (H9) — closes the in-bundle and score-time paths.
  2. **The `provider/` root is now staged OUTSIDE the benchmarks repo tree** (OS temp,
     `%TEMP%/bench-v21-provider/<row>/<scenario>/<run>/provider`), so a candidate running with
     cwd=provider/ **cannot traverse `../../../` up into the live `Scenarios-v2/<id>/oracle/` source**.
     Verified live (STAGE-OK to `R:\Temp\bench-v21-provider\...`; scoring reads `out/` in the scratch
     repeatRoot, unaffected). This closes the relative-traversal hole Terra flagged.
  3. **Residual (documented escalation, NOT built):** an absolute-path read
     (`D:\dev\...\Scenarios-v2\<id>\oracle\`) still succeeds if the candidate knows the exact repo
     path. A hard guarantee against that requires OS-level filesystem restriction (container / VM /
     restricted user account exposing only `provider/`). This is **intentionally not built**: the
     empirical canary (a decoy oracle planted directly in `provider/`) shows the honest frontier
     models do NOT read the oracle at all (`canaryLeakDetected: False` on N58/V3L05), so the
     absolute-path threat does not manifest for the benchmark's actual (non-adversarial) subjects.
     Build the OS-level jail only if adversarial-cheat robustness is ever required. Evidence docs
     should still carry this one-line residual disclosure.

- **LABELED-CONFOUND — no pinned max-output-token cap / turnaround timeout (Terra MEDIUM-5).**
  Neither CLI exposes a probe-confirmed hard output-token cap on this host (claude has no such flag;
  codex `-c model_max_output_tokens` unverified). The F1 stamina / F2 working-audit budget surfaces
  therefore CANNOT assert an equal enforced output budget across providers; they degrade to post-hoc
  token-telemetry stratification (BUILD-PLAN F1 degrade path). Any "equal budget" claim for those
  families is a LABELED-CONFOUND until a hard cap is verified.
