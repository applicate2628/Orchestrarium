# Decoy Map

| Path | Why it is a decoy |
|---|---|
| `candidate/workspace/docs/rollback-notes.md` | contains outdated rollback advice from an earlier design |
| `candidate/workspace/legacy/retry_runner.py` | sorts retry rows for display-only batch archives |
| `candidate/workspace/ui/status_badges.py` | maps report labels to badges but does not own execution semantics |

Fix the owned implementation modules instead of adapting these decoys.
