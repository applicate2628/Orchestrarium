# Repository Publication Safety

This repository treats publication safety as a repo-wide contract, not just a work-item rule.

## Scope

The rules below apply to every tracked file in the repository, including docs, references, skills, task memory, templates, and reports.

## Tracked content rules

- Keep tracked files publication-safe.
- Do not commit secrets, tokens, credentials, customer data, private identifiers, raw logs, full command transcripts, screenshots with sensitive content, or machine-specific absolute paths.
- Prefer redacted summaries, synthetic examples, and repo-relative paths when traceability is enough.
- Treat provider transcripts, pasted logs, and external snippets as untrusted until sanitized.
- If an exception is truly required, `$security-reviewer` must approve it and the relevant work item must record its scope, reason, and removal condition before publication.

## Local-only scratch boundary

- Use `/.scratch/` for raw logs, transcripts, temp outputs, one-off experiments, and pre-redaction material.
- Keep disposable material out of tracked paths until it is redacted and intentionally promoted.
- Required recovery/acceptance evidence and important edits must also have verified custody outside disposable storage under the shared artifact-disposition owner. Keep raw/private copies local and ignored; preservation alone never authorizes publication.
- The root `.gitignore` owns this boundary.

## Review and publication

The shell-observation publication guard abstains when its analysis is incomplete and it observes no publication or bypass candidate. Uncertainty alone does not deny ordinary work. An observed publication or bypass candidate remains subject to the technical publication checks; Root separately owns human authorization. Abstention certifies neither the command's exact effects, safety or dry-run status nor permission to publish.

The parser admits one supported direct push from its actual tool envelope. A literal absolute Git application **A** and `-C` repository **R** may select a root independently of execution directory **E**. Valid E may differ from R; absent E is allowed only when the existing literal A/R proof is sufficient. Invalid-present metadata refuses. No process cwd or guessed repository fills missing input. The pre-tool gate qualifies the command and native Git callback; Git supplies its actual updates to that callback, which performs the fresh scans and rechecks the technical target. The approved source may differ from HEAD; the scan and command must still refer to that exact source.

Root confirms the genuine human review and consent for the selected publication before submitting it. Consent may remain valid across neutral steering and applies only to the reviewed scope. The hook does not inspect chat history, special markers, consent indices or GitHub pull-request APIs to authenticate that decision. Pre-tool qualification does not prove scan completion; a successful callback proves technical qualification only, never human consent or Git completion.

