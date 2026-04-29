# Visual Acceptance Notes

The dashboard can ship only if these release invariants hold:

- tables, inspector panes, banners, toasts, and sticky regions do not cover actionable content
- disabled action controls are visibly disabled
- keyboard focus indicators are fully visible
- required warning and validation text remains readable and unobscured
- selected navigation state is visible without inspecting DOM attributes
- loading placeholders reserve enough space to avoid noticeable layout jumps

The team intentionally accepts:

- icon-only buttons when the visual target is clear and labels/tooltips exist
- decorative background grids that do not cover content or take pointer events
- muted timestamp metadata that is not required for task completion
