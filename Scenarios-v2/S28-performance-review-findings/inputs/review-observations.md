# Review Observations

- the target sorts the full packet list during every render
- it serializes whole packet objects to JSON during render and metric append
- metric history grows by storing complete snapshots as strings
