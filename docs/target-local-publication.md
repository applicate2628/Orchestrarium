# Target-local native publication

## Scope

Orchestrarium provides `check-git-push-gate.py --target-local-push REPOSITORY REMOTE SOURCE_OID DESTINATION_REF` for an already admitted local execution context. REPOSITORY must be an absolute repository root; REMOTE is a configured named remote; SOURCE_OID is a full immutable object ID; DESTINATION_REF is a full `refs/heads/` reference. Arbitrary Git flags, shell commands, executables, callback configuration and scan receipts are not accepted.

The entry constructs one argument vector, registers the existing command-scoped native Git pre-push callback, qualifies it locally, and executes that same vector with `shell=False`. Git remains the owner of the actual transfer and callback input. The callback still requires fresh Version 3 range and Version 4 native-object scans, current target identity and fail-closed findings. A callback failure produces a nonzero command exit. No force push or verification bypass is added.

## Requirements and installation

Use Python 3.13 or newer and Git supporting command-scoped hooks and `git hook list -z --show-scope pre-push`. The local Linux integration was verified with Python 3.15.2 and Git 2.56.0; Git 2.52.0 did not support that query and was not qualified. This is observed compatibility, not an inferred minimum Git release. The command must fail rather than downgrade its checks on unsupported Git.

The universal source is `scripts/universal-hooks/scripts/`. Run the existing `scripts/sync-universal-hooks.py --sync` and `--check`, then use the normal pack installer. Do not hand-create an alternative callback or edit an installed copy instead of source. This change alone does not install or activate a runtime.

## Transport boundary

This is not admission for Remote Desktop Commander or another remote carrier. `PGG-REMOTE-EXECUTION-UNBOUND` remains in force. A wrapper command name, device/account field or caller-supplied token is not proof that an external evaluator is bound to the target host. Do not disguise a denied remote push as this entry. A supported target-local execution boundary or separately reviewed explicit transport admission remains necessary.

## Verification evidence

Unit coverage includes exact argv dispatch, malformed arguments, native qualification refusal, Git identity/PATH drift, failure propagation, old-entry compatibility and rejection of nested/decorated DIRECT_ARGV provenance. A real isolated Linux test used a synthetic sender and local bare receiver: clean content produced fresh V3/V4 receipts and the exact requested destination object; a synthetic machine-path finding stopped the callback and left the receiver unchanged. No network, model or production repository was used. Windows receiving was independently repeated on 2026-11-11 with Git 2.56.0.windows.4, both a full Python 3.15 runtime and the candidate bundled minimal Python: clean transfer produced fresh V3/V4 results and the exact requested receiver OID; a following synthetic machine-path finding was refused and left the receiver unchanged. These isolated source-entry tests do not establish remote-carrier admission, installed hook dispatch, deployment readiness, or eliminate all filesystem replacement races.

## Terms and Abbreviations

- OID: immutable Git object identifier.
- argv: process argument vector, not shell text.
- DIRECT_ARGV: parser-owned direct argument-vector provenance.
- V3/V4: existing range and native-object scan receipt versions.

## Large full-history checks

New native branches may require a conservative full-history scan. Blob payloads are reacquired and hash-verified per path instead of retained for the entire history. Every selected object is still checked, with existing per-object, count, tree, coverage and cleanup constraints.

For an explicitly initiated full-history run, set `ORCHE_PUBLICATION_SCAN_SECONDS` before launching the gate process, for that invocation only (for example, `900`). Do not mutate it inside an already-loaded gate process. Canonical decimal integers from `240` to `3600` are accepted; absent means `240`. Invalid values fail closed. The supervising gate permits 60 additional seconds for settlement. Do not persist this as a live client setting. The budget never supplies scan credit, changes graph selection, suppresses findings or skips currentness checks. Both fresh V3 and V4 evidence remain mandatory before Git transfers.
