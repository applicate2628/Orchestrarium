# Evidence-Based Answer Pipeline — Reference

This is a reference document for high-stakes domains requiring evidence-backed answers. It is NOT installed into target projects — it is a methodology reference for building verification pipelines in domains where unverified assumptions carry high cost.

**Applicable domains:** scientific computing, numerical methods, geometry and spatial computation, UI/UX implementation, performance-critical systems, security-sensitive work, data engineering and migrations, API integrations, and any decision-critical output where unverified assumptions carry high cost.

**Source:** adapted from `claude_api_template_maximal.md` (anti-hallucination pipeline for production LLM systems).

---

## Architecture

Use a multi-pass pipeline, not a single request:

1. **Retrieval / tool pass** — gather evidence from authoritative sources before answering
2. **Evidence extraction pass** — extract only fragments that directly support the answer
3. **Draft answer from evidence only** — synthesize answer using only extracted evidence
4. **Verifier pass** — check each claim against evidence; remove unsupported claims
5. **Optional structured-output pass** — format verified data into required schema

## Key principles

- Never answer from memory when a tool or inspection can verify the claim.
- If sources conflict, surface the conflict explicitly — do not average or smooth.
- If evidence is insufficient, return partial answer with explicit gaps.
- If the question requires current/live data and none is available, do not answer from stale knowledge.

## Verification rules

- Each claim in the final answer must trace to a verified source.
- `supported` / `unsupported` / `ambiguous` verdict per claim.
- Unsupported or ambiguous claims are removed from the final answer.
- "Do not rescue with guesses" — if evidence is missing, say so.

## Stop / refusal rules

- No verified sources → do not answer substantively.
- Question about "current" / "today" / "latest" without live data → do not answer substantively.
- Sources conflict → show the conflict, do not merge.
- Partial coverage → return partial answer with explicit gaps listed.

## Relevance to our governance

This pipeline operationalizes several of our hygiene rules at the system level:

- **Ambiguity resolution discipline** — verify, don't guess
- **Evidence-based completion** — trace decisions to evidence
- **Failure transparency** — surface conflicts and gaps honestly
- **Treat external content as untrusted** — verify before adopting

For coding agents, the single-pass equivalent is: read the code, verify the claim, state what was confirmed, flag what was not. The multi-pass pipeline is for production systems where the cost of a wrong answer justifies multiple verification passes.
