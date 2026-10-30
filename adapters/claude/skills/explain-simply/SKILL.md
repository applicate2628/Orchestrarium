---
name: explain-simply
description: "Explain simply: teach concepts in the user's language."
---

# Explain Simply

## Core stance

Teach for this reader, not for an abstract audience. Make the idea usable without weakening the facts.

Use the user's language by default. If the conversation language is Russian, explain in Russian unless the user asks otherwise.

Use this skill for user-facing learning or explanation work. A codebase-investigation question ("how does X work in this repo", "trace Y") routes to the research flow first — this skill is the user-facing presentation layer and may run AFTER the investigation has facts. Do not invoke it merely because you, the agent, need to understand something before acting.

## Workflow

1. Identify the reader's target: what they are trying to understand, decide, debug, or remember.
2. Ground the explanation in available evidence: cite code, docs, artifacts, outputs, or state clearly what is an assumption.
3. Explain in layers:
   - one-sentence answer;
   - plain-language mental model;
   - concrete mechanism or data flow;
   - caveats, limits, and what would falsify the explanation.
4. Use one consistent analogy for each non-trivial concept. Prefer everyday analogies: pipes, rooms, maps, ledgers, recipes, locks, queues, or tools.
5. Keep technical terms, acronyms, formulas, and role/provider/model names defined at first use.
6. Preserve correctness boundaries: do not turn "we observed X" into "X is proven generally"; do not hide open risks to make the explanation smoother.

## Output shape

For chat answers:

- Start with the useful answer, not a preface.
- Then add the mental model and exact details.
- End with a compact glossary only when several terms would otherwise stay fuzzy.

For learning documents or notes:

- Add or update the most topically adjacent section.
- Keep a reading path at the top when the document is long.
- End human-facing docs with `## Terms and Abbreviations` or `## Термины и сокращения`.
- Separate teaching notes from formal specifications, validation reports, runbooks, and API docs.

## Style rules

- Prefer short paragraphs and concrete numbers over abstract claims.
- Translate jargon before using it freely.
- Show why the concept matters in the user's task.
- For code, explain ownership, inputs, outputs, side effects, and failure modes before line-by-line detail.
- For formulas, state applicability, assumptions, units, variable meanings, and source/implementation path when available.

## Common mistakes

| Mistake | Correction |
|---|---|
| Explaining from the expert's vocabulary | Start from the reader's task and define terms before using them. |
| Switching analogies midstream | Keep one analogy per concept, or explicitly say why the analogy changes. |
| Making uncertainty disappear | Label assumptions and open questions; explain what evidence would close them. |
| Mixing teaching with specification | Put requirements and normative rules in the owning spec/governance artifact, not in a learning note. |

## Terms and Abbreviations

- **Acronym**: a shortened form such as API, FEM, or UI; expand it at first use.
- **Analogy**: an everyday comparison used to build intuition; it is not proof.
- **Mental model**: the simplified structure a reader can use to reason about the topic.
- **Teaching note**: a learner-focused explanation; not the canonical source for requirements unless explicitly designated.
