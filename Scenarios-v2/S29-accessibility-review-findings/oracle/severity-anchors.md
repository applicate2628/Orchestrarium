# Severity Anchors

Use these anchors when writing or grading the review report:

- `blocking`: prevents keyboard-only users or assistive-technology users from operating the primary
  dialog flow, understanding a required control, or safely staying inside the modal while it is
  open
- `major`: meaningfully harms orientation, comprehension, or focus visibility and must be fixed
  before merge, even if some users can still complete the flow with extra effort
- `minor`: non-blocking polish or clarity issue; this scenario does not require a minor finding to
  pass the gate

The expected `S29` outcome is two `blocking` findings, two `major` findings, and a final gate of
`REVISE`.
