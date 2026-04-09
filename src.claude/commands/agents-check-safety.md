# Publication Safety Check

Scan staged files for secrets, credentials, and sensitive data before commit or push.

## Steps

1. Run: `bash .claude/agents/scripts/check-publication-safety.sh`
2. Read the output and present results to the user.
3. If any issues found:
   - List each finding with file path and matched pattern
   - Suggest whether it's a real leak or a false positive
   - Recommend fix (remove, redact, add to .gitignore, or mark as false positive)
4. If clean, confirm it's safe to proceed.

## Arguments

If `$ARGUMENTS` is provided, pass it through:
- `--path <path>` — scan a specific path instead of staged files

## Rules

- This is a read-only check — do not modify any files.
- Run from the repository root.
- On Windows, if bash is not available, fall back to: `powershell -ExecutionPolicy Bypass -File .claude/agents/scripts/check-publication-safety.ps1`
