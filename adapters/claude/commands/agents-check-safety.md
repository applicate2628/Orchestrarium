# Publication Safety Check

Scan staged blobs before commit, or the exact unpublished commit range before push.

## Steps

1. Before commit, run: `bash .claude/agents/scripts/check-publication-safety.sh`.
2. After the final commit, optionally run the diagnostic range check: `bash .claude/agents/scripts/check-publication-safety.sh --range <remote> <dst>`. At push evaluation the gate runs its own fresh canonical range scan; this manual result cannot mint authorization.
3. Read the output and present results to the user.
4. If any issues found:
   - Report only the stable failure identifier, subject kind, sanitized locator or commit object identifier, line, and detector class
   - Never request or echo the matched value, raw message, full machine path, command, or subprocess output
   - Recommend fix (remove, redact, add to .gitignore, or mark as false positive)
5. Treat all command output as diagnostic. Only the gate's direct bounded child result from its canonical sibling can authorize a pending push.

## Arguments

If `$ARGUMENTS` is provided, pass it through:
- `--path <path>` — scan a specific path instead of staged files
- `--range <remote> <dst>` — after the final commit, scan the exact commit set and commit messages intended for that push

## Rules

- This is a read-only check — do not modify any files.
- Run from the repository root.
- A manual v2 range receipt does not replace human review and is not gate authorization evidence.
- It covers selected commit messages and current-tip blobs, not repository identity, remote URL/server freshness, or other Git metadata.
- On Windows PowerShell, run the shipped Python entrypoint: `python .claude/agents/scripts/check-publication-safety.py`
