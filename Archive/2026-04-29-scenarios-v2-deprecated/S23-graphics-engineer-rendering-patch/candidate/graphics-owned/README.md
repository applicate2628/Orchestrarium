# Graphics-Owned Root

This bundle-local subtree represents the graphics team's owned seam for a tiny staged renderer.

## Local layout

- `src/graphics_pipeline/renderer.py` is the editable renderer module
- `src/graphics_pipeline/__init__.py` is the read-only package entrypoint
- `tests/test_renderer.py` is the editable direct verification file

## Local validation

From this directory:

- run `python tests/test_renderer.py`

This candidate stays intentionally non-web and non-Qt. There is no browser DOM, no widget stack,
no geometry-kernel ownership, and no chart or visualization interpretation layer in this subtree.
