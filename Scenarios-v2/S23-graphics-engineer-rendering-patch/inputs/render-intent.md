# Render Intent

`S23` models a tiny staged renderer with integer RGBA frame buffers and axis-aligned rectangle
draws. The intended pipeline contract is:

1. Opaque draws establish the base color and update the depth buffer.
2. Transparent draws run after opaque content, sort back-to-front, blend with alpha-over, and do
   not write depth.
3. Additive draws run after the transparent stage, keep the depth test, and add emissive light into
   the current color buffer instead of replacing or alpha-overing it.

The oracle cases are intentionally small, but they still represent graphics-pipeline behavior rather
than UI interactions, geometry predicates, or visualization semantics.
