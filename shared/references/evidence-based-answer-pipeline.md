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

The discipline has multiple structural backstops for code-bearing work:

1. **Pre-fix (text rule + auto-installed structural hook)** — before the first code-mutating tool call (`Edit`/`Write`/`NotebookEdit`/`apply_patch`) in a bug-report context, steps 1-3 of the Bootstrap (capture observable data → form hypothesis → verify each link) must complete. The text rule is the `Pre-fix diagnostic gate` rule named above. The structural backstop is the auto-installed `check-bugfix-discipline` PreToolUse hook: it reads the session transcript from the PreToolUse envelope, detects whether the last user message contains a bug-trigger phrase (`fix`, `change`, `broken`, `не работает`, `исправь`, `пофикси`, `поменяй`, traceback, `Error:`, etc.), and denies the edit if no discipline signals are present in the current turn (no `/agents-bugfix` invocation, no captured diagnostic data, no stated hypothesis). The user can override per-turn with the `[skip-bugfix-discipline]` marker when the trigger is a false positive (e.g. "fix this typo" — really a docs edit).
2. **Pre-stop (auto-installed structural hook)** — before ending a turn, the `check-passive-polling-stop` Stop hook inspects `last_assistant_message` from the Stop envelope. If the final message claims passive waiting for an async external source (bot, review, CI, job, notification, reply) and the current turn has no relevant probe (`date`, `Get-Date`, `gh pr view`, `gh run list`, `gh api`, `curl`, process/task output, or output/log/task file read), the hook emits `{"decision":"block","reason":"..."}`. It exits on `stop_hook_active=true`, exempts user handoffs such as `waiting for your response` / `жду твоего подтверждения`, and supports the per-stop `[acknowledge-passive-stop]` marker for intentional handoff.
3. **Pre-commit (text rule only)** — before authoring a commit that fixes/alters behavior, all 5 steps of the Bootstrap (the four diagnostic steps plus Recovery readiness) must complete and the commit message must disclose the verified hypothesis chain. There is no machine check here; the agent is expected to follow the text rule.

The structural hooks deliberately fire at the moments where the failure happens: the pre-fix hook catches editing before diagnostics, and the Stop hook catches passive async-wait claims before the turn ends. Tying hypothesis discipline to `git push` (an earlier design we removed) would have been theatre — by push time the unverified-hypothesis edit has already happened and the harm is done.

## Terms and Abbreviations

- `API`: Application Programming Interface; the programmatic contract between a system and an external or internal consumer.
- `claim`: a verifiable assertion that must be supported by evidence or removed from the answer.
- `evidence`: verified basis for a claim: a source, code path, command output, log line, test result, or other observable fact.
- `high-stakes domain`: a domain where an incorrect answer can produce costly corrections, safety, financial, scientific, or operational harm.
- `LLM`: Large Language Model; a machine-learning model trained on large text corpora to generate and reason over language.
- `pipeline`: a sequential sequence of processing and verification steps applied to a query or output before it is accepted.
- `stale knowledge`: knowledge not confirmed by a current verification pass; potentially outdated relative to the present state of the system.
- `UI`: User Interface; the user-facing interaction surface.
- `UX`: User Experience; usability, flow, comprehension, and interaction quality.
