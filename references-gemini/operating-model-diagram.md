# Operating Model Diagram

This file provides a visual companion to [subagent-operating-model.md](subagent-operating-model.md).
Strategy comparison companion: [workflow-strategy-comparison.md](workflow-strategy-comparison.md).

Platform note: this standalone Gemini pack keeps execution sequential and human-steered. The diagrams below show the intended governance flow, not a promise of native parallel dispatch.

## 1. End-to-end operating flow

```mermaid
flowchart LR
    PM["product-manager\nRoadmap decision"] --> L["lead\nCanonical brief"]
    PA["product-analyst\nProduct brief"] -.-> L

    L --> A["analyst\nResearch memo"]
    A --> D["architect + constraints\nDesign package"]
    D --> P["planner\nPhase plan"]
    P --> I["implementer\nCode + tests"]
    I --> INT["integration owner\n(if multi-phase)"]
    INT --> QA["QA / reviewers\nVerification"]
    QA --> H["Human gate"]
    H --> L

    L -. "scope drift" .-> PM
```

## 2. Sequential handoff topology

```mermaid
flowchart TB
    U["user or roadmap admission"] --> L["lead"]
    L -->|"facts"| AN["analyst / product-analyst"]
    AN -->|"accepted artifact"| L
    L -->|"design"| AR["architect / constraints"]
    AR -->|"accepted artifact"| L
    L -->|"plan"| PL["planner"]
    PL -->|"accepted artifact"| L
    L -->|"build"| IM["implementer"]
    IM -->|"accepted artifact"| L
    L -->|"verify"| QA["qa / reviewers"]
    QA -->|"accepted artifact"| L
    L -. "optional advisory" .-> CO["consultant"]
```

## 3. Minimal rules

- Keep runtime surfaces official-first: `GEMINI.md`, `/init`, and `.gemini/settings.json`.
- Keep Orchestrarium routing overlays in `.gemini/.agents-mode`.
- Keep maintainer-side governance references in `references-gemini/`.
