# Rollout Envelope

- preview publish may be retried, but promotion must be explicit and single-write
- rollback must restore the last fully consistent publish packet
- stale provider rows may degrade the preview, but must not silently reach promotion
