# Модель работы субагентов — Codex Addendum

Канонический shared core: [shared/references/ru/subagent-operating-model.md](../../shared/references/ru/subagent-operating-model.md)

Визуальное дополнение: [operating-model-diagram.md](operating-model-diagram.md)

Этот файл хранит только Codex-specific runtime и repository concretization для общей модели работы субагентов. Канонический blueprint, routing, role и governance-model текст теперь живёт в shared core.

## Codex-specific runtime notes

- Native subagent dispatch в Codex доступен, когда его предоставляет текущий host. Такие lanes допускаются по shared rolling lane-ready-set contract: нельзя считать internal execution только последовательным или выводить numeric concurrency cap из более раннего отказа либо поведения другого runtime. Dependency и shared integration surfaces по-прежнему сериализуются.
- Consultant config живёт в `.agents/.agents-mode.yaml`.
- Codex может расширять shared `agents-mode` schema полем `externalClaudeProfile` для выбора Claude CLI execution profile (`sonnet-high`, `opus-xhigh` — shipped default, `opus-max` — max-depth escalation, или `fable-xhigh` — текущий flagship-family best-effort tier), когда `externalProvider` resolves to Claude.
- `externalProvider: auto` разрешается по active named production priority profile, а не по Codex-line default; shipped production `auto` использует только `codex | claude`. Явный выбор Kimi допускается для разрешённой политикой работы только на чтение либо инженерной работы, для которой допустимость задачи и назначенная профессия соответствуют `external-worker`. Выбранный файл возможностей предоставляет только ограниченные вызывающей стороной инструменты в рамках существующего класса мутаций и соответствия роли; он не предоставляет полномочий и не является песочницей. Grok остаётся unavailable, а удалённые Gemini/Qwen scalar values fail closed с `E_EXTERNAL_PROVIDER_REMOVED`.

## Codex-side repository concretization

- Допущенные предложения о смежных дефектах используют заданный репозиторием путь реестра ошибок, если он определён, по контракту допуска ошибок `qa-engineer`. Типизированные остановки сохраняют фактическую причину, обязательный остаток работы, владельца и следующее действие по общему ядру.
- Task-memory root, recovery entry point, active-item directory и archive location в этой Codex-side reference модели остаются repository-defined.
- Periodic controls остаются pack-local в [periodic-control-matrix.md](periodic-control-matrix.md).
- В старых Codex-примерах ещё может встречаться `Gate: PASS | REVISE | BLOCKED | RETURN(role)`; typed форма `BLOCKED[:class]` из shared core остаётся совместимой.

## Shared core теперь владеет

- Основным правилом, core management rules, delivery loops, routing patterns, role map, prompts, gates и team composition
- Shared review/gate semantics, periodic-controls model, parallel-work guidance и generic task-memory expectations
- Универсальной запиской для lead и финальной формулировкой
