# Optional software development kit (SDK) execution implementation

This branch implements part of the SDK integration project separately from Rust/npm.
The implemented and historically qualified scope is the selected Codex review
route plus offline adapter checks for other providers. This is not the complete
multivendor SDK target. The completion roadmap below records the current PR19
integration outcome and remaining work, including provider execution and receiving;
the historical adapter-only acceptance does not close that broader outcome. A synthetic Codex success does not
qualify live execution or activate a default route; the optional outer Agents
workflow remains separate from this Host-led path.
Existing host-led Codex/Claude command-line interface (CLI) execution remains the
default. The explicit Codex review bridge described below is an opt-in source
contract, not an automatically selected fallback or an installed-runtime
qualification claim. The historical installed Windows success and receiving-collision
checks and the bounded live Codex review passed on October 25; the outer Agents
cycle passed on October 26. Their exact evidence boundaries are recorded below.
These results do not enable a default route or qualify arbitrary general use.

## PR19 completion roadmap, 2026-11-17

**Status: approved by Dmitry on 2026-11-17; implementation remains incomplete.**
The approved target is a working multivendor SDK integration in this pull request
(PR), not merely a setup menu or the existing Codex review slice. This completion
scope replaces the earlier Codex-only/stub-only plan. Approval permits staged
implementation, but does not upgrade old test results or authorize quota-consuming
provider calls, external reviews, bots or GitHub Actions.
Already-authorized bounded work retains its own scope. Rust remains a separate
implementation line, not a prerequisite for finishing this SDK work.

### Shared design

- Keep one dispatch, process supervisor, ledger and permission owner. Provider
  adapters translate supported requests/events/results into those existing
  contracts; they do not create a second scheduler, policy system or ledger.
- Separate the native Lead session from a programmatically invoked worker.
  Any suitable provider may be Lead; Antigravity (AGY) is not the exclusive Lead.
  The selected AGY and Claude subscription integrations are Lead-only: another
  provider does not invoke them as workers. Their own native subagents remain
  available. This project integration boundary is not a blanket claim about all
  access methods: do not transfer subscription restrictions to official API
  access. Copilot and other providers may serve the roles supported and permitted
  by the actual product, authorization method and applicable terms. Future
  selection interfaces must express that route-specific capability distinction,
  preserve permitted choices and avoid provider-name bans. These are target
  contracts, not claims that the corresponding adapters are already qualified.
- Install each official vendor agent SDK through its supported package route in
  the selected environment. A vendor-supplied runtime remains a vendor dependency;
  Orchestrarium does not repackage it. Do not force a model API SDK into an agent
  integration merely because it is available.
- Compatibility follows required capabilities/protocols and actual package
  dependencies, not an invented requirement for matching SDK/CLI version labels.
  Preserve existing working legacy routes until their replacement actually works.
- Installing a package, making a route callable, proving execution and choosing a
  default route are distinct results. Credentials, account selection and spending
  remain with their existing owners; no silent paid or alternate-account fallback.

### Execution route and context chosen before every delegation

The Lead first reads the relevant skill and retains that skill's workflow owner.
When delegation is useful, use a suitable native subagent by default. Select an
optional external SDK session when the task actually needs supported programmatic
session control or a permitted external provider/reviewer; name that need in the
existing dispatch record. SDK is a transport/execution option, not a claim of
better reasoning or a replacement for the skill. This selection is not a new
approval stage: existing vendor, role, account, data-sharing and spending rules
still apply. An external independent reviewer remains distinct from an
implementation worker, with the proper nonauthoring role and context.

For the PR-review-bot example below, the Lead follows the existing skill; a native
subagent may do suitable local work, while an optional SDK executor may perform
an authorized correction or independent external review. Neither route replaces
GitHub API state/thread operations, starts a second bot loop, or gains authority
merely because the SDK can issue a call. Do not mandate SDK use when the native
route already satisfies the task.

Before each delegation, the Lead deliberately selects the context mode for that
task: a fresh independent session, native fork/inheritance when the runtime
supports it, resume of a correctly bound existing session, or explicit handoff of
the necessary authorized context. This is the Lead's decision, not a fixed global
mode, a question to the user or a new permission gate.

Native subagent inheritance is not interchangeable with an external SDK resume
or handoff. Never claim that a handoff clones hidden history. Resume preserves
the correct provider/account/session binding; handoff supplies selected task
requirements, decisions, artifacts and relevant evidence without an unrequested
cross-provider history export. A fresh independent review does not inherit the
author's private working conversation, but still receives the explicit
requirements, reviewed artifact and relevant evidence.

Use the adapter's actual capabilities; surface an unsupported mode rather than
silently substituting one. Record the selected mode and session lineage in the
existing launch record, not a second session store. Verify fresh-review isolation,
correct resume, explicit-handoff contents and wrong-session/account/provider
refusal through the owning contract. These tests do not authorize model calls.

### Independent multi-Lead sessions and depth

Approved target: the root Lead can split genuinely independent outcomes
into separate sessions, each with a scoped child Lead and its own delegation.
Assign exclusive ownership and expected integration results before dispatch.
The existing shared Lead/lifecycle contract currently reserves dispatch and
lifecycle writing to the root main conversation. Implementing scoped child Leads
therefore includes an explicit, reviewed change to that existing owner contract:
root-global coordination and final acceptance stay with the root; a child may
delegate and record outcomes only within its assigned scope, not mutate root or
sibling lifecycle, acquire new grants or declare global completion. Do not
silently bypass the current root-only contract by relabeling a worker as Lead.
Use separate Git worktrees and pull requests when the change is independently
reviewable and needs isolation; do not create a PR for every small task or split
one atomic change into competing edits. Existing suitable PRs remain reusable.
The root retains overall integration, conflict resolution and final acceptance.
Keep this session/task contract independent of a specific IDE (integrated
development environment), with control available from supported native Claude
or Codex Leads through the same owners. A future interface may project
Todo/In progress/In review/Done and observed usage from existing task/execution
records, without a second state store or invented usage totals. This is an
architecture provision, not a request to implement a new interface in this plan.
A Git worktree separates working files, not permissions, processes or secrets;
it is not a security sandbox.

Keep two depth controls distinct. Orchestrarium can enforce the hierarchy of
sessions it actually creates, using existing dispatch/session lineage; native
subagent depth belongs to the selected vendor runtime. Make configuration
explicit with units (child-Lead/session levels versus native subagent levels)
and ownership. Do not invent a universal numeric ceiling, silently interpret
an unavailable vendor control as enforced, or promise control over hidden
vendor descendants. The root applies the selected authorized resource/scope
policy; any bound needs its actual rationale rather than a convenience constant.

Depth capability findings (source review, not Orchestrarium runtime acceptance):

