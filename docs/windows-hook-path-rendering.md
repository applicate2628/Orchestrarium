# Windows hook path rendering

Codex command hooks use a shell string, not an argument array. The upstream runner defaults to COMSPEC/cmd.exe on Windows, while the session may supply the turn environment's shell. A whole quoted executable is a string expression in PowerShell; cmd-only quoting is insufficient.

Orchestrarium keeps established simple path bytes unchanged. For supported absolute paths containing spaces or Unicode it leaves the drive/UNC prefix bare and double-quotes the remaining path, for example `C:/"bundle folder/python/python.exe" C:/"project folder/check.py"`. This is an Orchestrarium renderer convention, verified with real cmd.exe and Windows PowerShell subprocesses using a space-containing bundled interpreter path and Unicode script paths. Unicode executable paths have lexical round-trip coverage, not an exhaustive native runtime matrix. It is not a claim of native Codex hook activation or trust. Shell expansion characters, controls and noncanonical mixed commands remain refused. Health inspection accepts only an exact render/parse round trip.

Source provenance: OpenAI Codex revision `392ced7d3a9160fd35d40c606359869215f50522`, [`command_runner.rs`](https://github.com/openai/codex/blob/392ced7d3a9160fd35d40c606359869215f50522/codex-rs/hooks/src/engine/command_runner.rs), its quoted-path test, and [`core/src/session/mod.rs`](https://github.com/openai/codex/blob/392ced7d3a9160fd35d40c606359869215f50522/codex-rs/core/src/session/mod.rs). The tests reproduce the runner's Windows command-line framing without launching Codex.

This correction does not make legacy project registrations relocatable. They bind the selected interpreter and installed script at installation time. A portable distribution must keep bundle members relative and use the separately qualified plugin-root route: upstream plugin discovery supplies `PLUGIN_ROOT` and compatibility `CLAUDE_PLUGIN_ROOT`, but ordinary project hooks do not receive that guarantee. No absolute workstation path is added to shipped source or bundle manifests here. The existing plugin candidate and native activation remain separate acceptance work.

## Terms and Abbreviations

- UNC: Windows network path syntax; lexical rendering coverage does not qualify network execution.
- COMSPEC: Windows environment variable selecting the command processor.
