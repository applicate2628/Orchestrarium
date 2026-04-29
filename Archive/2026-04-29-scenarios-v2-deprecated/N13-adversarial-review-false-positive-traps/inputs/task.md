Role: `$architecture-reviewer`

Goal: produce an adversarial findings-only review for the routing result summarizer.

Edit only `candidate/review-report.md`.

Find the real blocking risks. Avoid reporting harmless UI helper styling as a finding.
Also inspect `candidate/review-target/routing/sample_rows.py` and report the composed causal path
when local classification, timeout labeling, and lane summarization corrupt the final scoreable read.

Each finding must be a separate bullet with these labels:

- `Mechanism:`
- `Impact:`
- `Fix:`
- `Regression:`

The report must contain exactly five findings.

The report must also include `## Scoreability Causal Ledger` with this exact table header:

`| Source signal | Local wrong class | Correct class | Downstream score impact | Owner fix |`

Use that ledger to show how `retry_policy.py`, `lane_summary.py`, and `sample_rows.py` compose into
the final scoreability corruption. Keep the ledger inside review output; do not edit the reviewed
code.
