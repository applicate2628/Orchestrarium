# Память задач репозитория

Этот репозиторий использует долговечные repo-local артефакты, а не chat memory, как источник истины для важной текущей работы.

Tracked task memory опционален и задаётся самим репозиторием. Когда репозиторий решает его использовать, task-memory directory, recovery entry point, active-item directory и archive location задаются конфигурацией репозитория.

`references-gemini/` — канонический дом для стабильной Gemini-side governance и methodology references в этой standalone ветке. `docs/agents-mode-reference.md` — канонический operator reference для optional `.gemini/.agents-mode` overlay. Когда task memory включён, конфигурируемая task-memory directory остаётся домом для item-specific execution memory.

## Обязательный набор артефактов

Для любой нетривиальной работы, маршрутизированной через `$lead`, папка item должна содержать:

| Артефакт | Требуется когда | Владелец контента | Назначение |
|---|---|---|---|
| `roadmap.md` | до старта нетривиальной delivery-работы | `$product-manager`, или `$lead`, когда он фиксирует прямой human admission source | почему item существует, какой outcome принят, что явно вне scope |
| `brief.md` | до старта нетривиальной delivery-работы | `$lead` | bounded source of truth для scope, stage, risks, owners и must-not-break surfaces |
| `status.md` | до старта нетривиальной delivery-работы | `$lead` | interruption-safe recovery log с current state и next action |
| `plan.md` | до начала реализации или review | `$planner` | approved phase plan и execution checklist |
| `closure.md` | до перемещения в archive | `$lead` | финальная запись outcome, residual risk и archive location |

Дополнительные артефакты требуются, когда workflow их запрашивает:

- `research.md`
- `design.md` или `adr.md`
- `constraints/*.md`
- `notes.md` или `notes/*.md`
- `reports/*.md`

## Применение и восстановление

- `$lead` не должен продолжать нетривиальную delivery-работу без stage-required artifacts, когда tracked task memory включён.
- `$lead` не должен начинать implementation или independent review без требуемых upstream accepted artifacts.
- После каждого принятого артефакта, прерывания или существенного изменения маршрута `$lead` обновляет `status.md` в configured recovery location.
- При возобновлении после прерывания или потери контекста начинайте с repository-defined recovery entry point, затем откройте `status.md` item'а, затем `brief.md`.
- Если required task-memory artifacts для текущего workflow отсутствуют или устарели, остановитесь и восстановите их до продолжения delivery.

## Безопасность tracked content

- Конфигурируемая tracked task-memory directory, когда она используется, — это tracked documentation репозитория и она должна быть безопасной для публикации.
- Общерепозиторная политика для всего tracked content живёт в [repository-publication-safety.md](repository-publication-safety.md).
- Не помещайте secrets, tokens, credentials, customer data, private identifiers, raw logs, полные command transcripts или machine-specific absolute paths в tracked task-memory artifacts.
