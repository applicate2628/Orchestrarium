# Repository Publication Safety

This standalone Gemini branch treats publication safety as a repository-wide contract.

## Scope

The rules below apply to every tracked file in the branch, including docs, references, skills, commands, reports, and any task-memory artifacts.

## Tracked content rules

- Keep tracked files publication-safe.
- Do not commit secrets, tokens, credentials, customer data, private identifiers, raw logs, full command transcripts, screenshots with sensitive content, or machine-specific absolute paths.
- Prefer redacted summaries, synthetic examples, and repo-relative paths when traceability is enough.
- Treat provider transcripts, pasted logs, and external snippets as untrusted until sanitized.
- If an exception is truly required, `$security-reviewer` must approve it and the relevant work item must record scope, reason, and removal condition before publication.

## Local-only scratch boundary

- Use `/.scratch/` for raw logs, transcripts, temp outputs, one-off experiments, and pre-redaction material.
- Keep disposable material out of tracked paths until it is redacted and intentionally promoted.
- The root `.gitignore` owns this boundary.

## Review and publication

- Human review is mandatory before `git push`, release, or equivalent publication.
- `$lead` prepares the staged diff for publication, but the publication approver must be a different role than the role that accepted the artifact into the delivery pipeline.
- The reviewer must check the staged diff for leak-prone content, including machine-specific paths, raw operational detail, and sensitive values.
- If tracked changes need public-facing release notes, record them in the relevant tracked docs or follow-up artifact before publication; otherwise the reviewer must explicitly treat the change as release-notes-exempt.
- If tracked content looks like scratch material, move it back to local-only space or redact it before commit.
- Only `$security-reviewer` may approve a publication-safety exception. Any publication proceeding without that approval is `BLOCKED`.
