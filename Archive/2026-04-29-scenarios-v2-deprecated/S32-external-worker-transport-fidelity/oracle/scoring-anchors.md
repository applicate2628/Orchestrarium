# Scoring Anchors

`S32` uses the `adapters` score profile.

Full-credit anchors:

- correctness: the report names the explicit Gemini route, assigned worker provenance, and exact transport path
- scope discipline: the report stays transport-only and does not drift into platform semantics
- verification cleanliness: provenance labels are complete and the transport facts cite the packet
- runtime cleanliness: no hidden internal fallback, proxy helper, or alternate provider path

Common deductions:

- missing `Resolved provider: Gemini CLI` or `Actual execution path: external CLI (Gemini CLI)`
- generic transport language that does not name the explicit direct route
- omitting the no-fallback or no-semantic-output scope boundary
- discussion of provider ranking, model preference, or semantic platform output
- any claim that another available CLI can be used because it is convenient
