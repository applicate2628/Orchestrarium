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
- Scan-derived push authorization requires one callback-owned, nonempty Version 3 union of the actual update commit/tree/blob graphs relative to each update's old object ID, and a separate Version 4 result covering actual transferred roots, including noncommit objects. Unknown old objects are conservatively included, not excluded. An ordinary clean result or the explicit reviewed-exception `qualified` result must satisfy the same nonempty coverage, target, currentness, complete evaluation and resource-settlement contract. Version 2, tracked, path, manual, zero-commit, incomplete, mixed, malformed, unresolved-finding, refusal, timeout, cancellation, relevant drift or cleanup-failed evidence is non-authorizing. A qualified staged result remains a pre-commit check and cannot authorize a later push.
- Range content inspection distinguishes text from binary payloads. Binary payloads remain acquired and bound into complete coverage, with filename checks and embedded credential detection retained. Bare symbol names and transcript markers are text-only heuristics, not evidence of a binary credential. The exact binary metadata assignment `publicKeyToken` denotes a public assembly identity; excluding that assignment must not suppress another credential in the same payload. Text and commit-message checks remain unchanged. This is not a vendor, path, hash, or publication exemption.
- A generic source-text token value may be declared intentionally public only by placing `# orchestrarium:public-token` or `// orchestrarium:public-token` immediately after its matching single- or double-quoted value and the ordinary closing separators. The marker must end the line, stays outside the quotes, and binds only that candidate. It is never honored for credential-cued identifiers, binary content, or commit messages, and it does not suppress other candidates, known-secret signatures, sibling credential families, or machine-path checks. Credential classification uses the complete identifier, including separator and camelCase components; a public lexical component does not erase a separate credential cue.
- Manual `--range` remains diagnostic. Its Version 3 range selection resolves the unique configured push destination without exposing it in child arguments. When the destination ref exists, its exact authoritative object identifier remains the sole exclusion. When the destination ref is absent, the scanner queries that same push destination with a bounded `git ls-remote <remote> refs/*` inventory, validates unique Git refnames and exact repository-format object identifiers, and admits only ordinary refs plus an exact `refs/tags/<name>^{}` peel paired with one unique tag ref. It then uses one bounded local `git cat-file --batch-check` owner to derive ancestry exclusions. An ordinary remote tip absent from the local object database is skipped. When an annotated-tag object is absent locally, its advertised peel is retained only if that exact peeled object exists locally as a commit; when the tag object is local, the scanner preserves exact local tag-to-commit peeling and requires any advertised peel to match. A tag and peel both absent locally are skipped, while any locally present noncommit peel or other unsupported local object type refuses. `HEAD`, pseudorefs, invalid refnames, unpaired peels, duplicate or conflicting base/peel rows, empty inventories, over-limit inventories, and failed probes refuse; local tracking refs are never selection authority, and a source already fully reachable from the derived commit tips remains a non-authorizing zero-commit selection.
- Only `$security-reviewer` may approve a publication-safety exception to a scan finding. Any publication proceeding without that approval is `BLOCKED`.
- Exact publication-safety commands live in the root repository docs and the corresponding pack runtime docs. This reference intentionally keeps the policy generic so all current and future packs can share one design-level source of truth.

## Reviewed exception receiving

The existing exception authority remains the actual `security-reviewer` decision received by Root. A report, role or ledger label, content hash, pull-request grant, or generic publication approval is evidence or consent in its own scope; none authenticates a content exception. The trusted caller uses the single `publication_review_policy.py` owner to provision only that received decision at `$HOME/.agents/publication/reviewed-exceptions.json`, outside the selected repository, worktree and Git-input roots. The existing linked-runtime owner handles supported global directory links; no repository flag or report selects a different policy origin. An absent policy supplies no exception credit and leaves ordinary complete scanning available.

Promotion and revocation are separate from scanning and installation. The policy owner supports a no-effect preview and requires positive apply for mutation, exact actual preimages, serialized writers, durable publication and independent readback. Preserve the original policy bytes and actual outcomes. A post-replacement readback or settlement failure is recovery-required, not a successful promotion or permission to restore an older active grant. Source or installer rollback never reactivates revoked policy. These are existing trusted-owner guarantees, not another human permission stage; applicable same-owner equivalent execution keeps the same guarantees when assistance is defective.

