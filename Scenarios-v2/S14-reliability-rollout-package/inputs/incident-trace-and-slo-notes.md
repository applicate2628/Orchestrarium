# Incident Trace And SLO Notes

- preview publishes must stay reversible until an approver promotes the packet
- one recent run wrote the role table but skipped the caveat table after a partial failure
- another run retried the whole publish and duplicated the preview artifact instead of replacing it
- operators want a rollback path that is explicit when one provider row is stale or missing
