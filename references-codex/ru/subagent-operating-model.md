# Модель работы субагентов — Codex Addendum

Канонический shared core: [shared/references/ru/subagent-operating-model.md](../../shared/references/ru/subagent-operating-model.md)

Визуальное дополнение: [operating-model-diagram.md](operating-model-diagram.md)

Этот файл хранит только Codex-specific runtime и repository concretization для общей модели работы субагентов. Канонический blueprint, routing, role и governance-model текст теперь живёт в shared core.

## Codex-specific runtime notes

- Codex использует sequential skill invocation для native skills. Нативного internal parallel skill dispatch нет, поэтому internal Codex-role work всё ещё оркестрируется последовательно на Codex-line. Independent external adapters всё ещё могут работать параллельно, когда routing contract и выбранные provider runtimes это разрешают.
- Consultant config живёт в `.agents/.agents-mode.yaml`.
- Codex может расширять shared `agents-mode` schema полем `externalClaudeProfile` для выбора Claude CLI execution profile (`sonnet-high`, `opus-xhigh` — shipped default, `opus-max` — max-depth escalation, или `fable-xhigh` — текущий flagship-family best-effort tier), когда `externalProvider` resolves to Claude.
- `externalProvider: auto` разрешается по active named production priority profile, а не по Codex-line default; shipped production `auto` использует только `codex | claude`. Явный Kimi разрешён только для policy-admitted read-only работы; Grok остаётся unavailable, а удалённые Gemini/Qwen scalar values fail closed с `E_EXTERNAL_PROVIDER_REMOVED`.

## Codex-side repository concretization

- Adjacent findings и `BLOCKED:prerequisite` используют configured bug-registry path, если репозиторий его определяет.
- Task-memory root, recovery entry point, active-item directory и archive location в этой Codex-side reference модели остаются repository-defined.
- Periodic controls остаются pack-local в [periodic-control-matrix.md](periodic-control-matrix.md).
- В старых Codex-примерах ещё может встречаться `Gate: PASS | REVISE | BLOCKED | RETURN(role)`; typed форма `BLOCKED[:class]` из shared core остаётся совместимой.

## Shared core теперь владеет

- Основным правилом, core management rules, delivery loops, routing patterns, role map, prompts, gates и team composition
- Shared review/gate semantics, periodic-controls model, parallel-work guidance и generic task-memory expectations
- Универсальной запиской для lead и финальной формулировкой
