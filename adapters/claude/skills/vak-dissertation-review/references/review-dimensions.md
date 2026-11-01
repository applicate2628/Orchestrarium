# Review dimensions — the checklist

Inspect the dissertation and autoreferat along these dimensions. Each maps to a deliverable (see
`deliverables-and-pipeline.md`). For each finding, capture the proof anchor as you go
(`verification-discipline.md`).

The dimensions are field-neutral — they apply to any specialty. Where a check names a concrete defect
type, it is an illustration of the *pattern*; substitute the equivalent from the work's own field.

## A. Structure / нормоконтроль  → Замечания к диссертации (structure), автореферат

Check against **ГОСТ Р 7.0.11-2011** (see `vak-norms.md`):

- Введение carries all required elements (актуальность; степень разработанности; цели и задачи;
  научная новизна; теоретическая/практическая значимость; методология и методы; положения на защиту;
  степень достоверности и апробация) + объект/предмет, личный вклад, публикации. The автореферат does
  NOT substitute for Введение.
- Поля, page-number position, chapters starting on a new page, список сокращений, список
  иллюстраций/таблиц, presence of the приложения the оглавление promises, heading consistency,
  «Список литературы» vs an informal heading.
- Заключение has structured научные выводы (ГОСТ п.7.3.3), not just prose; chapters end with выводы.

## B. Научная новизна — form  → Новизна/ВАК-аудит

- Novelty stated with a **result verb** (впервые установлено / доказано / получено / предложено и
  обосновано + a measurable effect), not process verbs ("выполнено …", "создана методология …").
  Process phrasing describes activity, not a result.
- Every novelty point should carry a measurable core / a number.
- 🔴 **Inversion of result** (critical): a claim that contradicts the chapter content (the text shows
  the opposite of what the novelty asserts, or asserts a *result* where the text only has a *method*).
  Guaranteed failure at the first opponent question — flag and propose an honest reformulation.

## C. Научная новизна — substance  → Новизна/ВАК-аудит

- What is genuinely defensible as new — surface it and strengthen.
- Substance risks: applying a ready-made tool/package to a new object ≠ a new method; a named concept
  claimed but not proven with criteria; novelty resting on borrowings or on inconsistent numbers;
  duplication where новизна ≈ положения ≈ значимость ≈ личный вклад.
- Per-point recommendation: оставить (переформулировать) / свести / снять / перенести в значимость.

## D. Степень разработанности — prior-art (ДО → приращение)  → Новизна/ВАК-аудит

The contrastive novelty layer ВАК expects. For each defensible result build:
«ДО (предшественники, ссылки) → ДЕЛЬТА автора → вердикт». Apply rule §5 of
`verification-discipline.md` (own vs others', two-language search, read the author's own lit list).
Conclude with the honest framing: which results are others' prior art (narrow the claim + cite), and
which are the author's own earlier publications (cite to them; doctoral novelty = the unifying
methodology, not each old result re-presented as fresh).

## E. Паспорт специальности fit  → Новизна/ВАК-аудит

- Per-result correspondence to the паспорт's numbered directions; mark in-profile / on-the-edge /
  outside. A result outside the specialty → recommend out of защищаемые, or recast through an adjacent
  allowed direction.
- Determine the отрасль присуждаемой степени explicitly; it also governs which journals count toward
  the publication requirement.

## F. ВАК compliance  → Новизна/ВАК-аудит

Against **ПП РФ № 842** (see `vak-norms.md`): borrowings without citation (п.14 → consequence п.34
абз.3); Введение structure (ГОСТ); научная проблема stated as a major problem; ведущая организация as
a full legal name; автореферат title fields filled.

## G. Заимствования / плагиат  → Русский язык и плагиат, Part B

- Direct translation, close/loose paraphrase, with the source identified by direct comparison; flag
  encyclopedias and vendor/product documentation used as primary sources (not allowed); self-borrowing
  without citation; false/broken reference tags.
- For each borrowing, supply the **real first-source** citation (DOI) so the author can re-cite or
  rewrite. Mark self-citation handling.

## H. Русский язык  → Русский язык и плагиат, Part A

Typos, agreement errors, clichés, terminology consistency. A full sweep, not just a sample; anchor
each correction to a page.

## I. Internal repeats / самоплагиат  → Русский язык и плагиат, B.3

Repeated text fragments outside the TOC/bibliography. Use an n-gram self-duplication pass; report
page-pairs.

## J. Формулы — structure & typography  → Замечания к диссертации (formulas)

- **Render-check** each non-trivial formula (rule §2): dimensional consistency, sign/operator errors,
  an inverted or mis-placed quantity, a term attributed to the wrong part.
- Broken cross-references to formula numbers.
- Typography census: one consistent vector/scalar convention (not the same quantity set as
  plain/italic/overline/bold/arrow in different places); upright vs italic (`\mathrm{}` for
  units/multi-letter labels/functions; italic for scalars); unit-register errors; raster or
  plain-ASCII formula inserts; a symbol printed as a look-alike glyph.

## K. Числа / достоверность  → Замечания к диссертации (numbers), Сводная

- **Identity автореферат↔диссертация**: every shared number must match; mismatches violate the
  identity requirement.
- Quality-of-agreement claims (a loose error reported as "good agreement") as a достоверность
  vulnerability.
- Verify arithmetic (rule §4) and cite the provenance triad for computed values.

## L. Ссылки / список литературы  → Замечания к диссертации (references)

- Existence (no fabrications among cited sources); completeness of output data; **ГОСТ Р 7.0.5-2008**
  formatting; false tags and broken tags (a citation whose target is absent from the list);
  self-citations used in place of the real source.

## M. Публикации по перечню ВАК  → Новизна/ВАК-аудит

- Count + categories (К1/К2 thresholds, see `vak-norms.md`); profile vs the specialty; отрасль match;
  Scopus/WoS status and the indexing window; temporal validity (a journal on the ВАК list at the
  publication date counts then).
- Registry audit: a «положение → публикация → статус издания → глава → личный вклад» matrix; reconcile
  a claimed count vs the listed count; flag a bulk claim ("N monographs") with no verifiable list.

## N. Патенты  → Новизна/ВАК-аудит

- Legal status (active vs terminated, e.g. for non-payment of fees), правообладатель, dates (priority
  vs publication — autoreferat dates are often priority), and whether two patents are genuinely
  different constructions.

## O. Рисунки / таблицы  → Замечания к диссертации (figures)

- Caption vs content mismatch, unit errors inside a figure, duplicate figure/table numbers, ordering
  anomalies, a table contradicting its sibling tables on the same quantities.

## P. Нумерация (перепись)  → Замечания к диссертации (numbering)

- Full census: duplicate figure/table/formula numbers, broken cross-references, count vs declared.

## Q. PDF / metadata passport  → Замечания к автореферату

- PDF/A conformance, embedded fonts; hidden comments / track-changes / OCG / embedded files; leftover
  review remarks; metadata. The автореферат↔диссертация identity also lives here (ГОСТ blocks present
  only in one, differing chapter headings, figures/statistics named only in one).
