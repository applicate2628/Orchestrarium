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

- SDK: software development kit used behind the common execution contract.
- CLI: command-line interface; some SDKs still depend on a provider CLI.
- npm: optional package distribution channel, not an installer-policy owner.
- Bootstrap: bounded acquisition, verification and dispatch entrypoint.
- Retained runtime: applied interpreter/resources kept independently of caches.
- CPython: the Python implementation bundled with this release.
