# Матрица периодических проверок

Этот репозиторий использует периодические проверки как дополнение к stage gates, а не их замену.

## Слои периодичности

| Слой | Назначение | Типичный владелец |
|---|---|---|
| На сессию | Поймать stale active items и отсутствующее recovery state до возобновления | `$lead` |
| Еженедельно | Поймать structural drift, ошибки risk routing, repo consistency gaps и проблемы publication safety | `$lead`, `$knowledge-archivist` или соответствующий reviewer |
| Веха / квартал | Поймать накопленный refactor debt, archive hygiene и operating-model drift | `$lead`, `$knowledge-archivist`, `$architecture-reviewer` |

## Матрица проверок

| Проверка | Владелец | Периодичность или триггер | Evidence | Действие при провале |
|---|---|---|---|---|
| Аудит свежести активных items | `$lead` | Каждое возобновление или старт сессии | Repository-defined recovery entry point плюс snapshot `status.md` каждого активного item | Обновить `status.md` или припарковать/архивировать item до продолжения |
| Аудит полноты требуемых артефактов | `$lead` | Каждое возобновление или смена стадии | Папка item содержит stage-required artifacts для текущей фазы | Восстановить недостающий артефакт или вернуть item на нужную upstream стадию |
| Синхронизация recovery entry point | `$knowledge-archivist` | Каждое возобновление, архивирование или завершение | Конфигурируемый recovery entry point и связанные active/archive locations соответствуют реальной структуре репозитория | Обновить recovery entry point или связанные locations до продолжения delivery |
| Аудит risk routing | `$lead` | Еженедельно или при изменении scope | `brief.md` и `status.md` item показывают корректный change class и требуемые specialist lanes | Переклассифицировать item и добавить недостающие specialist или reviewer lanes |
| Аудит консистентности репозитория | `$knowledge-archivist` | Еженедельно | `README.md`, `INSTALL.md`, `references-gemini/`, `docs/agents-mode-reference.md` и `src.gemini/` остаются консистентными | Открыть bounded docs или hygiene follow-up; если фикс меняет governance semantics, направить через `$architecture-reviewer` до публикации |
| Точечная проверка publication safety | `$lead` или соответствующий reviewer | Еженедельно или до публикации | Review staged diff показывает, что tracked content свободен от секретов, сырых логов, полных transcript и machine-specific paths | Redact или переместить сырой материал в `/.scratch/` до публикации |
| Гигиена закрытия и архива | `$knowledge-archivist` | Ежемесячно или при закрытии вехи | Завершённые или отменённые items перемещены в configured archive location, а связанная recovery metadata обновлена корректно | Архивировать item и обновить связанную recovery metadata |
| Проверка соответствия operating model | `$lead` с `$architecture-reviewer` при необходимости | Ежеквартально | Недавняя работа всё ещё соответствует документированной routing и gate model | Обновить docs или завести governance follow-up item |

## Минимальное правило

Используйте периодические проверки для ловли drift между gates. Используйте stage gates, чтобы не пускать плохую работу дальше.
