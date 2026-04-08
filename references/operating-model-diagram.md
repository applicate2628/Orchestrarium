# Operating Model Diagram

This file provides a visual companion to [subagent-operating-model.md](subagent-operating-model.md).
Strategy comparison companion: [workflow-strategy-comparison.md](workflow-strategy-comparison.md).

## 1. End-to-end operating flow

```mermaid
flowchart TB
    subgraph Intake["Roadmap / Intake"]
        direction LR
        PM["product-manager"] -. "clarify" .-> PA["product-analyst"]
    end

    subgraph Prepare["Research → Design → Plan"]
        direction LR
        L["lead"] --> A["Research"] --> D["Design &\nConstraints"] --> P["Plan"]
    end

    subgraph Execute["Implement → Verify → Gate"]
        direction LR
        I["Implement"] --> INT["Integrate"] --> QA["Verify"] --> R["Review"] --> H["Human /\nCI gate"]
    end

    PM -->|admit| L
    PA -.->|facts| L
    P --> I
    H -->|done| L
    L -. "re-intake" .-> PM
```

## 2. Interaction topology

```mermaid
flowchart TB
    R["product-manager +\nproduct-analyst"]
    L["lead"]

    subgraph Prepare[" "]
        direction LR
        F["Research"] ~~~ D["Design /\nConstraints"] ~~~ P["Plan"]
    end

    subgraph Execute[" "]
        direction LR
        B["Implement +\nIntegrate"] ~~~ V["QA +\nReview"] ~~~ C["Consultant\n(advisory)"]
    end

    R -->|admit| L
    L -. "re-intake" .-> R

    L <--> F
    L <--> D
    L <--> P
    L <--> B
    L <--> V
    L -. "second opinion" .-> C
```

## 3. Artifact progression

```mermaid
flowchart TB
    subgraph Upstream["Upstream artifacts"]
        direction LR
        A1["Roadmap\ndecision"] --> A2["Canonical\nbrief"] --> A3["Research\nmemo"]
    end

    subgraph Design["Design artifacts"]
        direction LR
        A4["Design\npackage"] --> A5["Constraint\npackages"] --> A6["Phase\nplan"]
    end

    subgraph Delivery["Delivery artifacts"]
        direction LR
        A7["Implementation"] --> A8["Integrated\nartifact"] --> A9["Verification +\nreviews"]
    end

    A3 --> A4
    A6 --> A7
    A9 --> A10["Human / CI\napproval"]
```

## 4. Delegation behavior

```mermaid
flowchart TB
    U["Unknown or ambiguity"]
    F["Narrow factual role<br/>product-analyst / analyst / specialist evidence lane"]
    AF["Accepted artifact"]
    I["Interpretive role<br/>product-manager / lead / architect / reviewer"]
    R["REVISE<br/>bounded correction in same role"]
    B["BLOCKED<br/>real external blocker or missing decision"]

    U --> F
    F --> AF
    AF --> I
    I -. "evidence insufficient" .-> R
    R --> F
    I -. "external blocker" .-> B
```

## 5. Workflow selection matrix

