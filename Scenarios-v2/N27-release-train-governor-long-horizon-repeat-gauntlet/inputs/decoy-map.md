# Decoy Map

| Path | Why it is a decoy |
|---|---|
| `candidate/workspace/docs/freeze-window-migration.md` | describes a deprecated freeze migration and must not own current scheduling |
| `candidate/workspace/legacy/dedupe_v1.py` | dedupes by request id only for archived imports |
| `candidate/workspace/ui/release_badges.py` | maps deployment statuses to display labels only |

Fix the owned deploygrid modules instead of adapting these decoys.
