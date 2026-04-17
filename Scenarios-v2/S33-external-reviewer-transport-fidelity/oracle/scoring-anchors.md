# Scoring Anchors

`S33` uses the `adapters` score profile.

Full-credit anchors:

- correctness: the report names the direct external-reviewer route, assigned reviewer provenance, and exact review strategy
- scope discipline: the report stays transport-only and does not drift into security findings, QA verdicts, or remediation advice
- verification cleanliness: provenance labels are complete and the transport facts cite the packet
- runtime cleanliness: no hidden internal fallback, proxy helper, or alternate provider route

Common deductions:

- missing or changed `Review strategy: adversarial`
- omitting the no-fallback or no-semantic-findings scope boundary
- inventing provider or model details beyond `runtime default`
- discussing provider ranking or the semantic quality of the review artifact
