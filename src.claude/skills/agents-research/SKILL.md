---
name: agents-research
description: Investigate a question using the `research` template chain.
disable-model-invocation: true
---
# Research

Investigate a question using the `research` template chain.

## Steps

1. **Get the question.** Use `$ARGUMENTS` as the research question. If empty, ask the user what to investigate.

2. **Run the research chain.** Follow the `research` template from CLAUDE.md:
   - **Analyst** (`subagent_type: analyst`): investigate the codebase — locate relevant files, trace data flows, identify contracts, find similar implementations. Return a factual research memo with file and line references.
   - **Architect** (`subagent_type: architect`): based on the analyst's findings, assess architectural implications, tradeoffs, and design options if applicable.

3. **Handle REVISE.** If the architect returns `REVISE` (research is insufficient or has gaps):
   - Route the architect's specific gaps back to the analyst for a focused follow-up investigation
   - Re-run the architect with the updated research
   - Max 3 iterations, then present what was found and the remaining gaps to the user

4. **Save.** Persist per artifact persistence protocol (`operating-model.md`):
   - If part of an active work-item → `work-items/active/<slug>/research.md`
   - Always log to `.reports/YYYY-MM/report(<role>)-YYYY-MM-DD_HH-MM_topic.md`
   - If no work-item exists and the result is worth preserving, create one

5. **Report.** Present:
   - Key findings with file:line references
   - Architectural context if relevant
   - Open questions or areas that need further investigation

## Rules

- **Every stage MUST be invoked via the Agent tool** with the specified `subagent_type`. Do not role-play specialists inline.
- This is read-only — do not modify any files.
- Pass the analyst's accepted memo to the architect.
- If the question is simple and the analyst's memo answers it fully, skip the architect stage.
