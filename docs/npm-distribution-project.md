# Orche distribution: bundled Python and thin delivery channels

Status: delivery design aligned with the SDK implementation in
[PR19](https://github.com/applicate2628/Orchestrarium/pull/19).
This PR does not publish an npm package, an internet bootstrap, a signed release,
or a supported-platform declaration.

## One operation owner, staged implementation

First integrate the SDK and the existing Python installer with a qualified,
minimal bundled CPython runtime and its required dependencies. Rust migration in
[PR21](https://github.com/applicate2628/Orchestrarium/pull/21) comes afterward.
Rust is not a prerequisite for this delivery release.

The canonical Python installer owns selection, installation, updates, receipts,
hook registration, preservation, rollback and uninstall. npm, PowerShell and POSIX
shell are thin acquisition/dispatch channels. They must not reproduce these
decisions or invent another policy, inventory, ledger or recovery owner.
A later Rust cutover replaces a qualified operation atomically; it does not create
simultaneous Python/Rust writers or an automatic fallback between implementations.

The product name is **Orche**. The planned public command is `orche`; registry
package names, publisher ownership and any compatibility alias require release-time
verification. Do not invent a semantic version. Preserve the actual pre-SDK main
boundary with a verified tag before integration, then select the next release from
the repository's established version history.

## Common payload and launch contract

Every channel delivers the same versioned, platform-specific release:
- The minimal qualified CPython runtime. Current SDK/delivery qualification uses
  normal-GIL CPython 3.15.2; freeze interpreter source, version and digest per target.
- The common installer, selected-client resources, schemas, validators and other
  dynamically loaded files required by that release.
- The exact dependency closure for the admitted SDK routes, with hashes, licenses
  and provenance. A provider's native CLI remains present when its SDK requires it.
  Optional future adapters must not silently make every installation larger.
- A bundle-relative manifest and thin entrypoint. Resolve executable and resource
  paths relative to the installed bundle, never to a developer machine, current
  working directory, ambient PATH or a system Python installation.

The prototype owner in PR19 is `scripts/distribution/build.py` for assembly and
`scripts/distribution/launch.py` for bundle-relative launch and retention.
The client-selection entry delegates to the existing installer. These references
describe the integration target, not files already landed on this PR's older base.

Internal payload paths are relative. Where a host hook schema requires absolute
paths, derive them from the admitted retained installation at registration time;
never ship workstation paths. Qualify quoting, Unicode, spaces and exact argument
boundaries independently on each supported host.

Selected clients receive independent ordinary copies of their owned payload.
Do not recreate shared skill links, junctions or peer-owned copies. Legacy link
conversion is explicit, selected-client-only and preserves the referent.
Updating or removing one client must not mutate the unselected peer.

## Selected-host integration acceptance

Accepted product requirements, reconciled 2026-11-14; these are qualification
criteria, not claims of implemented adapters or provider permission. Finish the
independent current-version repairs before the SDK/Rust transition. Common-rule
restructuring and new machine-enforcement mechanisms remain post-transition work
at their existing owners; they do not block independent installer repairs.

The common installer owns delivery of instructions, skills, native role definitions
and supported hooks. Host adapters translate the selected host's actual surfaces;
SDK execution remains owned by [PR18](https://github.com/applicate2628/Orchestrarium/pull/18)
and [PR19](https://github.com/applicate2628/Orchestrarium/pull/19). Do not infer an
external-worker route from installation of a host pack.

| Selected host | Requested role coverage | Receiving evidence |
| --- | --- | --- |
| Antigravity (AGY) | Native session as Lead, including its own native subagents as executors. | Discover the installed version and supported global/project surfaces; verify instruction/skill/role loading, supported hook events, and native delegation/result receiving independently. |
| Claude | Native session as Lead with its own native subagents; retain existing admitted roles. | Preserve the selected-client lifecycle and test native role loading/delegation separately from file receipt success. |
| Visual Studio Code Local harness | Any Orchestrarium role, including Lead and native delegated executor. | Qualify direct role selection and a separate delegated task/result using the available `runSubagent` contract; verify instruction loading and supported hooks in each admitted user/project scope. |
| Visual Studio Code Copilot harness | Any Orchestrarium role, including Lead and native delegated executor. | Qualify direct role selection and a separate delegated task/result using the available `task` contract; do not reuse Local tool arguments or acceptance evidence. |
| GitHub Copilot CLI | Any Orchestrarium role, including a directly selected custom Lead and delegated custom executor. | Qualify direct selection (`/agent` or `--agent`) separately from delegation, including repository-instruction loading in both contexts and result receipt by the Lead. |

Role eligibility and access method are separate dimensions. Native delegation is
not a third-party subscription wrapper. Programmatic invocation requires its own
verified provider-supported access method, account/billing binding and current
user permission. Retain the user's hold on subscription-backed external Gemini
and Claude workers; this is a project instruction, not a legal conclusion about
all CLI use. Copilot's role coverage does not prove that a particular BYOK model,
CLI/API route or billing lane is available. Never silently substitute a subscription
or different account for the selected API route.

Copilot qualification follows the official [VS Code subagent contracts](https://code.visualstudio.com/docs/agents/run/subagents),
[customization migration guidance](https://code.visualstudio.com/docs/agent-customization/migrate-customizations)
and [CLI custom-agent instruction behavior](https://docs.github.com/en/enterprise-cloud@latest/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli),
checked 2026-11-14. These describe provider behavior; the acceptance matrix above
is the Orchestrarium delivery requirement, not observed runtime acceptance.

For CLI custom executors that must follow repository conventions, emit
`include-custom-instructions: true` in their agent frontmatter: delegated custom
agents do not load repository instructions by default, unlike directly selected
custom agents. Verify the effective configuration, including instruction-disabling
options, rather than treating the emitted field as proof. Test personal/project
agent-ID collisions and selection after restart; IDs, not display names alone,
determine duplicate resolution. Preserve user-owned agents.

The [CLI command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference#repository-custom-instructions-for-subagents)
adds these qualification boundaries (checked 2026-11-14):

| CLI case | Documented boundary to verify on the selected version |
|---|---|
| Custom delegated agent with instruction opt-in | Repository instruction files are included; extra directories supplied only to the parent through `COPILOT_CUSTOM_INSTRUCTIONS_DIRS` are not inherited. |
| Session started with `--no-custom-instructions` | Repository instructions are excluded even when the delegated agent opts in. |
| Built-in delegated agents | `general-purpose` receives repository instructions; `explore`, `task`, and `code-review` do not. The built-in agent named `task` is distinct from the delegation tool with that name. |

Record instruction source separately from agent type in the acceptance evidence.
Do not infer installed-version support from current documentation. A discovery
listing is not evidence of effective instruction loading in a delegated run;
keep the native acceptance result unverified until that context is observed.

Record host version, selected harness, user/project scope, selected agent ID,
role-pack identity, observed instruction loading and delegated result receipt for
each applicable cell. Test reinstallation and duplicate active customizations.
For Local-to-Copilot migration, validate discovery and hook event timing, inputs,
outputs, approvals and failure paths; automatic hook conversion is unavailable.
Do not activate both old and converted hooks or assume editor search-location
settings apply to another client. A file loading is not proof its hook works.

Keep offline installer tests, installed host discovery/hook checks, native-session
acceptance and any authorized model run as distinct evidence. Unsupported or
unverified cells remain explicit, without holding unrelated admitted work.

**Layout decision still to qualify:** the independent-copy delivery target above
does not authorize rewriting existing shared or linked installations. The AGY
integration proposal also expects Codex and AGY to discover a common skill
surface; verify the actual host discovery contract before choosing physical layout.
If both consume the same physical target, one existing installer owner must retain
shared custody and preserve every consumer. If supported host configuration permits
independent targets, qualify isolated copies and their discovery instead. Neither
option is selected by this acceptance update. Existing selected Claude linked-root
updates in [PR25](https://github.com/applicate2628/Orchestrarium/pull/25) cover
agents/commands, not skill migration or whole-pack uninstall. Preserve that bounded
compatibility behavior; hold only a migration that depends on the unresolved layout.

## Acquisition and authenticity

All channels must:
1. Resolve an explicitly selected release and supported target from the official
   release origin. Unknown targets fail before changing installed state.
2. Authenticate the release manifest and verify every payload digest before
   executing its interpreter or entrypoint. A checksum beside an untrusted payload
   is not independent publisher authentication. Signing trust, key rotation and
   publisher ownership remain release gates; this plan provisions no keys.
3. Bound download size, extraction size/count and time. Reject traversal, absolute
   archive members, conflicting entries and escaping links/reparse points.
   Do not treat local quiescent-tree checks as a hostile-archive extractor.
4. Use exclusively owned staging, preserve the last working release on failure,
   and never execute a partial or mixed-version payload.
5. Forward exact arguments and exit status to the same operation owner.
   No automatic elevation, execution-policy changes, certificate bypass or
   provider activation is permitted.

PowerShell serves Windows; a thin POSIX entry serves Linux and macOS. The requested
`irm` convenience is an acquisition surface, not a trust mechanism. Instructions
must not require blindly executing unverified downloaded code.

## npm channel

npm distributes the same target-qualified bundle through a thin JavaScript
dispatcher and exact-version platform payload packages. Platform selection may
use optional dependencies, but absence of the selected platform must fail clearly.
No postinstall model calls, downloads, compilation, Python setup, login, hook
registration or project mutation.

Python and SDK dependencies are delivered in the qualified payload, not installed
from the network on the user's first run. A user need not install system Python.
Do not silently omit native CLI dependencies to advertise a smaller package.

Use the common installer's current selection and lifecycle semantics rather than
introducing a second npm-only command language. The eventual entrypoint maps to
the same selected-client, global/target, preview, migration and uninstall options.
The exact public syntax must be checked against that release's actual help.

npm update changes the distribution, not applied packs. Applying an update is an
explicit operation. npm uninstall removes the npm distribution only and must not
break already applied hooks or executors. Managed-pack uninstall is a separate,
ownership-checked operation implemented by the common installer.

## Applied runtime lifetime and uninstall

Retain an admitted release outside mutable npm caches, temporary downloads and
`node_modules` before registering consumers. The existing installer/lifetime owner
records the selected release and content identity. Do not register against PATH,
mutable latest links or a disposable acquisition directory.

Selected-client uninstall deactivates owned registrations, removes exact unchanged
owned payload and configuration portions, and preserves user additions, modified
content and other clients. Unknown or inconsistent ownership is preserved and
reported, not treated as empty. Verify rollback and repeated uninstall.

Applied runtime cleanup is distinct from removing client payload. Retain a runtime
while any verified consumer may reference it; unknown references preserve it.
Initial delivery retains old runtimes. Automatic last-consumer garbage collection
is not implemented or promised. Any later cleanup must use existing ownership and
registration evidence, not guessed reference counts or a new daemon.

## Qualification and release gates

- Windows and Linux: test actual assembled bundles without a checkout, including
  relocation, unavailable system Python/PATH, dependency imports, selected install,
  reapply/update, migration, hook registration/health, rollback and uninstall.
- Check unselected peer bytes, user-file preservation, interrupted acquisition,
  mixed versions, missing dependencies, invalid targets and failed verification.
- Compare npm, PowerShell and POSIX delivery by payload identity, arguments, exit
  status and installed effects, not only matching command names.
- macOS: documentation/static review only until a real macOS runner is available.
  Never report Windows/Linux results as macOS execution evidence.
- Architecture and operating-system tuples are qualification candidates, not a
  claim that every archive exists. State the Linux libc floor from the complete
  wheel/runtime closure; Alpine/musl requires separate evidence.
- Complete license inventory and measured minimization before release. Preserve
  required parsers/validators and runtime resources rather than weakening checks.
- Installer qualification does not authorize model/API calls, activate SDK routes,
  verify billing or establish complete provider lifecycle support.

The local assembly and lifecycle results recorded in PR19 are scoped evidence.
Authenticated remote release delivery, channel packaging, final versions and
publisher/name ownership remain open until independently verified.
No package publication, model launch or GitHub Actions dispatch follows from this
design. Preserve the earlier manual-trust documentation/tests in this PR.

## Terms and Abbreviations

- AGY: Antigravity, here treated as a native session host.
- BYOK: bring your own key, distinct from subscription access.
- API: application programming interface.
- Lead: the session's orchestration role, distinct from its access method.

- SDK: software development kit used behind the common execution contract.
- CLI: command-line interface; some SDKs still depend on a provider CLI.
- npm: optional package distribution channel, not an installer-policy owner.
- Bootstrap: bounded acquisition, verification and dispatch entrypoint.
- Retained runtime: applied interpreter/resources kept independently of caches.
- CPython: the Python implementation bundled with this release.
