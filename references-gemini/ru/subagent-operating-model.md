# Модель работы субагентов — Gemini Reference

Визуальное дополнение: [operating-model-diagram.md](operating-model-diagram.md)

Эта standalone ветка хранит один Gemini-local operating-model reference как addendum. Каноническая operator truth для `.gemini/.agents-mode`, принятого init-time preset family, общей lane matrix и Claude transport semantics живёт в [../../docs/agents-mode-reference.md](../../docs/agents-mode-reference.md).

## Gemini runtime notes

- `GEMINI.md` — Gemini runtime entrypoint.
- Встроенная команда Gemini CLI `/init` — канонический способ создать или обновить project `GEMINI.md`.
- `.gemini/settings.json` остаётся Gemini-native runtime config surface.
- `.gemini/.agents-mode` — routing overlay Orchestrarium, который seedится при установке, а не замена `.gemini/settings.json`.
- Принятое init-time preset family: `default`, `absolute-balance`, `external-aggressive`, `correctness-first`, `max-speed`. Это только shortcuts на этапе init; имя preset'а не сохраняется после разворачивания в канонические ключи.
- Skills живут в `skills/<name>/SKILL.md`.
- Пользовательские command helpers живут в `commands/**/*.toml`.
- Текущий pack surface остаётся последовательным и human-steered для native internal execution; не предполагайте native parallel dispatch. Независимые external adapters всё ещё могут идти параллельно, когда routing contract и выбранные provider runtimes это допускают.

## Delivery model

- `$lead` координирует approved work и держит pipeline по стадиям: `Research -> Design -> Plan -> Implement -> Review/QA/Security`.
- Factual roles идут раньше interpretive roles.
- Downstream передаются accepted artifacts, а не raw transcripts.
- `PASS` двигает дальше, `REVISE` остаётся локально до 3 циклов, а `BLOCKED` зарезервирован для реальных external blockers.

## Gemini-side repository concretization

- `references-gemini/` — обязательное standalone reference tree.
- [../../docs/agents-mode-reference.md](../../docs/agents-mode-reference.md) — канонический operator reference для `.gemini/.agents-mode`.
- Task-memory root, recovery entry point, active-item directory и archive location остаются repository-defined, когда task memory включён.
- Periodic controls живут в [periodic-control-matrix.md](periodic-control-matrix.md).
- Publication safety живёт в [repository-publication-safety.md](repository-publication-safety.md).
- `externalProvider: auto` использует active named priority profile, но documented repo-local visual heuristics всё ещё могут предпочесть сам Gemini для image, icon, decorative visual и других явно visual lanes.
- `.gemini/.agents-mode` может содержать `externalPriorityProfile`, `externalPriorityProfiles` и `externalOpinionCounts`; shipped profiles сейчас `balanced` и `gemini-crosscheck`.
- Текущая shared lane taxonomy включает `review.performance-architecture`, `worker.systems-performance-implementation`, `worker.ui-structural-modernization` и `worker.ui-surgical-patch-cleanup` вместе с более старыми advisory, review, implementation, long-autonomous, visual и decorative lanes.
- `externalOpinionCounts` задают same-lane distinct-opinion requirements, а не cap на количество same-provider helper instances; bounded helper batches используют `external-brigade`.
- Если Gemini маршрутизирует eligible external work в Claude, нужно уважать и `externalClaudeSecretMode`, и `externalClaudeApiMode`; `claude-api` остаётся Claude transport, а не отдельным provider.
