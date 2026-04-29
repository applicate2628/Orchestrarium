# Scoring Anchors

Binary PASS requires the completed report to match all exact finding tuples, avoid false positives,
and end with a `REVISE` gate decision. A wrapper/runtime failure is not a model fail unless the
candidate produced a scoreable report and the verifier failed that report.
