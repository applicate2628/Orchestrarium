# Provider MCP Templates

This directory contains ready-to-use artifacts for strict MCP isolation patterns.

## Status

These scripts and templates are a temporary fallback for the current provider behavior on this machine.

They are operationally useful now, but they should not be treated as the final intended interface. Re-verify the provider CLI surface after the next upstream plan or runtime update.

## Files

| File | Purpose |
|---|---|
| `codex-isolated-worker.ps1` | Launches a fresh `codex exec` worker with only the requested MCP servers enabled for that process, or disables all configured MCP servers if no allowlist is provided. |
| `claude-isolated-worker.ps1` | Launches native `claude` or the repo-canonical secret-backed Claude wrapper with either a strict MCP allowlist or a strict empty MCP config. |
| `gemini-isolated-worker.ps1` | Launches `gemini` either with an MCP allowlist or in a verified no-MCP runtime using a clean temporary `HOME` and clean temporary `cwd`. |
| `qwen-isolated-worker.ps1` | Launches `qwen` either with an MCP allowlist or in a clean no-MCP runtime using a temporary `HOME` that preserves only the minimum auth and model settings. |
| `claude-subagent-template.md` | Claude subagent template with child-only inline `fetch` MCP. |
| `gemini-subagent-template.md` | Gemini subagent template with child-only inline `fetch` MCP and explicit tool allowlist. |
| `claude-playwright-only.json` | Strict Claude MCP config containing only `playwright`. |

## Qwen experimental note

Treat `Qwen` as an experimental provider until it has both:

- an admitted local install and auth path on this machine
- an admitted benchmark launch contract

Officially verified baseline facts from `QwenLM/qwen-code` on `2026-04-15`:

| Fact | Current note |
|---|---|
| install | `npm install -g @qwen-code/qwen-code@latest` |
| prerequisite | Node.js `>= 20` |
| headless mode | `qwen -p "your question"` |
| config file | `~/.qwen/settings.json` |
| benchmark auth recommendation | use API-key auth for headless or non-interactive runs; do not rely on browser OAuth |

Current machine note:

- a repo-local wrapper now exists as `qwen-isolated-worker.ps1`
- local `qwen-oauth` was good enough for initial smoke and first experimental rows
- after the official free-tier shutdown date on `2026-04-15`, further benchmark work is now effectively blocked until `Qwen` is normalized to API-key auth on this machine

## Quick matrix

| Provider | With MCP allowlist | No MCP | Child-specific MCP |
|---|---|---|---|
| `codex` | `codex-isolated-worker.ps1 -AllowMcp ...` | `codex-isolated-worker.ps1` with no `-AllowMcp` | Separate worker process only |
| `claude` | `claude-isolated-worker.ps1 -McpConfigPath ...` | `claude-isolated-worker.ps1 -NoMcp` | `claude-subagent-template.md` |
| `gemini` | `gemini-isolated-worker.ps1 -AllowMcp ...` | `gemini-isolated-worker.ps1 -NoMcp` | `gemini-subagent-template.md` |
| `qwen` | `qwen-isolated-worker.ps1 -AllowMcp ...` | `qwen-isolated-worker.ps1 -NoMcp` | none yet |

## Codex wrapper

Example:

```powershell
.\codex-isolated-worker.ps1 `
  -AllowMcp fetch,memory `
  -CodexArgs @('--model','gpt-5.4','-c','model_reasoning_effort="xhigh"') `
  -Prompt "Review the repository for serialization issues." `
  -SkipGitRepoCheck
```

No MCP:

```powershell
.\codex-isolated-worker.ps1 `
  -CodexArgs @('--model','gpt-5.4','-c','model_reasoning_effort="xhigh"') `
  -Prompt "Review the repository without MCP access." `
  -SkipGitRepoCheck
```

Notes:

- The wrapper discovers currently configured Codex MCP servers from `codex mcp list`.
- It enables only the names passed via `-AllowMcp`.
- If `-AllowMcp` is omitted, it disables every configured Codex MCP server for that worker process.
- It uses `codex exec --ephemeral`, so the worker does not persist a session to disk.
- Use `-OutputFile` when you want the wrapper itself to persist a durable capture instead of relying on outer-shell redirection.
- Use `-PromptFile` for multiline benchmark prompts or any batch harness that would otherwise have to push large prompt text through CLI argument parsing.
- Current Codex `exec` does not accept a standalone `--reasoning-effort` flag. Pin reasoning via `-c 'model_reasoning_effort="xhigh"'` inside `-CodexArgs` when you need the benchmark's high-effort launch shape.

## Claude wrapper

With MCP allowlist:

```powershell
.\claude-isolated-worker.ps1 `
  -McpConfigPath D:\path\allowed-mcp.json `
  -Prompt "Review this repository with only the allowed MCP servers."
