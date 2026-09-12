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

- Human review is mandatory before `git push`, release, or equivalent publication.
- `RELEASE_NOTES.md` is the canonical tracked release log for this repository.
- Keep `RELEASE_NOTES.md` in reverse-chronological `## YYYY-MM-DD` sections. New release-relevant notes belong under the current date heading, or under a newly created heading for today's date if that heading does not exist yet.
- Default publication-gate approver is `$knowledge-archivist`.
- `$lead` is the primary operator of the publication-safety scan and prepares the staged diff for publication, but the publication approver must be a different role than the role that accepted the artifact into the pipeline.
- The reviewer must check the staged diff for leak-prone content, including machine-specific paths, raw operational detail, and sensitive values.
- If staged tracked changes are release-relevant, the staged diff must also contain the matching `RELEASE_NOTES.md` update before publication, and that entry must explain the practical effect of the change rather than only naming it. If no explanatory entry is present, the reviewer must explicitly determine that the change is release-notes-exempt; otherwise publication is `BLOCKED`.
- If tracked content looks like scratch material, move it back to local-only space or redact it before commit.
- `$security-reviewer`, `$knowledge-archivist`, or another relevant reviewer may also run the scan as part of a spot check or publication gate.
- Any author may run the scan as a local self-check, but that does not replace the required human publication review.
- Scan-derived push authorization requires one gate-owned Version 3 range receipt covering the complete unpublished commit/tree/blob graph and every commit/raw-path/blob subject. Version 2, tracked, path, manual, zero-commit, incomplete, mixed, malformed, finding, refusal, timeout, cancellation, drift, or cleanup-failed evidence is non-authorizing.
- Range content inspection distinguishes text from binary payloads. Binary payloads remain acquired and bound into complete coverage, with filename checks and embedded credential detection retained. Bare symbol names and transcript markers are text-only heuristics, not evidence of a binary credential. The exact binary metadata assignment `publicKeyToken` denotes a public assembly identity; excluding that assignment must not suppress another credential in the same payload. Text and commit-message checks remain unchanged. This is not a vendor, path, hash, or publication exemption.
- A generic source-text token value may be declared intentionally public only by placing `# orchestrarium:public-token` or `// orchestrarium:public-token` immediately after its matching single- or double-quoted value and the ordinary closing separators. The marker must end the line, stays outside the quotes, and binds only that candidate. It is never honored for credential-cued identifiers, binary content, or commit messages, and it does not suppress other candidates, known-secret signatures, sibling credential families, or machine-path checks.
- Version 3 range selection resolves the unique configured push destination without exposing it in child arguments. When the destination ref exists, its exact authoritative object identifier remains the sole exclusion. When the destination ref is absent, the scanner queries that same push destination with a bounded `git ls-remote <remote> refs/*` inventory, validates unique Git refnames and exact repository-format object identifiers, and admits only ordinary refs plus an exact `refs/tags/<name>^{}` peel paired with one unique tag ref. It then uses one bounded local `git cat-file --batch-check` owner to derive ancestry exclusions. An ordinary remote tip absent from the local object database is skipped. When an annotated-tag object is absent locally, its advertised peel is retained only if that exact peeled object exists locally as a commit; when the tag object is local, the scanner preserves exact local tag-to-commit peeling and requires any advertised peel to match. A tag and peel both absent locally are skipped, while any locally present noncommit peel or other unsupported local object type refuses. `HEAD`, pseudorefs, invalid refnames, unpaired peels, duplicate or conflicting base/peel rows, empty inventories, over-limit inventories, and failed probes refuse; local tracking refs are never selection authority, and a source already fully reachable from the derived commit tips remains a non-authorizing zero-commit selection.
- Only `$security-reviewer` may approve a publication-safety exception to a scan finding. Any publication proceeding without that approval is `BLOCKED`.
- Exact publication-safety commands live in the root repository docs and the corresponding pack runtime docs. This reference intentionally keeps the policy generic so all current and future packs can share one design-level source of truth.

## Pull-request-scoped repeated publication

A user may replace repeated push confirmations for one concrete GitHub pull request (PR) by sending the standalone marker `[approve-pr-publication]`, either raw or inside one balanced pair of single backticks or double asterisks. Outer whitespace is ignored; proposals, examples, extra text, fenced or malformed wrappers, assistant text, tool output, and compaction summaries never grant.

Only a marker in the current genuine-user turn may initialize the transcript-adjacent binding record. The pending push supplies the verified Git repository root, remote, and head branch; exactly one matching open pull request is then bound. Later pushes must match the stored root identity, remote, pull request, and head branch, and must still pass fresh pull-request, protection, leak-scan, and receipt checks. A historical marker with missing or corrupt state denies as a consent reset. A later exact revoke replaces the stored state with `revoked` before denial.

The following versioned forms remain compatibility input for existing transcripts:

```text
[approve-pr-publication:v1 pr=https://github.com/<owner>/<repo>/pull/<positive-number>]
[approve-pr-publication:v1 pr=<positive-number>]
```

The full URL form, including an equal Markdown link, retains its embedded identity. The numeric shorthand is resolved through a bounded authoritative lookup in the authorization-time repository, and the grant retains the resulting full owner, repository, number, and canonical URL. Missing, ambiguous, or changing authorization-time repository context fails closed; a later push must match the retained identity and cannot reinterpret the number in another repository.

The grant is ephemeral to the readable session transcript and can be revoked by the exact whole message `[revoke-pr-publication:v1]`. Only a genuine user-authored transcript entry can create or revoke it; assistant text, tool output, compaction summaries, repository files, and work-item records are not authorization sources.

The continuing grant replaces only repeated human confirmation. Every push attempt still requires a new non-empty `range` publication-safety receipt bound to the exact remote, full destination ref, and current `HEAD` tip. The gate freshly revalidates the open PR, its base/head repository and ref binding, remote branch object, and destination protection state for each attempt.

The continuing route is deliberately narrower than Git's full branch grammar. The provider head must contain 1–255 ASCII characters drawn only from `A-Z`, `a-z`, `0-9`, `.`, `_`, `/`, and `-`, and it must also pass direct-argument `git check-ref-format --branch`. A simple stored binding accepts one ordinary direct `git push <remote> HEAD:refs/heads/<head>` or `git -C <absolute-root> push <remote> HEAD:refs/heads/<head>` command; quoting every fixed token is not required. Existing Version 1 grants retain their owning shell's canonical literal serialization with an absolute resolved Git executable. Force, delete, tags, wrappers, chained or ambiguous commands, unsafe destinations, drift, stale/reused receipts, and generic fallback remain denied. The existing one-turn `[approve-publication]` marker and all-dry-run behavior remain separate compatibility paths.

## Terms and Abbreviations

- **HEAD** — the current local Git commit selected for publication.
- **PR** — pull request.
