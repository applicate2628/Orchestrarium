# Provider access: what can we connect?

**Checked: 2026-11-18.** This is the repository's source-linked access reference, not legal advice or a statement that an adapter is ready.

**Status:** **Supported** = the provider documents this use, subject to its terms; **Restricted** = an explicit restriction covers the described use; **Unclear** = the sources do not settle this exact use. Unclear is not a blanket provider ban.

A **Lead** coordinates work; a **worker** carries out delegated work. These are our roles, not provider licences. Permissions, account eligibility, spending approval and technical readiness remain separate.

## At a glance

| Provider | Connection and account | Intended use | Status | What matters |
|---|---|---|---|---|
| **Codex** | Official local SDK / app-server; user's ChatGPT account | Lead or delegated agent in the user's own workflow | **Supported** | Official SDK supports custom agents and applications; Codex supports subscription sign-in. Preserve the user's account and workspace controls. [Sources][codex-sdk] |
| **Codex** | Sharing an account with other users or bypassing limits | Any role | **Restricted** | These are separate restrictions, not a ban on the official SDK. [Terms][openai-terms] |
| **Claude** | Unmodified Claude Code; user's own subscription login | Native Lead and native subagents | **Supported** | Ordinary individual use; user signs in through Anthropic. [Authentication][claude-legal] |
| **Claude** | Unmodified Claude Code hosted inside another product | User's own session | **Supported, with conditions** | Host accepts Commercial Terms, preserves every auth method and does not resell or intermediate usage. [Hosting conditions][claude-legal] |
| **Claude** | Third-party app offering Claude.ai login or routing users' subscription credentials | External worker | **Restricted** | No credential/token intermediation. Do not confuse this with the unmodified-binary hosting exception. [Authentication][claude-legal] |
| **Claude** | Official Agent SDK with supported API/cloud authentication | Programmatic Lead or worker | **Supported** | Governed by Commercial Terms. A generic ACP connection does not itself grant subscription rights. [SDK][claude-sdk] |
| **Antigravity** | Native app/CLI; personal plan | Native Lead, native subagents; direct scripting/CI | **Supported** | Direct scripts are documented separately from third-party agent wrappers. [FAQ][agy-faq] |
| **Antigravity** | Official `agy acp`; personal login | Coding agent in an ACP editor/client | **Supported** | Google documents third-party editors, community VS Code and personal OAuth. [ACP][agy-acp] |
| **Antigravity** | Consumer `agy -p` wrapped by a third-party coding agent/app | External worker | **Restricted** | FAQ says unsupported under consumer plans; Terms §6 restrict third-party access. [FAQ][agy-faq], [Terms][agy-terms] |
| **Antigravity** | SDK or ACP; personal plan | Autonomous workers controlled by an external orchestrator | **Unclear** | ACP/editor support and SDK access do not settle this exact arrangement. See the documented ambiguity below. |
| **Kimi Code** | Official client or supported third-party coding tool; subscription | Personal interactive coding | **Supported** | Third-party tools/frameworks are explicitly supported; preserve real client identity. [Guidelines][kimi-guidelines] |
| **Kimi Code** | Subscription used for scripted batches or other non-interactive automation | Unattended worker | **Restricted** | Explicitly outside subscription scope. This is about usage, not the ACP protocol or a role name. [Guidelines][kimi-guidelines] |
| **Grok Build** | Official CLI / ACP; eligible SuperGrok or X Premium Plus account | Programmatic Lead or worker | **Supported** | Provider explicitly offers scripts, automations, bots and orchestration apps to subscribers. [Announcement][grok-build], [Current guide][grok-headless] |

## Read the boundary, not just the status

**Codex.** The [SDK guide][codex-sdk] explicitly supports controlling Codex from custom agents, CI and applications. [Authentication][codex-auth] distinguishes ChatGPT subscription access from API access and recommends API keys for automation; a recommendation is not a universal subscription prohibition. The [Terms of Use][openai-terms] (effective 2026-01-01), “Registration and access” and “Using our Services”, retain account-sharing and anti-circumvention restrictions. A user-owned local workflow is not a grant to resell account access or run a public shared service.

**Claude.** [Legal and compliance][claude-legal], “Can customers offer Claude Code in their products?” and “Authentication and credential use”, must be read together: unchanged hosted Claude Code with the end user's own sign-in is expressly contemplated, while third-party credential intermediation is not. [Consumer Terms][claude-consumer] (effective 2025-10-08) §3(7) restrict automated/non-human access except an Anthropic API key or other express permission. [Commercial Terms][claude-commercial] (effective 2025-06-17) §A.1 and the [Agent SDK licence section][claude-sdk] govern the separate developer-product route. Neither “all orchestration is forbidden” nor “any subscription SDK wrapper is allowed” follows.

