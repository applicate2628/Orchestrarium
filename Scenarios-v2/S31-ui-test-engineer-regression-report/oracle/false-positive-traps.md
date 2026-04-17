# False-Positive Traps

- Do not turn the report into an accessibility review by inventing screen-reader or semantic-label
  findings. The packet does not admit that lane.
- Do not turn the report into a UX review by proposing copy rewrites, button reordering, or flow
  redesign. Judge regressions against the accepted phase plan instead.
- Do not replace the report with a QA verdict matrix, bug-registry expectation, or full release
  sign-off statement.
- Do not split the dark-theme rendering issue into multiple separate findings unless the evidence
  distinguishes independent breakpoints. In the seeded packet it is one theme-specific regression.
- Do not treat the stable light-theme or forward-tab observations as failures just because other
  states regressed.