| Runtime surface | Confirmed control and boundary |
|---|---|
| Codex 0.169 native V1 | `agents.max_depth` applies to V1; [release source](https://github.com/openai/codex/blob/rust-v0.169.0/codex-rs/config/src/config_toml.rs#L695-L705). |
| Codex 0.169 native V2 | The same `agents.max_depth` is explicitly ignored. Instructions alone must not be reported as an enforced depth cap. |
| Claude native subagents | [Official nested-subagent documentation](https://code.claude.com/docs/en/sub-agents#let-subagents-spawn-their-own-subagents) documents `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`; qualify the selected runtime/version and actual enforcement before claiming it works through this adapter. |
| AGY SDK subagents | [Official SDK types](https://github.com/google-antigravity/antigravity-sdk-python/blob/main/google/antigravity/types.py) expose `CapabilitiesConfig.max_subagent_depth`, `enable_subagents` and `allowed_subagents`. This is an SDK surface, not proof of control over every native AGY Lead session. |
| Copilot, Kimi, Grok | Comparable native-depth enforcement is not established by this research; expose that fact instead of inheriting another provider's claim. |

Native-subagent control is also capability-specific, not implied by SDK session
creation. Represent configuration, observation, steering, cancellation and depth
as separate capabilities, rather than one misleading supports-subagents flag:

| SDK surface | What is documented; what still needs qualification |
|---|---|
| Codex Python 0.169 / app-server | [Client source](https://github.com/openai/codex/blob/rust-v0.169.0/sdk/python/src/openai_codex/client.py) provides generic thread list/read/resume/fork and turn steer/interrupt. [App-server docs](https://learn.chatgpt.com/docs/app-server) expose subagent source filtering and experimental parent/ancestor filters. Targeting a live native child through this adapter needs qualification; session fork is not proof of a dedicated native-child spawn operation. |
| Claude Agent SDK | [Subagent docs](https://code.claude.com/docs/en/agent-sdk/subagents) describe agent definitions and model-driven Agent-tool invocation/resume; the [Python interface](https://code.claude.com/docs/en/agent-sdk/python) exposes `stop_task(task_id)` for background tasks. Bind versions and actual task identity; this is not a universal direct child-spawn/control API shared by all vendors. |
| AGY SDK | [Subagent docs](https://antigravity.google/docs/sdk/subagents) expose subagent configuration. [Conversation source](https://github.com/google-antigravity/antigravity-sdk-python/blob/main/google/antigravity/conversation/conversation.py) exposes session messaging, steps and current-turn cancellation. A public child-ID spawn/list/steer/cancel interface was not established in this review; do not label it impossible, or pretend parent-turn cancellation is child-specific control. |

Distinguish requested depth, effective depth and enforcement (runtime,
instruction-only or unsupported) through the existing selected-route contract.
Creating a new root SDK session must not reset Orchestrarium's logical task depth.
Reconcile an uncertain/repeated create request against its existing
task/session/branch/PR binding before creating another, rather than duplicating
sessions or PRs. Use native vendor defaults honestly; do not invent a cross-vendor
number or mislabel those defaults as an Orchestrarium guarantee.

A child Lead chooses native or external execution and context before each of its
own delegations, using the same skill, role, access and permission owners as the
root. The intended mechanism is programmatic session creation through an official
SDK or supported agent protocol, not a new CLI-to-CLI wrapper. An official SDK
may internally launch its vendor runtime; that does not make it Orchestrarium
repackaging the runtime. Legal eligibility still depends on the exact provider,
product, credentials/access method and applicable terms: an SDK's technical
ability to create a session is not authorization to use consumer credentials.
Do not launder a prohibited route through a child Lead. Existing permitted
mechanisms are not categorically banned merely because a parent is an agent.

The [Orca orchestration reference](https://orca.dev/docs/cli/orchestration)
provides an experimental example of coordinator/task/worker sessions, child
worktrees and configured worker nesting. At reviewed commit `651f2efa`,
[Orca's depth configuration](https://github.com/stablyai/orca/blob/651f2efaa9502568b311babf9d14ac655a6444bd/src/shared/orchestration/workers/nested-worker-depth.ts)
and [dispatch evaluation](https://github.com/stablyai/orca/blob/651f2efaa9502568b311babf9d14ac655a6444bd/src/main/runtime/orchestration/db/dispatch-creator-evaluation.ts)
control Orca-owned dispatch lineage, not native Codex/Claude descendant trees.
Do not copy Orca's numeric default or infer vendor-native enforcement from it.
This is design evidence, not a dependency or proof that Orchestrarium controls
native vendor subagents. Reuse existing
Orchestrarium owners rather than importing a second coordinator or approval loop.
Acceptance covers independent ownership, child-result integration, conflicting
changes, cancellation/uncertain children and the distinction between configured
and actually enforced hierarchy/native depth.

### Official access terms and project choices

Reviewed official sources on 2026-11-17; recheck the applicable product and access
method when implementing or using a route. This plan is not a legal determination.

- **Antigravity consumer access:** [Terms, section 6](https://antigravity.google/terms)
  prohibit third-party software access, including the stated OAuth example.
  The [official FAQ](https://antigravity.google/docs/faq), under "Can I use
  Antigravity CLI headless mode in third-party coding agents or automate account
  switching?", distinguishes direct scripting/continuous integration from wrapping
  the CLI inside third-party agents/apps under consumer plans. The terms separately
  identify Enterprise/API agreements. Do not infer that consumer credentials
  authorize an external worker, or transfer the consumer restriction automatically
  to a separately contracted API route.
- **Claude authentication:** [Legal and compliance: authentication and credential
  use](https://code.claude.com/docs/en/legal-and-compliance#authentication-and-credential-use)
  disallows third-party applications offering Claude.ai login or routing the
  listed subscription credentials on users' behalf; developer products use the
  supported API/cloud path. The same official page's "Can customers offer Claude
  Code in their products?" section permits the described end-user sign-in to
  unmodified hosted Claude Code. Consequently, this plan's subscription
  **Lead-only** choice is an Orchestrarium integration boundary, not a claim that
  Anthropic universally prohibits all orchestration or all hosting.
  [Consumer Terms, section 3(7)](https://www.anthropic.com/legal/consumer-terms)
  restrict automated access with explicit exceptions for an Anthropic API key or
  other express permission; do not omit those exceptions.
  [Commercial Terms, section A.1](https://www.anthropic.com/legal/commercial-terms)
  cover the separate product/end-user route subject to their conditions.
- **Separate AGY SDK access:** the [official SDK quickstart](https://antigravity.google/docs/sdk/overview#quickstart)
  uses `GEMINI_API_KEY`; [Gemini Enterprise setup](https://antigravity.google/docs/sdk/overview#gemini-enterprise)
  uses its cloud authorization route. Neither is authorization to wrap a consumer
  subscription CLI. Assess these worker routes under their own applicable terms.
- **Programmatic child sessions:** the [official Codex Python SDK](https://github.com/openai/codex/blob/main/sdk/python/README.md)
  documents thread creation and Codex/ChatGPT authentication reuse. The
  [Claude Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview)
  distinguishes its supported internal Claude Code runtime from authorization:
  integrations use API/cloud access or an applicable approved arrangement, not
  an inferred right to reuse consumer login. AGY SDK sessions use the API or
  enterprise route cited above. A child Lead role does not change these access
  requirements. Keep the hosted unchanged-Claude-Code exception separate; it
  does not automatically qualify an unattended third-party SDK integration.
- For other routes, preserve the official package/protocol and check the terms
  governing the selected account/product. A license to install an SDK is not
  permission to reuse a subscription credential, invoke a model or spend quota.
  Unknown access eligibility remains explicit; do not turn it into a blanket
  provider restriction or an unsupported permission.

### Current baseline and remaining provider work

Published baseline for this roadmap: `23da8dba`. Subsequent changes must update
their own evidence below or in the existing PR description rather than relabel
historical results as fresh acceptance.

| Surface | Implemented or observed baseline | Remaining outcome in PR19 |
|---|---|---|
| Common execution | Existing shared dispatch/supervisor/ledger; SDK worker uses the invoking Python interpreter. | Exercise the same lifecycle, events, receipt and cancellation owners for each supported provider/role; retain main regressions. |
| Codex | Explicit Windows Reviewer, Consultant and scoped Worker source bridges; offline qualification and historical bounded native evidence below. | Complete current installed/native qualification and intended child-Lead/session/platform outcomes through the common mechanism. |
| Claude | SDK worker factory/adapter and offline checks; native Lead is a different boundary. | Complete the public execution path and receiving with the provider-supported programmatic access method; do not wrap a subscription CLI as a third-party worker. |
| Antigravity | Official setup direction; no implemented AGY runtime adapter in the current SDK execution factory. | Implement Lead/session integration and native subagent handoff; separately qualify any admitted programmatic worker route. |
| Copilot | Setup direction; existing integration candidates are not a callable SDK execution route. | Reconcile reusable candidate work, implement the common adapter and verify supported Lead/worker/reviewer roles without provider-name role bans. |
| Kimi | Existing ACP boundary is separate from the current SDK factory. | Reconcile the supported Kimi runtime with the official agent integration; do not silently substitute the older Python runtime or a model API for the chosen route. |
| Grok | Candidate protocol support is not live-qualified execution. | Integrate the official Grok Build Agent Client Protocol (ACP) route, including account/tool enforcement and result receiving; do not invent a separate vendor SDK or substitute the xAI model API. |

### Approved role/access acceptance scope

This approved target matrix is not an existing capability claim.
Lead is the owner of an orchestration scope, not an authentication mechanism.
It may run in a user-owned native session or an explicitly permitted SDK-created
child session. Worker, Reviewer and Consultant are separate task roles entering
the common execution contract. A role label never changes access eligibility.

| Provider/access route | Approved roles to finish | Entry and acceptance boundary |
|---|---|---|
| Codex, supported official agent access | Lead, Worker, Reviewer, Consultant | Native Lead integration plus public programmatic routes; Reviewer-only is not completion. |
| Claude consumer subscription | Lead, with vendor-native subagents | User-owned native session; no external-worker wrapper. |
| Claude official API/cloud | SDK-created Lead, Worker, Reviewer, Consultant | Official programmatic route; account and quota authorization are separate from implementing the adapter. |
| AGY consumer subscription | Lead, with vendor-native subagents | User-owned native session; no external-worker wrapper. |
| AGY official SDK/API/enterprise | SDK-created Lead, Worker, Reviewer, Consultant | Official non-consumer access and its applicable contract, not consumer-token reuse. |
| Copilot, supported official SDK access | Lead, Worker, Reviewer, Consultant | Native Lead integration and SDK execution without artificial provider-name role restrictions. |
| Kimi, supported official agent access | Lead, Worker, Reviewer, Consultant | Select the compatible supported runtime/protocol before implementation; no silent legacy-runtime substitution. |
| Grok Build, supported ACP access | Lead, Worker, Reviewer, Consultant | Native Lead integration and official ACP execution; model API is not a substitute. |

Approved target platforms are Windows, macOS and Linux where the selected vendor
officially supports the route. Current containment and public Codex bridge
evidence is Windows-only; this is an implementation gap, not an approved reduction
of the target. Specify and implement the missing supported-platform execution
owners and verify them natively. Record any vendor-unsupported combination as a
specific external limitation for approval, not an invented general platform ban.
A provider lacking a promised native role or access capability is an unresolved
target requiring plan reconciliation, not a passing stub or automatic scope cut.

For every included route, completion means its actual public/native entry,
authorized real execution and received result are demonstrated; focused negative
and cancellation checks preserve ownership and report uncertain outcomes honestly.
Record the commit, runtime/access method, platform, scenario and result. Local
fakes, setup success and unavailable live runs do not complete that route.
One unresolved provider does not stop independent ready implementation.

### Read-only Consultant adapter increment

The Codex Consultant adapter now uses the existing read-only transport lifecycle
with a typed task result (`run_id`, `artifact_id`, `role`, `content`), not a review
verdict. The request's explicit `result_kind: task` selects an output contract,
not a permission or launch route. Existing review requests omit the default kind
and existing results omit absent task evidence, retaining their serialized shape.
The adapter checks the Consultant role and task kind before client construction;
account verification, read-only sandbox, denied approvals, observations and
cleanup remain owned by the existing Codex adapter. Resume is not enabled by this
increment. Task content is evidence requiring independent validation, not proof
that files changed or a review passed.

The explicit `--sdk-task-binding PATH` selector now connects Consultant execution
through the existing runtime, process, ledger and receiving owners. Use
`--ledger-role consultant` with the existing ledger/artifact/terminal-receipt
controls and binding schema shown for review below. It is mutually exclusive
with `--sdk-review-binding`: the review selector remains review-only. Task kind
is committed in the request hash; launch and terminal keep the Consultant role,
`gate: none`, and nonauthorizing evidence. Advice is never a PASS/REVISE verdict
or a closure of another run. Failed receiving retains the same diagnostic and
explicit reconciliation path, without relaunching the operation.

This public source integration is tested offline, not installed or live-qualified.
Existing spending and launch authorization still apply; no default-route change
or provider call follows merely from selecting a binding. Worker write scope is described below; other provider task adapters remain
later slices, without a second ledger or permission owner.

### Whole-workspace Worker adapter increment

An explicit immutable `write_workspace` is a whole-directory write boundary,
not a permission derived from the free-text task `scope`. It must be a normalized
absolute path equal to `cwd`. The existing taxonomy identifies Worker professions;
Reviewer, Consultant and coordination operations do not inherit this capability.
The same request hash binds the selected workspace and result-kind when an owner
uses the request. Omitted write scope keeps existing read-only wire values stable.

The Worker adapter reuses the current Codex lifecycle with approval escalation
denied and no external MCP tools. It requests `workspace-write`, no additional
roots, network disabled and both native temporary-root exclusions. It verifies
the effective thread policy before the turn, then sends the same turn policy.
The native projection may explicitly include the already-authorized cwd, but not
another root. Missing exclusions or wider native profile requirements stop this
operation before its turn. Workspace identity is rechecked before effects; this
cooperative consistency check is not a hostile filesystem race-proof sandbox.

Official source at [Codex commit 69231e1](https://github.com/openai/codex/tree/69231e119bfca0b14453515e97d99688ce1c47c9)
(`codex-rs/protocol/src/protocol.rs`, `core/src/config/mod.rs`, and
`app-server/src/request_processors/thread_processor.rs`) establishes that
workspace-write implicitly includes cwd and that explicit permission profiles can
ignore legacy configuration. Therefore configuration alone is not enforcement.
OS enforcement and installed-runtime behavior still need separately authorized
qualification; offline fake-client tests prove contract handling only.

Runtime admission, selected provenance and task receiving now share the existing
owners. Custody rejects a writable directory containing, contained by, or aliased
to the selected work item (including ledger/artifacts), Codex home/credentials,
native runtime installation, Python/SDK installation, trusted source or hook root.
This selected-path check does not discover arbitrary secrets or enforce an OS
sandbox. Metadata exports only `writeWorkspaceSha256`, committed by the selected
request; it does not publish a local directory path. Observed policy must match
selected version-2 provenance. Worker evidence retains its canonical profession,
external-worker role and gate none; it cannot close review or authorize itself.

The public `--sdk-task-binding` route now accepts version 4 with an explicit
`writeWorkspace` and a canonical Worker profession supplied by `--ledger-role`.
The directory must equal the current working directory. Versions 1-3 remain
read-only Consultant bindings; the review selector cannot admit writes. Binding,
prompt and terminal-receipt files must remain outside the workspace. Select an
external owner-controlled capture directory with existing `CODEX_PROMPTS_DIR`;
the default inside cwd is unsuitable for this write route. The actual acquired
capture directory is bound before process creation and checked again at effects
and receiving; an unbound or substituted directory cannot authorize execution.
Preparation performs no provider launch. This public source integration is
verified offline only: native sandbox qualification, installed behavior and
independent review of actual file changes remain separate. Startup/hook trust remains its current
owner. A TaskResult reports evidence, not proof of accepted writes or completed
review. On interrupted/uncertain execution, retain evidence and inspect actual
changes; do not auto-replay, roll back, or delete work. Worker resume is not yet
qualified. Other read-only routes remain available.

### Claude read-only Consultant adapter increment

`ClaudeConsultantAdapter` reuses the existing Claude Agent SDK execution lifecycle
and common TaskResult contract. Both the synthetic StructuredOutput tool arguments
and final `structured_output` are checked against the selected task schema and
exact run/artifact/role. Advice never requires a fabricated review verdict.
Read/Glob/Grep scope, existing current-authority/account callbacks, cancellation,
observation capture and cleanup remain unchanged. Partial evidence is retained
without converting failure into completion; review adapters reject task requests.

The official [structured-output interface](https://code.claude.com/docs/en/agent-sdk/structured-outputs)
supports a caller-selected JSON schema and structured result. This is vendor
interface evidence, not proof of an installed runtime or a grant to invoke it.
The current [authentication guidance](https://code.claude.com/docs/en/legal-and-compliance#authentication-and-credential-use)
retains the distinction between programmatic API/cloud integrations and native
end-user Claude Code sessions. This project slice introduces no subscription
wrapper, credentials, login, billing fallback or live call.

The offline receiving increment binds Claude Consultant evidence to the exact
admitted request and retained runtime selection through existing provenance and
ledger owners. The selected mode is `tool-restricted-read-only`, not an operating
system sandbox guarantee. Completed advice remains nonauthorizing task evidence;
incomplete or mismatched evidence cannot become a review verdict or task closure.

The fixed Claude factory now selects `ClaudeConsultantAdapter` for the exact
admitted task contract. The existing public Python Host API,
`runtime.SdkReviewExecutor`, executes and receives this task despite its historical
Review name; no additional dispatcher, permission store or stage machine is
introduced. The Host supplies its existing request authority (`resolve` and
`assert_current`), concrete `ClaudeRuntimeSelection`, process owner, selected
environment, artifact, budgets/cancellation and trusted synchronous `authorize_tool`
and `verify_account` callbacks. Those callbacks are code owned by the Host, not
fields or callable paths supplied in an untrusted task binding.

The API/cloud mode check is transport eligibility, not proof of account identity
or spending consent. Official API authentication authenticates the selected
credential; SDK initialization and `apiKeySource` do not independently identify
a billing account. The existing Host account callback must use its own admitted
auth context rather than treating the request's arbitrary alias as verification.
This preserves the current callback contract, not a new universal account probe.
The tool callback checks exact tool arguments under the Host's current access.
Read-only tools do not constitute operating-system containment.

### Claude prompt-only command-line integration

The existing Claude wrapper accepts `--sdk-task-binding PATH` for Consultant
advice with an explicit concrete model identifier, `--ledger-role consultant`,
and the existing ledger/artifact/terminal-receipt controls. The task binding is
constraints, not launch or spending permission. Review binding, write workspace,
and Codex hook/account-email settings do not become Claude capabilities.

The CLI selects `tool_profile: prompt-only`: the request hash commits this
capability, while omission preserves the historical Host profile and wire format.
No Read, Glob, Grep, shell, network-tool, subagent or MCP capability is granted;
only schema-validated StructuredOutput is accepted. Supply relevant code,
artifacts and project constraints explicitly in the prompt file or chosen handoff.
The verified shared governance frame and native Claude preset are retained;
ambient project instruction files are not silently loaded or claimed as context.
Caller tool, permission and settings flags are not silently discarded: unsupported
SDK capability overrides are rejected during preparation. The legacy resolver
appends its own user-settings transport suffix; the SDK instead uses the verified
instruction capsule with native preset and disables ambient settings.
The existing Host API can still use its separately admitted read-only tools.

The CLI uses the existing auth resolver and the explicitly selected API/cloud
environment. `accountBinding` labels this selected auth context, not an observed
person or billing account. Auth-context checks compare the retained selection
without exporting credentials or their hashes. A cloud credential chain can
refresh its tokens; this is not proof of unchanged cloud principal identity.
Subscription override and implicit provider fallback remain unavailable here.
This introduces no new account service or identity probe.

[Official Python SDK options](https://code.claude.com/docs/en/agent-sdk/python)
and [permission behavior](https://code.claude.com/docs/en/agent-sdk/permissions)
distinguish available tools from auto-approval. This route configures the tool
set, checks observed initialization and applies existing hooks; it does not
mistake an empty allowed-tools list for containment. Offline fixtures are not
native SDK or operating-system acceptance.

Receiving failures retain the acquired RuntimeRun; repair/reconcile evidence
instead of repeating execution. Actual provider execution remains separately
permissioned. No installation, sign-in or model call is implied by this source
integration.

### Ordered implementation slices

1. **Official setup and selected environment.** Finish explicit apply, normal
   vendor dependency installation and package consistency checks. The existing
   entrypoint and supervised worker must use the selected interpreter. Test
   invalid targets, ambient installer-variable isolation and recovery after a
   partial environment/install failure. Ownership: the existing SDK integration
   and installer lanes; coordinate shared-file changes before parallel work.
2. **Programmatic external SDK execution.** Extend the existing dispatch and
   execution owners so the Lead can start an external task through the selected
   official SDK (or the vendor-supported agent protocol), observe streaming
   events, request cancellation and receive a validated common typed result
   envelope plus the existing terminal receipt. This normalization preserves
   provider provenance and raw evidence; it does not imply provider-native JSON
   answers or fabricate a structured review verdict from CLI/ACP output.
   Provider-native structured output is used only where supported. Where
   supported, resume the correctly bound
   external session/job; an explicit context handoff is not native resume.
   Before each call, the Lead chooses fresh independent execution versus
   supported continuation or explicit handoff, according to the task and actual
   adapter capabilities. Keep execution work distinct from independent review.
   Native vendor subagents are a separate mechanism, not evidence that these
   external calls work. Do not promise streaming, resume or cancellation semantics
   that the selected vendor does not support: expose the concrete capability and
   outcome, with no silent substitution or inferred history clone.
   The existing permission owner selects capabilities for the actual role/access
   route: a Worker may write only within its authorized workspace/tool scope;
   Reviewer and read-only Consultant routes retain their nonmutating scope.
   Verify admitted writes, rejected forbidden writes/tools and role switching
   without stale write permission. Preserve success, failure, uncertain outcomes,
   settlement and main regressions without a second ledger or blind replay.
   Extend the same session lineage for approved independent child-Lead sessions
   and their selected hierarchy limits; propagate role/access/context decisions
   without pretending native-provider depth is controlled by that lineage.
3. **Provider vertical slices.** Complete each approved route in the role/access
   matrix end to end. For programmatic roles, wire the public call to the real
   provider adapter: request/role/access selection, start or supported resume,
   stream/event mapping, cancellation and structured result/receipt receiving.
   Exercise task execution and independent review as distinct use cases, with
   the selected fresh/continuation/handoff mode carried to the real adapter.
   For native Lead integrations, use the user-owned session and vendor-native
   subagents; do not implement a Lead-only subscription route as an external
   worker. Independent adapter work may run in parallel after shared interfaces
   are agreed; one owner edits each shared boundary. Reconcile existing
   candidates before implementing missing behavior. Record unsupported or
   unqualified capabilities explicitly, not as stub successes or blanket claims
   that every SDK offers the same session controls.
4. **External-call and cross-provider acceptance.** Through public entrypoints,
   verify an allowed external task and a fresh independent review; a supported
   resume with correct session/account/provider binding; an explicit handoff
   carrying only selected authorized context; streaming/event mapping and a
   validated result. Verify cancellation and its actual terminal/unknown outcome,
   interrupted streams, unsupported modes and forbidden role/access combinations.
   Check that a suitable native-subagent task is not unnecessarily routed through
   an external SDK, that a justified external route preserves the skill's owner,
   and that independent review is not silently assigned to its implementation
   author. Unsupported SDK capabilities must not trigger an unapproved fallback.
   Fresh review receives requirements/artifact/evidence without the author's
   private working conversation. Preserve permissions, resource ownership and
   receipts across these cases and the selected supported platforms.
   For child-Lead work, verify disjoint ownership, integration/conflict handling
   and cleanup/cancellation without touching another session's resources.
   A fresh SDK root must preserve logical task depth and root identity; a child
   cannot exceed inherited authorized scope or mutate root/sibling lifecycle.
   Check these through the existing session/permission owners, not a second store.
   Check the actual native depth capability for each selected runtime; unsupported
   enforcement must remain visible rather than reported as a passing cap.
   A concrete integration scenario is the existing `github-pr-review-bot` cycle:
   optionally delegate an authorized correction or fresh independent review to
   an SDK executor, then return its result to the owning skill. The skill and
   GitHub API remain responsible for PR state and review threads; the SDK does
   not replace them or authorize a bot run, continuous integration (CI) or
   quota-consuming model calls. Verify that the result remains bound to the
   reviewed PR revision, that stale results are not applied to a newer revision,
   and that correction/review results do not themselves mutate or close threads.
   Use local contract fixtures unless a real external run is separately authorized.
   Run free local/contract checks first. Actual external model calls and quota
   use require applicable user authorization; mocks, package installation and
   native subagent runs do not qualify external SDK execution. Record unrun live
   checks precisely and continue independent ready work.
5. **Finish the existing PR.** Reconcile code, this roadmap, tests and the PR
   description against the final commit. Update affected shared and pack
   Lead/lifecycle and external-dispatch contracts, agents-mode schema/reference, installer
   propagation, README/INSTALL and release notes under their existing owners.
   AGY remains a distinct identity; do not revive the removed Gemini scalar or
   leave installed contracts contradicting implemented SDK capabilities. A
   retained legacy default is distinct from SDK availability and need not be
   widened merely to match the provider matrix. Commit and push coherent authorized
   slices to the existing PR branch. Report implemented routes, observed runs and
   remaining limitations separately. Merge and global installation are subsequent
   delivery actions, not prerequisites for a working PR implementation.

### Current execution state

The information-only setup baseline was followed by published setup apply/recovery
in commit `ee794cf2`; the approved plan baseline is `264f629d`, which also corrects test
module registration. Setup now creates/updates the selected virtual environment,
installs ordinary vendor dependencies and runs pip check while preserving failures
for diagnosis or retry. These are installer implementation results, not proof of
model execution or complete provider-role support. Actual native startup evidence
and full-suite outcomes retain their own exact recorded scope; this roadmap does
not claim an all-green runtime acceptance. Full multivendor execution remains
unfinished; neither plan entries nor setup catalog entries mark it done.

Continue with the next incomplete slice, not another unchanged broad audit.
Use this section and the existing PR for the completion state; do not create a
competing tracker or impose arbitrary run counts, time limits or new approval
stages. Preserve actual permissions, required checks and justified safety bounds.

## Provider installation boundary

Use the [official agent SDK setup proposal](../INSTALL.md#official-agent-sdk-setup) in a separate provider environment. Orche does not repackage provider SDKs or CLI binaries. Ordinary vendor installation may supply its own runtime and retains complete original metadata/dependencies. Launch the existing SDK entrypoint with that environment's Python; the supervised worker uses the same interpreter. The base distribution launcher remains installer-only. Historical SDK-only bundle and `--no-deps` qualification below is preserved evidence, not the current installation recommendation. No source fixture or package install activates a live route.

## Explicit Codex review opt-in (repository-local contract)

The existing provider-prompt entrypoint accepts `--sdk-review-binding <path>` only
for a Codex `external-reviewer` invocation. Omission keeps the legacy route. Other
providers and worker/consultant roles are not migrated by this option. The same
invoking Host (the existing orchestration session) remains the authorization
owner; the binding file supplies constraints, not permission, a transferable grant,
a new coordinator or an automatic retry. No outer Agents model loop is started.

The bridge requires the existing ledger, explicit review-artifact locator and
absolute caller-owned terminal receipt, the policy-resolved model/effort, and a
read-only review profile. It refuses unsupported platforms before native effects:
the current containment path is Windows-only. Its Python worker requires the
separately provisioned compatible environment; installing helper files does not
install dependencies or authorize their execution. Existing login/account owners
remain in control; this opt-in does not require or create a separate API billing
lane, copy credentials, switch accounts, or pin an SDK/runtime release.

The CLI and independently callable `prepare_dispatch` use the same managed
model-launch policy before binding or runtime effects. The selected logical
`runtime_namespace` follows the public launcher into SDK preparation; direct
Python callers default to their actual provider module's namespace. The local
`--user-approved-launch` projection never enters provider flags or the binding
file and is not itself human consent. The dispatch guard retains that projection
and rechecks the selected rule before each admitted native effect; changed
controls refuse rather than upgrading an existing operation's authority.

Lower-level `run_admitted_review` and coordinator APIs still require the Host's
explicit current policy owner. Such callers must enforce the shared
`model_routing/launch_policy.py` requirements, including genuine per-attempt
Astra/Max agreement, for outer and inner requests separately. These APIs do not
infer that agreement from a model name, ledger, binding file or earlier run.
The retained historical example remains limited to its exact Luna/high pair;
its historical qualification is not a new qualification of arbitrary profiles.

The public launcher imports the provider participant adjacent to its selected
logical namespace, including a linked launcher. Hook trust forwards the absolute
logical `hooks.json` spelling to the existing health owner; only that owner
resolves and rechecks the witnessed alias chain. Resolving it in the caller
would erase the alias evidence that the inventory needs. This preserves the
same policy and trust owners rather than introducing a second SDK-specific one.

The strict UTF-8 JSON binding is bounded to 65,536 bytes. Version 1 contains
exactly the following fields; version 2 additionally requires `installedHookRoot`.
Version 3 additionally selects context as described below. Version 4 has exactly
the version-3 fields plus a nonempty normalized absolute `writeWorkspace`; it is
valid only for explicitly selected task-mode Worker roles, never review or advice:

| Field | Meaning |
|---|---|
| `schemaVersion` | Integer `1`, `2`, `3` or `4`; repository-local binding schema, not SDK version. |
| `accountBinding` | Nonsecret identifier for the selected existing account. |
| `expectedAccountEmail` | Existing account email for auth-file verification, or null where the selected auth mode permits it; not a credential. |
| `coordinatorBinding` | Existing Host/session binding label; does not start a coordinator. |
| `scope` | Nonempty list of explicit review-scope strings. |
| `artifactIdentity` | Identity of the artifact being reviewed, distinct from the output locator. |
| `maxEvents` | Positive bounded adapter-observation/query count budget. |
| `jobMemoryLimitBytes` | Positive Windows Job committed-memory budget. |

Version 2 `installedHookRoot` is an absolute path to the selected installed hook
package. For custom CODEX_HOME layouts, the operator must select this version
and supply the package explicitly; version 1 still parses without that selection.
No package is inferred from hook commands. The immutable runtime selection and request hash include it,
and the existing hook-health owner validates it via `--installed-root`. This is
selection, not consent or native hook qualification. Version 1 remains closed and
does not accept this additional field.

Version 3 requires `contextMode` (`fresh` or `handoff`) and
`contextHandoff` (null for fresh, nonempty selected task evidence for handoff).
It also includes `installedHookRoot`, allowing null for the existing default
hook-selection route. The same binding byte limit applies; no new context cap
is introduced. Fresh review receives the explicit task prompt, requirements and
artifact evidence without importing the author's private conversation. Handoff
appends only the supplied text before ordinary governance framing and admission;
it does not clone native history, import files or grant authority. The immutable
execution request/result records `context_mode`, included in the existing request
hash. Canonical serialization omits the default `fresh` value to preserve
previously retained request commitments; absent means fresh, never inherited. Version 1/2 retain fresh behavior. This increment does not implement
new-turn resume/fork in the public review bridge; requesting either is rejected,
not converted to fresh. Existing interrupted-turn reconciliation is unchanged.
The remaining provider-specific context modes in the roadmap remain unfinished.

The binding cannot select extra tools, arbitrary launch flags or endpoints. This
bridge selects an empty Model Context Protocol (MCP) tool scope and fixed startup
isolation controls; it does not expose the lower-level adapter's selectable-MCP
interface. Empty scope is checked against returned thread inventories, not inferred
from an empty configuration table. This is not a proof that all native, dynamic or
extension tools are disabled, nor atomic isolation from configuration changes.

Resource bounds are separate, not interchangeable: existing `--ledger-max-events`
and `--ledger-max-bytes` govern durable ledger admission. Omit both to let each
locked ledger operation derive finite admission from its selected history and
planned writes; omission is not replaced by a fixed or launch-time ceiling.
Supplying only one bound is rejected. Current launch checks requalify the captured
ledger and selected participant identities before accepting their observations.
Binding `maxEvents` and
`--result-max-bytes` bound retained SDK evidence/result text; `--capture-max-bytes`
bounds the worker capture/serialized receipt and remains subject to the worker
transport ceiling; `jobMemoryLimitBytes` limits process-tree committed memory.
The existing finite timeout/cancellation owner also covers preparation and native
hook-trust work. None of these turns private SDK pipes into byte-complete evidence.

Known failure before SDK worker invocation is settled once by the runtime owner.
Receiving exports selected-only Version 3 (V3) blocked/none evidence after matching
durable readback and output scanning: its exit code is a wrapper failure code,
not a native exit observation, and cleanup remains conservatively incomplete.
An exception after worker invocation has uncertain effects; it must not be recast
as a preworker failure or replayed. Acquired execution evidence is retained before
receiving, and receiving/receipt failures remain failures rather than permission
to append another terminal. Diagnostic/recovery delivery across those failure
paths was exercised by the historical installed Windows receiving-collision check:
the diagnostic was retained and did not confer replay authority. This is evidence
for that tested scenario, not every possible crash or recovery path.

Installer-managed SDK helpers are shared by both host packs. The dispatch module
is registered in the source installer payload. The historical installed check
verified source and installed-file hashes together; subsequent changes must retain
their own source, installer and shared-owner regression evidence.

### Verified native evidence and subsequent changes

- October 25 installed Windows fixture: success and receiving-collision passed
  against candidate935, source-manifest SHA-256
  `bdd601615e7ef4bff2a595b5799c8e0744a544983965822e688508cb82307d5f`.
  The check verified 935 source files and 76 installed files, real hook-trust
  metadata probes, receipt/artifact/ledger agreement, retained nonreplayable
  collision diagnostics, and closure of the owned process trees and resources.
  The workers were synthetic; this fixture alone was not a model call.
- October 25 Host-led Codex review: one wrapper and one real Luna/high SDK turn
  completed in 18.343 seconds with coherent receipt/artifact/ledger readback and
  settled resources. This qualified the bounded review, not arbitrary tasks.
- October 26 outer Agents Runner to inner Codex SDK cycle: the separate
  [coordinator evidence](codex-coordination-model.md) records the live-qualified
  implementation tree `acf9a9addb0ea73b5544f8b3070d1dff9a773841`, two observed
  turns, current account/profile/hook checks and settled Windows Jobs.
- Through the October 27 custody correction, SDK modules, process supervision,
  provider-prompt and installer source are unchanged from that October 26 tree.
  Shared ledger/schema/validator changes are covered separately by the current
  delta-focused regression results; historical native results are not relabelled
  as a fresh complete-current-tree run.

The retained Windows archive has SHA-256
`b8dcc2c55fae195e438bc5f08f1bbe58a05f35fd2fd129e9374933de833d866c`;
its 20 manifest-listed payload hashes were independently checked during evidence
reconciliation. Raw operational logs and local account/configuration data are not
part of the published source. Offline fixtures alone still do not establish
native execution; the claims above rely on the separately retained native results.

### October 28 selected Windows qualification

The candidate based on upstream `8ba06110df4ed7f6a4ac76b950c803a2848b494c`,
with patch SHA-256
`0d57d2f0fa00701233f65b02f41ecb26732077775d19aa4c137e1e925f3b11a3`,
passed two separately scoped synthetic Windows runs:

- 15 tests, no skips: explicit hook-package binding, owned projection rollback
  after target removal, foreign-link replacement refusal, and the two ledger
  symlink cases. A disposable elevated tester used its own token; its existing
  symbolic-link privilege was disabled before, enabled during the tests, and
  restored to disabled afterward. Both adjustment calls and tester/launcher exits
  succeeded. This qualifies that prerequisite, not raw reparse creation with a
  disabled privilege; no persistent permission or active installation changed.
- Four selected runtime, process-owner, source-dispatch and installed-dispatch
  cases, no skips, under the ordinary account outside the command sandbox. A
  concurrent pytest cache-creation warning did not fail those cases. Earlier
  sandbox ancestor-access refusals remain distinct from this execution context.

These were synthetic workers, not model calls or evidence of native hook firing.
The actual hook callback's `tool_name` remains unverified. Later test-only fixture
corrections need their own review; these runs are not a complete-current-tree or
whole-repository pass. The earlier interrupted broad Windows run retains an
unresolved descendant-settlement observation and is not acceptance evidence.

### Bounded Codex CLI startup qualification

The explicitly opted-in `--sdk-review-binding` route selects an immutable
invocation-only profile: `features.memories=false`, `notify=[]`,
`model_provider="openai"`, `approvals_reviewer="user"`, followed by the existing
plugin, Apps, and native-delegation isolation controls. The complete ordered
selection is committed by the existing request hash and forwarded unchanged to
both the hook-trust probe and SDK worker. The low-level SDK default remains the
existing four controls. No global configuration, endpoint, or required hooks
are changed.

For this exact bounded profile, public `config/read` must explicitly report
memories false, notify an empty list, and provider/reviewer openai/user before
thread creation; missing, null, or incompatible values fail closed. This checks
raw layered configuration consistency, **not** complete effective managed state.
Before any native startup (including the hook probe), the Host must inventory
and admit the selected startup provider/endpoint, managed requirements, and
required versus unrelated hooks; incompatible requirements block qualification.
The bridge does not reset `openai_base_url` or automatically prove this gate.
Startup metadata discovery can precede config readback, and a one-turn guard
alone cannot bound background memory inference or legacy notification commands.
Normal native history/state writes remain possible.

## Boundaries

- Existing routing, role, artifact, permission, budget and ledger owners retain
  authority. A successful SDK call is external evidence, not an accepted review.
- `scripts/sdk_execution/coordinator.py` uses the official Agents SDK with an
  explicitly supplied model and existing authority owner. Tracing is disabled.
  Model/tool effects and resumed requests recheck current bindings. No second
  ledger, retry scheduler or automatic account selection is introduced.
- `scripts/sdk_execution/codex.py` uses the official Python Codex SDK and native
  structured output for a read-only review. SDK types stay inside the adapter.
- `scripts/process_supervision/sdk_worker.py` composes a fixed worker with the
  existing process owner. Protocol cancellation and OS tree settlement are
  separate observations. Neither a final answer nor SDK close proves tree cleanup.
- `scripts/sdk_execution/receiving.py` receives the paired execution/process result
  and calls the existing atomic ledger writer. Independent validated readback is
  required. No new writer or direct JSONL append is used.

## Provenance and compatibility

SDK rows use `actualExecutionPath: direct-external-sdk` and the versioned
`sdkExecution` object in the existing agent-run schema. Selected schema version 2
binds the model, effort, sandbox/permission policy, non-secret account identifier
and request digest without inventing unobserved SDK/runtime versions. The adapter
records actual version metadata separately; successful version-2 artifacts retain
it alongside the structured review. Historical schema-version-1 records retain
their original validation and matching rules. These objects contain no credentials.
The existing launch, evidence, role and artifact identities remain authoritative.
Successful receiving additionally requires the adapter's actual profile checks; a
blocked early failure retains the selected launch configuration without inventing
missing observed profile or runtime evidence.

SDK rows do not fabricate `launchFlags`. CLI rows retain their existing decoding
and validation. The provider-result v3 reader is distinct from v2 CLI records;
all SDK-derived fields participate in the existing safety-scan projection.
External results remain nonauthorizing and cannot close another run's obligations.
An older reader must reject an unsupported SDK record rather than call it CLI.

## Capability-based compatibility

Orchestrarium does not pin SDK or CLI releases or admit them by a version
allowlist. Adapters check the public API and operation capabilities they actually
use, then validate observed profile, permissions, output and cleanup contracts.
A different version alone is not a rejection reason; a missing required API or
incompatible observed behavior is. This does not promise compatibility with every
past or future provider release.

Version strings and executable digests are evidence about a particular run, not
product-wide compatibility gates. Preserve the selected executable identity and
request binding across a run; accepting different releases must not permit an
executable swap, fabricated observation, changed account or weaker permissions.
Unknown prelaunch runtime metadata must not be filled with a historical release.

The following releases were inspected as source evidence on 2026-10-23, not as
required package versions or an installation lock:

- OpenAI Agents SDK 0.24.0:
  [inspected source](https://github.com/openai/openai-agents-python/tree/17d994bd3045dae71acda676a4ef4762ed8ecd94).
- Codex Python SDK and bundled runtime 0.163.0:
  [inspected source](https://github.com/openai/codex/tree/83086188ae0614bd882818ff1aa23f3194962012/sdk/python).
- Claude Agent SDK 0.2.173 and bundled CLI 2.1.309:
  [inspected source](https://github.com/anthropics/claude-agent-sdk-python/tree/163f50ed56fa8c3fd9346148b6e56e7696794b58).

### Reviewed Codex source fixtures

On 2026-11-17, the published Python package `openai-codex` 0.169.0 was also
checked against [its official release source](https://github.com/openai/codex/tree/69231e119bfca0b14453515e97d99688ce1c47c9/sdk/python).
The Python SDK and the separately installed Codex command-line executable are
different artifacts; matching version labels alone do not establish compatibility.

`tests/fixtures/codex-sdk-sources.json` records the reviewed historical 0.163.0
and current 0.169.0 source evidence. The same adapter contract checks run for both:
generated public request/response/event models and the client method/configuration
signatures actually used by the adapter. These reviewed rows are not a minimum,
exclusive supported-version list, or runtime admission gate.

To provision the optional source-only fixtures from the repository root:

```console
python scripts/maintenance/fetch-codex-source-fixtures.py
python -m pytest -q tests/test_sdk_codex.py tests/test_fetch_codex_source_fixtures.py
```

The acquisition helper verifies the official wheel SHA-256 and each selected Git
blob hash, then retains only the upstream `client.py` and `generated/v2_all.py`, flattened as
`client.py` and `v2_all.py`, under ignored
`.scratch/sdk-api-fixture/<version>/`. It neither installs the SDK nor launches a
client/model. Existing different fixture bytes are preserved and reported, never
silently overwritten. Use `--version` to select one or more reviewed rows.
Missing optional fixtures remain explicit test skips, not runtime unavailability.
Updating reviewed evidence requires a reviewed manifest change and the same
behavioral checks; no test downloads or admits a moving latest release implicitly.

The 2026-11-17 offline checks used one isolated CPython 3.15.2 environment with
pytest 9.2.0, pydantic 2.14.3 and matching pydantic-core 2.50.4. Those versions
identify the check environment, not additional product requirements. They avoid
mixing compiled extensions from a different Python interpreter.

A provider package can constrain its own bundled dependencies; that upstream
packaging detail is not an Orchestrarium runtime-version requirement. A reviewed
source revision or reproducible test environment records evidence, not an
exclusive set of admitted versions. This compatibility contract supersedes the
SDK project draft's requirement to pin tested SDK/CLI combinations.

Provisioning and complete native qualification remain separate from API checks.
This branch performs no implicit package install, upgrade, downgrade,
authentication, credential copying or provider activation. For the explicitly
selected Codex review baseline described here, the execution route uses the
existing Codex login; a separate API account/billing lane is not a prerequisite
for that route and must not be silently introduced. This is not an access
guarantee for every provider in the approved multivendor roadmap. Claude, AGY
and other API/cloud routes follow their own role/access matrix and applicable
vendor terms, without an implicit billing or authentication fallback. Any
optional outer Agents Model used with this Codex subscription baseline needs an
explicitly supported subscription-compatible binding before use; no OAuth token
extraction or private API bridge is implied by its injectable Model interface.

## Typed observations and applicable semantic checks

The bounded dispatched SDK review consumes native item/call identities and actual
terminal command state instead of synthesizing a host transcript. Codex rejects
`item/completed` command data that is missing a recognized terminal status, even
if the event envelope or later turn claims completion. A completed command still
requires an observed integer exit code. A failed, declined or nonzero command is
retained as evidence, not automatically converted into failure of the final review.
The same checks apply to full-history reconciliation.
A live terminal that declares `itemsView=full` must also include every captured
completed item; `summary` and `notLoaded` retain their explicitly partial semantics.
A failed history reconciliation does not automatically interrupt a prior turn
that this lookup did not start. Explicit caller cancellation remains the separate
bound cancellation operation; client closure and owned process settlement remain
required on every path.

The main-conversation passive-polling Stop guard explicitly excludes dispatched
reviews/subagents, so this selected SDK lane must not fabricate input to that hook.
Publication-scan correlation remains with the existing publication owner; SDK
review evidence cannot replace its receipts. Existing receiving independently
checks request/profile identities, structured results, actual process outcomes and
settlement. This scenario mapping supersedes the earlier overly broad inference
that absent direct hook imports necessarily required a new SDK-to-hook bridge.

## Caller-owned conversation history

`AgentsCoordinator` and `create_review_coordinator` accept an optional public SDK
`session`. The selected object is passed unchanged to `Runner.run` for both new
runs and authenticated RunState resume. Without it, the existing no-session call
shape stays unchanged. Required public Session methods and Runner support are
checked before consuming a resume snapshot; a changed session ID is rejected.
No Session backend, history writer or cleanup owner is created by this module.
The caller and current authority owner must bind the ID **and backend** to the
admitted conversation/account and snapshot. A stable ID alone does not attest
backend identity. After restart, the caller supplies the same admitted Session
ID/backend; offline composition tests do not prove actual SDK persistence or
combined crash recovery.

## Per-run controls are not native-role customizations

`CodexRuntimeSelection.config_overrides` defaults to the four invocation-scoped
controls in `CODEX_MCP_ISOLATION_OVERRIDES`: `features.plugins=false`,
`features.apps=false`, `agents.enabled=false`, and `features.multi_agent_v2=false`.
They are passed to the public Codex configuration for that invocation. The
admitted review route retains these required controls; a lower-level explicit
configuration remains subject to its own caller and runtime checks.

Per-run settings must not rewrite native-role TOMLs, global configuration or the
stock role manifest. Native-role defaults and compatible user tuning remain owned
by the role contract, independently of the SDK invocation controls. SDK execution
must not bless modified hashes or bypass that owner. Regression coverage preserves
real temporary config/role/manifest bytes and both accepted and drift-denied
routing outcomes through runtime composition; it does not claim the external
runtime can never write its own state.

## Historical adapter-only acceptance scope, 2026-10-24

This dated acceptance explains the evidence below; it does not complete or narrow
the approved PR19 completion roadmap. Codex was the end-to-end priority with
existing orchestrator owners. Claude, Kimi, Grok, MiniMax and MiMo were limited to
adapters and offline protocol checks for that historical slice. Missing live
qualification cannot be worked around by buying API access or changing
authentication without the applicable authorization.
Do not describe offline support as live-qualified support. Existing closed live
gates remain closed until later authorization. This scope does not waive
capability, account, tool-policy, receiving or process-settlement checks for
Codex or any subsequently activated route.

Before PR integration, identify each existing orchestrator owner and caller that
the SDK retains or supersedes. Verify the dispatch transition and rollback;
passing an isolated SDK suite is not proof that the installed orchestrator uses
the intended single execution path.

## Dormant Grok ACP slice

`scripts/sdk_execution/grok.py` implements source-backed ACP protocol exchange and
a composition over the existing `ProcessRunnerV1`. It negotiates capabilities,
uses explicit authentication selection, sets model before reasoning effort with
observed configuration readback, denies permission requests, correlates messages,
and retains cancellation/terminal/close evidence. Configuration transitions and
flat/grouped selectors are distinguished; malformed terminal data preserves
already acquired output. Cleanup obeys the selected byte/event budgets.

The narrow `grok-acp-one-shot-v1` dialogue uses the existing native-parser contract,
exact executable binding and owned Windows lifecycle; it is not a second launcher
or supervisor and does not bypass the POSIX hold. Its selected command is
`<exe> --no-auto-update agent --no-leader --model <selected-id> stdio`; the command
shape is a protocol/profile contract, not a claim of installed-runtime qualification.
There is no release allowlist or inferred account identity.

**Live admission remains unconditionally held before process creation.** Empty ACP
client capabilities, a deny callback and `mcpServers: []` do not establish that
Grok's internal tools obey this read-only executor contract. Authentication also
can have external effects. No caller callback can remove the fixed unsupported
live boundary. Offline composition fixtures explicitly replace that boundary to
exercise borrowed channels and typed process receipts; an unpatched test proves
zero launches. This is source/offline evidence, not a real Grok run.

Durable Grok receiving, actual account selection/readback, internal-tool policy
and native compatibility remain unqualified. A clean protocol or process fixture
therefore does not become a fully received native terminal like the existing
Kimi owner. The adapter preserves the exact acquired process result even if
result scanning/reduction fails. Existing role/provider routing stays unavailable.

Official sources: [Grok agent mode](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/15-agent-mode.md),
[session configuration implementation](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-shell/src/agent/session_config.rs),
[ACP session configuration](https://agentclientprotocol.com/protocol/v1/session-config-options).
The Grok guide's nested config-value example conflicts with the declared ACP
schema; scalar `value` follows the actual public schema, without fallback retry.

## MiniMax Code ACP addition

MiniMax Code (`mcode`, published as `@minimax-ai/code`) is the coding agent,
not the separate `mmx-cli` platform client. Its public `mcode acp` entry point
is the selected integration target. The SDK request provider identity is
`minimax`; this does not activate installed routing or alias a Codex/Claude
runtime selection.

The optional adapter uses the official Python `agent-client-protocol` public
connection API (`acp`) behind an explicitly borrowed client boundary. It does
not introduce a second JSON-RPC implementation, subprocess supervisor, credential
store, model API client or ledger. Dependencies are not installed automatically.
No particular MiniMax or ACP release is a product compatibility requirement.

**The production acquisition path remains held before constructing a client.**
Official source omits an empty `mcpServers` list when creating the runtime session;
therefore `mcpServers=[]` does not prove that inherited tools are excluded.
The `permissionMode` configuration option changes runtime-level permissions and
broadcasts to attached sessions; the adapter must not use it as a per-run override.
Model option values must be selected from the advertised catalog and checked
after selection. Effort uses `thinkingEffort`, not Grok's `reasoning_effort`.

The supported native Node/entry-script launch binding, inherited tool isolation,
subscription/account readback, owned pipe lifetime and durable receiving still
require qualification. Windows `mcode.cmd` / `mcode.ps1` wrappers are not silently
admitted as native executables. Protocol fixtures are not a real provider run;
no global profiles, auth state or default routes are changed by this addition.

Official source evidence (not a pinned required release):
[MiniMax ACP implementation](https://github.com/MiniMax-AI/minimax-code/blob/da22f11c55d4748155d7162c1030414228a00565/packages/tui/src/acp/agent.ts),
[MiniMax config controls](https://github.com/MiniMax-AI/minimax-code/blob/da22f11c55d4748155d7162c1030414228a00565/packages/tui/src/acp/control-state.ts),
[official ACP Python SDK](https://github.com/agentclientprotocol/python-sdk).

## MiMoCode ACP addition

MiMoCode (`mimo`, published as `@mimo-ai/cli`) has both an ACP entry point
and a native local HTTP interface. The admitted first route is ACP through the
public Python `acp.core.Connection` and `acp.client.router.build_client_router`
interfaces. This avoids a TypeScript compiler or additional JavaScript worker.
The official library retains framing, request IDs and response correlation;
Orchestrarium retains provider policy, bounded capture and process ownership.
The explicit request identity `mimo` does not activate runtime selection.

Model selection uses public `send_request("session/set_model", ...)`, not
`ext_method` (which prefixes an underscore). Validate the separate model ID,
variant and advertised variants returned in `_meta.opencode`; a model name
ending in `/low` is not evidence that the low variant was selected. Observe and
drain received notifications before freezing a terminal result, including
notifications whose handler has not started yet. Callback failures must remain
visible even when the transport logs rather than propagates them.

**Live acquisition remains closed.** An empty ACP MCP list does not remove
inherited runtime servers. Effective tool permissions, subscription/account
binding, native executable and private HTTP shim ownership, process settlement
and durable receiving are not qualified by protocol fixtures. No installation,
login, credentials, profile change or model request is implied by this addition.
MiMo's `end_turn` is not a cancellation receipt; the inspected implementation
has no `session/close` operation. Do not substitute history deletion for cleanup.

The native local HTTP API remains an alternative for per-session permission
readback, durable queue receipts and richer history. It is not a direct billed
model API, but neither interface proves subscription coverage. Its official SDK
ships compiled JavaScript; using that client would add a JavaScript runtime,
not necessarily a TypeScript build. A Python HTTP client would be our maintained
binding rather than an official MiMo Python SDK.

Official source evidence (provenance, not required version pins):
[MiMo ACP agent](https://github.com/XiaomiMiMo/MiMo-Code/blob/e37f2c2d01460df19b31d67b8116d6c66fe33db8/packages/cli/src/acp/agent.ts),
[public ACP Connection](https://github.com/agentclientprotocol/python-sdk/blob/2ad204bb86111da9594bfe13f4a560249603feea/src/acp/connection.py),
[public client router](https://github.com/agentclientprotocol/python-sdk/blob/2ad204bb86111da9594bfe13f4a560249603feea/src/acp/client/router.py).

## Owned ACP byte streams

The public ACP SDK owns JSON serialization, newline framing and request
correlation. A byte-stream facade over the existing ProcessRunner dialogue
channel must not open another stdout reader, acquire descriptors or introduce
another subprocess owner. Connection shutdown and OS process settlement are
separate obligations.

Cancelling an asyncio await does not stop a blocking executor read. The process
owner closes child stdin only after the dialogue callback returns; waiting for
executor shutdown before releasing that read can therefore form a shutdown
cycle. The owner-local read-stop operation wakes the dialogue reader without
claiming provider EOF, closing stdin or settling the process. The facade drains
its retained I/O work before leaving the event loop. Existing pipe closure,
deadlines, capture and Windows Job settlement remain with ProcessRunner.

Close the official ACP Connection before closing the borrowed stream facade.
ACP sender shutdown does not itself close the supplied writer. A stalled write
remains subject to the process owner's deadline and cleanup result; it must not
be reported as graceful protocol completion. Local read-stop must remain
identifiable separately from peer EOF and capture/transport failure.

This capability does not admit a MiMo executable or activate a provider route.
MiMo needs its own exact argv profile and startup/configuration qualification;
it must not be disguised as the Grok, Kimi or SDK-worker profile.

## Selective MCP access: provider support versus this implementation

A per-run tool subset must not be implemented by modifying stock native-role
TOMLs or by treating `plugins=false` / `apps=false` as a selective allowlist.
The upstream mechanisms are different:

- OpenAI Agents SDK exposes only the MCP servers supplied to an Agent and supports
  server tool filters. This controls the functions exposed through that agent
  loop, not independent direct access to the server.
- Codex App Server accepts per-thread configuration and MCP server enablement plus
  `enabled_tools` / `disabled_tools`. An override is not automatically an exclusive
  replacement of every inherited server; plugin MCP and app connectors have
  separate configuration surfaces. The selected effective set must be established.
- Claude Agent SDK supports explicit `mcp_servers` with `strict_mcp_config` and
  per-subagent `tools`, `mcpServers` and `disallowedTools`. Its `allowed_tools`
  setting is auto-approval, not by itself a closed tool allowlist.
- ACP `session/new.mcpServers` supplies connections but does not establish exclusion
  of ambient configuration or provider-specific per-tool enforcement.

These are upstream capabilities, not a claim that Orchestrarium currently has a
qualified common selective-MCP path. The current Claude adapter explicitly has an
empty strict MCP set and verifies that fact; Codex carries selected per-invocation
configuration with an implemented thread-inventory validation gate whose current
live qualification remains open. Optional-null inventory fields follow the public
SDK schema; explicit null does not independently prove catalog completeness.
An extension must reuse current admission and adapter boundaries, preserve the selected subset on
resume, and exclude unexpected inherited tools without copying secrets into the
request. Filesystem read-only sandboxing does not constrain remote mutations made
through an MCP tool. No MCP server is activated by documenting this design.

Official references: [Agents MCP filtering](https://openai.github.io/openai-agents-python/mcp/#tool-filtering),
[Codex MCP configuration](https://developers.openai.com/codex/mcp/),
[Claude Python SDK](https://code.claude.com/docs/en/agent-sdk/python),
[Claude permissions](https://code.claude.com/docs/en/agent-sdk/permissions),
[ACP session setup](https://agentclientprotocol.com/protocol/session-setup).

## Limits beyond the bounded native qualification

1. The inspected Codex release uses an unbounded internal stdout line reader and
   line-count-bounded stderr storage. That release's public configuration does not expose a
   byte-bounded transport. The selected integration separates bounded public SDK
   evidence retention from a creator-applied Windows Job committed-memory budget
   and the existing hard deadline/settlement. The memory cap addresses uncontrolled
   decoder/buffer allocation without a private SDK fork; it is not a raw-output
   byte limit or complete capture of unavailable internal diagnostics. Allocation
   failure or missing required public evidence never counts as success. The bounded
   Windows runs established native ownership and settlement; they are not exhaustive
   memory-pressure or failure-path qualification. Another platform or materially
   changed containment path requires its own qualification.
2. Existing Windows atomic Job ownership is reused. The native runs above verify
   their owned descendant cleanup; source/unit evidence alone would not. Generic
   POSIX execution remains unavailable; process groups do not prove containment
   of escaping descendants. No generic private-directory hold is bypassed.
3. The caller must retain the actual Host/account/budget admission owner. Only
   the separate optional coordinator route additionally requires a coordinator
   model binding; only resume requires authenticated atomic snapshot ownership.
   Injected test owners do not establish real authority, account isolation or
   durable replay safety. These are existing host responsibilities, not a new
   policy, credential or session store in the SDK integration.
4. Claude has a direct SDK adapter and Kimi reuses its existing complete ACP owner
   through the same execution interface. Kimi results remain native CLI evidence,
   not fabricated structured SDK reviews; its existing owner receives them once.
   Claude selection currently requires a concrete model ID: existing short-alias
   parity is not established and no guessed alias mapping is used. Grok remains
   unavailable under the existing execution policy.

## Transport update compatibility

The combined installed transport contains the SDK helpers and the model-launch
policy companion. Normal validation requires the full ordered 30-member set.
Only predecessor acquisition accepts the exact historical 8-member transport,
the policy-enabled 9-member transport or the pre-policy 29-member SDK transport.
Their receipts, member hashes and both selected homes remain mandatory; partial
or reordered manifests are not compatibility modes. Newly introduced leaves
must be absent, and drift refuses before overwrite. Current strong tree
identities and qualified legacy receipt migration retain the installer owner.

## Explicit runtime composition

`runtime.run_codex` is the parent callable, not an automatic install action. It
requires an explicit runtime executable/digest, Codex home/auth mode/account
selection, finite process/ledger budgets, deadline, cancellation probe and current
policy owner. It frames the task with the existing governance owner, claims one
launch atomically, checks native hook trust and creates the fixed SDK worker.
The creator reads back its retained outer Windows Job limits before process
creation and verifies direct-process membership before resuming it. Nested Python
venv Jobs do not replace this ancestor boundary; workers do not mistake an inner
Job for the owner. All Job handles remain parent-owned and non-inherited. API-key account readback identifies its mode, not a unique account;
exact key selection stays with the existing auth/environment owner.

`run_admitted_review` accepts the exact already-admitted Codex or Claude request.
Codex governance framing happens before admission; Claude retains its native
preset and receives common/Claude instructions through the existing owned file
transport. Provider-specific SDK factories remain behind the fixed worker boundary.
Kimi continues through its existing complete CLI/ACP owner, not this SDK receiver.

`create_review_coordinator` returns the Agents coordinator and its concrete
`SdkReviewExecutor`. The executor joins the owned runtime to scanned artifact
materialization, atomic ledger receiving and independent readback before returning
tool evidence. It preflights known artifact-path conflicts without reserving a new
store; final exclusive creation remains authoritative. The caller retains the
executor for cancellation and acquired evidence, including receiving failures.

The returned `RuntimeRun` retains the effective request, admitted selection,
output-scan context and sealed worker observation. Receiving uses these exact
objects and the existing receipt owner, closes its exclusive writer before
independent reading, then calls the existing atomic writer and validated reader.
`requestSha256` commits the explicit request/runtime selection, not every native
config file that Codex may load. Codex selection can carry an immutable sequence
of nonsecret public SDK `config_overrides`; the same exact overrides reach the
owned hook-trust probe and worker, and participate in that commitment. Empty
MCP scope selects no MCP tools; startup isolation controls are fixed before
admission, and explicit override tuples must already include those controls.
Overrides are caller-selected data, not permission or proof of the complete effective configuration; the existing owner
must admit them and account for managed requirements and inherited integrations.
Do not put credentials in command-line overrides. An unresolved prior launch is
never replayed.

A bounded single-model live test must separately establish which native agents,
MCP servers, apps and plugins can start or be called under its actual profile.
An empty MCP table is not an isolation guarantee, and model approval denial is not
a universal external-tool switch. Preserve the required owned hooks and current
account/permission controls; do not edit the user's global profile to make a test
pass. Normal authorized account/model metadata requests are distinct from model
turns. No such live-profile qualification is implied by the offline suites.

The worker's native nonblocking-pipe bridge requires Python 3.12 or later on
Windows. Normal host-pack installation does not provision this optional environment
or start it. Offline fixtures use synthetic adapters/process observations; those
cannot grant activation or prove native platform behavior.

## Before and after: what can be measured

| Aspect | Existing route | Optional SDK route | Required evidence |
|---|---|---|---|
| Review format | Final-line `GATE` parsing after CLI output | Native structured review and independent shape/identity checks | Malformed, missing, extra and contradictory result fixtures |
| Profile identity | Actual argv-derived model/effort | Actual SDK config and observed profile | Drift, swapped run and account fixtures |
| Receiving | Existing atomic ledger and independent reader | Same owners with explicit SDK representation | Launch-to-terminal round trip, conflict and replay tests |
| Coordination | Host-led workflow | Explicit review bridge keeps the same Host; a separate optional SDK coordinator is not started by it | Offline current-authority/resume tests; separate native qualification |
| Processes | Existing platform-specific supervisor | Same owner enclosing SDK worker | Cancellation, failure, descendant and crash tests per platform |

The existing common wrapper is already present; one common call is not a new
benefit. Legacy parsers/hooks stay while their host routes use them. No reduced
hook count, model-quality improvement, throughput gain or live reliability claim
follows from adding SDK dependencies. This branch removes no legacy execution
route or hook: their host-mode consumers remain supported. The new SDK review
route avoids a new final-line verdict parser and prose-to-structure model call;
Agents SDK supplies its model/tool iteration and paused-call representation rather
than a new custom loop or session store. These are avoided additions, not deletions
or measured maintenance savings. Offline fixture parity is not a live benchmark.

## Terms and Abbreviations

- Host: the existing invoking orchestration session; it retains launch authority.
- Binding: a bounded per-invocation constraint document, not authorization.
- V3: version-three provider-result envelope; selected SDK metadata has its own schema version.
- MCP: Model Context Protocol, used by connected external tool servers.
- SDK: software development kit; maintained provider or coordination library.
- CLI / API: command-line / application programming interface.
- JSON: JavaScript Object Notation, the strict binding and envelope serialization.
- UTF-8: Unicode text encoding.
- V2: version-two legacy CLI provider-result envelope.
- OS: operating system.
- ACP: Agent Client Protocol, used only inside applicable provider adapters.
- Job: Windows operating-system ownership boundary for a process tree.
- Provenance: recorded actual execution identity/configuration, not permission.
