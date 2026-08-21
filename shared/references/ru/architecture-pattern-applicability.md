# Применимость архитектурных паттернов

Этот документ — перевод нормативного английского источника AP0-AP5. Он не является вторым владельцем семантики и не является энциклопедией паттернов: кандидаты рассматриваются только по наблюдаемым данным задачи, явные противопоказания требуют отклонения, а ноль выбранных паттернов — допустимый результат. Существующие правила допуска шаблонов и минимально достаточной устойчивой архитектуры не меняются.

Роли разделены строго: Lead только распознаёт данные для маршрутизации, Architect принимает решение `selected | rejected | deferred`, Architecture Reviewer независимо проверяет это решение. Backend, Data и Reliability отвечают за последствия уже принятой архитектуры, а не за выбор паттерна.

## Распознавание условий маршрутизации

В уже допущенной нетривиальной работе нужно направить задачу к `$architect` до Plan или Implement, если принятые данные подтверждают хотя бы одну форму проблемы: конфликт бизнес-смыслов или инвариантов; долгоживущий разветвлённый жизненный цикл; существенную асимметрию команд и чтения; неатомарную двойную запись в базу и брокер; одну бизнес-транзакцию через автономных владельцев данных. Lead не выбирает паттерн.

Это правило не меняет допуск шаблонов и не добавляет обязательную стадию Architect. Простой CRUD, небольшой согласованный домен, локальный линейный поток, одна локальная транзакция и отсутствие двойной записи не требуют Architect. Необратимый межвладельческий инвариант всё же направляется Architect, чтобы saga была явно отклонена или отложена, а не предположена.

<a id="apat-ru-apat-p01-semantic-boundary-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-P01-SEMANTIC-BOUNDARY.outcome" value="route-architect:consider-AP1:no-deployment-inference" -->
- `APAT-P01-SEMANTIC-BOUNDARY` -> направить Architect, рассмотреть AP1 и не выводить из семантической границы необходимость отдельного развёртывания.

<a id="apat-ru-apat-p02-long-lived-lifecycle-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-P02-LONG-LIVED-LIFECYCLE.outcome" value="route-architect:consider-AP2:require-transition-evidence" -->
- `APAT-P02-LONG-LIVED-LIFECYCLE` -> направить Architect, рассмотреть AP2 и потребовать данные о переходах.

<a id="apat-ru-apat-p03-read-write-asymmetry-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-P03-READ-WRITE-ASYMMETRY.outcome" value="route-architect:consider-AP3:no-event-sourcing-inference" -->
- `APAT-P03-READ-WRITE-ASYMMETRY` -> направить Architect, рассмотреть AP3 и не выводить автоматически event sourcing.

<a id="apat-ru-apat-p04-dual-write-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-P04-DUAL-WRITE.outcome" value="route-architect:consider-AP4:require-relay-evidence" -->
- `APAT-P04-DUAL-WRITE` -> направить Architect, рассмотреть AP4 и потребовать данные о доставщике сообщений.

<a id="apat-ru-apat-p05-cross-owner-transaction-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-P05-CROSS-OWNER-TRANSACTION.outcome" value="route-architect:consider-AP5:require-compensation-evidence" -->
- `APAT-P05-CROSS-OWNER-TRANSACTION` -> направить Architect, рассмотреть AP5 и потребовать данные о компенсациях.

<a id="apat-ru-apat-n01-coherent-domain-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-N01-COHERENT-DOMAIN.outcome" value="no-force-architect:reject-AP1" -->
- `APAT-N01-COHERENT-DOMAIN` -> не навязывать Architect; при запросе альтернатив отклонить AP1.

<a id="apat-ru-apat-n02-linear-flow-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-N02-LINEAR-FLOW.outcome" value="no-force-architect:reject-AP2" -->
- `APAT-N02-LINEAR-FLOW` -> не навязывать Architect; при запросе альтернатив отклонить AP2.

<a id="apat-ru-apat-n03-simple-crud-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-N03-SIMPLE-CRUD.outcome" value="no-force-architect:reject-AP3" -->
- `APAT-N03-SIMPLE-CRUD` -> не навязывать Architect; при запросе альтернатив отклонить AP3.

