# Failure Mode Notes

- current draft treats any partial table write as a recoverable warning instead of a publish stop
- retry logic is described, but the packet does not define idempotent promotion boundaries
- no one has specified what should happen when only one provider row is stale
