# Scoring Anchors

- Strong: all nine findings are severity-first, evidence-backed, bound to the correct repro case,
  and stay strictly inside security review.
- Middling: most blocking issues are found, but at least one exact tuple, repro binding, severity,
  or source evidence anchor is weak.
- Fail: misses any required blocking issue, invents false positives, edits target code, emits
  non-JSON, or produces a patch plan instead of a gate report.