<a id="apat-ru-apat-n04-no-dual-write-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-N04-NO-DUAL-WRITE.outcome" value="no-force-architect:reject-AP4" -->
- `APAT-N04-NO-DUAL-WRITE` -> не навязывать Architect; при запросе альтернатив отклонить AP4.

<a id="apat-ru-apat-n05-local-atomic-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-N05-LOCAL-ATOMIC.outcome" value="no-force-architect:reject-AP5" -->
- `APAT-N05-LOCAL-ATOMIC` -> не навязывать Architect; при запросе альтернатив отклонить AP5.

<a id="apat-ru-apat-n06-irreversible-invariant-outcome"></a>
<!-- APAT-SEMANTIC id="APAT-N06-IRREVERSIBLE-INVARIANT.outcome" value="route-architect:reject-or-defer-AP5" -->
- `APAT-N06-IRREVERSIBLE-INVARIANT` -> направить Architect, отклонить или отложить AP5 и потребовать изменения границы, требования либо реально поддерживаемого транзакционного механизма.

## Решение Architect о применимости

Architect владеет решением о применимости и сохраняет правило минимально достаточной устойчивой архитектуры. Рассматриваются только кандидаты с принятыми данными, подтверждающими условие. Для каждого такого кандидата создаётся Pattern Disposition Record; ноль выбранных паттернов допустим. Название, популярность или знакомство модели с паттерном не являются данными.

### AP0 — запись решения по данным

<a id="apat-ru-ap0-candidate"></a>
<!-- APAT-SEMANTIC id="AP0.candidate" value="evidence-triggered-candidate" -->
- `candidate`: кандидат AP1-AP5, вызванный подтверждёнными данными.

<a id="apat-ru-ap0-trigger-evidence"></a>
<!-- APAT-SEMANTIC id="AP0.trigger-evidence" value="accepted-positive-evidence" -->
- `trigger evidence`: принятые положительные данные о проблеме.

<a id="apat-ru-ap0-contraindication-evidence"></a>
<!-- APAT-SEMANTIC id="AP0.contraindication-evidence" value="accepted-negative-evidence" -->
- `contraindication evidence`: принятые данные против применимости.

<a id="apat-ru-ap0-tradeoffs-cost"></a>
<!-- APAT-SEMANTIC id="AP0.tradeoffs-cost" value="operational-cost-and-tradeoffs" -->
- `tradeoffs/cost`: добавленная эксплуатационная, консистентностная, миграционная и когнитивная цена.

<a id="apat-ru-ap0-composition-interactions"></a>
<!-- APAT-SEMANTIC id="AP0.composition-interactions" value="distinct-concern-and-boundaries" -->
- `composition interactions`: отдельная ответственность и границы состояния, отказов, сообщений и консистентности при композиции кандидатов.

<a id="apat-ru-ap0-disposition"></a>
<!-- APAT-SEMANTIC id="AP0.disposition" value="selected-or-rejected-or-deferred" -->
- `disposition`: ровно одно из `selected`, `rejected` или `deferred`.

<a id="apat-ru-ap0-open-evidence-questions"></a>
<!-- APAT-SEMANTIC id="AP0.open-evidence-questions" value="missing-evidence-and-resolving-probe" -->
- `open evidence questions`: недостающие данные и конкретная проверка, которая их получит; без обоих полей `deferred` недействителен.

### AP1 — предметно-ориентированное проектирование и bounded context

<a id="apat-ru-ap1-trigger"></a>
<!-- APAT-SEMANTIC id="AP1.trigger" value="semantic-boundary-conflict" -->
- Условие: одинаковые доменные слова, инварианты, владение или темп изменений имеют существенно разные смыслы, и на границе требуется перевод.

<a id="apat-ru-ap1-contraindication"></a>
<!-- APAT-SEMANTIC id="AP1.contraindication" value="small-coherent-domain-no-artificial-split" -->
- Противопоказание: домен мал и согласован либо граница только повторяет команды или таблицы, либо автоматически предполагает микросервисное разделение.

<a id="apat-ru-ap1-tradeoff"></a>
<!-- APAT-SEMANTIC id="AP1.tradeoff" value="boundary-governance-and-translation-cost" -->
- Цена: управление границей и перевод повышают стоимость координации и сопровождения.