```

No MCP:

```powershell
.\claude-isolated-worker.ps1 `
  -NoMcp `
  -Prompt "Review this repository without MCP access."
```

Use the repo-canonical secret-backed Claude wrapper instead of the native CLI:

```powershell
.\claude-isolated-worker.ps1 `
  -UseSecretWrapper `
  -NoMcp `
  -Prompt "Run through the repo-canonical secret-backed Claude wrapper."
```

Notes:

- `-NoMcp` now maps to `--strict-mcp-config --mcp-config '{"mcpServers":{}}'`; no `--bare` launch shape is used.
- `-McpConfigPath` maps to `--strict-mcp-config --mcp-config ...`.
- The wrapper defaults to non-interactive `--print`.
- Add extra CLI flags via `-ClaudeArgs`, for example `@('--output-format','json')`.
- Use `-Interactive` only when you explicitly want an interactive Claude session.
- Use `-OutputFile` when you want a durable capture without relying on outer-shell redirection.
- Use `-PromptFile` for multiline prompts and batch execution; it avoids prompt corruption from shell argument parsing.
- The wrapper now feeds the prompt over `stdin` in non-interactive mode, which avoids the old quoting and backtick-shell-substitution failures on Windows and secret-backed Claude paths.
- `-UseSecretWrapper` routes through the repo-canonical `src.claude/agents/scripts/invoke-claude-api.ps1` wrapper, which loads env from `SECRET.md` and then runs plain `claude`.

## Gemini wrapper

With MCP allowlist:

```powershell
.\gemini-isolated-worker.ps1 `
  -AllowMcp fetch,memory `
  -Prompt "Review this repository with only fetch and memory MCP."
```

No MCP:

```powershell
.\gemini-isolated-worker.ps1 `
  -NoMcp `
  -Prompt "Review this repository without MCP access."
```

Notes:

- `-AllowMcp` maps to `--allowed-mcp-server-names`.
- `-NoMcp` uses a clean temporary `HOME` and a clean temporary `cwd` outside the target workspace.
- The wrapper copies only the minimum Gemini auth state needed to avoid re-login.
- In `-NoMcp` mode the real workspace is exposed via `--include-directories`.
- This avoids project-level `.gemini/settings.json` from silently injecting MCP servers into the runtime.
- Add extra CLI flags via `-GeminiArgs`, for example `@('--output-format','json','--debug')`.
- Use `-OutputFile` when you need a durable capture from `-NoMcp` runs. The wrapper resolves the path before switching into its clean temp `cwd`, so relative output paths no longer break when benchmark harnesses or `Tee-Object` are used around the wrapper.
- Use `-PromptFile` for multiline prompts and batch execution; the wrapper now feeds Gemini prompt text over `stdin` with `--prompt=`, which matches the official Gemini CLI contract that `--prompt` appends stdin content and avoids the old multiline positional-prompt misparse.
- For `-NoMcp` runs, the wrapper now prefers the target workspace as `cwd` when no project-local `.gemini/settings.json` exists, which reduces relative-path tool noise while preserving clean `HOME` isolation.

Example with durable capture:

```powershell
.\gemini-isolated-worker.ps1 `
  -NoMcp `
  -OutputFile .\.scratch\gemini-run.txt `
  -GeminiArgs @('--model','gemini-3-flash-high-explicit') `
  -Prompt "Reply with exactly OK."
```

## Qwen wrapper

With MCP allowlist:

```powershell
.\qwen-isolated-worker.ps1 `
  -AllowMcp playwright `
  -Prompt "Use only Playwright MCP tools to open the page data:text/html,<title>QWEN_PW_SMOKE</title><h1>Hello</h1> and reply with exactly the page title and nothing else."
```

No MCP:

```powershell
.\qwen-isolated-worker.ps1 `
  -NoMcp `
  -QwenArgs @('--model','coder-model') `
  -Prompt "Reply with exactly OK."