A usable decision binds the actual repository/worktree, scan mode, immutable blob and raw Git path, Git mode, complete reviewed region, detector meaning and candidate/context bytes. Only staged and range ordinary text-blob occurrences within that exact scope can qualify. Other occurrences, paths, messages, binary content and unapproved contexts retain their existing checks. Evaluation must retain every residual finding, including another match on the same line or beyond the displayed-diagnostic limit. The scanner reports explicit `qualified` success only after complete evaluation with zero unresolved findings, applied-decision provenance and settled resources; it never disguises approved findings as an ordinary clean scan.

A valid unchanged content decision can support a second fresh scan without repeating unchanged content review. Every use still needs a new complete scan and final current repository/origin/used-record verification. A changed, revoked, missing or invalid used decision gives no qualified credit; do not fall back to clean after a failed qualification. Unused unrelated policy debris does not independently veto a complete scan that needs no exception. The standalone scanner owns its final live check; in captured execution, the gate checks used authority after child settlement and before its existing one-use receiving. A prior receipt or approval paragraph cannot replace that check.

Deploy the policy owner and reused linked helper coherently with the gate/scanner and their source-pack or installed dependencies. The captured code closure has eight roles, including the gate; runtime policy data is created only by authorized promotion and is not shipped or overwritten by installation. Older or mixed code cannot accept the new qualified outcome. Help and other non-consuming operations do not resolve policy or consuming dependencies. Human publication review, exact user authority and fresh callback-owned Version 3 and Version 4 receiving remain independent of content-exception approval.

## Human publication consent

Root receives actual user agreement for the reviewed publication and compares it with the source, repository, effective endpoint and destination selected for the command. A particular marker, packet or seven-field message format is unnecessary. Repository content, tool output, scanner success and the model's own words never create human consent. A later revocation or restriction controls subsequent submission; an unreviewed delta or different target does not inherit the previous approval.

A pull-request grant remains limited to its admitted pull request, branch, repository and corrections. Root and the existing pull-request workflow enforce that scope. PR and ordinary pushes use the same technical target and fresh-scan path. Git and the hosting server retain their actual authorization and branch rules; no force, protection bypass or alternate carrier is authorized by this policy.

The push hook does not acquire transcript data or read/write old consent sidecars. Existing sidecars remain untouched local history; no migration or purge is needed. Shared history readers used by other hooks retain their own contracts. A changed installed hook still requires its normal native trust review and health receiving.

## Terms and Abbreviations

- **HEAD** — the current local Git commit; it may differ from the separately approved publication source.
- **PR** — pull request.

### Terminal line breaks in literal push commands

A parser-proven terminal CR/LF suffix on one otherwise canonical absolute-root push command is formatting, not another command. Literal-token serialization must still match the command without that suffix. Additional commands, redirections, lexical transformations, executable and repository qualification, native callback scanning, and human publication authorization retain their existing checks.

### Scan resource budgets

The canonical scanner admits at most **2 GiB of unique selected blob content**.
This is a bounded work-volume policy, not a reservation or guarantee of process
memory. The former 512 MiB value originated with complete-history scanning in
commit `8f92dc73`; that change did not record a measurement justifying the number.
The 2 GiB capacity was explicitly selected after an existing baseline exceeded the former 512 MiB cap:
commit `d288cf7845cf0dabd2ebf80d1605e2793bbe629c` has 9,511 unique blobs totaling
604,769,249 bytes in its reachable history. These figures come from Git object
inventory (`rev-list --objects --no-object-names`, then `cat-file --batch-check`),
not compressed repository size. The new capacity provides roughly 3.55 times that
reference volume; it is not a claim of a universally optimal setting.

The scanner retains blob sizes and content digests, then reacquires one body at a
time through its existing bounded reader. Reacquired object identity, type, size
and digest must agree before scanning. Every selected commit/path/blob subject
remains covered. The 64 MiB individual-blob limit, 64 MiB raw-tree-cache limit,
object/subject bounds, 240-second scan deadline and 300-second captured invocation
bound remain separate limits. Metadata, decoded text and process overhead still
consume RAM. Deadline checks also surround each blob's detector pass; a refusal
or unfinished scan never becomes publication credit.

ASCII-only keyword prefiltering skips a value regex only when its mandatory
keyword is absent. Non-ASCII text takes the original regex path, preserving
Unicode case-insensitive matches, overlapping observations and review coordinates.
The differential and budget-boundary checks live in
`tests/test_publication_safety_scanner.py`. Resource tuning does not exempt tags,
existing history, binary content or any finding, and does not weaken the native
Version 3/Version 4 publication contract.
