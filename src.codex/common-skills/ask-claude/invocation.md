# Claude Invocation

Use this file as the canonical mechanics reference for calling Claude CLI.

## Preferred invocation

### macOS / Linux

```bash
printf '%s' "$PROMPT" | claude -p --effort high --permission-mode bypassPermissions
```

### Windows (Git Bash inside Codex)

```bash
printf '%s' "$PROMPT" | cmd.exe /c claude.exe -p --effort high --permission-mode bypassPermissions
```

Fallback (if `claude.exe` is not on PATH):

```bash
printf '%s' "$PROMPT" | cmd.exe /c claude.cmd -p --effort high --permission-mode bypassPermissions
```

## Prompt transport rules

- Do not pass multiline prompts as direct command-line arguments.
- For longer or multiline prompts, use `stdin` or a file.
- Do not use TTY for Claude.
- On Windows, keep command-line prompts short enough to avoid `cmd.exe` truncation.

## Stalled-run rules

- Wait about 5 to 15 minutes after starting `claude -p` before assuming it is stalled.
- Do not start a new chat while the current run may still be alive.
- If needed, poll or nudge the same session instead of creating a second one.
- If Claude returns quota, auth, or limit errors, record that in the relevant note or plan and continue locally through the fallback path.

## Hard-task note

- For hard complex tasks, prefer the strongest available Claude profile such as Opus when the installed client supports it.
