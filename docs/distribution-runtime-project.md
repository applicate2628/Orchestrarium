# Distribution and native runtime project

Status: standalone npm/native design project extracted from the 2.0 roadmap.
SDK integration now has its own [PR #18](https://github.com/applicate2628/Orchestrarium/pull/18),
extracted from this project's `b67b150f197aa53fcf7a088aa67eecaec80e0cf6` revision.
This PR retains native operations, common-hook replacement, npm delivery and the
narrow manual-trust documentation/test repair. No new runtime is implemented.

## Purpose, source baseline and scope

Distribute versioned rules/resources and native deterministic operations with a thin
npm launcher, while preserving current installation, state and receiving contracts.
Current-source baseline is [main 84eefb6b](https://github.com/applicate2628/Orchestrarium/commit/84eefb6bbeec9ebbe032f00788f249ae59da05b5).
Source observations are not verified installed behavior. Future component versions,
builds and supported targets require implementation qualification.

[PR #18](https://github.com/applicate2628/Orchestrarium/pull/18) owns the SDK-1…4 backlog,
common provider execution boundary, ACP/adapters, coordinator sessions/events,
SDK provenance and its Python dependency contract. SDK work starts first but does
not require this PR or a Rust port. This project consumes those declared boundaries
without copying the SDK design. [PR #13](https://github.com/applicate2628/Orchestrarium/pull/13)
retains ranking/evaluation, expanded native-role lifecycle, cross-host continuation
and optional policy preferences. No blanket merge dependency joins these projects.

Product Manager owns package scope; Toolchain/Platform Engineer owns delivery;
Architect and existing installer/hook/process/state owners accept implementation
boundaries. [Shared governance](../shared/AGENTS.shared.md),
[Lead](../src.codex/skills/lead/SKILL.md),
[role policy](../shared/role-routing-policy.v1.json),
[external dispatch](../src.codex/skills/lead/external-dispatch.md),
[installer](../scripts/production_installer.py) and
[publication safety](../shared/references/repository-publication-safety.md) remain
canonical. Reuse one owner per operation/state/process, immutable inputs, verified
readback, preserved recovery obligations and reconciliation of uncertain effects.
Do not create another governance framework, universal transaction manager or daemon.

The [installation contract](../INSTALL.md) and [runtime overview](../README.md)
still describe live Python-owned behavior. Their Rust-to-2.0 deferral is superseded
for project sequencing, not runtime activation. The Windows descriptor correction
[2e91ebee](https://github.com/applicate2628/Orchestrarium/commit/2e91ebeeb4cd693c13cea714f995cc3389972268)
already belongs to its source owner, not new Rust scope. Preserve publication
frontier [54c11111](https://github.com/applicate2628/Orchestrarium/commit/54c11111a4fe1eb1073d2a259165edeca8a519ef)
and decision custody [3a542fc5](https://github.com/applicate2628/Orchestrarium/commit/3a542fc5827d3b80c3203bf94943e900a95a4ba2).
This project changes documentation and narrow documentation tests, not production
scripts, schemas, installed state, provider admission or permissions. No provider
launch, payment, package publication or installation follows from this design.

## Existing behavior and target architecture

Current host-led coordination remains a supported mode until an admitted replacement
qualifies. External `auto` remains limited to current admitted Codex/Claude profiles;
Kimi remains explicit-only through fixed `kimi-code/k3`, for policy-admitted read
work or scoped engineering mapped to the existing external worker. External results
remain independently verified and nonauthorizing. Grok remains classifier-only with
execution unavailable; listing its upstream adapter is not launch/probe permission.

The [process runner](../scripts/process_supervision/process_runner.py) already defines request/result,
cancellation, settlement and Windows native parsing contracts. The generic Windows
CLI is blocked at its private request-directory boundary; generic POSIX execution
is unavailable. Specialized POSIX supervision and native-host dispatch are not proof
that either generic entrypoint works. A source-only store/activation registry is
also not evidence of a live durable execution service.

The native entry dispatcher exposes deterministic operation commands. Optional
coordination uses PR18's separately owned interface; it can consume current Python
operations before their native replacement and does not require Rust to start.
The native component uses one Cargo package (Rust build/package unit) and one CLI
per supported target, not one crate/service per script. This map names logical
boundaries; implementation admission fixes names and layout:
- [production_installer.py](../scripts/production_installer.py) → Rust installer
  plan/apply/reconcile, retaining coupled role/configuration ownership.
- [Universal-hook canon](../scripts/universal-hooks/) → Rust deterministic checks
  with narrow host/CLI adapters, not general-purpose Python coordination logic;
  pack-specific hooks retain their host semantics and consume the same canon.
- [resolve-agents-mode.py](../scripts/resolve-agents-mode.py) → Rust configuration/
  admission operations preserving precedence, normalization and role/profile policy;
  Python coordinates requests and consumes decisions, without duplicating that policy.
- [mutate-work-item.py](../scripts/mutate-work-item.py),
  [agent-run-ledger.py](../scripts/agent-run-ledger.py),
  [review_loop_state.py](../scripts/review_loop_state.py) and
  [solution_attempt/reducer.py](../scripts/solution_attempt/reducer.py) → distinct Rust
  state-operation submodules and pure reducer. Python coordinates workflow, not a
  second project-state store; SDK session mechanics do not replace these owners.
- [provider_prompt.py](../scripts/provider_prompt.py) and
  [process_runner.py](../scripts/process_supervision/process_runner.py) → separate
  Python SDK/provider coordination and Rust-owned native process operations; adapter
  replacement is limited to actual SDK/host coverage, not a claim that all providers
  or legacy CLI capabilities are supported.
- [skill_pack_validator_runtime.py](../scripts/skill_pack_validator_runtime.py),
  [publication canon](../scripts/universal-hooks/scripts/) and
  [check-publication-gate.py](../scripts/check-publication-gate.py) → distinct
  Rust validation and publication policy/scan/gate modules, not one universal gate.
- [repo_transfer.py](../src.codex/skills/manual-repo-transfer/scripts/repo_transfer.py)
  → Rust inventory/bundle, distinct archive-integrity/payload-source/trusted
  verification, and preview-only cleanup. Freeze and receiver restore remain with
  their workflow owners; this adds neither automatic restore/deletion nor live takeover.

## npm package and runtime-dependency contract

**Owner:** Toolchain Engineer with Product Manager and the existing installer owner.
These are selected design contracts, not installed commands or published packages.
The public CLI name is `orchestrarium`; the registry package identifier remains a
release-time publisher-ownership/name-availability check, not an architecture gap.

Historical npm scope is recorded in [24d0647](https://github.com/applicate2628/Orchestrarium/commit/24d064741b21e8e84dab78dfa2bfcb7091d972ce)
and [e55b246](https://github.com/applicate2628/Orchestrarium/commit/e55b2466281ecc50ad2a940a4de14a5ea90fb98c).
The detailed local-only epic was not recovered; the following is a new explicit
contract, not a claim to reproduce missing decisions. Current main has no root
`package.json`.

- Ship a thin JavaScript dispatcher, versioned rules/resources and exact-version
  native platform packages selected through npm `optionalDependencies`. No
  `postinstall` downloads, compilation, Python setup, providers or project mutation.
  Resolve prerequisites for the selected operation/route only. A selected native
  operation with a missing binary fails clearly; no implicit compilation or Python
  fallback. An explicitly selected legacy-Python apply route does not require an
  unrelated native hook or an unavailable Rust installer.
- `orchestrarium apply --provider codex|claude --global` selects global application;
  `orchestrarium apply --provider codex|claude --target PATH --allow-unsafe-target`
  selects an explicit project. Preserve current target admission, exact-digest
  adoption, force/refusal and preservation semantics from
  `scripts/production_installer.py:585–625` and `INSTALL.md:9–53`.
  `--dry-run` retains existing preview semantics, not an unproved zero-host-query claim.
  Repeating `apply` is the existing idempotent reinstall/update operation.
- npm update changes only the distributable; installed packs change on explicit
  `apply`. npm uninstall removes only the npm distribution. No complete applied-pack
  removal command is promised in the first release: the current narrow owned-hook
  removal is not whole-pack uninstall (`INSTALL.md:287–335`).
- During staged migration, an explicitly selected legacy installer route may
  forward to the canonical Python installer with its declared prerequisite; it
  is not an automatic missing-native fallback. Remove that implementation only
  after the Rust installer qualifies. Native hook delivery can precede this port.
- Copy each applied executable and matching resources into the selected scope's
  resolved canonical agents root under `runtime/<release>-<content-digest>/<target>/`.
  The logical layout is `.agents/runtime/...`; derive it from the installer's
  admitted root/link authority (`production_installer.py:10977–10991`), not a
  reconstructed path that bypasses existing symlink/junction handling.
  Registrations bind this retained pair, never npm cache, mutable `node_modules`,
  `latest` links or PATH. Extend the existing installer owner/receipts for this
  resource, not a parallel manager. Failed apply preserves the prior pair and
  recovery; identity changes retain manual host trust. Initially retain old applied
  versions without native-runtime reclamation. Codex and Claude can share this
  root; later explicit removal must inspect all retained provider registrations
  and configured coordinator bindings in that scope. Current single-registration
  Python retirement (`production_installer.py:10846–10877`) is not that proof.
  Unknown references preserve the version; no garbage collector/refcount service.
- npm does not provision Python or SDK dependencies. Optional coordination follows
  [PR #18's dependency contract](https://github.com/applicate2628/Orchestrarium/pull/18).
  Native hooks do not load Python/SDK; legacy operations keep their declared Python
  prerequisite until replaced. Retained-runtime removal must still account for any
  configured coordinator consumer, as required above.
- First native qualification target: Windows x64 MSVC
  (`x86_64-pc-windows-msvc`). Subsequent candidates: Linux x64 GNU
  (`x86_64-unknown-linux-gnu`) and macOS arm64 (`aarch64-apple-darwin`). All are
  currently unqualified for the new native product; no other architecture is
  implicitly supported. This is qualification order, not permission to drop any
  currently supported hook consumer. Before each shared-hook cutover verify all
  existing supported provider/host routes; qualify installer and process runner
  independently.

Prove the complete payload from an unpacked archive without a checkout, including
validators and dynamic resources. Check dependency closure, explicit apply,
reinstall/update, failure recovery, foreign-file preservation, manual trust and
survival of applied registrations after npm update/uninstall. No package publication
or runtime activation is authorized by this design. Expanded native-role lifecycle
is a dependency only for operations actually needing its broader ownership changes.

Minimize dependencies per consumer, not by a zero-dependency slogan. The existing
`review_loop_state.py` standard-library JSON path avoids PyYAML for suitable owned
ledgers; keep supported legacy YAML parsing explicit. The weaker string/regex
fallback in `skill_pack_validator_runtime.py` is not equivalent validation: retain
an adequate parser rather than silently weakening checks. Test dependencies remain
separate. Python coordination is retained; there is no whole-product Python-free claim.

## SDK project boundary

The detailed SDK/ACP design, concrete glue-removal cases, four implementation tasks,
result-to-ledger migration and live-route qualification belong solely to
[PR #18](https://github.com/applicate2628/Orchestrarium/pull/18). Native operations
retain existing interfaces and one state/process owner; Python coordination calls
those operations rather than replacing their authority. Neither project silently
activates an unavailable route or requires the other's full implementation.

## State, process and cutover ownership

Dependencies run from adapters to existing domain owners to pure decisions/platform
operations; the process layer grants no dispatch authority. Each child has one
lifecycle owner: Rust supervision for Rust-created children, SDK adapter supervision
for SDK-created children; any native containment must assign noncompeting guarantees.
SDK-side qualification is owned by PR18. Native operations must preserve their own
capture, private-path, cancellation and settlement contracts; an SDK caller cannot
bypass them. Current unavailable generic Windows paths stay unavailable.
The installer does not launch provider tasks/model inference. Preserve its existing
read-only Codex host health query (`hooks/list` through App Server), including CLI
availability, hook inventory and the separate manual-trust receiving step. Such a
query starts the host process; it is not an agent-task launch or proof of hook trust.
Publication policy, Git-object scanner and gate retain distinct validity, traversal
and authority/fresh-range responsibilities.

Entrypoints adapt input/output/errors; domain owners retain schemas, errors and
receipts. Pure checks/planners/reducers consume immutable inputs. The installer,
physical work-item lifecycle, agent-run ledger and review-loop state each retain
their own sole writer, transaction/recovery semantics and readback, not a universal
transaction/effect manager. Replace dynamic imports/subprocesses with typed calls only where
isolation or evidence boundaries are preserved; use per-operation consistent inputs,
not global mutable caches. The source-only
[operation store](../scripts/agent_run_persistence/operation_store.py) and
[route activation registry](../scripts/process_supervision/route_activation_registry.py)
remain disabled and nonauthorizing, including for matching supplied bindings; a Rust
port does not activate them.

Python remains the coordination implementation, not just a temporary test oracle.
Retire superseded deterministic Python/shell implementations only after their Rust
replacements qualify; retain useful development/test tools rather than mandate a
whole-language purge. Reuse state/contracts, not a new framework, registry or service.

Before the first production cutover, Architect and each affected owner must accept
the implementation boundary and update the binding Python production-owner policy
with its owning documentation. This plan changes neither that live policy nor any
runtime. Rust supports cross-platform implementation, not identical operating-system
semantics or verified binaries for every target. Keep real platform differences in
their owners; admit missing generic execution boundaries against concrete use cases.
Installation of source-only components remains a separate decision. Owner-equivalent
manual execution retains the same guarantees and is not a host-denial bypass.

## Native components to evaluate

[clap](https://github.com/clap-rs/clap) for CLI
arguments, [serde_json](https://github.com/serde-rs/json) for owned JSON data,
[toml_edit](https://github.com/toml-rs/toml/tree/main/crates/toml_edit) for TOML edits
retaining comments/layout where supported, not guaranteed byte preservation,
[tempfile](https://github.com/Stebalien/tempfile) for temporary resources, and
[walkdir](https://github.com/BurntSushi/walkdir) for filesystem traversal. Retain a
justified parser for supported legacy YAML; changing language cannot weaken validation.
Use [Rayon](https://github.com/rayon-rs/rayon) only for measured independent parallel
work with bounded workers and deterministic result assembly. Filesystem traversal
does not replace publication's complete commit/tree/blob object-graph scan; never
apply `.gitignore` exclusions to that publication scope.

For Rust-owned process operations, evaluate [process-wrap](https://github.com/watchexec/process-wrap)
with its Rust standard-library (`std`) frontend; add no mandatory Tokio asynchronous
runtime. Its Windows Job Object/POSIX process-group wrappers do not supply the full
runner lifecycle. Add a small Windows-specific adapter, using
[windows-rs](https://github.com/microsoft/windows-rs) only for proven uncovered native
operations; avoid duplicate wrappers already supplied transitively. Pin evaluated
revisions/features and inspect licensing, dependencies and supported targets before
implementation. These are upstream components, not verified Orchestrarium integration.

Libraries do not confer installer ownership, rollback/crash-atomicity, publication
authority, path confinement or process settlement. Preserve those application
contracts and their tests. Native publication needs an admitted replacement for held
Python-code closure/trusted-interpreter custody with executable/code-identity custody,
not erased isolation through an in-process call. Current main's Windows permission-rendering correction
already belongs to its native descriptor owner (see source baseline above); it is not
new Rust scope. Count packaging, updates, bridge removal and platform/dependency
maintenance when assessing complexity; claim no speed or reliability gain without
matched measurements.

## Acceptance, parity and deliberate improvements

Establish the current behavior and performance baseline.
For deterministic replacements require one-for-one parity of standard-output protocol, standard-error
output, exit codes, ordering, effects, persisted state/files and error behavior on
the same inputs, including malformed/missing data and preserved user content. Require
byte equality wherever the interface contract demands it. Structural comparison must
preserve all contract-visible distinctions; normalize only specifically justified
nondeterministic fields, never broad masking. Adjudicate known baseline defects
separately; neither enshrine them blindly nor disguise intentional semantic changes
as migration. SDK behavior/outcome criteria are owned by PR18; native parity here concerns
deterministic operations, not stochastic model prose.
Compare deterministic implementations only on isolated cloned fixtures/replayed
inputs with providers stubbed, never with
duplicate live effects or paid runs. Probe interruption/restart, partial writes and
rollback at the existing state owners, not just successful command output. For
parsing, preserve duplicate-key rejection or retention, strict/unknown-field rules,
number tokens, key ordering and canonical hashes at each actual owner; TOML edits
must retain accepted/refused configuration shapes, not merely parseable output.
Include encoding/byte-order marks/invalid bytes, Unicode matching/case-folding and
platform paths; preserve each hook's warn-only/fail-open/fail-closed outcomes rather
than strengthen gates. For
process slices also probe spawn/partial-setup failure, handles, timeout/cancellation
races, descendant cleanup and terminal evidence, including the actual Windows CLI
private-directory boundary. Reconcile uncertain outcomes before retry; missing
cleanup evidence is not success. Verify required Windows permissions and path-escape
behavior independently; unsupported routes stay typed unavailable before launch.
Require source-to-installed/package parity, upgrade/removal and recovery evidence
on each platform/architecture claimed by that slice, with bounded-parallel versus
serial checks. A simple hook need not wait for every generic process target. Verify
Windows/macOS/Linux support individually before advertising it. Verify native dependencies and interface compatibility with declared SDK consumers
without duplicating PR18's adapter/account/tracing qualification. No whole-product Python-free claim,
duplicate execution owner or second authoritative state store is introduced.

## Native and npm delivery plan

SDK work is first in the overall sequence and is specified only in
[PR #18](https://github.com/applicate2628/Orchestrarium/pull/18). The native/npm
workstreams below are independently scoped; neither starts an SDK/provider task.
Each implementation PR names removed code, preserved contracts and receiving proof.

### Rust workstream — replace shared operations, not provider copies

The unit of hook migration is one shared hook across all its current supported
consumers. Build one common Rust implementation with narrow host adapters where
registration/input/output genuinely differs. Do not fork its logic for Codex and
Claude or add a production Python/Rust switch. Python stays the current implementation
while the Rust candidate is tested on isolated fixtures. In the cutover PR, update
all affected registrations/consumers and remove the replaced Python canon and its
mirrors together. If a required consumer is not qualified, the common hook stays on
Python until the replacement is ready; other independent tasks continue. Migrate
hook by hook, not all hooks or the whole product at once. Retained installed old
versions for rollback are not a second maintained source implementation.

First hook: `orchestrarium hook mcp-usage-reminder`. Its current 34-line entrypoint
emits unconditional SessionStart context without reading stdin, scanning transcripts,
changing project state or spawning children. Generate the embedded policy from
`mcp_continuity_policy.py::SESSION_START_CONTEXT` during candidate development and
check the exact projection; no hand-copied policy. At cutover, remove the Python
entrypoint/mirrors. Keep the policy module only while other live Python consumers
use it; once its last consumer moves, move authored policy to one neutral resource
and remove the obsolete module rather than preserve a Python runtime dependency.

Select direct-native registration, not a permanent forwarding layer. Extend the
existing hook metadata/target descriptor: logical marker maps to retained executable
plus exact `hook <marker>` arguments, event, matcher and source. Registration,
inventory, health target extraction, replacement and retirement consume the same
binding. Current script-basename classification (`check-hook-health.py:1027–1117`)
and removal (`install-hypothesis-hook.py:343–351`) cannot identify multiple hooks in
one binary. `_command_identity` (`check-hook-health.py:353–358`) currently treats all
argv as paths: normalize path operands only, preserving selectors and argument
boundaries under supported host serialization. No binary-name-only ownership,
substring matching, per-hook exceptions or separate executable per hook.

Reuse `test_universal_reminder_hooks.py`, `test_sessionstart_reminder_python_hooks.py`
and hook installer/transaction/surface suites. Verify JSON/UTF-8/order/newline,
stdout/stderr/exit, startup/resume/clear/compaction/subagent inputs, malformed/open
stdin (no blocking), output-failure fail-open behavior and exact policy projection.
Embedding removes Python sibling-import failure; record that packaging difference,
not false byte-for-byte failure parity. Qualify native payload integrity, all current
supported consumers, wrong selector/path/source, duplicate/foreign entries, native
manual trust, reinstall/rollback and build-to-installed identity. Total installed
hook count is not managed membership. Update the current Python-owner source policy
and affected documentation together before cutover.

Then migrate justified deterministic helpers and installer operations using the same
owner-level parity/recovery discipline. Python remains for SDK coordination and
unmigrated operations, not as a fallback copy of a migrated operation.

### npm workstream — delivery, not a second installer

Implement the selected CLI/payload/retained-version contract above. Packaging can
use the explicitly selected current Python installer until the Rust installer is
qualified; hook migration does not require that larger port. Verify complete runtime
resource/dependency closure from an unpacked package without a checkout, npm
update/uninstall survival of applied packs and explicit apply/recovery. Publish only
qualified target binaries; package identity/locks/builds are release evidence, not
new architecture decisions. No full-pack removal or automatic reclamation is added.
Expanded native-role lifecycle or cross-host work blocks only actions actually
requiring those separately owned features.

### Receiving and remaining evidence

Implementation acceptance stays with affected owners and independent reviewers.
For each PR identify delivered behavior, deleted glue, unchanged obligations and
unqualified targets. Carry existing regression probes at the affected owner:
`test_hook_runtime_installers.py`, `test_hook_runtime_transactions.py`,
`test_universal_hook_surfaces.py`,
`test_manual_repo_transfer_security_contracts.py`, `test_agent_run_ledger.py`,
`test_review_loop_state_v2.py` and `test_solution_attempt_reducer.py`, all under
`tests/`. Compare selected probes against the pinned main baseline; source review
and stub-only tests do not prove live provider/platform behavior. No speed or
reliability gain is established until measured. This plan includes a narrow
manual-trust documentation/test correction, not the new runtime implementation.

## Terms and Abbreviations

- npm: the JavaScript package registry/tooling ecosystem; CLI design is selected,
  registry identity and actual release availability remain unverified.
- Rust / Cargo / crate: native programming language / its build and package tool /
  a Rust compilation unit. The target starts with one Cargo package and CLI.
- Python: the retained coordination language; existing production script ownership
  stays binding until each admitted language-boundary change.
- SDK: software development kit. The OpenAI Agents SDK provides coordination
  mechanics, not universal provider runtimes or Orchestrarium authority.
- ACP: Agent Client Protocol, the common agent-transport candidate; protocol support
  is not provider admission, platform qualification or coordinator-model API access.
- API / CLI: application programming interface / command-line interface.
- Codex / Claude / Kimi / Grok: provider runtimes whose adapters and eligibility
  remain distinct; an upstream adapter is not proof of an admitted local route.
- Lead / admission: the existing orchestration owner / existing permission and
  policy eligibility, not a new scheduler or ranking result.
- PR: pull request; a proposal does not prove implementation or merge.
- JSON / YAML / TOML: JavaScript Object Notation / YAML Ain't Markup Language /
  Tom's Obvious Minimal Language, structured data/configuration formats.
- PyYAML: a Python YAML parser; the existing validator's weaker fallback is not
  equivalent supported validation.
- Differential parity: comparison on the same isolated inputs and effects;
  normalization may remove only specifically justified nondeterminism.
- Standard library: language-shipped facilities, including Rust `std`, distinct
  from third-party components; Tokio is a separate asynchronous Rust runtime.
- POSIX / Windows Job Object: Unix-like operating-system interface family /
  Windows mechanism for managing groups of processes.
- Foreign-function / interprocess bridge: a language-boundary call / communication
  between processes; neither transfers state ownership or authority implicitly.
- Trace export: transmission of execution/interaction observations to a configured
  destination, distinct from the authoritative project ledger.
