# Decoy Map

These files are intentionally present but out of scope:

| Path | Why it looks relevant | Why it is not the owner |
|---|---|---|
| `candidate/workspace/docs/legacy-profile-notes.md` | mentions the old singular profile field | documentation is stale and must not override runtime config ownership |
| `candidate/workspace/legacy/legacy_score.py` | contains denominator math | legacy helper is archived compatibility material, not the live scorecard owner |
| `candidate/workspace/ui/chip_labels.py` | contains visual labels for timeout and fail states | UI labels do not own scoreability or routing semantics |