<a id="apat-ru-ap1-question"></a>
<!-- APAT-SEMANTIC id="AP1.question" value="meanings-invariants-owners-crossings-modular-monolith" -->
- Вопросы: какие смыслы и инварианты различаются, кто владеет каждой моделью, что пересекает границу и может ли модульный монолит сохранить её?

<a id="apat-ru-ap1-composition"></a>
<!-- APAT-SEMANTIC id="AP1.composition" value="bounded-context-not-deployment" -->
- Композиция: `bounded-context-not-deployment`; семантическая граница не предписывает отдельное развёртывание.

### AP2 — явный конечный автомат или workflow

<a id="apat-ru-ap2-trigger"></a>
<!-- APAT-SEMANTIC id="AP2.trigger" value="long-lived-branch-heavy-restartable-auditable-lifecycle" -->
- Условие: процесс долгоживущий, разветвлённый, возобновляемый, аудируемый либо имеет допустимые и запрещённые переходы, таймауты, отмену или ручные ветви.

<a id="apat-ru-ap2-contraindication"></a>
<!-- APAT-SEMANTIC id="AP2.contraindication" value="short-local-linear-flow" -->
- Противопоказание: поток короткий, локальный и линейный, а обычный типизированный код достаточно явно показывает недопустимые состояния.

<a id="apat-ru-ap2-tradeoff"></a>
<!-- APAT-SEMANTIC id="AP2.tradeoff" value="persisted-state-replay-and-operational-cost" -->
- Цена: сохраняемое состояние workflow, повторное воспроизведение, версионирование и эксплуатация добавляют сложность.

<a id="apat-ru-ap2-question"></a>
<!-- APAT-SEMANTIC id="AP2.question" value="states-transitions-owner-persistence-cancel-timeout-settlement" -->
- Вопросы: перечислить состояния, переходы, запрещённые переходы, владельца записи, хранение и повтор, отмену, таймаут и терминальное завершение.

<a id="apat-ru-ap2-composition"></a>
<!-- APAT-SEMANTIC id="AP2.composition" value="workflow-not-saga" -->
- Композиция: `workflow-not-saga`; workflow может координировать saga, но не является тем же паттерном.

### AP3 — разделение ответственности команд и запросов (CQRS)

<a id="apat-ru-ap3-trigger"></a>
<!-- APAT-SEMANTIC id="AP3.trigger" value="materially-asymmetric-command-query" -->
- Условие: модели команд и запросов, нагрузка, авторизация или требования консистентности существенно асимметричны.

<a id="apat-ru-ap3-contraindication"></a>
<!-- APAT-SEMANTIC id="AP3.contraindication" value="simple-crud-one-adequate-model" -->
- Противопоказание: обычному CRUD достаточно одной модели либо цена eventual consistency и эксплуатации проекций выше доказанной пользы асимметрии.

<a id="apat-ru-ap3-tradeoff"></a>
<!-- APAT-SEMANTIC id="AP3.tradeoff" value="eventual-consistency-projection-and-rebuild-cost" -->
- Цена: eventual consistency, эксплуатация проекций, перестроение и сверка добавляют сложность.

<a id="apat-ru-ap3-question"></a>
<!-- APAT-SEMANTIC id="AP3.question" value="asymmetry-staleness-projection-owner-rebuild-reconciliation" -->
- Вопросы: какая асимметрия наблюдается, какая устарелость допустима и кто владеет перестроением и сверкой проекций?

<a id="apat-ru-ap3-composition"></a>
<!-- APAT-SEMANTIC id="AP3.composition" value="cqrs-not-event-sourcing" -->
- Композиция: `cqrs-not-event-sourcing`; CQRS не подразумевает event sourcing.

### AP4 — transactional outbox

<a id="apat-ru-ap4-trigger"></a>
<!-- APAT-SEMANTIC id="AP4.trigger" value="unsafe-database-message-dual-write" -->
- Условие: локальное изменение состояния и публикация сообщения образуют небезопасную двойную запись в базу и брокер.

