# MCP Continuity

Model Context Protocol (MCP) continuity restores tool-discovery guidance at session start or compaction. Turn and parallel reminders carry workflow continuity; Claude also sends a nonblocking advisory for qualifying code-navigation choices.

## Shared semantic core

One dependency-free policy module, `scripts/universal-hooks/scripts/mcp_continuity_policy.py`, owns startup discovery, turn continuity and the classifier used by Claude's provider-specific search adapter:

| Event | Adapter | Shared behavior |
| --- | --- | --- |
| `SessionStart` | `mcp-usage-reminder.py` | Reintroduces the full MCP discovery and use guidance after a new session or compaction. |
| `UserPromptSubmit` | `turn-anchor-reminder.py` | Adds a short checkpoint for active-task continuation and delegation posture, without repeating tool-choice guidance. |
| Claude `PreToolUse` | `agents/scripts/check-mcp-momentum.py` | Uses the shared search classifier to send a nonblocking advisory; the root force-mode advisory restates the existing mandatory MCP-use duties. |

The policy admits exactly `Grep`, `Bash`, `PowerShell`, `shell_command`, and `exec_command`. Shell-shaped inputs read `tool_input.command`; `exec_command` reads `tool_input.cmd` and accepts `command` as a compatibility shape. Shell text is untrusted data: the policy tokenizes it and never executes it.

## Stateful and indexed freshness

The session guidance and standing tool-use rules treat a repository, project, branch,
worktree, or indexed-input change as invalidating an earlier result from a
connected stateful or indexed MCP. The agent must use that server's own
status/freshness probe; if it reports stale or pending state, run its documented
sync, update, or reindex operation, confirm freshness again, then repeat the
intended query. As an explicitly non-normative workflow example, CodeGraph uses
`status -> sync -> fresh status -> repeat query`; this name never selects a tool.

When selecting or changing a project, or recovering stale state, the reported project/index identity matches the selected root before use;
known omitted coverage is reported with the result. If instructions conflict
with an installed tool, inspect its own supported entrypoint, help, and version
before acting; do not invent or reimplement that tool's pipeline. Before treating graph call, dependency, or blast-radius output as exact decision evidence, match the qualified symbol plus declaring type/file where applicable to the requested target; distinguish direct calls, callback/indirect reachability, and fuzzy suggestions. Ambiguous/unmatched rows require source verification; do not declare them exact.

This is capability-based, not a per-provider or per-server registry: a
stateless or live MCP does not need a refresh. A failed refresh is reported
explicitly and stale output is not presented as current. The selection, change,
and recovery guard is not a per-call version check, requires no new vendor API,
and never directs an automatic deep or large-language-model build.

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

The shared classifier does not decide compliance or tool permission. Codex uses
startup guidance and workflow reminders, without a search-audit registration.
Claude sends a nonblocking advisory for `mcpMode: auto`, dispatched-agent
envelopes, and a root conversation in effective `mcpMode: force`. Under the
existing force duty, runtime tool discovery and the relevant tool schema are
required, as is use of a fitting MCP within the existing alternative-path
restrictions; selected-root and currentness checks still apply. Runtime
discovery is the only availability source. The advisory does not determine
compliance, grant permission, or override a host refusal. An unresolved mode
still emits a stable diagnostic advisory. All paths are process fail-open and
mutate no persistent state.

The universal policy does not read home-directory MCP configuration, infer
availability from configured names, or select a tool from a name registry.
Qualifying advisory paths emit one generic runtime-discovery checkpoint. Named
tools in documentation are explicitly non-normative examples and never
selection logic.

Advisory paths influence the next model action and cannot prove obedience. The turn anchor projects the shared **Primary-task continuity and side work** rule: brief inline answers, prompt eligible substantive side delegation and ready primary continuation without waiting for the side result. A synthetic payload test proves delivery of this context only. Both-pack receiving and an actual current-flow observation do not prove universal future model compliance; another provider's model-behavior trial is not mandatory.
The Claude root-force advisory does not determine compliance, prove MCP
success, or cover tools outside its matcher. Installed-source identity and
long-turn behavior require separate post-install verification.

Provider-specific event envelopes, matcher registration, and installed paths live in the [Codex addendum](../../references-codex/mcp-continuity.md) and [Claude Code addendum](../../references-claude/mcp-continuity.md).

## Terms and Abbreviations

- `MCP`: Model Context Protocol, the interface through which connected tools and resources are exposed.
