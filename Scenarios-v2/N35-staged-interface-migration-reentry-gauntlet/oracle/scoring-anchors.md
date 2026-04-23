# N35 Scoring Anchors

Score the run as a staged interface-migration task, not as a style rewrite.

- Correctness: structured interfaces, hidden consumer behavior, owner boundaries, and error
  semantics.
- Migration quality: all call sites migrated, old methods removed, no compatibility shims, and
  denied events do not dispatch.
- Re-entry quality: each fresh phase records a durable ledger that the final closeout can
  reconstruct without chat context.
- Review quality: real review findings are accepted and false-positive wrapper/readme requests are
  rejected with owner paths and validation cues.
- Patch quality: changed paths stay within the allowed surface and avoid unrelated churn.
