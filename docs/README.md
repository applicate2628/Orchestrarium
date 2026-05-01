# Docs

This directory is the branch-level docs surface for the standalone Claude pack.

Use it together with:

- [../README.md](../README.md) for the repository overview
- [../INSTALL.md](../INSTALL.md) for install and runtime rules
- [../src.claude/README.md](../src.claude/README.md) for the Claude source subtree
- [../references-claude/README.md](../references-claude/README.md) for the Claude reference tree
- [../shared/references/README.md](../shared/references/README.md) for the shared design core

Current docs in this branch:

- [agents-mode-reference.md](agents-mode-reference.md) for the shared operator schema
- [provider-runtime-layouts.md](provider-runtime-layouts.md) for the Claude runtime path map

## Terms and Abbreviations

- `agents-mode`: Orchestrarium operator overlay for delegation, provider routing, MCP use, and parallelism.
- `Claude Code`: Anthropic Claude runtime and provider line.
- `MCP`: Model Context Protocol; a protocol for exposing tools and resources to agent runtimes.
- `runtime`: installed provider-facing files and directories used by Claude.
