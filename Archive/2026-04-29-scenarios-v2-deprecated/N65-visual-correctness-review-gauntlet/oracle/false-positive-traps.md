# False-Positive Traps

Do not score these as defects:

- The refresh icon-only button has `aria-label` and `title`, and the visual target is acceptable.
- The decorative grid is hidden from assistive tech, has no pointer events, and does not cover
  content.
- The muted timestamp metadata is intentionally low emphasis and is not required warning or action
  text.