```

Notes:

- `-AllowMcp` maps to `--allowed-mcp-server-names`.
- `-NoMcp` uses a clean temporary `HOME` and a clean temporary `cwd`, while copying only the minimum Qwen auth files plus model or provider settings needed for the run.
- The wrapper defaults to `--approval-mode yolo` unless you already passed an explicit approval flag in `-QwenArgs`.
- Use `-OutputFile` when you need a durable capture without relying on outer-shell redirection.
- Use `-PromptFile` for multiline benchmark prompts and strict replay fixtures.
- Current machine reality: the wrapper parses cleanly, and the direct local `Qwen` Playwright smoke is admitted, but more benchmark work is blocked by `qwen-oauth` quota exhaustion after the free-tier shutdown date.

## Claude template

Place the template in one of:

- `~/.claude/agents/`
- `.claude/agents/`

Then customize:

- `name`
- `description`
- `tools`
- `mcpServers`
- `model`

## Gemini template

Place the template in one of:

- `~/.gemini/agents/`
- `.gemini/agents/`

Then customize:

- `name`
- `description`
- `tools`
- `mcpServers`
- `model`

## Recommended use

For the strictest isolation:

- `codex`: one worker equals one new process
- `claude`: parent with strict allowlist or strict empty MCP config, child inline `mcpServers`
- `gemini`: parent with empty or narrow allowlist, child inline `mcpServers`; for true parent no-MCP in a project that has `.gemini/settings.json`, use `gemini-isolated-worker.ps1 -NoMcp`

## Playwright smoke paths

### Codex

Confirmed runnable on `2026-04-14` with the current wrapper and current local installation:

```powershell
.\codex-isolated-worker.ps1 `
  -AllowMcp playwright `
  -Prompt "Use Playwright to open the page data:text/html,<title>PW_TEST</title><h1>Hello</h1> and reply with exactly the page title and nothing else." `
  -SkipGitRepoCheck
```

Observed result: `PW_TEST`

### Claude

The current CLI supports `--strict-mcp-config --mcp-config`, so the wrapper can run a Playwright-only session once quota is available again:

```powershell
.\claude-isolated-worker.ps1 `
  -McpConfigPath .\claude-playwright-only.json `
  -Prompt "Use Playwright to open the page data:text/html,<title>PW_TEST</title><h1>Hello</h1> and reply with exactly the page title and nothing else."
```

Current machine note:

- runtime blocked by quota until the next available Claude window
- the strict config uses the official Windows-safe `cmd /c npx -y @playwright/mcp@latest` shape Anthropic recommends for local `npx` MCP servers on native Windows

### Gemini

The current CLI supports `--allowed-mcp-server-names`, so the wrapper shape is already correct:

```powershell
.\gemini-isolated-worker.ps1 `
  -AllowMcp playwright `
  -Prompt "Use Playwright to open the page data:text/html,<title>PW_TEST</title><h1>Hello</h1> and reply with exactly the page title and nothing else."
```

### Qwen

The current CLI also supports `--allowed-mcp-server-names`, and local `Qwen` MCP config now connects successfully:

```powershell
qwen mcp add playwright npx.cmd -y @playwright/mcp@latest --headless --allow-unrestricted-file-access --isolated

.\qwen-isolated-worker.ps1 `
  -AllowMcp playwright `
  -Prompt "Use only Playwright MCP tools to open the page data:text/html,<title>QWEN_PW_SMOKE</title><h1>Hello</h1> and reply with exactly the page title and nothing else."
```

Observed result before quota wall: `QWEN_PW_SMOKE`

Current machine note:

- local Playwright MCP setup is now admitted for `Qwen`
- the stricter hidden-fixture benchmark is currently blocked by `qwen-oauth` quota exhaustion, not by MCP setup failure
- official Qwen docs recommend API-key auth for non-interactive or headless runs, and that is now the required next step for further benchmark rows

### Gemini Playwright setup

This is the exact setup used on this machine. It is a configuration step, not a separate Gemini plugin install.

Prerequisites:

- `node` and `npm` must already be installed and available in `PATH`
- `npx.cmd` must resolve on Windows
- Gemini CLI must already be installed and authenticated

