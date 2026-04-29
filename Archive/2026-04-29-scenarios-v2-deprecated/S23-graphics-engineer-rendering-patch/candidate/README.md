# Candidate Root

This is the mutable run root copied for each scored execution.

The start state is intentionally wrong for rendering-pipeline work. The local renderer in
`graphics-owned/` sorts transparent draws in the wrong direction, lets transparent draws stamp the
depth buffer, and treats additive emission as ordinary alpha compositing.

## Editable files

- `graphics-owned/src/graphics_pipeline/renderer.py`
- `graphics-owned/tests/test_renderer.py`

## Read-only context inside the candidate root

- `graphics-owned/README.md`
- `qt-preview-pane/`
- `web-preview-shell/`
- `geometry-kernel/`
- `visualization-lab/`

The intended repair path is to keep the change inside the graphics-owned seam and its direct test
file only.
