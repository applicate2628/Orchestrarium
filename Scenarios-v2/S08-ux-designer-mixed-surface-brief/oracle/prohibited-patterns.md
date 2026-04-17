# Prohibited Patterns

The following patterns should lose major points in `S08`:

1. collapsing the problem into a desktop-only or web-only redesign when the mixed surface is the
   point of the scenario
2. proposing component trees, route layouts, Qt widget classes, or API payloads instead of UX
   structure
3. writing an architecture ADR about tool ownership or dependency direction rather than an
   interaction-design brief
4. producing review findings, severity-ranked usability bugs, or accessibility-audit language
   instead of a forward-looking design brief
5. keeping state ownership implicit or failing to explain the change-request return loop
6. treating publish as always available even when web review blockers remain unresolved
7. rewriting the task as generic product prose without a concrete desktop-plus-web flow