- Human review is mandatory before `git push`, release, or equivalent publication.
- `RELEASE_NOTES.md` is the canonical tracked release log for this repository.
- Keep `RELEASE_NOTES.md` in reverse-chronological `## YYYY-MM-DD` sections. New release-relevant notes belong under the current date heading, or under a newly created heading for today's date if that heading does not exist yet.
- Default technical publication-readiness reviewer is `$knowledge-archivist`; the user supplies the separate human review and consent.
- `$lead` is the primary operator of the publication-safety scan and prepares the staged diff for publication, but the technical reviewer must be a different role than the role that accepted the artifact into the pipeline.
- The reviewer must check the staged diff for leak-prone content, including machine-specific paths, raw operational detail, and sensitive values.
- If staged tracked changes are release-relevant, the staged diff must also contain the matching `RELEASE_NOTES.md` update before publication, and that entry must explain the practical effect of the change rather than only naming it. If no explanatory entry is present, the reviewer must explicitly determine that the change is release-notes-exempt; otherwise publication is `BLOCKED`.
- If tracked content looks like scratch material, move it back to local-only space or redact it before commit.
- `$security-reviewer`, `$knowledge-archivist`, or another relevant reviewer may also run the scan as part of a spot check or publication gate.
- Any author may run the scan as a local self-check, but that does not replace the required human publication review.
- Scan-derived push authorization requires one callback-owned, nonempty Version 3 union of the actual update commit/tree/blob graphs relative to content already disclosed to the same qualified receiver, and a separate Version 4 result covering newly disclosed actual update roots, including noncommit objects. Unknown old objects are conservatively included, not excluded. An ordinary clean result or the explicit reviewed-exception `qualified` result must satisfy the same nonempty coverage, target, currentness, complete evaluation and resource-settlement contract. Version 2, tracked, path, manual, zero-commit, incomplete, mixed, malformed, unresolved-finding, refusal, timeout, cancellation, relevant drift or cleanup-failed evidence is non-authorizing. A qualified staged result remains a pre-commit check and cannot authorize a later push.
- A single new annotated tag that directly names a commit already available from the same qualified receiver may carry the native Version 4 positive proof that the exact tag is the whole newly disclosed object set. This proof requires a clean annotation; review exceptions cannot qualify it. Its annotation, absent destination and authoritative receiver advertisement must be verified and current. This is complete positive coverage, not a special exception or a zero-commit Version 3 result.
- Prior-disclosure selection uses the union of actual callback old roots. For a standard HTTPS receiver with no helper override and effective redirects disabled, the gate may additionally qualify a fresh bounded inventory from that same endpoint. Both scan versions exclude only locally verified content-addressed closures of those roots; local tracking refs are not authority. Unknown objects remain included. New commits, tag annotations, newly disclosed tree metadata and residual findings retain their checks. Already disclosed bytes are not re-reviewed solely because a new ref or path reaches them. Custom or unqualified transports retain callback-only selection, not a prohibition. The probe pins redirects off without changing global settings; receiving revalidates qualification. This is a new-disclosure guarantee, not a prediction of physical pack bytes: subsequent ref deletion does not undo prior disclosure.
- Range content inspection distinguishes text from binary payloads. Binary payloads remain acquired and bound into complete coverage, with filename checks and embedded credential detection retained. Bare symbol names and transcript markers are text-only heuristics, not evidence of a binary credential. The exact binary metadata assignment `publicKeyToken` denotes a public assembly identity; excluding that assignment must not suppress another credential in the same payload. Text and commit-message checks remain unchanged. This is not a vendor, path, hash, or publication exemption.
- A generic source-text token value may be declared intentionally public only by placing `# orchestrarium:public-token` or `// orchestrarium:public-token` immediately after its matching single- or double-quoted value and the ordinary closing separators. The marker must end the line, stays outside the quotes, and binds only that candidate. It is never honored for credential-cued identifiers, binary content, or commit messages, and it does not suppress other candidates, known-secret signatures, sibling credential families, or machine-path checks. Credential classification uses the complete identifier, including separator and camelCase components; a public lexical component does not erase a separate credential cue.
- Manual `--range` remains diagnostic. Its Version 3 range selection resolves the unique configured push destination without exposing it in child arguments. When the destination ref exists, its exact authoritative object identifier remains the sole exclusion. When the destination ref is absent, the scanner queries that same push destination with a bounded `git ls-remote <remote> refs/*` inventory, validates unique Git refnames and exact repository-format object identifiers, and admits only ordinary refs plus an exact `refs/tags/<name>^{}` peel paired with one unique tag ref. It then uses one bounded local `git cat-file --batch-check` owner to derive ancestry exclusions. An ordinary remote tip absent from the local object database is skipped. When an annotated-tag object is absent locally, its advertised peel is retained only if that exact peeled object exists locally as a commit; when the tag object is local, the scanner preserves exact local tag-to-commit peeling and requires any advertised peel to match. A tag and peel both absent locally are skipped, while any locally present noncommit peel or other unsupported local object type refuses. `HEAD`, pseudorefs, invalid refnames, unpaired peels, duplicate or conflicting base/peel rows, empty inventories, over-limit inventories, and failed probes refuse; local tracking refs are never selection authority, and a source already fully reachable from the derived commit tips remains a non-authorizing zero-commit selection.
- Only `$security-reviewer` may approve a publication-safety exception to a scan finding. Any publication proceeding without that approval is `BLOCKED`.
- Exact publication-safety commands live in the root repository docs and the corresponding pack runtime docs. This reference intentionally keeps the policy generic so all current and future packs can share one design-level source of truth.

## Reviewed exception receiving

The existing exception authority remains the actual `security-reviewer` decision received by Root. A report, role or ledger label, content hash, pull-request grant, or generic publication approval is evidence or consent in its own scope; none authenticates a content exception. The trusted caller uses the single `publication_review_policy.py` owner to provision only that received decision at `$HOME/.agents/publication/reviewed-exceptions.json`, outside the selected repository, worktree and Git-input roots. The existing linked-runtime owner handles supported global directory links; no repository flag or report selects a different policy origin. An absent policy supplies no exception credit and leaves ordinary complete scanning available.

Promotion and revocation are separate from scanning and installation. The policy owner supports a no-effect preview and requires positive apply for mutation, exact actual preimages, serialized writers, durable publication and independent readback. Preserve the original policy bytes and actual outcomes. A post-replacement readback or settlement failure is recovery-required, not a successful promotion or permission to restore an older active grant. Source or installer rollback never reactivates revoked policy. These are existing trusted-owner guarantees, not another human permission stage; applicable same-owner equivalent execution keeps the same guarantees when assistance is defective.