<a id="apat-ru-ap4-contraindication"></a>
<!-- APAT-SEMANTIC id="AP4.contraindication" value="reject-when-no-dual-write-or-verified-atomic-mechanism" -->
- Противопоказание: двойной записи нет либо доказанный атомарный механизм уже охватывает оба эффекта.

<a id="apat-ru-ap4-tradeoff"></a>
<!-- APAT-SEMANTIC id="AP4.tradeoff" value="relay-retry-dedup-retention-replay-cost" -->
- Цена: владелец доставки, повторы, дедупликация, хранение, воспроизведение и очистка добавляют сложность.

<a id="apat-ru-ap4-question"></a>
<!-- APAT-SEMANTIC id="AP4.question" value="local-transaction-relay-idempotency-retention-replay" -->
- Вопросы: какова граница локальной транзакции и кто доставляет, повторяет, дедуплицирует, хранит и воспроизводит сообщения?

<a id="apat-ru-ap4-composition"></a>
<!-- APAT-SEMANTIC id="AP4.composition" value="outbox-not-distributed-atomicity-or-exactly-once" -->
- Композиция: `outbox-not-distributed-atomicity-or-exactly-once`; outbox повышает надёжность локальной публикации, но не даёт межсервисную атомарность или exactly-once delivery.

### AP5 — saga или компенсация

<a id="apat-ru-ap5-trigger"></a>
<!-- APAT-SEMANTIC id="AP5.trigger" value="cross-owner-transaction-no-safe-distributed-transaction" -->
- Условие: транзакция пересекает автономных владельцев данных, безопасной распределённой транзакции нет, а компенсации могут сохранить требуемые гарантии.

<a id="apat-ru-ap5-contraindication"></a>
<!-- APAT-SEMANTIC id="AP5.contraindication" value="local-atomic-or-noncompensable-immediate-invariant" -->
- Противопоказание: доступна одна локальная атомарная транзакция либо немедленный инвариант и необратимый шаг нельзя безопасно компенсировать.

<a id="apat-ru-ap5-tradeoff"></a>
<!-- APAT-SEMANTIC id="AP5.tradeoff" value="compensation-coordination-manual-repair-cost" -->
- Цена: компенсация, координация, частичный прогресс и ручное восстановление добавляют сложность.

<a id="apat-ru-ap5-question"></a>
<!-- APAT-SEMANTIC id="AP5.question" value="local-steps-compensations-retry-timeout-idempotency-settlement" -->
- Вопросы: кто владеет каждой локальной транзакцией и компенсацией, и как наблюдаются повторы, таймауты, идемпотентность, ручное восстановление и терминальное завершение?

<a id="apat-ru-ap5-composition"></a>
<!-- APAT-SEMANTIC id="AP5.composition" value="saga-not-local-transaction" -->
- Композиция: `saga-not-local-transaction`; saga может использовать outbox, но не заменяет доступную локальную транзакцию.

Если выбирается больше одного кандидата, нужно объяснить отдельную ответственность каждого и композицию границ состояния, отказов, сообщений и консистентности без двух владельцев одного инварианта.

## Проверка Architecture Reviewer

Architecture Reviewer проверяет, но не перепроектирует: полноту Pattern Disposition Record; положительные и отрицательные данные; допустимость нуля выбранных паттернов; соответствие минимально достаточной архитектуре, одному владельцу, устойчивым швам и явным отказам; все пять различий при композиции; отсутствие логики выбора у Lead, Backend, Data и Reliability; ссылку на принятое решение; построчное смысловое соответствие русского перевода.

Статическая эквивалентность исходников и установки не доказывает поведение провайдера или модели. Без отдельно допущенного отчёта закреплённого запуска в свежем контексте точность исполнения остаётся `ASSUMPTION (UNVERIFIED)`.

## Значения диагностик

<a id="apat-ru-apat-e001-canonical-missing-meaning"></a>
<!-- APAT-SEMANTIC id="APAT-E001-CANONICAL-MISSING.meaning" value="canonical-missing-or-duplicate" -->
- `APAT-E001-CANONICAL-MISSING`: нормативный документ или его нормативный проекционный блок отсутствует либо дублируется.

