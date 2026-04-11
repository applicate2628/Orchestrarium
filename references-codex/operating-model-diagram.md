# Operating Model Diagram

This file provides a visual companion to [subagent-operating-model.md](subagent-operating-model.md).
Strategy comparison companion: [shared/references/workflow-strategy-comparison.md](../shared/references/workflow-strategy-comparison.md).

**Platform note:** Orchestrarium targets Codex, which uses sequential skill invocation. Unlike Claude Code's parallel Agent tool dispatch, Codex processes one skill at a time. Diagrams below reflect this sequential execution model.

## 1. End-to-end operating flow

```mermaid
flowchart LR
    PM["product-manager\nRoadmap decision"] --> M["lead\nCanonical brief"]
    PA["product-analyst\nProduct brief"] -.-> M

    M --> A["analyst\nResearch memo"]
    A --> D["architect + constraints\nDesign package"]
    D --> P["planner\nPhase plan"]
    P --> I["implementer\nCode + tests"]
    I --> INT["integration owner\n(if multi-phase)"]
    INT --> QA["QA / UI test\nVerification"]
    QA --> R["independent reviewers\nReview reports"]
    R --> H["Human / CI gate"]
    H --> M

    M -. "scope drift" .-> PM
    M -. "needs product facts" .-> PA
```

## 2. Hub-and-spoke topology (sequential)

Lead invokes one role at a time. Each role completes and returns before the next is invoked. No native parallel dispatch.

```mermaid
flowchart TB
    PM["product-manager"] -->|"admit item"| L["lead"]
    L -. "re-intake" .-> PM

    L -->|"1. facts"| AN["analyst\nproduct-analyst"]
    AN -->|"artifact"| L
    L -->|"2. design"| AR["architect\nconstraint roles"]
    AR -->|"artifact"| L
    L -->|"3. plan"| PL["planner"]
    PL -->|"artifact"| L
    L -->|"4. build"| IM["implementers"]
    IM -->|"artifact"| L
    L -->|"5. verify"| QA["QA / reviewers"]
    QA -->|"artifact"| L
    L -. "advisory (optional)" .-> CO["consultant"]
```

## 3. Sequential handoff chain (no native parallel)

Unlike Claude Code, Codex does not dispatch multiple skills simultaneously. Constraint roles run sequentially, not in parallel. Lead orchestrates the ordering.

```mermaid
flowchart LR
    AR("architect") --> SE("security-eng")
    SE --> PE("performance-eng")
    PE --> RE("reliability-eng")

    RE --> PL("planner")

    PL -->|"CLAIMS"| IM("implementers")
    IM -->|"CLAIMS"| QA("qa-engineer")
    QA -->|"CLAIMS"| RV("reviewers")

    QA -. "ESCALATE" .-> PE
    RV -. "RETURN" .-> AR
    RV -. "RETURN" .-> IM
```

Note: if a project requires algorithm-scientist, computational-scientist, or ux-designer constraints, they are invoked sequentially before the planner, not in parallel with security/performance/reliability.

## 4. Artifact progression

```mermaid
flowchart LR
    R0["Roadmap\ndecision"] --> R1["Canonical\nbrief"]
    R1 --> R2["Research\nmemo"]
    R2 --> R3["Design\npackage"]
    R3 --> R4["Constraint\npackages"]
    R4 --> R5["Phase\nplan"]
    R5 --> R6["Implementation\npackages"]
    R6 --> R7["Integrated\nartifact"]
    R7 --> R8["Verification\nreport"]
    R8 --> R9["Review\nreports"]
    R9 --> R10["Human / CI\napproval"]
```

## 5. Delegation behavior

```mermaid
flowchart TB
    U["Unknown or ambiguity"]
    F["Narrow factual role\nanalyst / product-analyst"]
    AF["Accepted artifact"]
    I["Interpretive role\narchitect / lead / reviewer"]
    R["REVISE\nbounded correction"]
    B["BLOCKED\nexternal blocker"]

    U --> F --> AF --> I
    I -. "evidence insufficient" .-> R --> F
    I -. "external blocker" .-> B
```

## 6. Workflow selection

