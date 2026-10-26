# Distribution: PowerShell bootstrap and compatible npm channel

Status: independent documentation task; no npm package or native target is
published or activated here. Source baseline: main
`317e1448a020aeaa58f65aaceb180e835741d6de`.

## Goal and boundary

Deliver one versioned Rust CLI and its matching resources through a thin Windows
PowerShell bootstrap, with npm retained as a compatible alternative channel.
Neither channel owns installation policy or managed-file mutation: both invoke
the same qualified Rust operations. The current Python installer remains the
explicit existing route until its Rust replacement has passed parity qualification.
Do not disguise that transition as a completed native installer or silently fall
back from a missing Rust operation. Distribution design and testing can proceed
independently of PR21; enabling native apply depends on that specific operation
being qualified, not on the full Rust roadmap or optional SDK coordination.

## Common delivery and PowerShell boundary

PR17 owns delivery through PowerShell and npm. PR21 owns native operation
semantics. Both channels select the same release identifier, target tuple,
executable and resource digests; parity means the same admitted operation inputs
and effects, not merely the same command name. Neither channel creates a second
installer, ledger, trust inventory, recovery engine or policy store.

The PowerShell script is a bootstrap only:
- Detect the supported OS/architecture and resolve an explicitly selected release
  from the official release origin. Reject unknown targets before changing state.
- Download the versioned executable/resources and verify their integrity and
  authenticity before execution. A digest downloaded beside an attacker-controlled
  payload is not an independent authenticity check. Release signing/verification
  trust, key rotation and publisher ownership must be specified and tested before
  enabling this channel; this plan invents no signing keys or trust grants.
- Stage only bootstrap-owned temporary downloads, verify the complete pair, then
  invoke the selected Rust CLI with exact argument boundaries and propagate its
  exit status. Interrupted or failed verification must not launch a partial payload
  or replace a working installation. Temporary download cleanup is not pack removal.
- Do not edit agent configuration, hooks, trust, managed-file inventories or user
  projects in PowerShell. Do not elevate automatically or relax execution policy,
  host trust, certificate verification or security settings. Preserve explicit
  existing-user consent and the native operation's own target admission.
- Separate downloading from execution in documented operator instructions. A
  convenient one-line web invocation is not an integrity, authenticity or approval
  mechanism; do not require piping unchecked downloaded code into execution.

The Rust installer remains the sole owner of installed payload placement,
managed-file changes, update/removal decisions, preservation and recovery. Existing
Python ownership persists for each unmigrated operation until one qualified
cutover, not simultaneous Python/Rust writers. PowerShell supplies no hook or
business logic. npm is optional for users choosing direct native distribution.

## npm compatibility and runtime-dependency contract

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
  fallback. npm is a thin dispatcher to the same qualified native command used
  by the PowerShell channel, not an independent implementation of apply.
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
  is a clearly labelled transitional compatibility route, not the target native
  installer or an automatic missing-native fallback. Do not claim native channel
  parity for it. Remove the superseded implementation only after a separately
  qualified Rust installer is selected. Native hook delivery can precede this port.
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


## Delivery and acceptance

1. Verify publisher/name ownership at release time, exact package/payload closure
   and supported operation prerequisites from an unpacked archive without a checkout.
2. Implement the PowerShell bootstrap and thin npm dispatcher against one release
   contract; do not create a second installer or activate unqualified Rust apply.
3. Test selected qualified targets, missing target refusal, offline payload integrity,
   foreign-file preservation, failed apply/reinstall/recovery and retained identities.
4. npm update changes distribution; npm uninstall must not break applied packs.
   Keep full-pack uninstall and automatic collection outside the initial channel
   release. A later managed-pack removal command belongs only to the Rust operation
   owner after explicit ownership/preservation qualification.
5. Compare PowerShell and npm delivery of the same qualified release: executable
   and resource identities, exact argv, exit codes, installed effects, update and
   recovery. Reject tampering, unknown targets, download interruption, mixed versions
   and invalid authenticity evidence before execution. No silent channel fallback.

The minimal shared payload contract belongs to the [existing installer](../scripts/production_installer.py):
admitted resolved root, immutable retained executable/resources, explicit apply,
recovery and persisted readback. Unknown references preserve a retained version;
no new garbage collector, reference-count service or payload manager.
The [Rust task](https://github.com/applicate2628/Orchestrarium/pull/21) may supply qualified targets
independently. Python/SDK environment provisioning remains outside npm.

## Architecture decisions and risks

Prefer two thin delivery channels over one native operation owner, not a new
daemon or global runtime manager. Rust owns qualified install/update/removal and
recovery; current Python ownership remains only until each explicit cutover. The
PowerShell channel removes npm as a mandatory prerequisite, not Python from SDK
coordination or from deliberately retained legacy operations.
Package downloads/builds and provider execution cannot occur through postinstall.
Native payloads are shipped only for qualified targets; absence is a clear failure
for that selected operation, never an implicit language/runtime fallback.

## Terms and Abbreviations

- npm: optional JavaScript package distribution channel; package availability is unverified.
- PowerShell bootstrap: Windows download/verification/launch script, not an operation owner.
- SDK: software development kit; not provisioned by this distribution task.
- CLI: command-line interface.
- Retained payload: immutable applied executable/resources independent of npm cache.
