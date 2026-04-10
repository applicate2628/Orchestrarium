# Evidence-Based Answer Pipeline

This is a reference document for high-stakes questions that need evidence-backed answers instead of unsupported guesses.

Use a multi-pass pipeline:

1. Retrieve evidence from authoritative sources before answering.
2. Extract only the fragments that directly support the answer.
3. Draft from evidence only.
4. Verify every claim against the evidence.
5. Remove unsupported or ambiguous claims before finalizing.

Core rules:

- Do not answer from memory when inspection or tools can verify the claim.
- If sources conflict, surface the conflict explicitly.
- If evidence is partial, return a partial answer with the gap called out.
- If the question is about current or live state and no current evidence is available, do not answer substantively from stale knowledge.

For coding agents, the lightweight equivalent is simple: inspect the code, confirm the claim, say what was verified, and name what was not.
