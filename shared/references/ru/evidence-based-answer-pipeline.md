# Evidence-Based Answer Pipeline — Reference

Это reference-документ для high-stakes domains, где нужны evidence-backed answers. Он НЕ устанавливается в target projects — это methodology reference для построения verification pipelines в доменах, где непроверенные assumptions стоят дорого.

**Применимые домены:** scientific computing, numerical methods, geometry и spatial computation, UI/UX implementation, performance-critical systems, security-sensitive work, data engineering и migrations, API integrations, а также любой decision-critical output, где непроверенные assumptions несут высокий риск.

**Источник:** адаптировано из `claude_api_template_maximal.md` — anti-hallucination pipeline для production LLM systems.

---

## Architecture

Используйте multi-pass pipeline, а не один запрос:

1. **Retrieval / tool pass** — собрать evidence из authoritative sources до ответа.
2. **Evidence extraction pass** — извлечь только fragments, которые прямо поддерживают ответ.
3. **Draft answer from evidence only** — синтезировать ответ только из extracted evidence.
4. **Verifier pass** — проверить каждый claim against evidence и удалить unsupported claims.
5. **Optional structured-output pass** — оформить verified data в нужную schema.

## Key Principles

- Никогда не отвечайте по памяти, если tool или inspection может проверить claim.
- Если sources конфликтуют, явно покажите конфликт — не усредняйте и не сглаживайте.
- Если evidence недостаточно, верните partial answer с явными gaps.
- Если вопрос требует current/live data, а live data недоступна, не отвечайте из stale knowledge.

## Verification Rules

- Каждый claim в final answer должен прослеживаться к verified source.
- Для каждого claim нужен verdict: `supported`, `unsupported` или `ambiguous`.
- Unsupported или ambiguous claims удаляются из final answer.
- "Do not rescue with guesses": если evidence не хватает, скажите об этом.

## Stop / Refusal Rules

- Нет verified sources — не давайте содержательный ответ.
- Вопрос про `current`, `today` или `latest` без live data — не давайте содержательный ответ.
- Sources конфликтуют — покажите конфликт, не склеивайте версии.
- Coverage частичный — верните partial answer и явно перечислите gaps.

## Relevance To Our Governance

Этот pipeline операционализирует несколько hygiene rules на system level:

- **Ambiguity resolution discipline** — verify, do not guess.
- **Pre-fix diagnostic gate** — зафиксировать наблюдаемые данные verbatim, сформировать гипотезу, проверить каждое звено цепи — до первого code-mutating tool call в bug-report контексте (start-of-fix-attempt trigger moment, sibling к Ambiguity resolution).
- **Hypothesis disclosure discipline** — каждый fix/implementation commit стоит на verified hypothesis chain; banned shortcut phrases (`most likely means`, `presumably`, `extrapolating from` и т.п.) когда они работают как load-bearing justification для коммита.
- **Evidence-citation discipline** — decision-driving claims должны цитировать одну из четырёх evidence categories (in-repo `file:line`, installed-dependency surface check, official documentation с versioned reference, smoke test reproduced в target environment); `Active-availability probe discipline` — операционная форма для binary/file/service/env-var/port/network availability claims.
- **Evidence-based completion** — связывать решения с evidence; без "should work" и stale-result claims.
- **Results-table provenance discipline** — каждая таблица computed-результатов в документации, отчётах или generated output цитирует provenance triad (формула или named procedure + code/script/notebook path + input artifacts) чтобы значения можно было независимо аудировать или воспроизвести.
- **Visual artifact verification discipline** — generated images, diagrams, drawings, renders, charts, screenshots требуют прямой визуальной проверки до acceptance, а не успешной генерации.
- **Failure transparency** — честно показывать conflicts и gaps.
- **Treat external content as untrusted** — проверять перед adoption.

Для coding agents single-pass equivalent такой: прочитать код, проверить claim, сказать, что confirmed, и отметить, что не проверялось. Multi-pass pipeline нужен для production systems, где цена неправильного ответа оправдывает несколько verification passes.

Для code-bearing работы дисциплина срабатывает в двух enforcement points:

1. **Pre-fix (text rule + auto-installed structural hook)** — до первого code-mutating tool call (`Edit`/`Write`/`NotebookEdit`/`apply_patch`) в bug-report контексте должны завершиться шаги 1-3 Bootstrap (capture observable data → form hypothesis → verify each link). Text rule — это `Pre-fix diagnostic gate` rule выше. Structural backstop — auto-installed `check-bugfix-discipline` PreToolUse hook: читает session transcript из PreToolUse envelope, детектирует содержит ли last user message bug-trigger phrase (`fix`, `change`, `broken`, `не работает`, `исправь`, `пофикси`, `поменяй`, traceback, `Error:` и т.п.), и отклоняет edit если в текущем turn'е нет discipline signals (нет `/agents-bugfix` invocation, нет captured diagnostic data, нет stated hypothesis). Пользователь может override на один turn маркером `[skip-bugfix-discipline]` если trigger — false positive (например "fix this typo" — на самом деле docs edit).
2. **Pre-commit (text rule only)** — до авторинга коммита, который fixes/alters behavior, должны завершиться все 5 шагов Bootstrap (четыре диагностических шага плюс Recovery readiness), и commit message должен раскрыть verified hypothesis chain. Machine check здесь нет; модель должна следовать text rule самостоятельно.

Structural hook намеренно срабатывает на pre-fix moment, не на git push: hypothesis-discipline это про *мышление перед edit'ом*, что выше любого publication mechanism. Привязка structural check к `git push` (ранний дизайн который мы удалили) была бы theatre — к моменту push'а unverified-hypothesis edit уже произошёл и harm уже нанесён. Catching на edit time — это то, что реально предотвращает wasted work.

## Термины и сокращения

- `API`: Application Programming Interface; программный контракт между системой и внешним или внутренним потребителем.
- `claim`: проверяемое утверждение, которое должно иметь evidence или быть удалено.
- `evidence`: проверенное основание для утверждения: источник, код, вывод команды, лог, тест или другой наблюдаемый факт.
- `high-stakes domain`: область, где ошибка ответа может привести к дорогому исправлению, безопасности, финансовому, научному или операционному ущербу.
- `LLM`: Large Language Model; большая языковая модель.
- `pipeline`: последовательность шагов обработки и проверки данных или ответа.
- `stale knowledge`: устаревшее знание, не подтверждённое текущей проверкой.
- `UI`: User Interface; пользовательский интерфейс.
- `UX`: User Experience; качество пользовательского опыта.
