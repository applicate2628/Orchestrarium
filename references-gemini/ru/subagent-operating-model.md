# Модель работы субагентов — Gemini Addendum

Канонический shared core: [shared/references/ru/subagent-operating-model.md](../../shared/references/ru/subagent-operating-model.md)

Визуальное дополнение: [operating-model-diagram.md](operating-model-diagram.md)

Этот файл хранит только Gemini-specific runtime и repository concretization для общей модели работы субагентов. Канонический blueprint, routing, role и governance-model текст живёт в shared core.

## Gemini-specific runtime notes

- `src.gemini/GEMINI.md` — Gemini runtime entrypoint в этом монорепозитории.
- Встроенный Gemini CLI `/init` — канонический способ создать или обновить project `GEMINI.md`.
- `.gemini/settings.json` остаётся Gemini-native runtime config surface.
- `.gemini/.agents-mode.yaml` — routing overlay Orchestrarium, который seedится при установке, а не замена `.gemini/settings.json`.
- Gemini runtime assets живут в `src.gemini/skills/`, `src.gemini/commands/` и `src.gemini/extension/`.
- Текущее Gemini source tree остаётся sequential и human-steered; не предполагайте native parallel dispatch.
- На Gemini-линии `externalProvider: auto` разрешается по lane type через active named priority profile, а не через один жёсткий Gemini-line default. Если репозиторий хочет Gemini-first routing для visual lanes, это нужно выражать явным provider override или repo-local custom profile, а не считать, что shipped shared profiles уже делают это по умолчанию. Если Gemini резолвится в Claude, нужно уважать `externalClaudeApiMode` как единственный Claude wrapper-transport toggle (`disabled | auto | force`, default `auto`).

## Gemini-side repository concretization

- `references-gemini/` хранит Gemini-specific addenda и compatibility pointers для common layer монорепозитория.
- [../../docs/agents-mode-reference.md](../../docs/agents-mode-reference.md) — канонический operator reference, когда важно поведение Gemini-line `.gemini/.agents-mode.yaml`.
- Task-memory root, recovery entry point, active-item directory и archive location остаются repository-defined, когда tracked task memory включён.
- Периодические проверки остаются pack-local в [periodic-control-matrix.md](periodic-control-matrix.md).

## Shared core теперь владеет

- Основным правилом, core management rules, delivery loops, routing patterns, role map, prompts, gates и team composition
- Shared review/gate semantics, periodic-controls model, parallel-work guidance и generic task-memory expectations
- Универсальной запиской для lead и финальной формулировкой
