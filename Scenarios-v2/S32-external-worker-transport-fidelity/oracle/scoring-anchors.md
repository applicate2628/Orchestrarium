# Scoring Anchors

`S32` uses the `adapters` score profile.

Full-credit anchors:

- correctness: the report names the explicit disabled-route outcome and the exact dependency cause
- scope discipline: the report stays transport-only and does not drift into platform semantics
- verification cleanliness: provenance labels are complete and the transport facts cite the packet
- runtime cleanliness: no hidden internal fallback, proxy helper, or alternate provider path

Common deductions:

- missing `Resolved provider: none` or `Actual execution path: role disabled`
- generic "provider failed" language without the missing-CLI cause
- discussion of provider ranking, model preference, or semantic platform output
- any claim that another available CLI can be used because it is convenient
