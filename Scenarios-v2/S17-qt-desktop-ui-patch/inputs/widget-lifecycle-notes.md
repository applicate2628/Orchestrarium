# Widget Lifecycle Notes

The dialog instance may be reused for a different preset name instead of recreated from scratch.

`prepare_for_reopen(suggested_name)` is the lifecycle seam for this scenario. After it runs:

- previous accept or reject state should be cleared
- the new suggestion should be loaded through the same validation path as live edits
- stale validation errors should not remain visible if the new suggestion is valid
- keyboard focus should return to `name_edit`

The benchmark is intentionally checking lifecycle behavior in the widget seam itself, not in a
separate presenter, browser wrapper, or model/view layer.
