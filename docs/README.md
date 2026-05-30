# Docs

This directory is the branch-level docs surface for the Orchestrarium monorepo common layer.

Use it together with:

- [../README.md](../README.md) for the repository overview
- [../INSTALL.md](../INSTALL.md) for install and runtime rules
- [../src.codex/README.md](../src.codex/README.md) for the Codex source subtree
- [../src.claude/README.md](../src.claude/README.md) for the Claude source subtree
- [../src.gemini/README.md](../src.gemini/README.md) for the Gemini source subtree
- [../src.qwen/README.md](../src.qwen/README.md) for the Qwen source subtree
- [../shared/references/README.md](../shared/references/README.md) for the shared design core
- [../references-codex/README.md](../references-codex/README.md)
- [../references-claude/README.md](../references-claude/README.md)
- [../references-gemini/README.md](../references-gemini/README.md)
- [../references-qwen/README.md](../references-qwen/README.md)

Current docs in this branch:

- [agents-mode-reference.md](agents-mode-reference.md) for the shared operator schema
- [external-worker-design.md](external-worker-design.md) for external execution adapter design notes
- [new-session-guide.md](new-session-guide.md) for new-session orientation and source-first maintenance rules
- [provider-runtime-layouts.md](provider-runtime-layouts.md) for cross-provider runtime path mapping
- [work-item-execution-tracking.md](work-item-execution-tracking.md) for the execution ledger helper and periodic active work-item checker
- [routing/12-lane-routing-matrix-v1-2026-04-18.md](routing/12-lane-routing-matrix-v1-2026-04-18.md)

## Terms and Abbreviations

- `agents-mode`: Orchestrarium operator overlay for delegation, provider routing, MCP use, and parallelism.
- `agent-runs.jsonl`: JSONL execution ledger stored beside `status.md` for machine-readable work-item state.
- `check-work-items-state.*`: helper script family that checks every active work item under a repository root.
- `Codex`: OpenAI Codex runtime and provider line.
- `Claude`: Anthropic Claude runtime and provider line.
- `Gemini`: Google Gemini CLI provider line, documented here as an example integration.
- `MCP`: Model Context Protocol; a protocol for exposing tools and resources to agent runtimes.
- `Qwen`: Qwen provider line, documented here as an example integration.
- `runtime`: installed provider-facing files and directories used by an agent tool.
