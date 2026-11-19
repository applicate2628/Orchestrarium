# Client integration notes

Codex is the primary host. Kimi and Grok have higher secondary integration priority
than Claude. This product priority is not an execution-routing or credential grant.
The host-installer catalog contains Codex, the existing Claude adapter and a
bounded Antigravity native startup projection. Startup instruction discovery is
not SDK execution or full native lifecycle qualification. SDK model transports
and host-install support are distinct.

## Secondary adapter authentication

A native interactive Claude Code session and an automated worker are different
routes. The explicit Claude SDK worker route accepts direct Anthropic API
authentication or the supported Amazon Bedrock and Google Cloud Vertex AI
modes. Configuration is not proof of account access or consent to spend.
Consumer subscription credentials are not an authorized programmatic worker
route. Missing Claude credentials do not block a selected Codex route.

The separate legacy `invoke-claude-prompt.py` transport runs headless
`claude -p`. With no explicit authentication mode it refuses subscription-only
authentication and does not execute `apiKeyHelper`. This is not a fallback for
an unavailable SDK or an authorization to automate subscription use. See
[Anthropic's authentication guidance](https://code.claude.com/docs/en/legal-and-compliance#authentication-and-credential-use).

## Antigravity native startup

The selected native session can receive shared governance through the installed
SessionStart hook and discover a separate Lead skill/rule. The common installer
preserves other clients and user customizations. This is not a wrapper around a
consumer subscription CLI, nor permission to start a provider. A narrow native pre-write advisory uses the shared machine-local-path AUDIT
classifier without granting permission or blocking execution. Remaining tool/lifecycle
hooks, subagent receiving and separately admitted SDK/API routes retain their
own implementation and qualification boundaries. See [installation scope](../INSTALL.md#antigravity-native-startup).

## Terms and Abbreviations

- SDK: software development kit; transport capability does not imply host-install qualification.
- OAuth: delegated account authorization.
- CLI: command-line interface.