| Situation | Default strategy | Primary roles | Expected accepted artifact | Escalate when |
|---|---|---|---|---|
| What should enter discovery or delivery next? | `Roadmap / Intake loop` | `$product-manager`, `$product-analyst` as needed | Roadmap decision package, then optional product brief | Product facts are unclear or milestone intent is unstable |
| Approved item needs normal execution | `Delivery loop` | `$lead -> analyst -> architect -> planner -> implementation -> QA/review` | Canonical brief, research memo, design package, phase plan, implementation and verification artifacts | A critical risk lane or reviewer becomes mandatory |
| The next decision is blocked by missing facts | `Fact-first routing` | `$analyst`, `$product-analyst`, or a narrow specialist evidence lane | Accepted factual artifact | Interpretive roles are being asked to guess instead of consume evidence |
| A domain risk can independently fail the result | `Risk-owner routing` | `$security-engineer`, `$performance-engineer`, `$reliability-engineer`, `$algorithm-scientist`, `$computational-scientist`, `$ux-designer`, or another explicit owner | One specialist design or constraint package | The risk is being left implicit inside general implementation |
| The admitted item has changed materially mid-delivery | `Re-intake loop` | `$lead -> $product-manager -> $lead` | Updated roadmap decision package or re-admission decision | Scope, priority, or milestone intent no longer matches the admitted item |
| Multiple implementation phases or specialists must land together | `Integration ownership` | `$lead` plus one explicit integration owner | One integrated artifact ready for QA | QA would otherwise receive a partial multi-phase result |
| A known bounded risk needs independent checking | `Claim-Verify review` | Upstream builder plus the relevant independent reviewer | Implementation artifact plus claims list, then review report | The reviewer needs to verify stated guarantees and coverage gaps |
| A novel or externally exposed risk needs blind-spot hunting | `Adversarial review` | Relevant independent reviewer | Review report against the implementation artifact only | Missing an unknown risk is more dangerous than missing an execution bug |
| A change needs independence between builder and gate | `Builder / blocker separation` | Builder role plus reviewer/blocker role | Builder artifact, then independent review artifact | The builder would otherwise approve the same risk they introduced |
| Ambiguity or tradeoffs need a non-blocking second opinion | `Consultant advisory` | `$lead -> $consultant` | Advisory memo | Facts are already assembled, but route choice is still ambiguous |
| Read-heavy scopes are independent | `Parallel read lanes` | Multiple research, triage, or test-analysis roles | Multiple independent factual artifacts | Merge cost would exceed the time saved |
| Write-heavy scopes are independent and contracts are fixed | `Parallel write lanes` | Multiple implementation roles with disjoint ownership | Multiple implementation artifacts with fixed boundaries | Write scopes overlap or contracts are still moving |

## 6. Role map by category

Current team shape: `31 roles`, `6 categories`.

Note: this role map shows the canonical core team only; installed or repo-local specialists are not listed here.

| Category | Roles |
|---|---|
| Coordination | `lead`, `product-manager`, `consultant` (advisory-only) |
| Research | `analyst`, `product-analyst` |
| Design / Constraints | `architect`, `ux-designer`, `algorithm-scientist`, `computational-scientist`, `security-engineer`, `performance-engineer`, `reliability-engineer` |
| Plan | `planner` |
| Implement | `backend-engineer`, `frontend-engineer` (web/React UI), `data-engineer`, `platform-engineer`, `toolchain-engineer`, `graphics-engineer`, `visualization-engineer`, `geometry-engineer`, `qt-ui-engineer` (Qt desktop UI), `model-view-engineer`, `knowledge-archivist` |
| QA + Review | `qa-engineer`, `ui-test-engineer`, `architecture-reviewer`, `performance-reviewer`, `security-reviewer`, `ux-reviewer`, `accessibility-reviewer` |

Notes:
- `knowledge-archivist` is a cross-cutting hygiene lane and is usually invoked outside the main feature phase even though it sits closest to implementation support.
- `consultant` is advisory-only and does not become a required delivery gate.

## 7. Reading notes

- `product-manager` owns what enters discovery or delivery.
- `lead` owns execution of approved work.
- `ux-designer` owns scoped interaction design before implementation when the UI surface needs dedicated UX ownership.
- If an in-flight item no longer fits its admitted scope, priority, or milestone intent, `lead` routes it back to `product-manager` for re-intake.
- `analyst` and `product-analyst` should reduce uncertainty before interpretive roles make tradeoff decisions.
- Delegation should reduce noise: pass accepted artifacts, not raw transcript dumps, whenever an accepted artifact already exists.
- Interpretive roles should consume accepted evidence instead of filling factual gaps with judgment.
- Subagents exchange accepted artifacts, not direct peer task assignments.
- `$consultant` stays advisory-only whether it is fulfilled by an external provider or by an internal independent subagent fallback.
- Multi-phase or multi-specialist implementation requires one explicit integration owner before QA.
- Reviewers stay independent and report to the orchestrating owner.
- `REVISE` returns work to the same stage owner for up to 3 consecutive cycles on the same role and artifact; `BLOCKED` stops progression until a new decision or artifact exists. `BLOCKED` has two typed classes: `BLOCKED:dependency` (external, escalate to user) and `BLOCKED:prerequisite` (internal blocker, record in the configured bug registry path if the repository uses one).
