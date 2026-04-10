# Модель работы субагентов — Gemini Reference

Визуальное дополнение: [operating-model-diagram.md](operating-model-diagram.md)

Эта standalone ветка хранит один Gemini-local operating-model reference вместо разделения methodology между shared и provider-local layers.

## Gemini runtime notes

- `GEMINI.md` — Gemini runtime entrypoint.
- Встроенная команда Gemini CLI `/init` — канонический способ создать или обновить project `GEMINI.md`.
- `.gemini/settings.json` остаётся Gemini-native runtime config surface.
- `.gemini/.agents-mode` — optional Orchestrarium overlay, а не замена `.gemini/settings.json`.
- Skills живут в `skills/<name>/SKILL.md`.
- Пользовательские command helpers живут в `commands/**/*.toml`.
- Текущий scaffold остаётся последовательным и human-steered; не предполагайте native parallel dispatch.

## Delivery model

- `$lead` координирует approved work и держит pipeline по стадиям: `Research -> Design -> Plan -> Implement -> Review/QA/Security`.
- Factual roles идут раньше interpretive roles.
- Downstream передаются accepted artifacts, а не raw transcripts.
- `PASS` двигает дальше, `REVISE` остаётся локально до 3 циклов, а `BLOCKED` зарезервирован для реальных external blockers.

## Gemini-side repository concretization

- `references-gemini/` — обязательное standalone reference tree.
- [../docs/agents-mode-reference.md](../docs/agents-mode-reference.md) — канонический operator reference для `.gemini/.agents-mode`.
- Task-memory root, recovery entry point, active-item directory и archive location остаются repository-defined, когда task memory включён.
- Periodic controls живут в [periodic-control-matrix.md](periodic-control-matrix.md).
- Publication safety живёт в [repository-publication-safety.md](repository-publication-safety.md).
- Если Gemini маршрутизирует eligible external work в Claude CLI, `externalClaudeSecretMode` определяет, будет ли secret env injection автоматическим на limit fallback или принудительным уже для primary call.
