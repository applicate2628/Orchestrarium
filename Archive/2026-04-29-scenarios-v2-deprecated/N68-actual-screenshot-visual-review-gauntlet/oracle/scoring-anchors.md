# Scoring Anchors

Design note: this diagnostic follows the same failure modes targeted by GUI/web grounding benchmarks:
element grounding, action or defect grounding, coordinate evidence, and resistance to false-positive
visual cues.

Research anchors used during design:

- VisualWebBench: web screenshot understanding and grounding tasks.
  `https://visualwebbench.github.io/`
- ScreenSpot-Pro: high-resolution professional GUI grounding.
  `https://arxiv.org/abs/2504.07981`
- OSWorld-G: fine-grained GUI grounding over layout and manipulation targets.
  `https://osworld-grounding.github.io/`

Binary pass requires matching all eight seeded visual defects and avoiding the three false-positive
traps. The secondary score reports partial grounding quality but does not override binary pass/fail.
