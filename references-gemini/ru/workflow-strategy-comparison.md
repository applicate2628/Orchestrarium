# Сравнение стратегий workflow

Этот reference сравнивает основные workflow, review и control strategies, которые важны для standalone Gemini branch.

Используйте его вместе с:

- [subagent-operating-model.md](subagent-operating-model.md)
- [operating-model-diagram.md](operating-model-diagram.md)
- [../../docs/agents-mode-reference.md](../../docs/agents-mode-reference.md), когда важно поведение `.gemini/.agents-mode`

## Семейства стратегий

| Семейство | Главный вопрос | Типичные примеры |
|---|---|---|
| Structural gate | Нужен ли вообще независимый approval? | `builder / blocker separation`, `maker / checker`, `single-owner self-approval` |
| Reviewer mode | Как независимый reviewer должен смотреть на артефакт? | `Claim-Verify`, `Adversarial`, `Claim-Verify + Adversarial` |
| Workflow protection | Как не допустить хаоса ещё до начала review? | `fact-first routing`, `risk-owner routing`, `rolling loop`, `re-intake`, `integration ownership`, `change isolation` |
| Automation support | Что можно проверить без human judgment? | tests, linters, static analysis, structural validators |

## Текущие default protections репозитория

| Concern | Default protection | Примечание |
|---|---|---|
| Roadmap vs delivery ownership | `Roadmap / Intake loop` | `product-manager` владеет admission; `lead` владеет execution |
| Missing evidence | `Fact-first routing` | factual roles идут до interpretive roles |
| Critical domain risk | `Risk-owner routing` | у риска должен быть свой owner и artifact |
| Self-approval bias | `Builder / blocker separation` | builder и blocking reviewer разделены |
| Scope или priority drift | `Re-intake` | вернуть к `product-manager` |
| Multi-phase landing | `Integration ownership` | назвать одного owner до QA |
| Stop-and-wait churn | `Rolling loop` | `PASS` продвигает, `REVISE` остаётся локально, `BLOCKED` редок |
| Broad unnecessary diff | `Change isolation` | держать approved seams и blast radius явными |

## Матрица классификации изменений

| Класс изменения | Обязательная routing / gates | Пример |
|---|---|---|
| `cosmetic` | Обычно только QA | wording, formatting, comments |
| `additive` | Обычный delivery loop; extra specialist lanes только если появляется новый risk owner | новый код или docs, расширяющие поведение без изменения contracts |
| `behavioral` | Сначала factual или design owner, если evidence тонкий; QA обязателен | validation, error handling, runtime flow changes |
| `breaking-or-cross-cutting` | Architect и обычно planner; re-review downstream artifacts | contract, seam, migration или multi-boundary changes |

## Минимальный selection guide

| Ситуация | С чего начать | Что добавить потом |
|---|---|---|
| Мы пока знаем недостаточно | `Fact-first routing` | `Risk-owner routing`, если появляется критичный domain risk |
| Риск известен и ограничен | `Claim-Verify` | `Adversarial`, только если blind spots дороги |
| Риск новый или плохо смоделирован | `Adversarial` | `Claim-Verify`, если одновременно критична fidelity исполнения |
| Изменение явно локальное и additive | `Additive fast lane` | Переклассифицировать, если поверхность расширяется или появляется новый risk owner |
| Сам admitted item изменился | `Re-intake` | Новый delivery loop после повторного admission |
