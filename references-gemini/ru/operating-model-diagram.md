# Диаграмма operating model

Этот файл — визуальное дополнение к [subagent-operating-model.md](../subagent-operating-model.md).
Справочник по стратегиям: [shared/references/ru/workflow-strategy-comparison.md](../../shared/references/ru/workflow-strategy-comparison.md).

Platform note: Gemini-линия остаётся sequential и human-steered. Диаграммы ниже показывают intended governance flow, а не обещание native parallel dispatch.

## 1. Сквозной operating flow

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

## 2. Последовательная топология handoff

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

## 3. Минимальные правила

- Держите runtime surfaces official-first: `GEMINI.md`, `/init` и `.gemini/settings.json`.
- Держите Orchestrarium routing overlays в `.gemini/.agents-mode`.
- Держите maintainer-side governance references в `references-gemini/`.
