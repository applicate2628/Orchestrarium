# Native operations in Rust

Status: independent design task, no native implementation or activation. Baseline
main `317e1448a020aeaa58f65aaceb180e835741d6de`; source observations do not prove
installed behavior. PowerShell/npm delivery and SDK coordination are independent consumers,
not blanket prerequisites or mandatory phases of a Rust port.

## Goal, quality attributes and architecture

Priorities: preserve operation/security semantics; maintain one owner for each
state/process; reduce lifecycle complexity. No measured speed or reliability gain
is claimed. Start with one Cargo package/CLI and internal operation modules, not
one service/crate per script. Python remains SDK coordination and unmigrated
operations. Do not introduce a daemon, scheduler, ledger or transaction framework.

| Decision | Benefit | Cost / acceptance boundary |
| --- | --- | --- |
| One common hook implementation and descriptor | Avoid host copies and basename-based ownership | Qualify all currently supported consumers before shared cutover |
| One installer operation owner, migrated from Python to Rust | Reuse admission, recovery and readback | Thin PowerShell/npm channels never implement managed-file changes or trust |
| Candidate reminder slice has no child processes or state writes | Small deterministic parity surface | Provides no proof for process, publication, transfer or installer ports |
| Independent later operation slices | Keeps risky owners separate | Each retains its own evidence and platform qualification |

## Delivery channels and native installer ownership

