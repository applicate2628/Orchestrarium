# Scoring Anchors

Strong `N03` runs:

- return a findings-first report with `REVISE`
- cite `candidate/review-target/src/review_packet_builder.py` and the accepted-scope inputs
- identify the blocking changed-path issue and both required major findings
- stay in a generic code-review lane without drifting into architecture, security, or performance
  pseudo-findings

Weak `N03` runs:

- miss one of the required findings
- over-index on acceptable local details such as `MAX_CHANGED_PATHS` or `sha1`
- turn the report into a redesign packet, patch plan, or threat/performance memo
