# Модель работы субагентов — Claude Addendum

> **Примечание**: этот файл хранит Claude-specific addendum к shared blueprint. Канонические routing и operator semantics живут в shared core и в текущих Claude operator reference surfaces.

Канонический shared core: [shared/references/ru/subagent-operating-model.md](../../shared/references/ru/subagent-operating-model.md)

Визуальное дополнение: [operating-model-diagram.md](operating-model-diagram.md)

Этот файл хранит только Claude-specific runtime и repository concretization для общей модели работы субагентов. Канонический blueprint, routing, role и governance-model текст теперь живёт в shared core.

## Claude-specific runtime notes

- Claude runtime использует Agent tool и текущие Claude operator reference surfaces. Считайте этот файл локальным runtime addendum к shared blueprint, а не канонической полной копией методологии.
- Consultant config живёт в `.claude/.agents-mode.yaml`.
- Claude-line canonical config не включает `externalClaudeProfile`; Claude-side `externalProvider: auto` разрешается через active named priority profile, а не через жёсткий Codex-only default, а explicit provider selection может честно отправить eligible external work в Codex CLI, Claude CLI или Gemini CLI.
- `$external-worker` и `$external-reviewer` dispatch'ят из Claude Code в провайдера, выбранного `.claude/.agents-mode.yaml`.

## Claude-side repository concretization

- Adjacent findings и `BLOCKED:prerequisite` идут в `work-items/bugs/`.
- Recovery начинается с `work-items/index.md`; active items живут в `work-items/active/<date>-<slug>/`, а archive target — `work-items/archive/<date>-<slug>/`.
- Claude-side examples используют `Gate: PASS | REVISE | BLOCKED:<class> | RETURN(role)`.
- Claude runtime docs дополнительно держат явные `Artifact invalidation protocol` и `Parallel execution protocol`; используйте их вместе с shared core.

## Shared core теперь владеет

- Основным правилом, core management rules, delivery loops, routing patterns, role map, prompts, gates и team composition
- Shared review/gate semantics, periodic-controls model, parallel-work guidance и generic task-memory expectations
- Универсальной запиской для lead и финальной формулировкой
