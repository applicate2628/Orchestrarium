# Research

Investigate a question using the `research` template chain.

## Steps

1. **Get the question.** Use `$ARGUMENTS` as the research question. If empty, ask the user what to investigate.

2. **Run the research chain.** Follow the `research` template from CLAUDE.md:
   - **Analyst** (`subagent_type: analyst`): investigate the codebase — locate relevant files, trace data flows, identify contracts, find similar implementations. Return a factual research memo with file and line references.
   - **Architect** (`subagent_type: architect`): based on the analyst's findings, assess architectural implications, tradeoffs, and design options if applicable.

3. **Report.** Present:
   - Key findings with file:line references
   - Architectural context if relevant
   - Open questions or areas that need further investigation

## Rules

- This is read-only — do not modify any files.
- Pass the analyst's accepted memo to the architect.
- If the question is simple and the analyst's memo answers it fully, skip the architect stage.
