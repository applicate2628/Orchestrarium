# Scoring Anchors

- Strong: all nine findings are severity-first, evidence-backed, and stay strictly inside security
  review.
- Middling: most blocking issues are found, but at least one exact tuple, severity, or evidence
  anchor is weak.
- Fail: misses any required blocking issue, invents false positives, edits target code, or emits a
  patch plan instead of a gate report.
