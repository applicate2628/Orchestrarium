# Сравнение стратегий workflow

Этот справочник сравнивает основные стратегии workflow, review и control, которые важны для этого репозитория.

Используйте его вместе с:
- [subagent-operating-model.md](subagent-operating-model.md)
- [operating-model-diagram.md](operating-model-diagram.md)
- [operating-model.md](../agents/contracts/operating-model.md)

## 1. Семейства стратегий

| Семейство | Главный вопрос | Типичные примеры |
|---|---|---|
| Structural gate | Нужна ли независимая приёмка вообще? | `builder / blocker separation`, `maker / checker`, `single-owner self-approval` |
| Reviewer mode | Как независимый reviewer должен смотреть на артефакт? | `Claim-Verify`, `Adversarial`, `Claim-Verify + Adversarial` |
| Workflow protection | Как не дать процессу развалиться ещё до review? | `fact-first routing`, `risk-owner routing`, `rolling loop`, `re-intake`, `integration ownership`, `change isolation` |
| Automation support | Что можно проверять без человеческого judgment? | `single-owner + automated gates`, CI, linters, tests, static analysis |

## 2. Текущие дефолты репозитория

| Контекст | Дефолтная защита в этом репозитории | Комментарий |
|---|---|---|
| Кто решает, что вообще входит в delivery | `Roadmap / Intake loop` | `product-manager` владеет admission, `lead` владеет execution |
| Не хватает evidence | `Fact-first routing` | Сначала factual roles, потом interpretive roles |
| Критичный риск домена | `Risk-owner routing` | У риска должен быть собственный owner и собственный artifact |
| Bias на self-approval | `Builder / blocker separation` | Builder и blocking reviewer должны быть разными |
| Известный bounded review risk | `Claim-Verify` | Дефолт, когда risk surface понятен |
| Новый или внешне exposed review risk | `Adversarial` | Дефолт, когда blind spots важнее скорости |
| Критичный change с execution и blind-spot риском одновременно | `Claim-Verify + Adversarial` | Запускать по очереди, сохраняя независимость reviewer'ов |
| Drift scope или priority | `Re-intake` | Возвращать к `product-manager` |
| Несколько фаз должны слиться в один результат | `Integration ownership` | Назначать одного owner до QA |
| Stop-and-wait churn | `Rolling loop` | `PASS` двигает дальше, `REVISE` остаётся локальным не более 2 последовательных циклов для одной роли и одного артефакта, `BLOCKED` должен быть редким |
| Слишком широкий diff | `Change isolation` | Держать seams, blast radius и nearby smoke coverage явными |

## 3. Структурные и review-стратегии

| Стратегия | Тип | Что она разделяет | Лучше всего ловит | Слабее всего ловит | Стоимость | Когда использовать | Статус в репозитории |
|---|---|---|---|---|---|---|---|
| `Single-owner self-approval` | structural baseline | ничего | мелкие low-risk changes | blind spots, self-approval bias, скрытые риски | очень низкая | только для тривиальной работы | не дефолт |
| `Single-owner + automated gates` | automation-supported baseline | builder vs automated checks | syntax, tests, static issues, contract regressions | architecture, UX, product intent, unknown unknowns | низкая | low-risk changes с хорошей автоматикой | support, не sole strategy |
| `Pair / co-builder` | collaborative build mode | два builder'а против одного | быстрое exploration и общий implementation context | слабая независимость, общий anchoring | средняя | для быстрого exploration, не для финального governance | не core pattern |
| `Maker / checker` | lightweight independent gate | builder vs checker | clear execution errors against known criteria | глубокие design blind spots | средняя | bounded work, которому всё ещё нужен второй взгляд | частично пересекается с reviewer lanes |
| `Builder / blocker separation` | structural gate | builder vs independent blocker | self-approval bias, risk-domain independence | слабее, если blocker слишком anchored к builder reasoning | средняя - высокая | любой change, где риск может независимо завалить результат | core |
| `Claim-Verify` | reviewer mode | builder claims vs independent verification | bounded risks, known surfaces, execution fidelity | unknown unknowns и unmodeled threats | средняя | когда builder может сформулировать falsifiable guarantees | core |
| `Adversarial` | reviewer mode | builder reasoning vs hostile review | blind spots, novel failure modes, external exposure | routine bounded defects, speed-sensitive reviews | высокая | когда пропустить unknown risk опаснее, чем пропустить execution bug | core |
| `Claim-Verify + Adversarial` | combined review | сначала verify, потом attack | критичная работа, которой нужны и execution checking, и blind-spot hunting | время и coordination cost | очень высокая | критичные изменения с серьёзным downside | supported when justified |
| `Spec-first + compliance review` | design-control mode | spec vs implementation | API/schema fidelity, предсказуемое выполнение на стабильных контрактах | слабее, если сам spec неверный | средняя - высокая | когда контракты и интерфейсы — главный риск | используется в части design/plan flow |
| `Audit sampling` | governance mode | весь поток vs sampled review | throughput в high-volume flows | по определению может пропускать проблемы | низкая - средняя | bulk operations, где полный review слишком дорог | не core pattern |