1. Open `C:\Users\<you>\.gemini\settings.json`
2. Add an `mcpServers.playwright` entry
3. Use `npx.cmd` on Windows, not `npx`
4. Keep the args exactly in this order:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx.cmd",
      "args": [
        "-y",
        "@playwright/mcp@latest",
        "--headless",
        "--allow-unrestricted-file-access"
      ]
    }
  }
}
```

Current machine example:

```json
{
  "security": {
    "auth": {
      "selectedType": "oauth-personal"
    }
  },
  "general": {
    "defaultApprovalMode": "auto_edit"
  },
  "model": {
    "name": "gemini-3-pro-high-explicit"
  },
  "modelConfigs": {
    "aliases": {
      "gemini-3-pro-high-explicit": {
        "extends": "gemini-3-pro-preview",
        "modelConfig": {
          "generateContentConfig": {
            "thinkingConfig": {
              "thinkingLevel": "HIGH"
            }
          }
        }
      },
      "gemini-3-flash-high-explicit": {
        "extends": "gemini-3-flash-preview",
        "modelConfig": {
          "generateContentConfig": {
            "thinkingConfig": {
              "thinkingLevel": "HIGH"
            }
          }
        }
      }
    }
  },
  "agents": {
    "overrides": {
      "browser_agent": {
        "enabled": false
      }
    }
  },
  "mcpServers": {
    "playwright": {
      "command": "npx.cmd",
      "args": [
        "-y",
        "@playwright/mcp@latest",
        "--headless",
        "--allow-unrestricted-file-access"
      ]
    }
  }
}
```

Verification steps:

1. Confirm the config is present in `~/.gemini/settings.json`
2. Run a narrow wrapper smoke:

```powershell
.\gemini-isolated-worker.ps1 `
  -AllowMcp playwright `
  -GeminiArgs @('--model','gemini-3-flash-high-explicit') `
  -Prompt "Use Playwright to open the page data:text/html,<title>PW_TEST</title><h1>Hello</h1> and reply with exactly the page title and nothing else."
```

3. If the wrapper still fails, inspect the raw tool error in the Gemini output instead of trusting `gemini mcp list`

Notes:

- `gemini mcp list` still prints no configured servers on this machine, so it is not a trustworthy source of truth here
- the wrapper and config surface are valid, but the current machine still shows `mcp_playwright_browser_navigate` failures on the stricter hidden-fixture browser benchmark
- current canonical Gemini fallback target is `gemini-3-flash-high-explicit`
- current canonical Gemini top target is `gemini-3-pro-high-explicit`
- the current Gemini CLI docs express Gemini 3 “high effort” through `generateContentConfig.thinkingConfig.thinkingLevel`, not through a separate CLI `--effort` flag
- if `gemini-3-pro-high-explicit` hits transient capacity, verify Playwright wiring first on `gemini-3-flash-high-explicit`
- if `npx.cmd` does not resolve, fix Node/npm first; this is not a Gemini-side MCP schema issue

## Current machine reality

| Provider | Flag/path support | Runtime status now |
|---|---|---|
| `codex` | yes | confirmed runnable, including the stricter local-file Playwright benchmark |
| `claude` | yes | CLI surface ready; strict config now matches official Windows `cmd /c npx` guidance; secret-backed fallback path also passes the stricter local-file Playwright benchmark |
| `gemini` | yes | configured and wrapper-runnable, but current strict local-file Playwright benchmark still fails in `mcp_playwright_browser_navigate`; adding official `--isolated` did not recover the lane |
| `qwen` | partial | local Playwright setup and smoke are admitted, but current benchmark execution is blocked by `qwen-oauth` quota exhaustion after the free-tier shutdown date; next honest path is API-key auth |

## Batch execution note

- For parallel benchmark runners on this machine, prefer `pwsh -File ...` as the outer host instead of legacy `powershell -File ...`.
- Context7-backed PowerShell docs confirm that native-command stderr handling changed in PowerShell 7.x; using `pwsh` avoids several legacy `powershell.exe` batch-host edge cases with Node-backed CLIs such as `codex` and `gemini`.

## Official references

| Surface | Official source |
|---|---|
| `Playwright MCP` | `https://github.com/microsoft/playwright-mcp` |
| `Claude Code MCP` | `https://docs.anthropic.com/en/docs/claude-code/mcp` |
| `Gemini CLI MCP` | `https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md` |
| `Gemini CLI configuration` | `https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/configuration.md` |
| `Qwen Code README` | `https://raw.githubusercontent.com/QwenLM/qwen-code/main/README.md` |
| `Qwen Code MCP docs` | `https://qwenlm.github.io/qwen-code-docs/en/developers/tools/mcp-server/` |

