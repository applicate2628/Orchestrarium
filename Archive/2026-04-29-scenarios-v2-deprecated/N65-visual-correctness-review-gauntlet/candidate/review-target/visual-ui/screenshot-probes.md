# Screenshot Probe Evidence

The probes below summarize deterministic screenshots captured from Chromium with default fonts.
They are immutable review evidence, not suggested fixes.

| Probe ID | Viewport | Observed result |
|---|---|---|
| rightActionsProbe | 1440x900 desktop | The inspector overlaps the rightmost Actions column by 92 px from x=1128..1220 while the table still reports visible width. |
| mobileBannerProbe | 390x844 mobile | The status banner starts at y=0 under the sticky topbar region; 44 px of banner text is hidden behind the topbar. |
| disabledPublishProbe | 1440x900 desktop | The Publish button marked aria-disabled=true has the same blue fill, white text, opacity, and pointer cursor as enabled primary buttons. |
| focusClipProbe | 1440x900 desktop | The Retry window focus outline is clipped on the left and bottom edges by 3 px inside the settings card. |
| warningContrastProbe | 1440x900 desktop | Warning copy text color #b96f00 on #fff7e6 measures 2.8:1 for normal-size text. |
| toastFieldProbe | 390x844 mobile | The fixed toast covers the handoff validation message and lower 28 px of the textarea at the bottom of the form. |
| tabStateProbe | 1440x900 desktop | Active and Muted tabs differ by deltaE 1.1; selected state is not visible without reading aria-selected. |
| skeletonShiftProbe | 1440x900 desktop | The summary skeleton reserves 0 px before data load and causes a 64 px downward layout shift when populated. |

False-positive calibration:

- `icon-button` has both `aria-label` and `title`; the icon-only refresh control is not a visual bug.
- `decorative-grid` is aria-hidden, pointer-events none, and not in the task flow; do not report it.
- `muted-meta` is low-priority timestamp metadata, not required warning or action text.
