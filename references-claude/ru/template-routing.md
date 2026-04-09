# Маршрутизация по шаблонам

Этот документ описывает актуальную runtime-модель маршрутизации. Полный blueprint архитектуры — в [subagent-operating-model.md](subagent-operating-model.md).

## Дерево выбора шаблона

```text
Нужны параллельные risk owners (security + performance + ...)?
  Да → шаблон с requiresLead: true (full-delivery / security / performance / geometry / combined-critical)
  Нет → Нужна реализация?
          Нет → research или review
          Да  → Один модуль, контракты без изменений?
                  Да  → quick-fix
                  Нет → full-delivery
```

## Шаблоны

| Шаблон | Lead? | Min ролей | Когда |
| --- | --- | --- | --- |
| `quick-fix` | Нет | 1 | Баг-фикс, опечатка, локальное добавление |
| `research` | Нет | 2 | Исследование, ADR, анализ альтернатив |
| `review` | Нет | 3 | Ревью PR, quality gate, валидация |
| `full-delivery` | Да | 4 | Новая фича, существенное изменение |
| `security-sensitive` | Да | 6 | Auth, trust boundaries, credentials, уязвимости |
| `performance-sensitive` | Да | 6 | Жёсткие бюджеты, SLA, latency/throughput |
| `geometry-review` | Да | 7 | Пространственные вычисления, transforms, meshing |
| `combined-critical` | Да | 5 | Несколько доменов риска одновременно |

## Маршрутизация

- `requiresLead: false` — main conversation управляет цепочкой напрямую, вызывая specialists по порядку и передавая accepted artifact следующей роли.
- `requiresLead: true` — `$lead` координирует work-items, risk owners, интеграцию и gates.
- Пользователь может вызвать любую роль напрямую: `$analyst`, `$consultant`, `$lead review`.
- Roadmap/приоритеты → `$product-manager`.
- Переклассифицировать немедленно, если scope выходит за текущий шаблон.

## Примеры

| Запрос | Шаблон | Что происходит |
| --- | --- | --- |
| "почини баг в auth.ts" | `quick-fix` | implementer → QA |
| "сделай ревью этого PR" | `review` | analyst → QA → reviewers |
| "исследуй как работает кеширование" | `research` | analyst → architect |
| "реализуй регистрацию пользователей" | `full-delivery` | `$lead` координирует pipeline |
| "$consultant" | — | Консультант для второго мнения |
| "$product-manager что делать дальше?" | — | PM для roadmap-решений |

## Recovery

Все chains с 2+ стадиями сохраняют state и accepted artifacts в `work-items/active/`. При прерывании сессии следующая сессия продолжает с последнего accepted artifact.
