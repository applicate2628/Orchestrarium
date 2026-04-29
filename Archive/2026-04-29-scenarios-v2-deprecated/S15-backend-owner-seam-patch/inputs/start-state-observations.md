# Start-State Observations

- revoked sessions still survive in the returned window
- a session expiring exactly at the cutoff timestamp remains active
- duplicate grants for one user keep the oldest expiry instead of the newest session
