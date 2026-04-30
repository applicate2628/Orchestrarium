# Docs

This directory is the branch-level docs surface for the standalone Qwen pack.

Use it together with:

- [../README.md](../README.md) for the repository overview
- [../INSTALL.md](../INSTALL.md) for install and runtime rules
- [../src.qwen/README.md](../src.qwen/README.md) for the Qwen source subtree
- [../references-qwen/README.md](../references-qwen/README.md) for the Qwen reference tree
- [../shared/references/README.md](../shared/references/README.md) for the shared design core

Current docs in this branch:

- [agents-mode-reference.md](agents-mode-reference.md) for the shared operator schema
- [provider-runtime-layouts.md](provider-runtime-layouts.md) for the Qwen runtime path map

## Terms and Abbreviations

- `agents-mode`: Orchestrarium operator overlay for delegation, provider routing, MCP use, and parallelism.
- `MCP`: Model Context Protocol; a protocol for exposing tools and resources to agent runtimes.
- `Qwen`: Qwen provider line, documented here as an example integration.
- `runtime`: installed provider-facing files and directories used by Qwen.
