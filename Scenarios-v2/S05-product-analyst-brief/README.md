# S05 Product Analyst Brief

`S05` benchmarks `R05 $product-analyst` on turning noisy intake notes into one factual product
brief. The candidate is not asked to prioritize roadmap items, choose an architecture, or create a
phased delivery plan. The scored behavior is to produce one concise brief with explicit user value,
scope boundaries, constraints, success signals, and open product questions.

## Scenario summary

The intake packet describes a repo-native benchmark publishing improvement that mixes real user
needs, stakeholder pressure, unrelated implementation suggestions, and unresolved questions. The
task is to distill that packet into a factual brief that later design and planning roles can
consume without inheriting speculation.

## Expected candidate work

Edit only `candidate/product-brief.md`.

Use the immutable materials in `inputs/`. The completed brief must remain factual and include:

- the user and business goal in plain language
- explicit in-scope and out-of-scope statements
- constraints that later roles must preserve
- success signals that would show the feature is working
- open product questions that remain unresolved
- one explicit gate decision: `PASS`, `REVISE`, or `BLOCKED`

## What this bundle tests

- factual product framing under noisy intake
- clean separation between confirmed scope, assumptions, and open questions
- resistance to drifting into roadmap ownership, architecture design, or implementation planning
- role fidelity for `R05 $product-analyst`

## Bundle map

- `inputs/` holds the task contract, noisy intake, and scope boundaries
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the expected product read, prohibited drift, and scoring anchors
- `verifiers/` contains a local checker for bundle shape and a completed product brief