## 4. Стратегии защиты workflow

Embedded repository defaults shown in **bold**.

| Стратегия | Главная цель | Лучше всего предотвращает | Когда эскалировать | Статус в репозитории |
|---|---|---|---|---|
| **`Roadmap / Intake loop`** | держать roadmap ownership выше delivery | priority drift, implicit admission, когда delivery начинает владеть roadmap-вопросами | admission в delivery ещё не явный | **core** |
| **`Delivery loop`** | проводить approved work через один staged execution path | lifecycle mixing и ad hoc routing | нужен критичный risk-лан или независимый reviewer | **core** |
| **`Fact-first routing`** | сначала собрать evidence, потом интерпретировать | opinion noise, speculative design, false certainty | interpretive roles начинают гадать | **core** |
| **`Risk-owner routing`** | сделать один риск явно owned | security/performance/reliability/UX drift внутри generic implementation | риск может независимо завалить результат | **core** |
| **`Rolling loop`** | не превращать процесс в stop-and-wait churn | idle handoff latency и лишнее раздувание small corrections | работа застревает между принятыми artifact'ами | **core** |
| **`Re-intake`** | вернуть изменившуюся работу к roadmap ownership | тихая renegotiation scope внутри delivery | сам admitted item уже изменился | **core** |
| **`Integration ownership`** | собрать один coherent result до QA | “каждая фаза прошла, но система целиком не собрана” | несколько implementation phases или specialists должны land together | **core** |
| **`Change isolation`** | ограничить blast radius и защитить seams | unrelated-module churn, случайные cross-cutting edits, скрытый dependency reversal | local feature требует широких structural edits | **core** |
| **`Human / CI gate`** | добавить явную внешнюю approval перед publication | тихая промоция AI-accepted work в push/merge/release | policy требует human или CI approval | **core** |
| **`Consultant advisory`** | добавить non-blocking second opinion, не ломая main pipeline | преждевременное решение при неоднозначности или cross-cutting tradeoffs | facts уже собраны, но route choice всё ещё ambiguous | **supported, optional** |
| **`Parallel read lanes`** | ускорить независимый сбор evidence | serial read-only bottlenecks | scopes overlap или synthesis cost выше выгоды | **supported** |
| `Parallel write lanes` | ускорить disjoint implementation work | ненужная serial implementation, когда boundaries уже frozen | write scopes overlap или contracts ещё двигаются | conditional only |

## 5. Краткий guide выбора

| Если ситуация такая | Начать с | Потом добавить |
|---|---|---|
| Мы ещё не знаем достаточно | `Fact-first routing` | `Risk-owner routing`, если появляется критичный domain risk |
| Мы знаем задачу, но domain risk может её завалить | `Risk-owner routing` | `Builder / blocker separation`, если риску нужна независимая approval |
| Риск известный и bounded | `Claim-Verify` | `Adversarial` только если потеря blind spot очень дорогая |
| Риск новый, exposed или плохо смоделирован | `Adversarial` | `Claim-Verify` сначала, если execution fidelity тоже критична |
| Change явно локальный и additive | `Additive fast lane` | сразу re-classify в normal delivery loop, если поверхность шире ожидаемой или появляется новый risk owner |
| Сам item изменился | `Re-intake` | новый delivery loop после re-admission |
| Работу должны вместе land'ить несколько implementation phases | `Integration ownership` | QA и reviewer gates после появления одного integrated artifact |
| Diff стал слишком широким для local change | `Change isolation` | перекинуть на `architect`, `planner` или `architecture-reviewer` |

## 6. Эвристики выбора

- Используйте `Claim-Verify`, когда reviewer должен проверить, что builder действительно отдал обещанное.
- Используйте `Adversarial`, когда reviewer должен искать то, что builder мог вообще не смоделировать.
- Используйте `Builder / blocker separation`, когда self-approval делает результат ненадёжным.
- Используйте `Fact-first routing`, когда следующий реальный вопрос — factual, а не interpretive.
- Используйте `Re-intake`, когда admitted item изменился, а не просто текущий artifact.
- Используйте `Integration ownership`, когда QA иначе получит частично собранную работу.
- Считайте `change isolation` первичной защитой, а не implementation detail.
