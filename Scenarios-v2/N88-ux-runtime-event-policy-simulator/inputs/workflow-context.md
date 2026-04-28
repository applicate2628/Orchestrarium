# Workflow Context

ConsoleShip publishes release packets after local checks, remote review source, owner assignment,
risk signoff, and regression proof are all ready.

Auditors can export a scoped copy that hides owner-only notes. That export is not a publish action.

After publish, a follow-up diff re-enters review. The receipt must remain visible while the next
dominant action shifts to reviewing the diff.
