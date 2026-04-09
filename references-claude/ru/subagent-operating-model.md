# Модель работы субагентов — Claude Addendum

> **Примечание**: этот файл хранит Claude-specific addendum к shared blueprint. Актуальная runtime-модель использует template-based routing — см. [template-routing.md](template-routing.md) и `.claude/CLAUDE.md`.

Канонический shared core: [shared/references/ru/subagent-operating-model.md](../../shared/references/ru/subagent-operating-model.md)

Визуальное дополнение: [operating-model-diagram.md](operating-model-diagram.md)

Этот файл хранит только Claude-specific runtime и repository concretization для общей модели работы субагентов. Канонический blueprint, routing, role и governance-model текст теперь живёт в shared core.

## Claude-specific runtime notes

- Claude runtime использует template-based routing и Agent tool. Считайте этот файл локальным runtime addendum к shared blueprint, а не канонической полной копией методологии.
- Consultant config живёт в `.claude/.agents-mode`; legacy `.claude/.consultant-mode` остаётся fallback-only на время миграции.
- Claude-line canonical config не включает `externalClaudeProfile`, потому что Claude-side external dispatch идёт в Codex CLI.
- `$external-worker` и `$external-reviewer` dispatch'ят из Claude Code в Codex CLI.

## Claude-side repository concretization

- Adjacent findings и `BLOCKED:prerequisite` идут в `work-items/bugs/`.
- Recovery начинается с `work-items/index.md`; active items живут в `work-items/active/<date>-<slug>/`, а archive target — `work-items/archive/<date>-<slug>/`.
- Claude-side examples используют `Gate: PASS | REVISE | BLOCKED:<class> | RETURN(role)`.
- Claude runtime docs дополнительно держат явные `Artifact invalidation protocol` и `Parallel execution protocol`; используйте их вместе с shared core.

## Shared core теперь владеет

- Основным правилом, core management rules, delivery loops, routing patterns, role map, prompts, gates и team composition
- Shared review/gate semantics, periodic-controls model, parallel-work guidance и generic task-memory expectations
- Универсальной запиской для lead и финальной формулировкой
