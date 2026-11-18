# Client integration notes

Codex is the primary host. Kimi and Grok have higher secondary integration priority
than Claude. This product priority is not an execution-routing or credential grant.
The host-installer catalog contains Codex, the existing Claude adapter and a
bounded Antigravity native startup projection. Startup instruction discovery is
not SDK execution or full native lifecycle qualification. SDK model transports
and host-install support are distinct.

## Secondary adapter authentication

The Python-owned `invoke-claude-prompt.py` transport (also exposed through the thin POSIX launcher `invoke-claude-prompt.sh`) runs automated, headless `claude -p`. Orchestrarium currently admits only `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` for automated Claude runs; subscription sign-in (OAuth), the subscription override, Amazon Bedrock, and Google Vertex AI fail closed. Claude authentication is irrelevant when the Codex route is selected, so absent Claude credentials do not block Codex. Orchestrarium 1.x refuses `apiKeyHelper` before prompt capture or provider lookup because a helper-generated credential cannot be bound to the transport's exact output scan. For the secret-backed path, use `invoke-claude-api.py` or its thin `invoke-claude-api.sh` launcher with the credentials documented in `SECRET.md`. See [Anthropic's Claude Code legal and compliance guidance](https://code.claude.com/docs/en/legal-and-compliance).

## Antigravity native startup

The selected native session can receive shared governance through the installed
SessionStart hook and discover a separate Lead skill/rule. The common installer
preserves other clients and user customizations. This is not a wrapper around a
consumer subscription CLI, nor permission to start a provider. Native tool/lifecycle
hooks, subagent receiving and separately admitted SDK/API routes retain their
own implementation and qualification boundaries. See [installation scope](../INSTALL.md#antigravity-native-startup).

## Terms and Abbreviations

- SDK: software development kit; transport capability does not imply host-install qualification.
- OAuth: delegated account authorization.
- CLI: command-line interface.
