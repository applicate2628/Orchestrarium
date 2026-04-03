# Operating Model Diagram

This file provides a visual companion to [subagent-operating-model.md](subagent-operating-model.md).

## 1. End-to-end operating flow

```mermaid
flowchart LR
    PM["product-manager<br/>Roadmap decision package"]
    PA["product-analyst<br/>Product brief"]
    M["lead<br/>Canonical brief"]
    A["analyst<br/>Research memo"]
    AR["architect<br/>Design package"]
    S["Specialist constraints<br/>algorithm / computational / security / performance / reliability"]
    P["planner<br/>Phase plan"]
    I["Implementation specialist<br/>Implementation package"]
    QA["QA / UI test<br/>Verification package"]
    R["Independent reviewers<br/>architecture / performance / security / UX / accessibility"]
    H["Human / CI gate"]

    PM -->|"admit item to discovery or delivery"| M
    PM -. "needs factual product clarification" .-> PA
    PA --> M

    M --> A
    M -. "product context still unclear" .-> PA
    A --> AR
    PA --> AR
    AR --> S
    S --> P
    P --> I
    I --> QA
    QA --> R
    R --> H
    H --> M
```

## 2. Interaction topology

```mermaid
flowchart TB
    subgraph Roadmap["Roadmap / Intake"]
        PM["product-manager"]
        PA["product-analyst"]
    end

    subgraph Delivery["Approved delivery work"]
        M["lead"]
        A["analyst"]
        AR["architect"]
        P["planner"]
        IMPL["implementation specialists"]
        QA["qa-engineer / ui-test-engineer"]
        REV["independent reviewers"]
    end

    PM <--> PA
    PM --> M

    M --> A
    M --> AR
    M --> P
    M --> IMPL
    M --> QA
    M --> REV

    A --> M
    AR --> M
    P --> M
    IMPL --> M
    QA --> M
    REV --> M
```

## 3. Artifact progression

```mermaid
flowchart LR
    R0["Roadmap decision package"]
    R1["Canonical brief"]
    R2["Product brief / Research memo"]
    R3["Design package"]
    R4["Specialist constraint packages"]
    R5["Phase plan"]
    R6["Implementation package"]
    R7["Verification package"]
    R8["Review reports"]
    R9["Human / CI approval"]

    R0 --> R1
    R1 --> R2
    R2 --> R3
    R3 --> R4
    R4 --> R5
    R5 --> R6
    R6 --> R7
    R7 --> R8
    R8 --> R9
```

## 4. Delegation behavior

```mermaid
flowchart LR
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

## Reading notes

- `product-manager` owns what enters discovery or delivery.
- `lead` owns execution of approved work.
- `analyst` and `product-analyst` should reduce uncertainty before interpretive roles make tradeoff decisions.
- Delegation should reduce noise: pass accepted artifacts, not raw transcript dumps, whenever an accepted artifact already exists.
- Interpretive roles should consume accepted evidence instead of filling factual gaps with judgment.
- Subagents exchange accepted artifacts, not direct peer task assignments.
- Reviewers stay independent and report to the orchestrating owner.
- `REVISE` returns work to the same stage owner; `BLOCKED` stops progression until a new decision or artifact exists.
