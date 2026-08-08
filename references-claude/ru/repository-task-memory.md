# Память задач репозитория

Этот репозиторий использует `work-items/` как канонический локальный корень памяти задач, но сам каталог намеренно остаётся local-only и не должен попадать в tracked git.

### Условное хранение

- `work-items/` — каноническая локальная task-memory документация для recovery и handoff на машине оператора. Активный item означает `work-items/active/<slug>/` текущей задачи, а не простое наличие каталога `work-items/`.
- При активном item специалисты пишут только канонические артефакты item; root фиксирует краткие результаты линий и provenance в `agent-runs.jsonl`. Дубликаты в `.reports/` и `.plans/` не создаются.
- `.reports/YYYY-MM/` — опциональное одноразовое резюме meaningful standalone результата без активного item. Формат: `report(<role>)-YYYY-MM-DD_HH-MM_topic.md`.
- `.plans/YYYY-MM/` — опциональный одноразовый снимок только для явно запрошенного standalone-плана без активного item. Формат: `plan(<role>)-YYYY-MM-DD_HH-MM_topic.md`.

Тривиальная работа без ценности для recovery или сохранения ничего не пишет. Работа, требующая stages, recovery или continuation, принимается как work-item.

## Структура

```
work-items/
  README.md             # Generated human-readable recovery start/read-model
  index.md              # Необязательный compatibility snapshot
  backlog/              # Допущенные, но ещё не начатые items
  active/
    <date>-<slug>/      # Текущая работа в delivery
      roadmap.md        # Решение по допуске (owned by product-manager или пользователь напрямую)
      brief.md          # Канонический brief (owned by lead)
      status.md         # Живой журнал выполнения (owned by lead)
      plan.md           # План фазы (owned by planner, требуется перед implementation/review)
      closure.md        # Финальная запись перед архивированием
      notes.md / notes/ # Technical notes, открытия, follow-ups
  archive/
    <date>-<slug>/      # Завершённая или отменённая работа
```

## Обязательные артефакты по стадии

| Стадия | Требуется |
|--------|-----------|
| Roadmap / Intake | `roadmap.md` |
| Delivery начато | `roadmap.md`, `brief.md`, `status.md` |
| Перед реализацией / ревью | `plan.md` + все upstream-артефакты |
| Перед архивированием | `closure.md` |

Если требуемые upstream-артефакты отсутствуют или устарели, остановитесь и восстановите их или верните item на требуемую upstream-стадию до продолжения delivery.

## Владение артефактами

- `$product-manager` владеет `roadmap.md` когда intake — roadmap item
- `lead` владеет `brief.md` и `status.md`
- `$planner` владеет `plan.md`
- Каждый специалист владеет артефактом своей стадии
- `$knowledge-archivist` владеет физической lifecycle-сверкой, generated read-model, шаблонами и гигиеной архива

## Task-memory linkage

- Каждый work-item в `work-items/` соответствует записи в индексе задач команды, управляемом операционной средой.
- `status.md` work-item ДОЛЖЕН включать поле `Task ID` когда среда поддерживает кросс-линки.
- При архивировании work-item соответствующая задача помечается `completed`/`cancelled` с архивной заметкой.
- Generated `work-items/README.md` — портируемая human-readable entry point; физические roots и owning artifacts остаются истиной даже при устаревшем generated view.
- Эта связь поддерживается `$lead` при каждом переходе стадии и проверяется `$knowledge-archivist` по физическому состоянию во время аудитов старта сессии. `work-items/index.md` не является sync-gate.

## Технические notes и история решений

- Используйте `notes.md` или `notes/` для технических находок, открытий реализации, отклонённых альтернатив, миграционных замечаний и follow-up идей, которые должны пережить текущую сессию.
- Используйте `status.md` для хронологического состояния выполнения и заметок при передаче.
- Используйте `closure.md` для финальной записи закрытия до перемещения item из `active/`.
- Используйте `design.md` или `adr.md` для принятых долгосрочных технических решений. Заметка не заменяет принятый артефакт решения.

## Правила безопасности публикации

- Правила безопасности публикации репозитория применяются ко всем work-item артефактам. См. [shared/references/ru/repository-publication-safety.md](../../shared/references/ru/repository-publication-safety.md).
- `work-items/` не должен force-add'иться или staging'иться для публикации; в tracked git должны попадать только дистиллированные принятые артефакты в канонических docs-поверхностях.
- Секреты, credentials, клиентские данные и машинно-специфичные пути не должны попадать ни в локальные work-item папки, ни в distilled tracked artifacts, которые из них рождаются.
- Используйте `/.scratch/` для raw transcript'ов и пред-redaction материала.

## Восстановление после прерывания

При потере контекста или прерывании сессии:
1. Откройте generated `work-items/README.md` для human-readable обзора
2. Найдите item в физических roots `backlog/`, `active/` или `archive/YYYY-MM/`
3. Откройте `status.md` item'а — посмотрите последнюю стадию и gate
4. Откройте `brief.md` — восстановите scope и constraints
5. Проверьте что все требуемые для текущей стадии артефакты существуют
6. Если артефакты устарели или отсутствуют, восстановите их до продолжения delivery