| Situation | Strategy | Key roles |
| --- | --- | --- |
| What should enter delivery next? | Roadmap / Intake loop | `$product-manager`, `$product-analyst` |
| Approved item needs execution | Delivery loop (sequential) | `$lead` -> research -> design -> plan -> implement -> QA/review |
| Next decision blocked by missing facts | Fact-first routing | `$analyst`, `$product-analyst`, specialist evidence lane |
| Domain risk can independently fail result | Risk-owner routing (sequential) | Relevant constraint role then corresponding reviewer |
| Admitted item changed mid-delivery | Re-intake loop | `$lead` -> `$product-manager` -> `$lead` |
| Multiple phases must land together | Integration ownership | `$lead` + one integration owner |
| Known risk needs checking | Claim-Verify review | Builder (with claims list) + reviewer |
| Novel risk needs blind-spot hunting | Adversarial review | Reviewer only (no design package) |
| Need non-blocking second opinion | Consultant advisory | `$lead` -> `$consultant` |
| Independent read-heavy scopes | Sequential fact-gathering | Research roles invoked one at a time |
| Independent write-heavy scopes (fixed contracts) | Sequential implementation | Implementers invoked one at a time with disjoint ownership |

## 7. Role map

31 roles, 6 categories. Canonical core team only.

| Category | Roles |
| --- | --- |
| Coordination | `lead`, `product-manager`, `consultant` (advisory-only) |
| Research | `analyst`, `product-analyst` |
| Design / Constraints | `architect`, `ux-designer`, `algorithm-scientist`, `computational-scientist`, `security-engineer`, `performance-engineer`, `reliability-engineer` |
| Plan | `planner` |
| Implement | `backend-engineer`, `frontend-engineer`, `data-engineer`, `platform-engineer`, `toolchain-engineer`, `graphics-engineer`, `visualization-engineer`, `geometry-engineer`, `qt-ui-engineer`, `model-view-engineer`, `knowledge-archivist` |
| QA + Review | `qa-engineer`, `ui-test-engineer`, `architecture-reviewer`, `performance-reviewer`, `security-reviewer`, `ux-reviewer`, `accessibility-reviewer` |

Notes:

- `knowledge-archivist` is cross-cutting hygiene, usually invoked outside the main feature phase.
- `consultant` is advisory-only and never becomes a reviewer or approver; ordinary consultant use is optional, and completed lead-managed batches still end with the active lane policy's required external consultant sweep before closure.

## 8. Claims chain

The claims chain is a traveling artifact that ensures builder claims reach reviewers reliably.

```mermaid
flowchart LR
    A["architect\nseeds claims"] --> C["constraint roles\npopulate claims"]
    C --> PL["planner\nfreezes claims"]
    PL --> IM["implementers\nannotate only"]
    IM --> QA["QA\nverifies claims"]
    QA --> RV["reviewers\nfinal disposition"]
```

Lifecycle of `constraints/claims.md` in the work-item folder:

1. **Created** after design acceptance — architect seeds initial constraints.
2. **Populated** by each constraint role as they complete (sequentially).
3. **Frozen** by the planner before implementation. The plan references the claims list.
4. **Annotated** by each implementer — verification notes only, cannot modify claims.
5. **Verified** by QA — each claim receives a verification status.
6. **Reviewed** by each independent reviewer — primary input for Claim-Verify.
7. **Returned** to lead — final claims disposition with pass/fail per review domain.

## 9. Key rules

- `product-manager` owns what enters delivery. `lead` owns execution of approved work.
- `analyst` and `product-analyst` reduce uncertainty before interpretive roles make tradeoff decisions.
- Delegation passes accepted artifacts, not raw transcripts.
- **Codex sequential model:** one skill invocation at a time. No native parallel dispatch. If independent work could theoretically run in parallel, lead still invokes roles sequentially and manages the ordering.
- `REVISE` returns work to the responsible role for up to 3 iterations; after 3, escalate to the user. `BLOCKED` stops progression — classified as `BLOCKED:dependency` (external blocker) or `BLOCKED:prerequisite` (adjacent work needed first).
- Multi-phase implementation requires one explicit integration owner before QA.
- Reviewers stay independent and report to the orchestrating owner.
- Interaction types: `LEAD_MED` (default), `DIRECT` (sequential, lead-authorized), `CLAIMS`, `RETURN`, `ESCALATE`, `ADVISORY`, `NONE`. Note: `PARALLEL` is not natively supported in Codex — independent scopes are handled sequentially.
- Reviewers tag cross-domain findings with `[CROSS-DOMAIN: <target-domain>]`; the orchestrator routes them to the appropriate specialist.
- Any role files adjacent findings in `work-items/bugs/` without expanding scope.
- Every completed chain persists artifacts: canonical docs in `work-items/`, session logs in `.reports/`, plan logs in `.plans/`.
