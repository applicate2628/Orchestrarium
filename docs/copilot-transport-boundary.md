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

## Terms and Abbreviations

- SDK: software development kit.
- JSON: JavaScript Object Notation, a data interchange format.
- Codec: decoder/encoder for the supported wire representation.
