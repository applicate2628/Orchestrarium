# Docs

This directory is the branch-level docs surface for the standalone Claude Code pack.

Use it together with:

- [../README.md](../README.md) for the repository overview
- [../INSTALL.md](../INSTALL.md) for install and runtime rules
- [../src.claude/README.md](../src.claude/README.md) for the installable source subtree
- [../references-claude/README.md](../references-claude/README.md) for the provider-local reference tree
- [agents-mode-reference.md](agents-mode-reference.md) for the Claude-line `.claude/.agents-mode` operator reference
- [provider-runtime-layout.md](provider-runtime-layout.md) for the source-vs-installed Claude surface map

This branch keeps a Claude-line `agents-mode` reference in `docs/`, but that local table intentionally omits the Claude-target keys because the canonical Claude-line config does not use `externalClaudeSecretMode` or `externalClaudeProfile`.
