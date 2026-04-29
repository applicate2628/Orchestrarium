# Модель работы субагентов — Qwen Addendum

Канонический shared core: [shared/references/ru/subagent-operating-model.md](../../shared/references/ru/subagent-operating-model.md)

Визуальное дополнение: [operating-model-diagram.md](operating-model-diagram.md)

Этот файл хранит только Qwen-specific runtime и repository concretization для общей модели работы субагентов. Канонический blueprint, routing, role и governance-model текст живёт в shared core.

## Qwen-specific runtime notes

- `src.qwen/QWEN.md` — Qwen runtime entrypoint в этом монорепозитории.
- `Qwen Code /init` — канонический способ создать или обновить project `QWEN.md`.
- `.qwen/settings.json` остаётся Qwen-native runtime config surface.
- `.qwen/.agents-mode.yaml` — routing overlay Orchestrarium, который seedится при установке, а не замена `.qwen/settings.json`.
- Qwen runtime assets живут в `src.qwen/skills/`, `src.qwen/commands/` и `src.qwen/extension/`.
- Orchestrarium ставит pack в workspace/user extension tier Qwen и оставляет верхние `.qwen/skills`, `.qwen/agents` и `.qwen/commands` для осознанных overrides.
- Текущее Qwen source tree остаётся sequential и human-steered; не предполагайте native internal parallel dispatch. Independent external adapters всё ещё могут работать параллельно, когда это разрешают routing contract и выбранные provider runtimes.
- Qwen на этой линии поддерживается как explicit example и compatibility integration со статусом `WEAK MODEL / NOT RECOMMENDED`: shipped production `externalProvider: auto` профили остаются на `codex | claude`.
- На Qwen-линии `externalProvider: auto` по-прежнему разрешается по lane type через active named production priority profile, а не через один жёсткий Qwen-line default, но shipped production profile исключает Gemini и Qwen и остаётся на `codex | claude`.
- Явный `externalProvider: qwen` — это только manual example path, а не production recommendation.
- На Qwen-line external routing `externalClaudeApiMode` управляет только supplemental `claude-secret` candidate для advisory/review (`disabled | auto | force`, default `auto`); worker lanes не должны его использовать.

## Qwen-side repository concretization

- `references-qwen/` хранит Qwen-specific addenda и compatibility pointers для common layer монорепозитория.
- [../../docs/agents-mode-reference.md](../../docs/agents-mode-reference.md) — канонический operator reference, когда важно поведение Qwen-line `.qwen/.agents-mode.yaml`.
- Task-memory root, recovery entry point, active-item directory и archive location остаются repository-defined, когда включена tracked task memory.
- Periodic controls остаются pack-local в [periodic-control-matrix.md](periodic-control-matrix.md).

## Shared core теперь владеет

- Основным правилом, core management rules, delivery loops, routing patterns, role map, prompts, gates и team composition
- Shared review/gate semantics, periodic-controls model, parallel-work guidance и generic task-memory expectations
- Универсальной запиской для lead и финальной формулировкой
