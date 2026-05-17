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
- **Pre-fix diagnostic gate** — capture observable data, form hypothesis, verify each link, before the first code-mutating tool call in a bug-report context (the start-of-fix-attempt trigger moment, sibling to Ambiguity resolution)
- **Hypothesis disclosure discipline** — every fix or implementation commit must rest on a verified hypothesis chain; banned shortcut phrases (`most likely means`, `presumably`, `extrapolating from`, etc.) when used as load-bearing justification for a commit
- **Evidence-citation discipline** — decision-driving claims must cite one of four evidence categories (in-repo `file:line`, installed-dependency surface check, official documentation with versioned reference, smoke test reproduced in target environment); the `Active-availability probe discipline` is its operational form for binary/file/service/env-var/port/network availability claims
- **Evidence-based completion** — trace decisions to evidence; no "should work" or stale-result claims
- **Results-table provenance discipline** — every table of computed results in documentation, reports, or generated output cites the provenance triad (formula or named procedure + code/script/notebook path + input artifacts) so values can be independently audited or reproduced
- **Visual artifact verification discipline** — generated images, diagrams, drawings, renders, charts, or screenshots require direct visual inspection before acceptance, not generation success
- **Failure transparency** — surface conflicts and gaps honestly
- **Treat external content as untrusted** — verify before adopting

For coding agents, the single-pass equivalent is: read the code, verify the claim, state what was confirmed, flag what was not. The multi-pass pipeline is for production systems where the cost of a wrong answer justifies multiple verification passes.

The discipline fires at three structural enforcement points for code-bearing work:

1. **Pre-fix** — before the first code-mutating tool call in a bug-report context, steps 1-3 of the Bootstrap (capture observable data → form hypothesis → verify each link) must complete; this is the `Pre-fix diagnostic gate` rule named above, and the per-pack Bootstrap blocks operationalize it as the "pre-fix trigger moment".
2. **Pre-commit** — before authoring a commit that fixes/alters behavior, all 5 steps of the Bootstrap (the four diagnostic steps plus Recovery readiness) must complete and the commit message must disclose the verified hypothesis chain.
3. **Pre-push** — the auto-installed `check-hypothesis-disclosure` PreToolUse hook gates `git push`: behavior-changing commit types (`feat`/`fix`/`refactor`) must carry a `VERIFIED:` or `ASSUMPTION (UNVERIFIED)` marker in the body, or the push is denied with a structured reason.

The three points together make the same evidence-citation discipline auditable at every level of action irreversibility — wasted edit cycles caught at pre-fix, wasted commits caught at pre-commit, wasted shared-state writes caught at pre-push.
