# Память задач репозитория

Этот репозиторий использует долговечные repo-local артефакты, а не память чата, как источник истины для важной текущей работы.

Tracked task memory опционален и задаётся самим репозиторием. Когда репозиторий решает использовать его, `task-memory directory`, `recovery entry point`, `active-item directory` и `archive location` задаются конфигурацией репозитория.

`shared/references/` — канонический дом для стабильной общерепозиторной design-методологии. `references-gemini/` хранит Gemini-specific reference material и compatibility pointers. `docs/agents-mode-reference.md` — общий operator reference, когда важно поведение `.gemini/.agents-mode.yaml`.

## Обязательный набор артефактов

Для любой нетривиальной работы, маршрутизированной через `$lead`, папка item должна содержать эти артефакты:

| Артефакт | Требуется когда | Владелец контента | Назначение |
|---|---|---|---|
| `roadmap.md` | до старта нетривиальной delivery-работы | `$product-manager`, или `$lead` при фиксации прямого human admission source | почему item существует, какой outcome принят, что явно вне scope |
| `brief.md` | до старта нетривиальной delivery-работы | `$lead` | bounded source of truth для scope, стадии, рисков, владельцев и must-not-break surfaces |
| `status.md` | до старта нетривиальной delivery-работы | `$lead` | interruption-safe recovery log с текущим состоянием и следующим действием |
| `plan.md` | до старта реализации или ревью | `$planner` | утверждённый план фазы и чеклист выполнения |
| `closure.md` | до перемещения в архив | `$lead` | финальная запись outcome, residual risk и расположения архива |

Дополнительные артефакты требуются когда workflow их запрашивает:

- `research.md`
- `design.md` или `adr.md`
- `constraints/*.md`
- `notes.md` или `notes/*.md`
- `reports/*.md`

## Применение и восстановление

- `$lead` не должен продолжать нетривиальную delivery-работу без артефактов, требуемых текущей стадией, когда tracked task memory включён.
- `$lead` не должен начинать реализацию или независимое ревью без требуемых upstream принятых артефактов.
- После каждого принятого артефакта, прерывания или существенного изменения маршрута `$lead` обновляет `status.md` в конфигурируемой recovery location.
- При возобновлении после прерывания или потери контекста начинайте с repository-defined recovery entry point, затем откройте `status.md` item'а, затем `brief.md`.
- Если требуемые task-memory артефакты для конфигурируемого workflow отсутствуют или устарели, остановитесь и восстановите их до продолжения delivery.

## Безопасность публикации

- Конфигурируемая tracked task-memory directory, когда она используется, — это документация репозитория и должна быть безопасна для публикации.
- Общерепозиторная политика для всего tracked-контента живёт в [shared/references/ru/repository-publication-safety.md](../../shared/references/ru/repository-publication-safety.md).
- Не помещайте секреты, токены, credentials, клиентские данные, приватные идентификаторы, сырые логи, полные транскрипты команд или machine-specific абсолютные пути в tracked task-memory артефакты.
