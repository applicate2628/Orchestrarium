# N09 Candidate: Autonomous Resume And Path Recall

Fix the resume/path-recall helper without widening scope.

Only this file should change:

- `workspace/src/workspace/recallWorkspaceRootAfterEdit.js`

Do not edit:

- `workspace/src/runPathRecallTask.js`
- `workspace/src/ui/recallWorkspaceRootAfterEdit.js`
- `docs/project-mirror/**`
- `legacy/project-copy/**`
- tests or scripts

Run from `workspace/`:

- `node --test`
- `node scripts/verify-path-recall.js`
