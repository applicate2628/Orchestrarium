# Протокол бота ревью Pull Request в GitHub

Этот документ — каноническая нейтральная к провайдеру методика координации одного hosted review run без ошибочной атрибуции evidence от другого run. Установленные копии `github-pr-review-bot/SKILL.md` для Codex и Claude Code остаются самодостаточными operative bindings, потому что эта maintainer reference не устанавливается.

## Идентичность evidence

Каждое решение привязывается к hosted repository, pull request, текущему `headRefOid` и точному идентификатору issue comment `@codex review`. Local ancestry, запомненный status, summary prose и elapsed time не заменяют текущее полное hosted state.

На Representational State Transfer (REST) surface для issue comments после полной pagination используйте `IssueCommentOrder = (parsed UTC created_at, numeric stable REST issue-comment ID)`. Это Orchestrarium total-order convention только для этой surface, а не гарантия chronology от GitHub. Она выбирает самый новый точный trigger и упорядочивает более поздние issue-comment evidence, но не связывает иначе не привязанный result с одним из нескольких overlapping runs. Отсутствующий, malformed, duplicate или incomplete ordering input делает затронутую classification indeterminate.

Cross-surface timestamps не наследуют REST tie-breaker. Evidence с одинаковым временем из REST review, REST issue comment и Graph Query Language (GraphQL) review thread несопоставимы, если surface не предоставляет независимую точную correlation.

## Идентичность автора connector

Используйте один author predicate для evidence успеха, ошибки, finding и in-progress:

- REST objects требуют `user.login == "chatgpt-codex-connector[bot]"` и `user.type == "Bot"`.
- GraphQL objects требуют exact same-node pair `author.login == "chatgpt-codex-connector"` и `author.__typename == "Bot"`, возвращённую этой queried surface.
- Числовой REST `user.id` можно записать как evidence, но нельзя превращать в отдельно придуманный allowlist. Не переносите REST suffix `[bot]` в GraphQL, не удаляйте его из REST и не заимствуйте author field из другой surface.

Отсутствующие, null, mismatched или incompletely fetched author fields делают signal indeterminate. Общего признака «bot-authored» недостаточно для подтверждения identity.

## Атрибуция overlapping runs

Intrinsically correlated signal, например reaction на одном точном trigger, принадлежит этому trigger. Даже тогда он не может сделать весь head clean, пока другой точный trigger для того же `(repository, pull request, headRefOid)` остаётся unresolved.

Submitted review или REST issue-comment result без точного trigger identifier можно связать только тогда, когда полное hosted state оставляет ровно одного unresolved earlier exact trigger candidate на том же head. Если остаются два и более candidates, расположение result после них не определяет owner: оставьте evidence и все затронутые runs в состоянии indeterminate. Не помечайте run как failed или dismissed, не изменяйте retry state и не создавайте новый trigger до reconciliation ownership.

## Семантика clean и failure

Clean result определяется семантически, а не фиксированной фразой. Обязательны connector author identity, current-head reviewed-commit binding, post-trigger order, complete collections, явный и однозначный финальный смысл no-findings, отсутствие current findings и unresolved current connector threads. Wording, emoji и boilerplate могут меняться. Summary-only completion остаётся nonauthorizing.

Для failure signatures действует противоположное правило: каждая retryable или non-retryable terminal signature — точный repo-local predicate, включающий normalized body, surface, connector author identity, current-head binding, ordering и unresolved-trigger attribution. Error-like prose, не включённая в exact list, остаётся indeterminate.

## Retry lineage

Terminal failure и его authorized successor составляют один lineage не более чем с одним successor trigger. Retry никогда не выполняется автоматически. До создания привяжите explicit user authorization и запишите creating transition. Засчитывайте retry только после полного hosted refresh, который однозначно связывает successor trigger identifier, creation time и unchanged head. Definite failed create требует доказательства отсутствия successor; ambiguous create переходит в reconciliation и не может быть повторён. Failed successor не может разрешить ещё одного successor.

## Термины и сокращения

- `GraphQL`: Graph Query Language, язык запросов к API.
- `PR`: Pull Request, запрос на включение изменений.
- `REST`: Representational State Transfer, архитектурный стиль программного интерфейса.
- `UTC`: Coordinated Universal Time, всемирное координированное время.