The accepted target is Rust CLI plus a thin PowerShell bootstrap, with npm retained
as a compatible delivery channel. [PR17](https://github.com/applicate2628/Orchestrarium/pull/17)
owns release selection, download/verification and dispatch. This PR owns native
operation behavior; the installer is not reimplemented in PowerShell or JavaScript.

Rust install/update and, when separately qualified, managed-file removal preserve
the current installer's target admission, user-file preservation, coupled
configuration/registration ownership, trust boundaries, interruption recovery and
persisted readback. Uninstalling a distribution channel does not remove applied
packs. Full-pack removal is not inferred from the existing narrow hook-retirement
operation; inventory, all consumers and foreign/unknown content must be qualified
before enabling it. No global garbage collector or parallel installer is added.

Both delivery channels invoke the same qualified Rust executable/resources for
an admitted release and target. Native installation must not require npm. Existing
Python installation remains explicit until Rust parity/cutover, with no silent
fallback or competing writer. This plan does not override the live Python-owner
policy; update its owner documents only with the admitted production cutover.

The installer migration is a bounded operation slice, not a prerequisite for all
other native hooks or optional SDK coordination. Neither selecting this architecture
nor implementing a bootstrap authorizes building, publishing, trusting or activating
native binaries. The first implementation slice will be chosen with the user after
SDK acceptance; the existing reminder proposal below is a candidate, not a launch.

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

## State, process and cutover ownership

Dependencies run from adapters to existing domain owners to pure decisions/platform
operations; the process layer grants no dispatch authority. Each child has one
lifecycle owner: Rust supervision for Rust-created children, SDK adapter supervision
for SDK-created children; any native containment must assign noncompeting guarantees.
SDK design/qualification tracking is owned by PR18; PR19 contains the implementation. Native operations must preserve their own
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


## Candidate first vertical slice: mcp-usage-reminder

Source: [canonical entrypoint](https://github.com/applicate2628/Orchestrarium/blob/317e1448a020aeaa58f65aaceb180e835741d6de/scripts/universal-hooks/scripts/mcp-usage-reminder.py),
[emitter](https://github.com/applicate2628/Orchestrarium/blob/317e1448a020aeaa58f65aaceb180e835741d6de/scripts/universal-hooks/scripts/hook_common.py),
[policy](https://github.com/applicate2628/Orchestrarium/blob/317e1448a020aeaa58f65aaceb180e835741d6de/scripts/universal-hooks/scripts/mcp_continuity_policy.py),
[health identity](https://github.com/applicate2628/Orchestrarium/blob/317e1448a020aeaa58f65aaceb180e835741d6de/scripts/check-hook-health.py)
and [installer](https://github.com/applicate2628/Orchestrarium/blob/317e1448a020aeaa58f65aaceb180e835741d6de/scripts/production_installer.py).
The current Python hook imports SESSION_START_CONTEXT and emits SessionStart JSON
unconditionally. It reads no stdin, writes no project state, creates no children,
catches import/output errors and returns zero. Existing thin launchers are not
another maintained implementation.

### Invocation and payload contract

Define one common descriptor for logical marker, retained executable identity,
exact argv, event, matcher, source and matching resource identities. Registration,
inventory, health target extraction, replacement and retirement consume it.
Current _command_identity normalizes every argument and _invoked_script identifies
interpreter/script operands; neither alone identifies multiple native selectors.
Normalize only typed path operands; preserve selectors, case and argv boundaries
under the supported host serialization. No substring/binary-basename ownership,
per-hook exception or permanent forwarding layer.

Extend the existing installer to place the immutable executable and resources
under its admitted resolved agents root, independent of npm caches or node_modules.
The same owner performs explicit apply, recovery, source/inventory registration
binding, manual native trust, readback, replacement and retirement. Unknown foreign
references preserve old versions. No automatic collection or reference-count service.
Generate the exact embedded policy projection from SESSION_START_CONTEXT at build
time; a hand-copied text block is not another policy source. The migrated runtime
has no Python dependency. Keep the Python policy module while other live consumers
need it; only later move authored policy to one neutral single-source resource.

### Acceptance and cutover

1. Capture the consumer inventory and baseline for Codex and Claude, every supported
   host/architecture, event/matcher/argv/source and output contract. Windows x64 is
   first qualification target, not permission to drop existing consumers.
2. Compare JSON shape, literal UTF-8, property/order/newline, stdout, stderr and exit
   status on startup/resume/clear/compaction/subagent cases, malformed and open
   stdin (must not block), and output failure. No stdin read, file write or child
   creation is added. Preserve fail-open. Record removal of Python sibling-import
   failure as a packaging difference, not fabricated failure-byte equality.
3. Verify wrong selector/path/source, duplicate and foreign registrations, host
   serialization, native trust, resource drift and build-to-installed identity.
   Exercise reinstall, interruption and conditional rollback/readback through the
   existing owner; do not mask failures with a mock process owner.
4. Once every existing supported consumer qualifies, one cutover changes their
   registrations and removes the superseded Python entrypoint/canon/mirrors.
   No permanent Python/Rust switch or maintained duplicate. Retained installed old
   binaries for rollback are historical resources, not a second source implementation.
   Update the binding Python-production-owner policy and owning docs together
   before production cutover; this design does not change that live rule.

Reuse tests/test_universal_reminder_hooks.py,
tests/test_sessionstart_reminder_python_hooks.py,
tests/test_hook_runtime_installers.py, tests/test_hook_runtime_transactions.py
and tests/test_universal_hook_surfaces.py as behavior/receiving oracles; extend only
missing native descriptor and lifecycle cases. Source review is not installed proof.

## Independent subsequent slices

If the reminder is selected first, a possible later order is another simple
shared hook, then justified pure reducers/validators, then state-owner/installer
operations. Choose the actual first slice together with the user; the order here
is not implementation authorization. Process supervision,
publication and repository transfer are separate high-risk migrations with their
own authority, creator-custody and complete-graph/settlement requirements.
Unavailable generic routes stay unavailable. A simple hook does not wait for
every generic process target; npm and SDK do not wait for this full roadmap.
Use each existing state owner, not one universal Rust transaction manager.

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


## Receiving and implementation admission

Affected owners and independent architecture/security reviewers accept each
implementation boundary and its removed code, preserved obligations and unqualified
targets. This document is a source-based plan, not that production cutover approval.
Matched benchmarks must include packaging/update/bridge maintenance and actual
platform behavior before claiming speed or reliability improvements.

The [independent delivery task (PR17)](https://github.com/applicate2628/Orchestrarium/pull/17) owns PowerShell/bootstrap and npm distribution; this task consumes
only the existing installer's minimal retained payload contract. SDK design is
[PR18](https://github.com/applicate2628/Orchestrarium/pull/18), source implementation
is [PR19](https://github.com/applicate2628/Orchestrarium/pull/19). Neither activates
an unavailable route or grants native/provider launch authority.

## Terms and Abbreviations

- Rust / Cargo: native programming language / its build and package tool.
- CLI / argv: command-line interface / exact argument vector.
- PowerShell bootstrap: download/verification/launch channel, not managed-state logic.
- npm: compatible optional distribution channel for the same native release.
- JSON / UTF-8: structured interchange data / Unicode byte encoding.
- SDK / ACP: software development kit / Agent Client Protocol.
- MCP: Model Context Protocol; the reminder names no particular server.
- POSIX / Windows Job Object: Unix-like interface family / Windows process container.
- Native trust: existing host review/qualification, not a descriptor self-assertion.
