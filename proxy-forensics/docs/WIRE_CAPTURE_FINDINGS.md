# Wire Capture Findings — `claude-aw.cmd` via mitmproxy

**Date**: 2026-04-24
**Method**: mitmproxy v12.2.2 as explicit HTTPS proxy, CA cert trusted via `NODE_EXTRA_CA_CERTS`, `HTTPS_PROXY=http://127.0.0.1:8080`, claude-aw.cmd run with `--bare` (skip plugins).
**Captured flows**: 7 total (2 to api.anthropic.com bootstrap, 5 to api.claudecodeapi.cloud)
**Result status**: Client-side fully captured; server responses NOT captured (AW rejected all proxied requests with "connection closed" after receiving request body).

## What we captured

### Outbound /v1/messages request body (client-side, verbatim)

CLI sends to `https://api.claudecodeapi.cloud/v1/messages?beta=true`:

```json
{
  "model": "claude-opus-4-7",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "<system-reminder>...currentDate...</system-reminder>\n\n"},
        {"type": "text", "text": "<user prompt>", "cache_control": {"type": "ephemeral"}}
      ]
    }
  ],
  "system": [
    {"type": "text", "text": "x-anthropic-billing-header: cc_version=2.1.119.fc7; cc_entrypoint=sdk-cli; cch=22dae;"},
    {"type": "text", "text": "You are a Claude agent, built on Anthropic's Claude Agent SDK.", "cache_control": {"type": "ephemeral"}},
    {"type": "text", "text": "CWD: ...\nDate: ...\ngitStatus: ...", "cache_control": {"type": "ephemeral"}}
  ],
  "tools": [],
  "max_tokens": 64000,
  "thinking": {"type": "adaptive"},
  "context_management": {"edits": [{"type": "clear_thinking_20251015", "keep": "all"}]},
  "output_config": {"effort": "max"},
  "stream": true,
  "metadata": {"user_id": "{device_id, account_uuid, session_id}"}
}
```

### Request headers

```
POST /v1/messages?beta=true HTTP/1.1
Host: api.claudecodeapi.cloud
User-Agent: claude-cli/2.1.119 (external, sdk-cli)
Accept: application/json
Content-Type: application/json
Authorization: Bearer <AW-specific token from wrapper ANTHROPIC_AUTH_TOKEN>
X-Claude-Code-Session-Id: <uuid>
X-Stainless-Arch: x64
X-Stainless-Lang: js
X-Stainless-OS: Windows
X-Stainless-Package-Version: 0.81.0
X-Stainless-Retry-Count: 0
X-Stainless-Runtime: node
X-Stainless-Runtime-Version: v24.3.0
X-Stainless-Timeout: 600
anthropic-beta: claude-code-20250219,interleaved-thinking-2025-05-14,context-management-2025-06-27,prompt-caching-scope-2026-01-05,advisor-tool-2026-03-01,effort-2025
anthropic-dangerous-direct-browser-access: true
anthropic-version: 2023-06-01
x-app: cli
Connection: keep-alive
Accept-Encoding: gzip, deflate, br, zstd
Content-Length: 1864
```

Headers use Stainless SDK markers (`X-Stainless-*`) — standard Anthropic SDK client identification.

## Interpretation upgrades

### 1. Euler-bias injection is SERVER-SIDE (AW gateway), not CLI-side

The captured CLI system prompt contains only:
- Standard billing header
- Standard "You are a Claude agent" preamble
- CWD/Date/git-status context

**Nothing about Euler, totient, φ, or any math framing.** The biased `φ(100)=40` opening we observed in AW responses (see `RESULTS.md`) must therefore be injected by the AW gateway **server-side** after receiving the CLI's normal request, before forwarding to the backend model.

This upgrades our earlier inference (based on +7 constant tokenizer offset + Euler-override behavior) to direct evidence of the injection location. Injection is downstream of the client, invisible from client-side instrumentation.

### 2. AW strips request parameters server-side, confirmed

CLI sends:
- `thinking: {type: "adaptive"}` — but AW responses show no thinking content, no thinking-cost overhead → AW strips it
- `cache_control: {type: "ephemeral"}` — but AW responses show `cache_creation_input_tokens=0, cache_read_input_tokens=0` → AW strips it
- `output_config: {effort: "max"}` — but AW responses show identical output length regardless of effort → AW ignores it
- `max_tokens: 64000` — but AW outputs are typically capped at 60-240 tokens → AW enforces a much lower cap

All client-requested parameters are ignored by AW. The gateway forwards a sanitized request to its backend, regardless of client intent.

### 3. AW uses TLS fingerprinting to reject MITM-inspection

All 5 POST attempts through mitmproxy completed TLS handshake, delivered the request body (evidenced by mitmproxy capturing Content-Length: 1864 and body content), then received `connection closed` from AW before any response bytes.

This pattern excludes:
- Cert trust failure (our CA is trusted; api.anthropic.com works through the same proxy)
- Request-body rejection (AW received body before closing)

The most likely remaining cause is **TLS client fingerprinting (JA3/JA4) mismatch**. mitmproxy's Python TLS client signature differs from claude-cli's Node.js TLS signature. AW fingerprints clients and rejects non-Node signatures. This is a sophisticated anti-inspection middleware.

### 4. Claude CLI Anthropic bootstrap uses user's REAL OAuth

Bootstrap calls (MCP servers list, penguin_mode, claude_cli/bootstrap) go to `api.anthropic.com` regardless of `ANTHROPIC_BASE_URL`. Those calls use a standard `Authorization: Bearer ...` header which is the user's real Anthropic OAuth session token.

Only `/v1/messages` is redirected by `ANTHROPIC_BASE_URL` to AW, using the AW-specific token set in `ANTHROPIC_AUTH_TOKEN` by the wrapper script.

Security implication: installing a wrapper like `claude-aw.cmd` does NOT leak your Anthropic OAuth credentials to AW. Your anthropic.com bootstrap continues to use your account. But your actual model prompts + responses go through AW with AW's token.

## What we did NOT capture

- **Response body from AW**: all requests closed mid-stream. We did not see:
  - The literal text of the injected system prompt
  - AW's reply format
  - Whether AW genuinely forwards to Anthropic-Vertex or to a different backend
- **Timing of the close**: we know connection closed after request body received, but don't have precise timing (could be immediate post-body, could be after AW forwarded and backend replied but AW refused to relay).

## Next-level options (if pursuing further)

1. **JA3/JA4 spoofing**: configure mitmproxy (or a Go-based alternative) to emit Node.js TLS fingerprint. Sophisticated setup, ~2-4h work.
2. **Patch the Claude CLI Node bundle**: inject a logging hook into the HTTPS transport inside `claude.exe`. Highly invasive, likely breaks CLI updates.
3. **Use a different intercept method**: Wireshark + Node TLS keylog file (`SSLKEYLOGFILE=<path>`). Node supports this via `--tls-keylog` but it depends on whether the Claude CLI bundled Node respects it.
4. **Contact AW operator**: ask for API docs or log access if legitimate customer.

For the current classification purpose, wire capture provided the evidence we needed (server-side injection confirmed). Further capture is diminishing returns unless the specific question "what is the exact injected system prompt?" is business-critical.

## Files

- Raw flow dumps: `mitm_flows/*.flow` (gitignored — binary, may contain auth tokens; regenerate locally)
- Capture script: `scripts/mitm_capture.py`
- Parser utility: `scripts/parse_mitm_flow.py`
