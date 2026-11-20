# Receiver-scoped target-local publication

`--target-local-push [--dry-run] REPOSITORY REMOTE SOURCE_OID DESTINATION_REF`
keeps Git in charge of native hooks and the final transfer. No hook files or
persistent Git configuration are changed. Other hooks retain their veto.

The qualified Windows HTTPS route holds one actual Git/official HTTPS-helper
lifecycle. It captures that helper's complete advertisement before callbacks,
checks the native callback through held process identities, runs the captured
scanner and consumes its V5 receipt once, then admits only the exact immutable
OID/ref batch to that same live helper. Neither a separate remote query nor
local tracking refs supplies exclusion authority. Missing local objects remain
in the conservative scan. A rejected, replayed, changed or unqualified scope
never turns into an empty successful scan.

The first supported profile is the qualified Git for Windows 2.56 build and
canonical GitHub HTTPS endpoint, SHA-1 repositories, the observed plain config
origins and recognized preserved GH credential helper/Schannel configuration.
Executable identities and config inputs remain pinned. Includes, worktree
configuration, redirects, rewrites, custom receive-pack and unsupported routes
stay on full-graph scanning (or refuse before transfer when pinning fails).
Only the owner's private helper directory may replace Git's helper search path.
Submodule publication and implicit followed tags are not part of this single
explicit-ref command. The owner never silently retries after admission.

This follows the existing trusted owner/runtime model, not an operating-system
sandbox against arbitrary same-user native code. Runtime installation and
source closure remain part of that trust boundary. The helper parser's bounded
framing and scanner's coverage checks remain mandatory.

Verification includes captured-child V4/V5 acceptance and mutation negatives,
source/installed layout receiving, actual held-helper local transfers, genuine
GitHub HTTPS dry-run on the publication repository, and native hooks producing
large stdout/stderr output and vetoing transfer. A dry-run is not evidence of
remote ref creation; successful real publication requires exact ref readback.

## Portable review preparation repository layout

The separate portable-review preview resolves the local configuration through
Git's actual common directory. Linked worktrees retain pins on both the `.git`
file and the common-directory pointer, then recheck the resolved paths before
continuing. Regular repositories keep their existing local configuration.
This is a repository-layout correction, not a new executable or provider trust
route: the admitted Windows/GitHub binaries and plain global/system origins
remain restricted. Includes and per-worktree configuration remain unsupported.
The native transfer owner retains its existing narrower layout profile.

## Terms and Abbreviations

- OID: immutable Git object identifier.
- HTTPS: authenticated encrypted HTTP transport.
- SHA-1/SHA-256: Git object or evidence digest formats, not publication consent.
- V3/V4/V5: distinct publication receipt versions; V5 additionally binds the actual receiver scope.
- Helper: the official Git transport subprocess used for this invocation.
