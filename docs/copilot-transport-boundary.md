# Copilot transport integration boundary

This SDK-to-main slice supplies an offline pre-tool codec in
`scripts/installation/copilot_transport.py`. It does not register Copilot,
modify host configuration, select a model, or add a qualified installer client.

The codec preserves camel-case or snake-case carriers and tool identity.
Encoded camel-case arguments are decoded once, rejecting duplicate fields and
nonfinite numbers. The caller has already decoded the outer object; the codec
cannot discover duplicate outer JSON fields lost before that call. Object
arguments are shared read-only data, not a fully validated JSON schema.

File-operation targets pass through the existing shared
`hook_common.acquire_tool_input` owner. Unsupported carriers remain unresolved;
multi-target operations cannot earn partial target credit. A resolved target
carrier is not filesystem resolution, tool admission or policy authorization.
The renderer emits neutral context or denial, never an allow decision; an empty
object is neutral, not approval. Registration formatting alone installs nothing.

The two wire shapes and custom-tool text carrier were carried forward from SDK
fixtures. Current acceptance is offline tests against main's shared owner and
isolated installed owner copies. No native Copilot or VS Code activation or
enforcement is qualified by this integration. Windows command tests use the
already-published serializer, not a new SDK-only command serializer.

Still required before enabling installation: provider registration/lifecycle
ownership consistent with shared Lead, host-version dispatch qualification,
failure/exit behavior, and native receiving evidence under separately authorized
host runs. Do not enable a new CLIENTS entry merely because these codec tests pass.

## Official registration contract and isolated receiving

Checked on 2026-11-12:
- [VS Code hook configuration](https://code.visualstudio.com/docs/copilot/customization/hooks)
  distinguishes the current Copilot harness from the deprecated Local harness.
  Workspace configuration is `.github/hooks/*.json`; `version: 1` and the
  `preToolUse` event select the camel-case carrier.
- [GitHub hook reference](https://docs.github.com/en/copilot/reference/hooks-reference)
  documents `powershell` on Windows, `bash` on Unix and `command` as a
  fallback. Applicable hook sources are combined, not replaced.
  Timeouts fall through to normal permission checks even for preToolUse.

The formatter now accepts an explicit shell selector. Its default output remains
unchanged; selecting powershell emits only that key, not a Unix fallback.
The existing literal-path serializer is reused by a PowerShell-specific wrapper
that initializes LASTEXITCODE to failure and returns the native executable child status exactly; arbitrary PowerShell functions or scripts are not qualified by this wrapper.
It is not substituted into existing Codex command registrations.

The official pages differ in how they scope shell-free exec/args: the VS Code
page mentions that form while GitHub labels it CLI-only. This slice therefore
uses the explicitly documented PowerShell field instead of assuming editor
support for shell-free execution.

Tests write actual registration JSON in an isolated project, read the configured
command, feed synthetic event JSON on stdin, and check stdout plus exit 0/2/7.
A missing executable must not inherit a previous successful LASTEXITCODE.
User-sibling configuration bytes remain unchanged. These tests run the command
directly, without a VS Code window, Copilot session, model or live configuration.
They do not prove discovery, trust, dispatch, host timeout handling or activation.

No installation command is added by this slice: managed registration still needs
shared-ownership integration and duplicate-source checks. Do not manually enable
this formatter's output as if it installed Orchestrarium policy enforcement.

## Terms and Abbreviations

- SDK: software development kit.
- JSON: JavaScript Object Notation, a data interchange format.
- Codec: decoder/encoder for the supported wire representation.
