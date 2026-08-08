# MCP Continuity

Model Context Protocol (MCP) continuity means keeping relevant connected tools visible at three points where tool choice can drift: session start or compaction, the start of each user turn, and a code-navigation shell search.

## Shared semantic core

One dependency-free policy module, `scripts/universal-hooks/scripts/mcp_continuity_policy.py`, owns the shared semantics for all three event adapters:

| Event | Adapter | Shared behavior |
| --- | --- | --- |
| `SessionStart` | `mcp-usage-reminder.py` | Reintroduces the full MCP discovery and use guidance after a new session or compaction. |
| `UserPromptSubmit` | `turn-anchor-reminder.py` | Adds a short checkpoint requiring relevant configured MCP discovery before ad hoc repository search. |
| `PreToolUse` | `check-mcp-momentum.py` | Classifies a qualifying code-navigation search before provider-specific advisory or force-mode enforcement. |

The policy admits exactly `Grep`, `Bash`, `PowerShell`, `shell_command`, and `exec_command`. Shell-shaped inputs read `tool_input.command`; `exec_command` reads `tool_input.cmd` and accepts `command` as a compatibility shape. Shell text is untrusted data: the policy tokenizes it and never executes it.

## Stateful and indexed freshness

The session reminder and turn anchor treat a repository, project, branch,
worktree, or indexed-input change as invalidating an earlier result from a
connected stateful or indexed MCP. The agent must use that server's own
status/freshness probe; if it reports stale or pending state, run its documented
sync, update, or reindex operation, confirm freshness again, then repeat the
intended query. For CodeGraph this is `status -> sync -> fresh status -> repeat
query`.

This is capability-based, not a per-provider or per-server registry: a
stateless or live MCP does not need a refresh. A failed refresh is reported
explicitly and stale output is not presented as current.

## Navigation classification

The momentum warning recognizes source-navigation patterns rather than every text search:

- `rg`, `ag`, and `ack` are recursive by default; `grep` qualifies only with a recursive option.
- Source scopes, source-oriented selectors, symbol or definition patterns, and `rg --files` over a source scope qualify.
- A known-file read does not qualify merely because it uses a search command.
- The adapter forwards the raw hook-envelope `cwd`; the policy alone validates that it is absolute and finds the nearest ancestor containing a `.git` directory or file.
- An explicit scope is exempt only when lexical normalization from that validated `cwd` makes it equal to, or a component-bounded descendant of, `<repo>/work-items`, `<repo>/.reports`, `<repo>/.plans`, or `<repo>/.scratch`. A matching path segment at any other depth is not exempt.
- Exemption keeps an invocation silent only when it has at least one explicit scope and every explicit scope is rooted-exempt. A mixed, outside, malformed, or unresolvable scope prevents exemption; missing or malformed `cwd` or a missing repository marker grants no exemption and has no process-working-directory fallback.
- Scope normalization is lexical and does not require the target to exist, expand shell syntax, or follow symlinks or junctions. A directory-changing command makes a later relative scope unresolvable; a later absolute scope remains classifiable.

The exact task-memory exemption is intentionally narrow. It does not create a general documentation or repository-path exemption.

## Delivery and privacy boundary

The shared classifier does not choose whether a provider advises or denies.
Codex remains warn-only. Claude remains warn-only for `mcpMode: auto` and for
dispatched-agent envelopes, but a root Claude conversation in effective
`mcpMode: force` denies each qualifying search when a configured
code-intelligence server is present. Exact `[approve-mcp-fallback:v1]` in the
bounded host-projected `user`-role record grants one Claude root recovery turn;
assistant and tool text cannot mint it. This projection is not authenticated
authorization, and a forged host-shaped user record can satisfy it. Missing
servers or unresolved mode allow with a stable
diagnostic so the hook cannot create an impossible retry loop. All paths are
process fail-open and mutate no persistent state.

Configuration discovery reads only server names from the supported Claude JSON and Codex TOML MCP tables. Advisory output contains at most three matching safe names plus an omitted-count suffix. It never serializes server commands, environment values, tokens, or other configuration fields.

Advisory paths influence the next model action and cannot prove obedience. The
Claude root-force denial is an action-level guard only for searches admitted by
the shared classifier; it does not prove MCP success or cover tools outside its
matcher. Installed-source identity and long-turn behavior require separate
post-install verification.

Provider-specific event envelopes, matcher registration, and installed paths live in the [Codex addendum](../../references-codex/mcp-continuity.md) and [Claude Code addendum](../../references-claude/mcp-continuity.md).

## Terms and Abbreviations

- `MCP`: Model Context Protocol, the interface through which connected tools and resources are exposed.
- `TOML`: Tom's Obvious Minimal Language, the configuration format used by Codex.
- `JSON`: JavaScript Object Notation, the configuration format used by Claude Code.
