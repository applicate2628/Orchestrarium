# Модель работы субагентов — Codex Addendum

Канонический shared core: [shared/references/ru/subagent-operating-model.md](../../shared/references/ru/subagent-operating-model.md)

Визуальное дополнение: [operating-model-diagram.md](operating-model-diagram.md)

Этот файл хранит только Codex-specific runtime и repository concretization для общей модели работы субагентов. Канонический blueprint, routing, role и governance-model текст теперь живёт в shared core.

## Codex-specific runtime notes

- Codex использует sequential skill invocation. Нативного parallel skill dispatch нет, поэтому даже теоретически независимая работа на Codex-линии оркестрируется последовательно.
- Consultant config живёт в `.agents/.agents-mode.yaml`.
- Codex может расширять shared `agents-mode` schema полем `externalClaudeProfile` для выбора Claude CLI execution profile (`sonnet-high` или `opus-max`).
- `externalProvider: auto` разрешается по active named priority profile, а не по Codex-line default; `$external-worker` и `$external-reviewer` могут честно dispatch'иться в Claude CLI или Gemini CLI, а Gemini-first routing для image/icon/decorative lanes нужно выражать явным provider override или repo-local custom profile, а не скрытой эвристикой по умолчанию.

## Codex-side repository concretization

- Adjacent findings и `BLOCKED:prerequisite` используют configured bug-registry path, если репозиторий его определяет.
- Task-memory root, recovery entry point, active-item directory и archive location в этой Codex-side reference модели остаются repository-defined.
- В старых Codex-примерах ещё может встречаться `Gate: PASS | REVISE | BLOCKED | RETURN(role)`; typed форма `BLOCKED[:class]` из shared core остаётся совместимой.

## Shared core теперь владеет

- Основным правилом, core management rules, delivery loops, routing patterns, role map, prompts, gates и team composition
- Shared review/gate semantics, periodic-controls model, parallel-work guidance и generic task-memory expectations
- Универсальной запиской для lead и финальной формулировкой
