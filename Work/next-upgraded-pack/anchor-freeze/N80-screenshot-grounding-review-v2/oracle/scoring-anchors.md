# Scoring Anchors

This diagnostic follows GUI/web grounding failure modes: element grounding, defect grounding,
coordinate evidence, and resistance to false-positive visual cues.

Research anchors used during design:

- VisualWebBench: web screenshot understanding and grounding tasks.
  `https://visualwebbench.github.io/`
- ScreenSpot-Pro: high-resolution professional GUI grounding.
  `https://arxiv.org/abs/2504.07981`
- OSWorld-G: fine-grained GUI grounding over layout and manipulation targets.
  `https://osworld-grounding.github.io/`

Binary pass requires returning exactly ten findings, meeting the configured visual-defect match
threshold, staying inside the calibrated coordinate window for matched defects, preserving valid
severity fields, and avoiding false-positive findings. The secondary score reports partial grounding
quality and supplies the pass threshold for this visual diagnostic.
