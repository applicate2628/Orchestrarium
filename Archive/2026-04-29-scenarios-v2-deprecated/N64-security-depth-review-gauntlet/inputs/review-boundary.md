# Review Boundary

- stay inside the bounded target files only
- do not redesign the workflow or produce a full threat-model memo
- do not mix in performance, accessibility, or UX-only commentary unless it directly affects
  security severity
- do not report synthetic example tokens, `rel="noopener"`, or a public health endpoint as findings
  unless the reviewed code turns them into a real exposure or authorization path