**Antigravity.** [Terms][agy-terms] §6 and the [FAQ][agy-faq] restrict third-party access/consumer CLI wrappers, but Google's [ACP guide][agy-acp] explicitly supports outside clients with personal login. The [pricing page][agy-pricing] includes Python SDK in Individual plans and [authentication][agy-auth] mentions shared SDK sign-in; however its programmatic section and [SDK overview][agy-sdk] describe API/cloud/local-model authentication, not an explicit consumer-quota grant for external orchestration. This unresolved distinction should be clarified for that exact arrangement; do not turn it into a ban on all SDKs or all ACP clients.

**Kimi Code.** [Community Guidelines][kimi-guidelines], “Scope of Use” and “Don't use Kimi Code for non-interactive automation”, explicitly separate supported interactive third-party tools from unsupported subscription automation. The [overseas Terms][kimi-terms] (effective 2026-11-05), §2, incorporate documentation/guidelines and restrict automation except express written authorization; §1 restricts account sharing. Mainland-China accounts have separate applicable terms. An API-shaped key supplied by a coding subscription does not automatically turn that subscription into unrestricted platform access.

**Grok Build.** The [official announcement][grok-build] explicitly combines subscriber access with headless automation and ACP orchestration apps. The [current guide][grok-headless] documents cached local sign-in for ACP. [Terms][grok-terms] (updated 2026-10-27) §3 incorporates documentation and the [Acceptable Use Policy][grok-aup] restricts unauthorized automation, not every automated use. Keep actual account entitlement and limits separate from Orchestrarium's unfinished technical qualification.

## Example: Antigravity Lead delegates to Codex

The user works in a native Antigravity Lead session; it delegates a task to an external Codex agent through Codex's official SDK/app-server using the user's own eligible ChatGPT account. Assess the recipient under the Codex row: this is not an external wrapper consuming Antigravity's subscription, and it is not a native Antigravity subagent. The sources support the recipient's official integration; they do not prove this complete Orchestrarium route is implemented, tested or separately approved for spending. Preserve both providers' applicable terms and the user's tool permissions.

## How this relates to our plan

The [SDK execution plan](sdk-execution.md#approved-roleaccess-acceptance-scope) owns implementation scope and readiness. Its selected Lead-only consumer integrations for Claude and Antigravity are project choices, not universal legal classifications. Role names and a successful test cannot create service access rights. Native Lead integration, vendor-native subagents and externally invoked workers must be assessed separately.

Recheck the affected row when the provider changes its terms or when the product, authentication, billing or usage arrangement changes. Keep the date and primary-source links here rather than creating another permissions table.

## Terms and abbreviations

- **SDK:** software development kit used to control an agent from code.
- **ACP:** Agent Client Protocol, a client-to-agent interface; it does not grant account rights.
- **CLI:** command-line interface; **CI:** continuous integration.
- **OAuth:** the provider's account sign-in flow; **API:** application programming interface.

[codex-sdk]: https://learn.chatgpt.com/docs/codex-sdk
[codex-auth]: https://learn.chatgpt.com/docs/auth
[openai-terms]: https://openai.com/policies/terms-of-use/
[claude-legal]: https://code.claude.com/docs/en/legal-and-compliance
[claude-sdk]: https://code.claude.com/docs/en/agent-sdk/overview
[claude-consumer]: https://www.anthropic.com/legal/consumer-terms
[claude-commercial]: https://www.anthropic.com/legal/commercial-terms
[agy-terms]: https://antigravity.google/terms/
[agy-faq]: https://antigravity.google/docs/faq/
[agy-acp]: https://antigravity.google/docs/ide/extensions/acp/
[agy-pricing]: https://antigravity.google/pricing/
[agy-auth]: https://antigravity.google/docs/install/
[agy-sdk]: https://antigravity.google/docs/sdk/overview/
[kimi-guidelines]: https://www.kimi.com/code/docs/en/kimi-code/community-guidelines.html

[kimi-terms]: https://www.kimi.ai/user/agreement/modelUse?version=v2
[grok-build]: https://x.ai/news/grok-build-cli
[grok-headless]: https://docs.x.ai/build/cli/headless-scripting
[grok-terms]: https://x.ai/legal/terms-of-service
[grok-aup]: https://x.ai/legal/acceptable-use-policy
