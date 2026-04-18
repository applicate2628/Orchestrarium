# Prohibited Patterns

The following patterns should lose major points in `N02`:

1. treating the scenario as a static hierarchy problem while leaving interruption behavior vague
2. writing a generic user-journey narrative with no explicit state model or ownership
3. proposing component trees, route layouts, widget classes, or API payloads instead of UX
   structure
4. writing an architecture ADR, dependency memo, or implementation plan instead of a UX brief
5. producing review findings, severity-ranked bugs, or accessibility-audit language instead of a
   forward-looking design brief
6. collapsing all interruptions into one generic `needs work` state
7. allowing publish to appear available while a return loop or blocking question is still open
