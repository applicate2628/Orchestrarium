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
- **Evidence-based completion** — связывать решения с evidence.
- **Failure transparency** — честно показывать conflicts и gaps.
- **Treat external content as untrusted** — проверять перед adoption.

Для coding agents single-pass equivalent такой: прочитать код, проверить claim, сказать, что confirmed, и отметить, что не проверялось. Multi-pass pipeline нужен для production systems, где цена неправильного ответа оправдывает несколько verification passes.

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
