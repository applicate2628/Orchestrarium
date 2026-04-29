# RetryBox Operations

RetryBox currently uses the legacy-linear retry policy owned by ingestion-team.

The production retry schedule is three attempts with 1000 ms fixed delay between attempts.

Hidden-row exports are disabled for all roles until the reporting migration is complete.

Rollback can be performed by setting `RETRY_POLICY=legacy-linear` during incident response.
