# Provider access: subscription or API?

**Checked: 2026-11-18.** Choose the billing route first, then the role. **Lead** coordinates; **external worker** is called by another agent or orchestrator. A provider's native subagent is not an external worker.

**Supported** means officially documented, subject to the applicable terms. **Restricted** means a stated restriction applies. **Unclear** means this exact arrangement is not settled. These are access findings, not adapter readiness or spending permission.

## 1. Subscription / personal plan

| Provider and official connection | Lead | External worker | Practical boundary |
|---|---|---|---|
| **Codex** — local SDK / app-server, own ChatGPT account | Supported | Supported | User-owned workflow; no account sharing or limit bypass. API is recommended for automation, not universally required. [SDK][codex-sdk] · [Auth][codex-auth] · [Terms][openai-terms] |
| **Claude** — unchanged Claude Code, own subscription login | Supported | Not generally established; see conditions | Native subagents are supported. Hosting the unchanged client with the user's own sign-in has explicit conditions; third-party subscription credential intermediation is restricted without separate Anthropic approval. [Conditions][claude-legal] · [SDK exception][claude-sdk] |
| **Antigravity** — native app/CLI or official ACP editor connection, personal login | Supported in documented use | Unclear for external SDK/ACP orchestration; consumer CLI wrapper restricted | Direct scripts/CI and ACP editors are documented. They do not settle every external orchestrator arrangement. [FAQ][agy-faq] · [ACP][agy-acp] · [Terms §6][agy-terms] |
| **Kimi Code** — official client or supported coding tool, membership | Supported for interactive coding | Depends on actual use; one-off cross-agent delegation not expressly classified | Agent-driven requests are not automatically forbidden. Non-interactive batches/pipelines are restricted; no universal human-presence or approval-click threshold is defined. [Guidelines][kimi-guidelines] · [Codex][kimi-codex] · [Hermes][kimi-hermes] |
| **Grok Build** — official CLI / ACP, eligible subscription entitlement | Supported | Supported | Scripts, automation and orchestration apps are explicitly documented. Preserve account entitlement and limits. [Announcement][grok-build] · [Current guide][grok-headless] · [Terms][grok-terms] |

## 2. API / cloud developer access

**This is a separate access and billing route, not permission to reuse consumer subscription credentials.** A key issued by Kimi Code membership still belongs in the subscription table.

| Provider and connection | Lead | External worker | Practical boundary |
|---|---|---|---|
| **Codex** — official SDK / app-server with API key | Supported | Supported | Programmatic agent access under the applicable API account and terms. [SDK][codex-sdk] · [Auth][codex-auth] |
| **Claude** — official Agent SDK with supported API/cloud auth | Supported | Supported | Commercial Terms and the selected cloud/account permissions apply. [SDK][claude-sdk] · [Commercial Terms][claude-commercial] |
| **Antigravity** — official SDK with Gemini API key or eligible Google Cloud auth | Supported | Supported | Uses the selected API/cloud entitlement and service terms, not assumed personal-plan quota. [SDK][agy-sdk] · [Auth][agy-auth] · [Terms scope][agy-terms] |
| **Kimi Platform** — platform-issued key, separate API billing | Documented; contractual check incomplete | Documented; contractual check incomplete | Model API for your own agent loop, not a built-in agent runtime. Developer integration is documented; the applicable platform agreement has not been fully verified in this audit. [Quickstart][kimi-platform] · [Product distinction][kimi-comparison] |
| **Grok API** — API key, separate API account/billing | Supported | Supported | Model API for your own agent loop. API agreement explicitly covers integrations into your products/services. [Developer terms §1.1][grok-api-terms] · [API guide][grok-api] |

## Important distinctions

- **AGY Lead → Codex worker:** assess the recipient under Codex's route. This is neither a native AGY subagent nor a wrapper consuming AGY subscription quota. Both providers' applicable terms still apply; this example does not prove Orchestrarium readiness.
- **Claude:** the unchanged-client hosting exception is not blanket permission to collect tokens or offer a third-party Claude.ai login. Consumer automation restrictions retain expressly permitted exceptions. [Conditions][claude-legal] · [Consumer Terms §3(7)][claude-consumer]
- **AGY:** broad Terms §6/FAQ wording is in tension with the explicit ACP editor guide. Documented product support is not a legal amendment inferred here. Python SDK inclusion in Individual plans does not resolve external consumer-quota orchestration. ACP partner-model availability also varies by client. [Terms][agy-terms] · [ACP][agy-acp] · [Plans][agy-pricing]
- **Kimi:** assess the workflow, not the label “worker”. Interactive coding through other agent tools is documented; unattended batch pipelines are a different use. Overseas and mainland terms differ. [Guidelines][kimi-guidelines] · [Overseas Terms §2][kimi-terms]

The [SDK plan](sdk-execution.md#approved-roleaccess-acceptance-scope) owns implementation scope. Its selected routes are project choices, not universal provider bans. Recheck the relevant row when the account, region, contract, billing or use changes. This is a dated source reference, not account-specific legal advice.

**Terms checked:** OpenAI consumer terms effective 2026-01-01; Anthropic consumer 2025-10-08 and commercial 2025-06-17; Google universal terms US version 2026-07-30 plus AGY additional terms; Kimi overseas 2026-11-05; xAI consumer/API terms updated 2026-10-27. Regional and separately signed agreements may differ. [Google universal terms][google-terms] · [xAI AUP][grok-aup]

**Abbreviations:** SDK = software development kit; ACP = Agent Client Protocol; CLI = command-line interface; API = application programming interface.

[codex-sdk]: https://learn.chatgpt.com/docs/codex-sdk
[codex-auth]: https://learn.chatgpt.com/docs/auth
[openai-terms]: https://openai.com/policies/terms-of-use/
[claude-legal]: https://code.claude.com/docs/en/legal-and-compliance
[claude-sdk]: https://code.claude.com/docs/en/agent-sdk/overview
[claude-consumer]: https://www.anthropic.com/legal/consumer-terms
[claude-commercial]: https://www.anthropic.com/legal/commercial-terms
[google-terms]: https://policies.google.com/terms
[agy-terms]: https://antigravity.google/terms/
[agy-faq]: https://antigravity.google/docs/faq/
[agy-acp]: https://antigravity.google/docs/ide/extensions/acp/
[agy-pricing]: https://antigravity.google/pricing/
[agy-auth]: https://antigravity.google/docs/install/
[agy-sdk]: https://antigravity.google/docs/sdk/overview/
[kimi-guidelines]: https://www.kimi.com/code/docs/en/kimi-code/community-guidelines.html
[kimi-terms]: https://www.kimi.ai/user/agreement/modelUse?version=v2
[kimi-codex]: https://www.kimi.com/code/docs/en/third-party-tools/codex.html
[kimi-hermes]: https://www.kimi.com/code/docs/en/third-party-tools/hermes.html
[kimi-platform]: https://platform.kimi.ai/docs/get-your-api-key
[kimi-comparison]: https://www.kimi.com/code/docs/en/#platform-comparison
[grok-build]: https://x.ai/news/grok-build-cli
[grok-headless]: https://docs.x.ai/build/cli/headless-scripting
[grok-terms]: https://x.ai/legal/terms-of-service
[grok-aup]: https://x.ai/legal/acceptable-use-policy
[grok-api-terms]: https://x.ai/legal/terms-of-service-enterprise
[grok-api]: https://docs.x.ai/docs/overview
