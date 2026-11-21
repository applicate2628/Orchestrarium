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

## Local commit-message diagnostics

Use the same repository, remote, destination and source as the standalone
range scan you are investigating:

```text
python PATH_TO_SCANNER --range origin main --range-source WORKING_REF --history-diagnostics
```

Use a local terminal; keep the JSON within the review scope. It lists the
full commit object ID, message field, line and detector class without
printing the message, the matching text, local filesystem paths or the
configured remote URL. The scope binds the checked repository, source commit,
destination endpoint digest and ref, and observed destination commit (null
for a new ref). The report is local, but the existing read-only range
discovery contacts the configured receiver. It describes the range checked
at selection time, not a later remote state. A native pre-push callback
checks the actual ref updates and receiver evidence it was given. A standalone
report does not reproduce that callback or authorize a retry.
`reportComplete: false` means the report reached its display limit, not that
the listed rows are the complete set. Other finding types remain redacted;
only aggregate detector-class counts are shown. Diagnostic output is
unreviewed and counts history-file findings per path and blob. Ordinary
publication evaluation checks reviewed text per commit. Its display groups
repeated unresolved locations within the same path and blob before applying
the output limit, without changing the review decision. Neither report
authorizes a push.

A finding still exits with status 1; an unqualified scan exits with status 2
without a locations report. No history, hook, policy or remote ref is changed.
This JSON is for diagnosis, not a clean-scan receipt, approval, or transfer
authorization. The separate diagnostic mode does not change the ordinary
publication check or its output.

## Large full-history checks

New native branches may require a conservative full-history scan. Blob payloads are reacquired and hash-verified per path instead of retained for the entire history. Every selected object is still checked, with existing per-object, count, tree, coverage and cleanup constraints.

For an explicitly initiated full-history run, set `ORCHE_PUBLICATION_SCAN_SECONDS` before launching the gate process, for that invocation only (for example, `900`). Do not mutate it inside an already-loaded gate process. Canonical decimal integers from `240` to `3600` are accepted; absent means `240`. Invalid values fail closed. Git object reads use this same deadline. A shorter explicit reader deadline still takes precedence; a reader without a scan owner retains its short fallback. The supervising gate permits 60 additional seconds for settlement. Do not persist this as a live client setting. The budget never supplies scan credit, changes graph selection, suppresses findings or skips currentness checks. Both fresh V3 and V4 evidence remain mandatory before Git transfers.

## What the scanner limits protect

`PS-MSG-LIMIT` denotes a resource refusal, not specifically a long commit
message. A category describes which boundary stopped that run; a refusal
without a category does not establish the cause. No partial scan qualifies
publication, and display truncation of findings is not permission to continue.

| Resource | Categories | Why the boundary exists |
| --- | --- | --- |
| Git subprocess input and selection output | `selection-bytes`, `bytes`, `count` | Bound revision input, framed output and the in-memory selection or union. Fixed-width object IDs tie the output byte envelope to its row budget; malformed output still must not grow the buffer. |
| Remote advertisement | `destination-ref`, `remote-ref-count` | Bound individual names and accumulated ref records before using the advertisement as evidence. |
| Individual acquired objects | `commit-bytes`, `tree-bytes`, `tag-bytes`, `blob-bytes` | Reject an oversized object before reading its declared body into memory. |
| Text processing | `message`, `line-bytes` | Bound individual decoding and line processing. Commit and tag text is processed one object at a time under the scan deadline; only commit topology and tag targets are retained. A verified blob's line bound is checked once, while each path still receives its own detector and review context. |
| Tree traversal and cache | `tree-frontier`, `tree-visits`, `tree-visited`, `tree-cache-count`, `tree-cache-bytes` | Bound pending paths, recurring traversal work, distinct tree identities and retained cache memory. A repeated tree at a different path still contributes path evidence. |
| Paths and scan subjects | `path-bytes`, `subject-count`, `blob-count`, `blob-path-count` | Bound expanded paths, coverage records, distinct blobs and path-specific blob work; one blob may appear at multiple paths. |

These are distinct resource concerns, not proof that every current numeric
default is appropriate for supported repositories. Before changing a default,
identify the rejecting category, measure normal and worst-case work on a
representative fixture, and show that the replacement preserves bounded work
and complete coverage. A qualified receiver may exclude only history it has
proved belongs to that same transfer; a local branch name or tracking ref
never substitutes for that evidence.
