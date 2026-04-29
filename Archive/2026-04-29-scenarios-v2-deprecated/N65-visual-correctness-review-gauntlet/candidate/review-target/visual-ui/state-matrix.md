# UI State Matrix

| State | Expected visual invariant |
|---|---|
| Desktop table with inspector open | Row actions must remain visible and clickable; inspector may not cover table content. |
| Mobile topbar and status banner | Sticky regions must stack without hiding banner text. |
| Disabled publish action | Disabled controls must be visually distinct from enabled primary actions. |
| Keyboard focus inside cards | Focus indicators must remain fully visible and not be clipped by parent containers. |
| Warning copy | Required warning text must meet at least 4.5:1 contrast for normal-size text. |
| Mobile form with toast | Toasts may not cover validation messages or the active input area. |
| Tabs | Selected and unselected tabs must have a visible non-color-only state difference. |
| Loading skeleton | Loading placeholders must reserve stable space for populated content. |
