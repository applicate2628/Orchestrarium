# Bounded Scope

- The visible slice is `candidate/repo-snapshot/` only: `config/defaults.py`, `config/effective.py`,
  `pipeline/scorer.py`, and `docs/legacy-config.md`.
- Answer only for the batch pipeline (`pipeline/scorer.py`).
- The override SOURCE (which env var or CLI flag selects the batch profile) is not in the slice; treat
  it as an explicit unknown rather than guessing.
- Whether other, non-batch pipelines exist or override differently is not in the slice; explicit unknown.
