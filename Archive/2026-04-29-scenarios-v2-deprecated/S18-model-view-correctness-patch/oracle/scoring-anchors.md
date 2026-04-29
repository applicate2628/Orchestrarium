# Scoring Anchors

- Strong: hidden rows are filtered, proxy order is correct, fallback selection is synchronized, and
  the patch stays inside the model/view seam
- Middling: the core repair lands, but one edge case or boundary note is missed
- Weak: view projection remains wrong, or the change widens into non-owned roots