<a id="apat-ru-apat-e002-projection-drift-meaning"></a>
<!-- APAT-SEMANTIC id="APAT-E002-PROJECTION-DRIFT.meaning" value="source-projection-differs" -->
- `APAT-E002-PROJECTION-DRIFT`: проекция роли отличается от нормативного блока или соответствующей проекции другого провайдера.

<a id="apat-ru-apat-e003-route-miss-meaning"></a>
<!-- APAT-SEMANTIC id="APAT-E003-ROUTE-MISS.meaning" value="positive-route-missed-or-negative-forced" -->
- `APAT-E003-ROUTE-MISS`: положительный сценарий не попал к Architect либо отрицательный простой сценарий принудительно попал к Architect.

<a id="apat-ru-apat-e004-cargo-cult-meaning"></a>
<!-- APAT-SEMANTIC id="APAT-E004-CARGO-CULT.meaning" value="pattern-selected-without-evidence-or-negative-not-rejected" -->
- `APAT-E004-CARGO-CULT`: паттерн выбран без положительных данных либо не отклонён в отрицательном сценарии.

<a id="apat-ru-apat-e005-disposition-incomplete-meaning"></a>
<!-- APAT-SEMANTIC id="APAT-E005-DISPOSITION-INCOMPLETE.meaning" value="disposition-required-field-missing" -->
- `APAT-E005-DISPOSITION-INCOMPLETE`: отсутствует обязательное решение, противопоказание, цена, композиция или вопрос о данных.

<a id="apat-ru-apat-e006-installed-missing-meaning"></a>
<!-- APAT-SEMANTIC id="APAT-E006-INSTALLED-MISSING.meaning" value="disposable-install-projection-missing-or-drifted" -->
- `APAT-E006-INSTALLED-MISSING`: в изолированной установке проекция отсутствует либо отличается от исходника провайдера.

<a id="apat-ru-apat-e007-model-fidelity-meaning"></a>
<!-- APAT-SEMANTIC id="APAT-E007-MODEL-FIDELITY.meaning" value="pinned-model-misapplies-installed-contract" -->
- `APAT-E007-MODEL-FIDELITY`: закреплённый запуск провайдера и модели в свежем контексте игнорирует либо неверно применяет установленный контракт.

<a id="apat-ru-apat-e008-ru-semantic-drift-meaning"></a>
<!-- APAT-SEMANTIC id="APAT-E008-RU-SEMANTIC-DRIFT.meaning" value="russian-semantic-meaning-differs" -->
- `APAT-E008-RU-SEMANTIC-DRIFT`: русский текст пропускает, отрицает, ослабляет, усиливает или иначе меняет нормативное поле, правило, результат сценария либо значение диагностики.

## Регрессионные проверки

- `APAT-G01-NO-UNIVERSAL-PRELUDE`: простые отрицательные сценарии не навязывают Architect, ненужная церемония отклоняется.
- `APAT-G02-MECHANICS-PRESERVED`: существующая механика архитектурных слоёв и её валидатор 19 ролей не меняются.
- `APAT-G03-ROLE-SEPARATION`: Lead маршрутизирует, Architect принимает решение, Reviewer проверяет; роли реализации и риска не выбирают.
- `APAT-G04-PROVIDER-PARITY`: каждый нормативный блок имеет по одной точной проекции Codex и Claude Code.
- `APAT-G05-INSTALLED-PARITY`: файлы ролей в изолированной установке равны исходникам провайдера.
- `APAT-G06-NO-RUNTIME-OVERCLAIM`: статическое выполнение контракта не доказывает послушание провайдера или модели.
- `APAT-G07-C6-CLEAN-STATE`: в живой поверхности изменения остаётся одна актуальная истина AP0-AP5.
- `APAT-G08-RU-SEMANTIC-PARITY`: каждой нормативной строке соответствует одна русская строка и независимая двуязычная проверка.

## Термины и сокращения

- **APAT** — пространство имён контракта и тестов применимости архитектурных паттернов.
- **DDD** — предметно-ориентированное проектирование.
- **CQRS** — разделение ответственности команд и запросов.
- **CRUD** — создание, чтение, обновление и удаление.
- **PASS** — данных достаточно для указанного контрольного этапа.
- **ASSUMPTION (UNVERIFIED)** — утверждение, не подтверждённое текущими данными и снабжённое проверкой для его разрешения.
