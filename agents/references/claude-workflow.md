# Claude Workflow

Use this file only when Claude is installed and selected as one execution method for `$consultant`.

This file extends, but does not replace, [consultant-workflow.md](consultant-workflow.md).

## Availability

- Use this adapter only if `claude.exe` or `claude.cmd` is available in the current environment.
- If Claude is not installed, ignore this file and follow the provider-neutral workflow only.

## Preferred invocation

```powershell
printf '%s' "$PROMPT" | cmd.exe /c claude.exe -p --effort high --permission-mode bypassPermissions
```

Fallback:

```powershell
printf '%s' "$PROMPT" | cmd.exe /c claude.cmd -p --effort high --permission-mode bypassPermissions
```

For hard complex tasks, prefer the strongest available profile such as Opus when supported by the installed client.

## Prompt transport rules

- Do not pass multiline prompts as direct command-line arguments to `claude.exe` or `claude.cmd`.
- Keep command-line prompts short enough to avoid truncation.
- For longer or multiline prompts, use `stdin` or a file.
- Do not use TTY for Claude.

## Stalled-run rules

- Wait about 5 to 15 minutes after starting `claude -p` before assuming the run is stalled.
- Do not start a new chat while the current run may still be alive.
- If needed, poll or nudge the same session instead of creating a second one.
- If Claude returns quota, auth, or limit errors, record that in the relevant plan or note and continue with the internal-subagent fallback described in [consultant-workflow.md](consultant-workflow.md).
