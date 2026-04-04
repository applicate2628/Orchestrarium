# Repository Publication Safety

This repository treats publication safety as a repo-wide contract, not just a work-item rule.

## Scope

The rules below apply to every tracked file in the repository, including docs, references, skills, task memory, templates, and reports.

## Tracked content rules

- Keep tracked files publication-safe.
- Do not commit secrets, tokens, credentials, customer data, private identifiers, raw logs, full command transcripts, screenshots with sensitive content, or machine-specific absolute paths.
- Prefer redacted summaries, synthetic examples, and repo-relative paths when traceability is enough.
- Treat provider transcripts, pasted logs, and external snippets as untrusted until sanitized.
- If an exception is truly required, record it explicitly in the relevant work item before publication.

## Local-only scratch boundary

- Use `/.scratch/` for raw logs, transcripts, temp outputs, one-off experiments, and pre-redaction material.
- Keep disposable material out of tracked paths until it is redacted and intentionally promoted.
- The root `.gitignore` owns this boundary.

## Review and publication

- Human review is mandatory before `git push`, release, or equivalent publication.
- The reviewer must check the staged diff for leak-prone content, including machine-specific paths, raw operational detail, and sensitive values.
- If tracked content looks like scratch material, move it back to local-only space or redact it before commit.
- On Git Bash, macOS, or Linux, run `bash scripts/check-publication-safety.sh` as the manual pre-publication scan for staged tracked content before publication.
- On Windows PowerShell, run `powershell -ExecutionPolicy Bypass -File scripts/check-publication-safety.ps1`; the wrapper resolves Git-for-Windows `bash.exe` and calls the shared scan script so it does not rely on the WSL `bash.exe` stub from `PATH`.