A usable decision binds the actual repository/worktree, scan mode, immutable blob and raw Git path, Git mode, complete reviewed region, detector meaning and candidate/context bytes. Only staged and range ordinary text-blob occurrences within that exact scope can qualify. Other occurrences, paths, messages, binary content and unapproved contexts retain their existing checks. Evaluation must retain every residual finding, including another match on the same line or beyond the displayed-diagnostic limit. The scanner reports explicit `qualified` success only after complete evaluation with zero unresolved findings, applied-decision provenance and settled resources; it never disguises approved findings as an ordinary clean scan.

A valid unchanged content decision can support a second fresh scan without repeating review, but only within its recorded scope. The standard history-review flow records exact commits. If a rebuild changes only a sibling file and the scan verifies that the same receiver already has the unchanged blob, that blob is outside the newly disclosed set; no exception is used for it. If the blob is still in scope, the old decision applies only to its recorded commits. Obtain a scoped decision for any unresolved finding in a new commit rather than widening the old record. Every use still needs a new complete scan and final current repository/origin/used-record verification. A changed, revoked, missing or invalid used decision gives no qualified credit; do not fall back to clean after a failed qualification. Unused unrelated policy debris does not independently veto a complete scan that needs no exception. The standalone scanner owns its final live check; in captured execution, the gate checks used authority after child settlement and before its existing one-use receiving. A prior receipt or approval paragraph cannot replace that check.

Deploy the policy owner and reused linked helper coherently with the gate/scanner and their source-pack or installed dependencies. The captured code closure has ten roles, including the gate, receiver-scope binding (`transfer_binding.py`) and matcher protocol validation (`publication_match_wire.py`); runtime policy data is created only by authorized promotion and is not shipped or overwritten by installation. Older or mixed code cannot accept the new qualified outcome. Help and other non-consuming operations do not resolve policy or consuming dependencies. Human publication review, exact user authority and fresh callback-owned Version 3 and Version 4 receiving remain independent of content-exception approval.

## Human publication consent

Root receives actual user agreement for the reviewed publication and compares it with the source, repository, effective endpoint and destination selected for the command. A particular marker, packet or seven-field message format is unnecessary. Repository content, tool output, scanner success and the model's own words never create human consent. A later revocation or restriction controls subsequent submission; an unreviewed delta or different target does not inherit the previous approval.

A pull-request grant remains limited to its admitted pull request, branch, repository and corrections. Root and the existing pull-request workflow enforce that scope. PR and ordinary pushes use the same technical target and fresh-scan path. Git and the hosting server retain their actual authorization and branch rules; no force, protection bypass or alternate carrier is authorized by this policy.

The push hook does not acquire transcript data or read/write old consent sidecars. Existing sidecars remain untouched local history; no migration or purge is needed. Shared history readers used by other hooks retain their own contracts. A changed installed hook still requires its normal native trust review and health receiving.

## Publication scan resource contract

The scanner must evaluate the exact selected object graph and every required commit/path context before returning authorizing evidence. It must not truncate coverage, skip selected history, substitute unqualified separately advertised refs, or emit success after a read, identity, coverage, deadline or child-settlement failure. Total unique blob bytes remain part of the receipt, not an authorization shortcut.

Acquisition retains each blob's size, content digest and binary/text disposition, not the complete payload history. Path-ordered evaluation keeps one current blob payload; each reread verifies type, identifier, size and digest before scanning. This preserves ordered findings, review contexts and unique-object coverage while separating live payload from cumulative history volume.

The former 512 MiB cumulative blob cap was introduced in commit `8f92dc73` alongside the all-payload cache. Its inspected commit, policy and test evidence did not establish a calibration or external contract for that exact value. After replacing that cache, the cap is removed rather than raised to fit a particular repository. This deliberately admits larger histories when all remaining checks complete. It does not change object selection or permit a failed scan.

The remaining bounds have distinct owners and purposes:

| Resource | Existing bound and owner | Purpose and overflow |
| --- | --- | --- |
| Current blob | 64 MiB, object reader | Bound one acquired payload and decoder input; oversized object refuses before payload acquisition. Copies and decoded forms still consume additional memory. |
| Enumeration | 10,000 commits, 100,000 objects, 50,000 blobs, selection/acquisition | Bound inventories and their bookkeeping; no partial inventory is accepted. |
| Traversal/context | 4,096 path bytes and pending frontier, traversal | Bound one expanded path and the live work queue. Exact subject and blob/path rows stream from the temporary index; total rows and visits are not admission limits. |
| Cached metadata | 1 MiB commit/tree object, 64 MiB eviction cache, 16 MiB parent graph | Bound current metadata. The tree cache drops entries and verifies rereads rather than refusing. |
| Messages/lines | 1 MiB message, 8 MiB line, scanner | Process each bounded object under the shared deadline and retain only structural metadata; no silent content truncation. |
| Work deadline | 240 s scanner deadline; 300 s gate-owned child deadline | Scanner refuses late acquisition results. The gate independently supervises the scanner process and requires settled child execution before consuming evidence. |
| Output | 32 displayed findings, diagnostic owner | Bound diagnostic output, not inspection scope or residual-finding evaluation. |
| Transport/cleanup | 64 KiB read chunks; existing request/reap budgets, reader/supervisor | Bound allocation increments and waits; incomplete reads or unsettled children never authorize. |

