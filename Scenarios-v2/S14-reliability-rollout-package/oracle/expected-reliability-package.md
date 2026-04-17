# Expected Reliability Package Read

- the package should distinguish preview publish from promotion publish
- partial table writes should be treated as blocking failures, not harmless warnings
- rollback must restore the last fully consistent publish packet
- stale provider rows may degrade preview output but require explicit promotion blocking or policy