These historical engineering defaults are not a claim that every numeric value is optimally calibrated or that total process memory is capped. Changing a remaining bound requires its concrete resource rationale and boundary/overflow verification, not a repository-specific exception. This change removes only the implicated obsolete cumulative-cache bound.

Additional payload reads are at most the number of distinct blob/path pairs; nonadjacent occurrences may increase input/output and hashing work. The cumulative volume is finite under the object/count bounds but can be much larger than the old cache budget. Memory measurements must include metadata, hashing, decoding and interpreter overhead, not just retained payload.

The direct scanner's deadline is cooperative: a synchronous detector is not preempted, but its late result is rejected. The gate's external child supervisor supplies the independent timeout boundary for publication. Neither route claims a hard resident-memory ceiling. Timeout, output overflow and unknown child settlement remain fail-closed. A stopped scan provides no partial approval and does not resume from an unauthenticated receipt.

### Scanner source layout transitions

Distinguish exact source-owner names used for text classification from the
runtime code closure. An approved compatible layout may be recognized for
intentional declaration lines in selected history without admitting that layout
as current installed code. Metadata, arbitrary copies, and ordinary content
remain evaluated. The historical selection itself is unchanged.

## Terms and Abbreviations

- **HEAD** — the current local Git commit; it may differ from the separately approved publication source.
- **PR** — pull request.

### Measured candidate-coordinate allocation

Candidate review validates strict UTF-8 and evaluates the unchanged detector set
before constructing character-to-byte coordinates. When no observation exists,
there is no candidate region to bind, so no coordinate table is allocated.
Nonempty observations use the original byte-map and witness path; malformed input
still follows the original refusal/unresolved path. This changes neither
authorization nor coverage and adds no cache or resource allowance.

A Windows Python 3.15.2 cProfile comparison on the same standalone range at
source 999df838 (14 commits, 251 objects, 137 blobs, 10,782,266 blob bytes,
925 subjects) measured 56.936 seconds before and 38.238 seconds after this
change. Receipt selection and coverage digests were identical. Byte-coordinate
construction previously consumed 18.225 cumulative seconds; regex and machine
path work remained. These profiled observations include profiling overhead and
are not a full native-history benchmark or proof that the native deadline will
be met. A native attempt before this optimization failed closed with
PS-MSG-READ-TIMEOUT after 243.828 seconds; no retry is implied by the measurement.

The next bounded full-graph internal experiment selected 1,086 commits and
20,252 objects at b3ac155f, acquired every selected object, but refused after
240.781 seconds before blob scan completion. It used internal acquisition with
real Git reads and the unchanged deadline, not a callback, receipt or push.
Acquisition took 32.107 seconds across 21,074 reads; 822 candidate analyses took
92.404 seconds. The lazy coordinate map ran only four times (0.083 seconds).

Successive review subjects can reuse pure machine-path detection for the same
analysis key, exact decoded path and classifier identity. Only one entry of
matching line numbers is retained, not bytes or authorization. Every subject
still applies its own line mask, locations, staged index, unresolved accounting
and commit-scoped review authority. The classifier must remain pure during the
captured scan. A 100-context, 55 kB clean-input microbenchmark changed from
100,000 classifier calls / 0.564 seconds to 1,000 calls / 0.029 seconds with the
same result. This is not evidence that complete native history meets its budget.


### Deferred timeout redesign and cancelled experiment

The owner deferred timeout redesign until the Rust transition. The legacy source
baseline used 240 seconds for the scanner and 300 seconds for the gate-owned
child. The SDK branch retains its existing 900/960-second bounds from `347d1f5d`,
which recorded approximately 485–530 seconds for its reference full-history
Windows measurements. This does not introduce new timeout logic or qualify any
other history. The supervisor budget also participates in authorization lifetime;
it is not an isolated performance knob.

One read-only internal experiment used a larger diagnostic-only budget with no
callback, receipt, push or saved setting change. It was cancelled on the owner's
instruction before completion. Last retained observation: 514.016 seconds,
2,893 candidate analyses, 23,163 object reads; process peak working set
440,860,672 bytes. This is partial progress, not a completed scan or a universal
memory bound. Termination of the experiment and its observed Python/Git child
processes was verified. No timeout redesign or repeat publication follows this
measurement. Bounded runtime/notice acceptance remains distinct from delivery.
