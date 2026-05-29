---
name: mathtype-book-page
description: Use when formatting, correcting, or reviewing translated technical-book DOCX pages that require full source-text coverage, editable MathType formulas, source-PDF mathematical typography/index proofread, book-like typography, display formula tables, equation-number cells, inline math fidelity, MathType size/alignment checks, figure/caption table grouping, contents formatting, and visual validation against source PDF pages in any repository.
---

# MathType Book Page

## Purpose

Use this skill to bring translated technical-book DOCX pages to an accepted MathType-based format. The skill is repo-independent: discover local paths and scripts from the current repository instead of hardcoding drive letters, document segment names, UIDs, or machine-specific locations.

Use the currently accepted page in the active repo as an exemplar, but express every rule as a reusable pattern for other pages. Do not encode page numbers, formula numbers, formula identifiers, source document names, or one repository's directory layout into the skill body.

Applying this skill means closing the visual/template defects in the document, not merely reviewing them. A raw OMML/MathML-to-MathType conversion, an OLE count report, or a worker report that says formulas were converted is not skill application. If the rendered document still shows old defects such as small/clipped integrals, loose or wrong braces, short determinant bars, detached hats, artificial alignment cells, wide gaps before `=`, or text/formula numbers inside MathType, mark the chunk `REVISE` and route it to template/source repair before final review.

Applying this skill also means preserving the full translated source coverage. A formula-complete or figure-complete chunk that omits ordinary prose, section introductions, derivations, problem statements, footnotes, captions, table titles, or continuation text is `REVISE` even when every visible formula is editable MathType OLE.

## Source PDF Authority

Treat the original source PDF as the mathematical and layout authority for every final DOCX/PDF candidate. An accepted exemplar controls reusable formatting patterns, but it never overrides the current source PDF's formula content, indices, accents, inline math, equation references, captions, page numbering, or source-specific layout.

No chunk may receive final `PASS` until the current rendered candidate has been compared against the corresponding source PDF pages after the latest edit. This comparison must cover the whole source-page content: prose paragraphs, headings, section transitions, derivation text, problem statements, footnotes/endnotes, captions, table titles, table bodies, display formulas, meaningful inline MathType objects or styled Word math runs, nearby punctuation, equation-number references in prose, figures, and any formula/table/layout region touched by the repair.

When text extraction from the PDF is noisy, render or crop the source page and compare visually. If the source PDF is ambiguous, record the ambiguity in the repo QA artifact and keep the chunk at `REVISE` or `CANDIDATE`; do not infer the formula from neighboring patterns or from the generated DOCX.

## Gate Discipline For Workers

Never collapse stage-specific success into final acceptance.

| Stage | Allowed result | Not allowed |
|---|---|---|
| Source-map or no-Word repair | `PASS` only for the scoped source-map subset, with final chunk still `REVISE` | Claiming final MathType/layout/source-PDF acceptance |
| XML-only layout/table/figure repair | `CANDIDATE` only, until the exact scratch DOCX is rendered and compared with the source PDF | Treating clean DOCX XML, grouped figures, or fixed table counts as visual acceptance |
| Writer/OLE insertion | `PASS` only for mechanical conversion counts, exported DOCX/PDF, and zero placeholders | Treating OLE count, validation JSON, or exported PDF existence as skill PASS |
| Skill review | `PASS` only after full source-text coverage review, rendered visual review, source-PDF formula proofread, inline proofread, layout review, and figure/caption review | Accepting spot checks, formula-only checks, stale reports, or worker summaries |

## Full-Text Coverage Gate

Before final `PASS`, prove that the candidate represents the whole source chunk, not just formulas and figures.

Required coverage checks:

1. Build or update a source-page ledger for the chunk. For each source page, record the section/problem range, important prose anchors, figures/tables, footnotes, captions, and numbered formulas that must appear in the candidate.
2. Extract text from the rendered candidate PDF and compare it with the source OCR/text as a rough falsification check. For normal prose-heavy technical-book chunks, an output/source character ratio below `0.85` is a hard `REVISE` unless the QA artifact explains a source-specific reason such as OCR garbage, mostly-image pages, very dense formulas, or intentional scope exclusion approved by the user. A high ratio is not a PASS by itself.
3. Visually inspect the rendered candidate pages against the rendered source pages after the latest edit. Confirm that prose blocks have not been skipped between formulas, across page breaks, after figures/tables, or at chapter/section boundaries.
4. Check continuation areas explicitly: text before the first formula, text after the last formula, text between consecutive display formulas, problem lists, footnotes, and captions that wrap across lines.
5. Record the coverage result in the QA artifact. If the chunk is formula-only by admitted scope, state that scope explicitly; otherwise formula-only output is defective.

Do not advance to the next chunk when the current chunk is missing ordinary text. Freeze the pipeline, mark the affected chunk `REVISE`, and repair the coverage defect before producing more chunks unless the user explicitly parks the repair.

For sequential chunk production, treat the previous chunk's full-coverage closure as a prerequisite for the next chunk. Do not start the next chunk from formula/OLE success alone: the current chunk's QA or status artifact must contain fresh evidence for rendered-PDF/source text coverage, source-map/source coverage or an equivalent source-page ledger, visual source comparison, and any source-specific exception. If a low-ratio repair required adding ordinary prose, update the reusable source-map or builder pattern before continuing so the omission does not propagate.

Before any worker starts a chunk, require a quick anti-false-pass scan:

1. Locate the source PDF, final DOCX/PDF candidate, validation JSON, formula checklists, and existing review/spec artifacts.
2. Check whether the final candidate is missing, stale, mechanically converted only, or already marked `REVISE`.
3. Compare source OCR/text length and candidate rendered-PDF text length as a rough coverage sanity check; investigate low ratios before touching MathType.
4. Inspect the DOCX structure for formula tables, table cell counts, OLE/object counts, drawing/image paragraphs, caption paragraphs, obvious font/justification drift, and remaining OMML/placeholders.
5. Inspect the rendered PDF visually enough to catch missing prose blocks, oversized body text, loose figures/captions, table merges, clipped formulas, and obvious inline-math corruption.
6. Compare current findings with prior QA artifacts, but do not let an older report close the gate. Old `PASS` or `REVISE` rows are evidence to recheck against the current rendered DOCX/PDF.
7. If any required skill surface is unchecked, mark the chunk `REVISE` and write a repair/spec artifact instead of advancing the queue.

Workers must state the scope of their verdict. Use phrases such as `PASS for no-Word source-map repair only` or `PASS for mechanical writer conversion only`. Do not write bare `PASS` unless the full skill review gate has passed.

## Defect Blocking Gate

Treat this skill as a quality gate, not a generator prompt. A worker may produce only a repair candidate while any hard blocker remains. It must not advance a chunk, start a batch, or claim final acceptance.

Hard blockers:

- no current source-PDF render or accepted exemplar was consulted;
- no current candidate DOCX/PDF was rendered after the latest edit;
- any source page, prose block, problem item, footnote, caption, table row, or section/chapter boundary is not mapped into the translated candidate;
- rendered-candidate text coverage is far below source coverage without a recorded source-specific explanation and visual reconciliation;
- any display formula, meaningful inline formula, or formula reference is unchecked against the source PDF;
- any known defect pattern from an earlier page/chunk recurs: clipped integrals, wrong braces/cases, short bars, detached hats, artificial alignment cells, wide gaps before `=`, wrong bold/italic/upright math style, wrong indices, text inside MathType, formula numbers inside MathType, loose figure/caption blocks, merged formula tables, or plain-text formula markers;
- the candidate changes unrelated formulas/pages without an explicit accepted reason;
- the worker cannot name exactly what changed, what stayed untouched, which pages were rendered, and which source-PDF regions were compared.

The agent that generated or converted a chunk must not issue final `PASS` for that same artifact. It may report `CANDIDATE`, `REVISE`, or a scoped stage result. Final `PASS` requires a separate current-render review by the main/integration gate or an explicitly assigned reviewer.

If a defect is systematic in one chunk, freeze the same pipeline for later chunks until the rule/script is updated and the failing example has a rendered repair candidate. Do not multiply known-bad output.

## Defective-Chunk Repair Workflow

For any defective chunk, read and execute `references/defective_chunk_repair.md` before changing files. That reference is mandatory when the task is to fix a bad chunk, not optional background reading.

Minimum repair loop:

1. Classify the chunk state: missing final candidate, mechanical-conversion candidate, source-map defect, localized formula/template defect, inline-math defect, layout/typography defect, figure/caption defect, table-structure defect, or systematic pipeline defect.
2. Choose exactly one repair lane for the next pass and write the expected artifact: source-map patch, targeted OLE patch, layout candidate, figure/caption grouping candidate, or justified full writer.
3. Create a scratch candidate first; do not overwrite the final DOCX/PDF before the repaired area renders correctly.
4. Render the affected pages and compare them with the source PDF plus the accepted exemplar.
5. Record changed formulas/pages, untouched formulas/pages, current blockers, and the next gate.

If the worker cannot complete these steps, it must return `REVISE` with a defect ledger instead of producing more converted output.

## Targeted Repair First

Do not run a full Word/MathType writer pass when the active defects are layout, figure/caption grouping, typography, grammar, punctuation, source-map review, or one-to-few formula/template defects. For local formula defects, replace only the defective formulas or inline objects and leave accepted formulas untouched. A full rebuild is the last step for broad source-map changes or stale OLE state, not the default repair tool.

Use this order:

1. Audit the current final DOCX/PDF and source PDF to identify the exact affected pages, formulas, inline objects, tables, or paragraphs.
2. For text, layout, table, figure/caption, TOC, grammar, or punctuation defects, repair the DOCX layout/source structure first without invoking MathType conversion for unrelated formulas.
3. For a small number of formula defects, create or reuse a one-object MathType sample and replace only the affected OLE objects in a scratch candidate. Do not reconvert unrelated formulas just to validate the repaired ones.
4. For source-map defects, run no-Word prepare-only and payload audits first; do not start Word/MathType until the map is writer-ready.
5. Render only the affected pages first and compare them against the source PDF and accepted exemplar.
6. Promote the targeted candidate only after visual/source-PDF checks pass for the repaired area.

After a source-map repair changes any formula payload, split, order, or inline object, any older MathType OLE output for that changed object is stale even if the previous writer run was mechanically clean. Route it to targeted OLE replacement or a justified chunk-local writer only after non-Word blockers are closed.

After an XML-only repair changes layout, table structure, figure/caption grouping, page markers, or number cells while preserving OLE binaries, the output is a structural candidate only. It must be exported/rendered from that exact scratch DOCX and checked against the source PDF before promotion or final review. If the render rejects the structure, update the repair rule or template instead of rerunning the same XML patch.

XML parse success and ZIP integrity are not enough for XML-only candidates. Before handing a candidate to the render gate, run a semantic OpenXML sanity check for Word-openability defects introduced by serialization: every prefix listed in `mc:Ignorable` must be declared in the same root scope; bookmark/comment/permission/proofing/move range starts and ends must be balanced or proven unchanged from a Word-openable base; typed attributes must not be serialized as empty strings, especially numeric spacing/indent values such as `w:before=""` or enum values such as `w:jc w:val=""`; `sectPr` must remain body-level and final; table cells must have terminal block content; object/image relationships must resolve to existing parts; OLE/VML shape IDs and drawing IDs must remain coherent. A candidate with missing `mc:Ignorable` namespace declarations, invalid empty typed attributes, orphaned range markers, dangling relationship targets, or malformed object anchors is `REVISE` even if every XML part parses.

Run a full chunk writer only when at least one of these is true:

- this is the initial MathType build for a chunk with no final MathType candidate;
- a broad source-map repair changes many formula payloads and targeted replacement would be less reliable than a clean rebuild;
- the current final OLE set is stale or structurally inconsistent across most of the chunk;
- a targeted patch path was attempted or evaluated and cannot safely preserve the document.

Before starting such a full writer, record the reason, the non-Word blockers already closed, the affected chunk only, the expected formula count, and the cleanup plan for Word/MathType processes.

## Writer Process Ownership

Treat each Word/MathType writer or render lane as owned by the session that started it. No-Word, source-map, review, or layout workers must not stop, kill, restart, or "clean up" a Word, MathType, LibreOffice, Python, or PowerShell process that belongs to another active lane.

Before any cleanup:

- identify the owning lane from the command line, scratch path, progress log, start time, or explicit handoff;
- stop only processes that the current lane started, or processes that are clearly stale/orphaned after their owner has completed, failed, or been explicitly parked;
- if another active lane is running, record it as a resource conflict and continue with no-Word work or return `REVISE/BLOCKED`; do not interfere with it;
- after cleanup, record which owned processes were stopped and which unrelated active processes were left untouched.

If a writer exits with a negative code or no traceback while another worker had cleanup rights nearby, treat the evidence as contaminated until a clean bounded probe is rerun with no competing cleanup worker.

## Dense Matrix And Writer-Stall Gate

Clean prepare-only output and clean MathML payload audits prove only that the source-map XML is well formed. They do not prove that Word/MathType can import one very large dense `mtable`, rotated matrix, or broad multi-row display as one editable MathType object.

Before marking a chunk `READY_FOR_WRITER`, inspect the first high-risk display payloads for dense matrices, many columns, rotated displays, nested bracketed arrays, and prior stall history. If a prior writer attempt stopped at `before_set_mathml` for a UID and never wrote a matching `saved` event, that UID is not writer-ready in the same one-object form even when audits are clean.

Required handling for dense display payloads:

- treat the issue as a source-map/template defect, not as a transient writer failure;
- compare the display against the source PDF before changing the split;
- split the display into source-faithful smaller MathType objects at natural row groups, or use a verified editable MathType sample when a continuous bracket or delimiter template must be preserved;
- keep the equation number as ordinary Word text outside MathType;
- run prepare-only and payload audits after the split;
- validate with a bounded writer probe that crosses the former stalled UID before any full chunk writer retry;
- record the failed UID, split strategy, bounded probe result, and remaining source-PDF review gate.

Do not blind-rerun the full writer on a known stalled dense matrix. Do not let a worker report `READY_FOR_WRITER` if its only evidence is `0` payload issues and it has not addressed the import-size/template risk.

## Repo-Independence Contract

Treat this skill as a portable operating procedure.

- Discover repository paths from the current workspace and existing docs/scripts.
- Refer to paths through local variables such as `FINAL_DOCX`, `SOURCE_PDF`, `SAMPLE_DIR`, and `SCRATCH_DIR`.
- Refer to formulas by the current task's source location and equation number only in task notes or repo pipeline docs, not in this skill.
- Refer to fragile structures by pattern: nested integrals, brace-with-cases, aligned multi-row equations, equation-number cells, inline indexed symbols, and figure/caption groups.
- Keep machine-specific facts out of shared artifacts: drive letters, usernames, installed MathType paths, Word profile state, temporary COM object names, and local process IDs.
- When a repo needs a concrete mapping, store it in that repo's pipeline script or runbook, not in this skill.

## Repo Discovery

Before editing:

1. Set `REPO_ROOT` to the Git root when available; otherwise use the current workspace root.
2. Use this skill as the style and MathType source of truth. Use repository docs or scripts only to discover local commands, paths, and existing pipeline entry points.
3. Locate final MathType DOCX outputs, validation previews, source PDFs, manual sample DOCX files, and targeted patch scripts with repository file search.
4. Identify the affected page, formula, and source PDF page before changing anything.
5. Identify whether a targeted patch path exists. If not, create a scratch candidate path before touching final output.

Use repo-relative variables in notes and scripts:

- `FINAL_DOCX`: final translated DOCX for the page or document segment.
- `FINAL_PREVIEW_PDF`: rendered PDF preview for `FINAL_DOCX`.
- `SOURCE_PDF`: original PDF page source.
- `SAMPLE_DIR`: repo-local directory containing editable MathType sample DOCX files.
- `SCRATCH_DIR`: repo-local scratch directory for candidates and rendered page images.
- `VALIDATION_JSON`: repo-local validation summary.

Do not bake absolute workstation paths, usernames, drive letters, or installed MathType paths into shared scripts or docs. Discover MathType from the local installation or accept a documented environment variable override.

If a repository has no runbook, no exemplar, no sample directory, no validation JSON, or no scratch convention, create only the minimum repo-local working area needed for the current task, document the new convention in the repo pipeline, and keep this skill free of those local names.

## Accepted Page Style

- Use book-like typography: normal body weight, justified paragraphs, restrained spacing, and source-like heading hierarchy.
- Keep every display formula in a borderless two-column table: MathType OLE formula in the left cell, equation number as ordinary Word text in the right cell.
- Keep equation numbers out of MathType. The number cell owns the visible source equation number as ordinary Word text.
- Keep prose labels out of MathType. Region labels, conditions in words, figure labels, and explanations are ordinary Word text.
- Keep prose connectors between equivalent display forms outside MathType. If the source has words such as `or`, `where`, `for`, `if`, or localized equivalents between formulas, split the display into separate MathType placeholders and put the connector as Word text in the formula cell; do not bury the connector inside one opaque MathType OLE.
- Keep figures and captions together in one grouped Word structure, usually a table, so they do not drift apart.
- Use editable MathType OLE (`Equation.DSMT4`) as the final formula format. OMML, LaTeX, images, and scratch DOCX files are auxiliary unless the user explicitly changes the target format.
- Check inline math in ordinary paragraphs: indexed symbols, Greek letters, primes, bars, bold/vector style, italic/upright style, operators, punctuation, and references to equations must match the source PDF.
- Keep punctuation around inline MathType objects as Word text on the source-correct side of the object. If an inline expression completes a phrase or sentence, the comma/period belongs after that inline object, not before it; verify the rendered line because text extraction can hide this defect.

## Document Formatting Contract

Before formatting a new page or document segment, identify the accepted local exemplar and copy its style decisions as patterns. If no exemplar exists, match the source PDF's book layout instead of inventing a modern report layout.

Create a brief style snapshot before editing. Record the observed target values from the exemplar or source PDF, then apply them consistently:

| Style item | Record and match |
|---|---|
| Page setup | page size, margins, header/footer position, page-number placement |
| Body text | font family, font size, justification, first-line indent, line spacing, paragraph before/after spacing |
| Headings | level hierarchy, bold/italic use, alignment, spacing before/after |
| Captions | font, size, bold/italic use, alignment, spacing to figure |
| Contents | indentation levels, tab/page-number alignment, leader or no leader, source page-number convention |
| Display formulas | table structure, formula alignment, number alignment, typical MathType visual size |
| Inline math | whether complex inline expressions are MathType or styled Word text |

### Page And Text

- Use the repo's existing page size, margins, headers/footers, page-number style, and section setup unless the source PDF forces a change.
- Use a single book-style serif body font family and consistent body size derived from the exemplar or source PDF.
- Keep body paragraphs justified, readable, and not bold by default.
- Use source-like first-line indents, paragraph spacing, line spacing, and heading hierarchy.
- Do not create oversized headings, poster-like body text, decorative boxes, marketing layouts, or card-style sections.
- Keep section titles, figure captions, source notes, and contents entries as Word text with styles, not images.
- Normalize accidental extra spaces, duplicated tabs, empty paragraphs, and manual line breaks that create uneven rivers or broken justification.
- Preserve source meaning and technical terminology; fix grammar and punctuation while checking against the original page.

### Typography Normalization Against Exemplar (LOAD-BEARING)

Stale OMML→DOCX pipeline produces non-book defaults. Every chunk's `word/styles.xml` must be reconciled against the accepted exemplar's `word/styles.xml`, not left at the pipeline output. Confirmed defect pattern observed in a recent Russian-language technical-book DOCX translation before normalization:

- Body Normal style: `Arial 10.5pt` (sz=21 half-points) instead of exemplar's `Times New Roman 11pt` default
- Title 18pt, Heading1 15.5pt, Heading2 13pt, Subtitle 14pt — all oversized relative to exemplar's Title 16pt / Heading1 14pt / Heading2 12pt / Subtitle 12pt
- Caption, TOC, FootnoteText, etc. all carried pipeline defaults rather than book typography

Procedure for typography normalization:

1. Extract exemplar `word/styles.xml`. Record full block of Normal style plus each Heading1..5, Title, Subtitle, Caption, TOC1..9, FootnoteText, Hyperlink, etc.
2. For every other chunk in release:
   - Read its `word/styles.xml`
   - Identify chunk-specific style IDs (pandoc styles like `FirstParagraph`, `Compact`, `Bibliography`, `BlockText`, `SourceCode` and its token children `KeywordTok` / `DataTypeTok` / etc., `CaptionChar`, `Figure`, `CaptionedFigure`, `VerbatimChar`, `Table`, `Author`, `Date`, `AbstractTitle`, `Abstract`, `TableCaption`, `ImageCaption`, `SectionNumber`, `FootnoteReference`, `FootnoteBlockText`, `DefinitionTerm`, `Definition`) — these are referenced by `<w:pStyle>` / `<w:rStyle>` in the chunk's `word/document.xml` and must stay
   - Replace styles.xml with exemplar styles.xml plus appended chunk-specific style blocks (merge, not wholesale replace)
3. Verify OLE/media byte-identity per chunk before/after via SHA-256
4. Render at least one representative chunk and confirm headings/body match exemplar visually
5. Record the typography-normalization step in the chunk's canonical skill review

If exemplar's styles.xml is missing or ambiguous, use the source PDF page as authority (book-style serif font, 11pt body, sentence-case headings, sized headings hierarchy).

### Heading Case Normalization (Russian sentence case)

Russian production books use sentence case for headings: only first letter of first word capitalized, the rest lowercase, except proper nouns and acronyms. Stale pipelines often emit ALL CAPS headings (e.g. `9. МЕТОД ОБОБЩЕННОЙ МАТРИЦЫ РАССЕЯНИЯ`) — this is a defect, not a style choice.

Procedure:

1. Find every paragraph with `<w:pStyle w:val="Heading1|Heading2|Heading3|Heading4|Heading5|Title|Subtitle"/>`
2. Concatenate all `<w:t>` text in the paragraph
3. If concatenated text contains 8+ consecutive uppercase Cyrillic chars (signal: not just an acronym), apply Russian sentence case transform:
   - Preserve number prefix (`9. `, `12.1 `, `Глава 3. `) — leave as-is
   - First content character: keep uppercase
   - Rest: lowercase
   - Latin acronyms 2-4 chars (extend per book domain — RF/microwave example list: TLM, TE, TM, FEM, FDTD, MoM, CAD, MMIC, OMML, MathML, TEM, EM, SDM, MoL): keep uppercase if surrounded by spaces or punctuation
4. Apply transformation by editing the affected `<w:t>` elements; multi-run headings (text split across `<w:r>` elements) require careful merge / redistribute
5. Preserve text run styling (`<w:b/>`, `<w:i/>`, color) — only change text content, not run properties
6. Verify all OLE/media byte-identical after edit

Caveat: chapter-title chapter prefixes (`Глава 9. Метод обобщенной матрицы рассеяния`) and similar conventional patterns also need sentence-case body even if the number prefix carries chapter signal.

### Listing Provenance Pointer (Class N)

Program listings printed inside a translated technical-book chunk are OCR-cleaned samples from the source book; the verified, compilation-tested source typically lives separately in the project's verified-source root (commonly under a path such as `code/chapter_NN_*/restored/`, but the project's own convention controls). A chunk that prints or narratively references a program without a provenance pointer is a defect — a future reader cannot reproduce the run or distinguish the printed code from a cross-validated translation. The global rule is `Results-table provenance discipline` in `shared/AGENTS.shared.md`; this section is the skill's operational form of that rule for the "program listing" surface.

The chapter-to-verified-code map is project-specific (e.g. one RF-engineering book mapped Chapter 02 / 05 / 08 / 10 / 11 to specific Fortran and Pascal restorations under `code/chapter_NN_*/restored/`, with cross-language cross-validation for the chapter with both Pascal and Fortran sources). When the project maintains a written defect-class catalogue (commonly `docs/translation-defect-checklist.md`), the chapter-to-path map and per-chapter compile/run invocations live there; the skill enforces the procedure regardless of where the map lives.

How to find a listing in a chunk:

1. Grep `word/document.xml` for monospace run properties: `w:rFonts w:ascii="(Courier|Consolas|Lucida Console|Source Code)"`, `w:rStyle w:val="(VerbatimChar|SourceCode.*)"`, `pStyle w:val="(SourceCode.*|Verbatim.*)"`.
2. Grep for narrative references to programs: the named program identifier (e.g. `TLM_INHO`), language name (`Fortran`, `Pascal`, `Turbo Pascal`), or convention markers (`Листинг N`, `Program N`, `Listing N`).
3. Cross-reference the chunk's printed-listing or narrative mention against the project's `code/.../README.md` or equivalent index of verified source files.

Procedure for adding the provenance pointer:

1. Locate the reference paragraph (listing block OR narrative mention of the program).
2. Read the corresponding compiled-and-run output file with the Read tool to extract one representative numeric line for the empirical fingerprint (a future re-run that produces a different number flags a regression even without diffing the full output).
3. Construct a 3-line provenance block as new Caption-styled `<w:p>` paragraphs immediately after the reference:
   - `Verified source: <repo-relative-path-to-source-file> (<compile invocation>)`
   - `Input artifact: <repo-relative-path-to-input-file>` (omit when the program has no external input)
   - `Output: <repo-relative-path-to-output-file> (<one-line numeric summary>)`
4. When the source has cross-validated translations across multiple languages (e.g. an original Turbo Pascal and a Fortran restoration), include both source paths, both compile invocations, the cross-validation row count, the max absolute difference between the two outputs, and the per-language output filenames.
5. Insert by adding the new `<w:p>` paragraphs after the reference paragraph using the chunk's existing Caption style if defined, otherwise a plain body paragraph.
6. Preserve OLE/media byte-identity: the provenance block is text-only and never touches `<o:OLEObject>` or `<w:drawing>` elements; SHA-256 of `word/media/*` and `word/embeddings/*` must match PRE backup.
7. If the chunk references the listing narratively but the printed listing block is in a different chunk (e.g. a narrative-only mention of a program whose source pages fall in another chunk), still anchor the provenance block at the narrative reference site so the citation chain is intact.

Skip rule: a chunk that contains only a numerical data table (e.g. parameter values styled with VerbatimChar) is NOT a listing — skip with rationale recorded in the project's audit JSON or equivalent. A trivial illustrative fragment with no verified-code counterpart is also skipped.

### Contents And Page Numbers

- Format contents as a real structured Word layout: aligned titles, aligned page numbers, consistent indentation, and source/global page numbering.
- Do not let local document page numbers replace book page numbers when the source contents uses global book pagination.
- Check contents entries after rendering; page-number drift is a formatting defect.

### Figures And Captions

- Place each figure and its caption in one stable grouped Word structure, preferably a borderless one-column table with one image row and one caption row.
- Keep the figure table inline in the document flow unless the accepted repo format explicitly uses another stable non-floating structure.
- Keep the figure centered and scaled to the source-like visual width without stretching or cropping.
- Grouping a figure and caption is not sufficient if the embedded image itself is cropped or incomplete. Compare the rendered figure against the source PDF image area; if the source top, bottom, side labels, arrows, or subfigures are missing, repair the image extraction/source crop before acceptance.
- Keep captions centered, close to the figure, styled consistently, and on the same page as the image.
- Keep image row and caption row together; prevent a page break between them where the document model supports that.
- A grouped figure/caption table can still fail after render if the image row is too tall for the remaining column, the table begins too low on the page, or the section uses multi-column text. Use source-faithful flow controls such as `keepNext`, `cantSplit`, or a column/page break before the group, constrain the table to the effective column width, and scale the image proportionally so image plus editable caption render together. Do not ungroup the caption or crop away source figure content to force the page break.
- For multi-part figures, keep all subfigures and the shared caption in one grouped structure, preserving source order and relative spacing.
- Place captions above or below the figure according to the source PDF or accepted exemplar; do not normalize all captions mechanically.
- Let long captions wrap as Word text inside the caption row rather than using images or text boxes.
- Verify the full rendered caption and legend/prose associated with the figure, not just the image crop. A grouped figure still fails if the caption row, table cell, or fixed-height frame clips the caption, leaves only the first caption line visible, or drops source-equivalent material/substrate/legend text.
- Do not leave a figure as a floating object if it can drift away from its caption.
- Do not put figure captions inside MathType, screenshots, or loose text boxes.
- If the source has a figure number and caption text, keep both as editable Word text.
- Reject a DOCX where figures are top-level image paragraphs and captions are separate following paragraphs. This is still a drift risk even when the rendered page happens to look acceptable.
- Reject captions or surrounding prose that lost inline formulas during conversion, such as blank spaces where symbols should be, plain caret notation, or formula-like text left outside MathType without correct Word math styling.

### Formula Tables

- Put each numbered display formula in its own borderless two-column table.
- Left cell: exactly one display MathType OLE object or one coherent display formula block.
- Right cell: ordinary Word text equation number only.
- Prefer fixed table layout or disabled autofit for formula tables.
- Use stable preferred widths derived from the accepted page geometry: the formula cell gets the usable width, and the number cell gets only enough width for the widest equation number.
- Use small, consistent cell margins so formulas do not touch cell edges and numbers do not drift.
- Prevent a display formula row from breaking across pages unless the source formula itself is split across pages.
- Keep the paragraph containing the formula object and the paragraph containing the number together with their row where possible.
- Keep both cells vertically centered.
- Center the formula within the formula cell unless the source clearly uses left alignment for a long multiline block.
- Right-align the number within the number cell.
- Use stable column widths or fixed table layout so long formulas do not create extra columns, table wrapping artifacts, or a number pushed into the formula.
- Give the number cell enough width and explicit line breaks or separate paragraphs for multi-number displays. Do not rely on Word auto-wrapping to stack equation numbers; a number such as `(52a)` must never split into `(52a` and `)`.
- Suppress borders at table and cell level.
- Render formula tables after Word save and reject visible table borders, horizontal rules, or bottom lines that are not present in the source PDF. XML border settings alone are not enough because table style inheritance can still render lines.
- Separate adjacent formula/figure/table structures with a small normal paragraph when Word would otherwise merge tables during save.
- For unnumbered display formulas, use the same stable layout but omit the number cell only if the repo's accepted format does so; otherwise use a blank number cell for alignment consistency.
- Preserve the source sequence of formula and prose blocks. If the PDF has an unnumbered identity, then explanatory prose such as "so that equation ...", then a numbered equation, keep those as separate Word structures: unnumbered formula table, ordinary prose paragraph, numbered formula table. Do not merge them into one MathType object or one numbered formula table.
- Preserve connector prose between adjacent display formulas even when the generator merged the formulas into one multi-row table. If the source shows a connector such as `where`, `где`, `with`, `Let`, or `so that` between two display rows, split the table or insert an ordinary Word-text connector at the source-flow position. Do not leave the connector dangling after both formulas, and do not move it inside MathType unless it is mathematical notation in the source.
- Reject accidental table merges after Word save. A single logical formula table must not become a multi-row or extra-cell table merely because two adjacent display tables were inserted without a separator.
- For multi-number displays, verify whether the source truly has one coherent multi-row formula. If the generated DOCX uses multiple numbers in one right cell or creates extra cells, inspect the rendered PDF and split or rebuild until each row/number relationship is unambiguous.
- Count structural rows, not just visible rows. A table that appears acceptable in the PDF can still fail if DOCX XML shows unexpected extra cells, merged grids, or a neighboring figure/formula table merged into it.

### MathType Size And Alignment

- Match MathType object size to the surrounding book text and source PDF, not to the generator default.
- If an accepted exemplar exists, normalize new formulas to that exemplar's visual MathType profile before comparing to the source PDF.
- If the exemplar and source PDF disagree, preserve mathematical readability and source fidelity first, then keep page-level consistency as close as possible.
- Keep display formulas visually consistent across the page: baseline, symbol height, integral/sum size, and subscript/superscript scale should look like one book source.
- Keep inline MathType objects on the text baseline; reject inline objects that float high/low or enlarge line spacing unless the source does the same.
- Scale only the whole OLE object when fitting width; do not distort width and height independently.
- Preserve aspect ratio when scaling an OLE object.
- Record any scaling rule in the repo pipeline if it is automated.
- If a display formula is too wide, first try a source-faithful line break or MathType layout change; use scaling only after preserving readability.
- If the source render proves the display topology is already correct and the only rendered defect is that the Word/VML preview is wider than the effective formula cell, constrain the table/preview geometry before rebuilding MathType. Scale the whole preview shape proportionally, keep the equation number as ordinary Word text in the number cell, preserve OLE/media bytes, and render the exact scratch DOCX to prove the number no longer overlaps or clips. Do not use preview scaling for formulas whose source uses a multiline layout or whose formula content/style has not been source-checked.
- If a formula looks too small after automatic import, rebuild or copy a better MathType template instead of accepting a shrunken object.
- Validate baseline and size in both Word and exported PDF when possible; trust the exported PDF when they differ.
- Verify sizes visually in the exported preview PDF; OLE metadata alone is not enough.

### Mathematical Symbol Style

- Use MathType math style for variables and symbols, not plain Word text pasted into an equation object.
- Treat mathematical typography as semantic content, not decoration. A formula is wrong if symbol identity is correct but italic/upright, boldness, vector mark, index, accent, delimiter, or operator style differs from the source PDF.
- Preserve source distinctions between italic variables, upright function names, upright operators, bold/vector symbols, Greek letters, and ordinary prose.
- Keep multi-letter function/operator names upright when they are functions or operators; keep products of variables italic when they are variables.
- Keep differential symbols, domains, constants, and units in the style used by the source or accepted exemplar.
- Preserve boldness and vector style for fields, vectors, matrices, and basis/test functions.
- For Latin vector, field, dyadic, position, unit-vector, and basis/test symbols, verify whether the source uses bold upright, bold italic, arrow, hat, or another mark. Do not assume all bold Latin symbols are italic.
- Keep scalar components, modal coefficients, indices, and ordinary scalar variables in their source style. A bold vector field such as `H` can be upright while a scalar component such as `H_x` or a modal coefficient such as `H_{mn}` remains italic.
- Do not trust TeX `\mathbf` alone as visual proof. Some MathML routes convert Latin `\mathbf` to bold-italic Unicode that MathType renders slanted. If the source shows upright bold vectors, use a verified route such as MathML `mi mathvariant="bold"`, a MathType TeX sample that renders upright, or a user-corrected one-object sample.
- Build hats and other over-accents with native MathType accent templates, with the base symbol inside the accent slot. Do not accept a loose combining mark or typed caret that merely appears above or beside the base. For generated MathML, normalize combining-circumflex movers into explicit `mover accent="true"` hat templates when MathType otherwise renders a detached hat.
- Generalize that rule to any mark, enclosure, or stretchy symbol that MathType represents as a template: tilde, bar/overline, vector arrow, dot/double-dot, wide hat, radical, brace/cases, determinant bars, brackets, parentheses, norms, and matrix/vector delimiters. Put the intended expression inside the MathType slot first, then render and compare. Do not assemble these from ordinary glyphs, short bars, separate text runs, or adjacent cells unless the source PDF truly shows separate symbols.
- If rendered math shows replacement glyphs, black diamonds, boxes, missing brackets, or wrong angle-bracket symbols, treat it as a MathType/font/template defect even when text extraction looks plausible. Rebuild the affected expression with explicit MathType delimiter templates or source-faithful math characters and re-render.
- Preserve primes, bars, hats, dots, arrows, overlines, superscripts, subscripts, and nested scripts.
- Verify indices against the source PDF character by character. Check base symbol, case, Greek/Latin identity, subscript, superscript, prime order, multi-character grouping, nesting, and attachment point. Do not infer that a repeated pattern has the same indices unless the PDF shows it.
- Do not use a visual look-alike glyph if MathType has the proper mathematical template or symbol.

### Source-PDF Math Proofread

Run a source-PDF proofread for every edited page before PASS. This is exhaustive for all changed display formulas, all inline MathType objects, and all styled Word math runs on that page; it is not a spot check.

For each formula or inline expression, compare left-to-right against the rendered source PDF and mark `REVISE` for any mismatch in:

| Area | Check |
|---|---|
| Symbol identity | Latin/Greek identity, uppercase/lowercase, similar glyphs such as `ν` vs `v`, `μ` vs `u`, `φ` vs `ψ`, `k` vs `K`, `0` vs `O` |
| Indices | Subscripts, superscripts, left scripts, stacked scripts, prime-after-index order, multi-letter grouped indices, attachment to the intended base |
| Style | Italic/upright, bold/non-bold, vector/dyadic/matrix style, function names, operators, constants, differential symbols |
| Accents and marks | Prime/double-prime, hats, bars, overlines, dots, arrows, transposes, conjugates |
| Operators and relations | Signs, equality/inequality, sums, products, integrals, derivatives, cross/dot products, plus/minus placement |
| Delimiters and templates | Parentheses, brackets, braces, cases, determinants, norms, matrix bars, stretch height and nesting |
| Spacing and punctuation | Punctuation outside MathType unless mathematical, no jumped comma/parenthesis, no prose text inside formulas |

Use source crops or high-resolution rendered pages when PDF text extraction is noisy. If the source is visually ambiguous, record the ambiguity in the repo QA artifact and choose the smallest source-faithful correction; do not silently normalize to a guessed pattern.

## MathType Formula Construction

Prefer a deterministic source-to-OLE path only when it reproduces the required MathType visual structure. Otherwise use an editable manual OLE sample and preserve the mapping in the repo pipeline.

### Formula Intake

For every formula or inline-math cluster:

1. Crop or render the corresponding source PDF region.
2. Identify whether the item is a numbered display formula, an unnumbered display formula, or inline math.
3. Transcribe the mathematical meaning separately from the desired visual structure.
4. Build a source-PDF proofread list for the cluster: base symbols, indices, superscripts, primes, accents, vector/bold/upright style, delimiters, and nearby punctuation.
5. Mark all non-math text that must stay outside MathType: equation numbers, region names, prose conditions, captions, and sentence punctuation.
6. Choose the construction route:
   - direct MathType TeX import when it renders the exact native template;
   - copy from an existing editable MathType OLE object when a verified exemplar exists;
   - manual MathType editing when template choice matters and import is unreliable.
7. Render and inspect the affected page before promoting the edit.

### Manual MathType Editing Procedure

When creating or repairing a MathType OLE object manually:

1. Start from a one-object sample DOCX or create one before patching the final document.
2. Open the object in MathType and use palette templates for structure. Do not type visual substitutes for mathematical templates.
3. Build the expression from the outside in:
   - whole equation row;
   - equals or relation symbol at its real source position;
   - outer operator, brace, matrix, array, or delimiter template;
   - nested operators and rows;
   - symbols, indices, primes, bars, vectors, and punctuation.
4. Keep one logical display formula inside one MathType object unless the source really separates it into distinct objects.
5. Keep row fragments complete. Do not put a left-hand symbol in one internal slot and `= ...` in a distant slot just to fake alignment.
6. Remove equation numbers and prose from the MathType object after editing.
7. Save, close MathType, close Word, then reopen or render the sample to verify that the OLE object survived as editable `Equation.DSMT4`.
8. Only after sample validation, copy that exact OLE object into the final DOCX through the repo pipeline.

For targeted OLE repairs, replace the old equation object instead of mutating it in place: locate the target `Equation.DSMT4`, delete it, insert a fresh blank MathType equation or copied sample at the same range, populate it once, then render the page. Calling MathType data setters on an existing populated OLE can leave duplicate or merged formula content.

### One-Object Sample Discipline

Use one-object samples for fragile formulas.

- A one-object sample DOCX must contain exactly one editable MathType OLE object intended for copying.
- If a comparison document contains a reference object and a target object, extract the accepted object into a new one-object sample first.
- Name and map the sample in the repo pipeline docs/scripts using repo-local identifiers, but keep this skill free of those identifiers.
- Render the sample preview before using it in a final document.
- After patching, render the final page and compare against the source PDF, not merely against the sample.

### Display Formula Tables

For numbered display formulas:

1. Strip the equation number from the MathType payload.
2. Insert the MathType OLE object into the left cell.
3. Insert the equation number as ordinary text in the right cell.
4. Set table borders to none at both table and cell level.
5. Use fixed layout or stable column widths so Word does not reflow the number into the formula.
6. Render the preview PDF and inspect the page visually.

Reject display formula layout when:

- the formula and number are in the same MathType object;
- the equation number is an image or OLE object;
- the Word table has extra visible columns or accidental merged cells;
- the formula is clipped, horizontally distorted, or much smaller/larger than adjacent formulas;
- `lhs`, relation symbols, or continuation rows are separated by artificial internal MathType gaps;
- the final PDF shows the number vertically detached from the formula row.

### Inline Math

Convert inline expressions to MathType when they contain operators, indices, fractions, vectors/bold variables, bars, primes, Greek indexed symbols, or compact formulas.

Keep tiny standalone symbols as styled Word text only when MathType makes punctuation or spacing worse. If kept as text, explicitly style italic/bold/superscript/subscript to match the PDF.

If a tiny standalone vector or dyadic symbol remains Word text, style it as the PDF shows it. For bold upright vectors, set the run bold and non-italic; do not leave it as italic just because nearby scalar variables are italic.

Use this boundary:

| Inline item | Preferred representation |
|---|---|
| Single variable or Greek symbol with no complex scripts | Styled Word text if it matches the source cleanly |
| Indexed variable, primed symbol, barred/hatted symbol, vector/bold symbol | Inline MathType unless styled Word text is visibly identical and stable |
| Fraction, derivative, summation, integral, relation, compact equation | Inline MathType |
| Prose condition or translated word near math | Word text, not MathType |
| Punctuation adjacent to math | Word text unless mathematically part of the expression |

Check inline math as a first-class formula surface:

- preserve italic/upright convention for variables, functions, constants, operators, and words;
- preserve bold/vector marks and distinguish scalar symbols from vector symbols;
- preserve subscript/superscript nesting, prime position, bars, hats, Greek letters, and punctuation spacing;
- verify every index from the PDF, including repeated inline occurrences that look similar but may differ by `m`, `n`, `i`, `j`, `\mu`, `\nu`, plus/minus, or prime marks;
- do not leave source-language words, captions, or condition labels inside MathType;
- verify equation references in prose point to the same visible numbers as the source PDF.

Inline math must read like part of the sentence:

- keep surrounding spaces and punctuation outside MathType unless punctuation is mathematically part of the expression;
- keep commas, periods, parentheses, brackets, and dashes visually attached to the correct words or formulas;
- avoid alternating text MathType text MathType for one compact symbol cluster when one inline object is cleaner;
- do not convert ordinary prose words to MathType just because they sit near a formula;
- check every inline occurrence after PDF export, especially Greek letters with indices, bold vectors, primes, superscripts, and references such as "from (n) into (m)".
- Reject plain-text formula placeholders or OCR-like markers left in prose, for example caret-only superscripts, `Y^<`/`Y^>`, `Y^*`, collapsed indexed families, or comma-separated formula lists that should be separate inline MathType objects.
- When one source sentence contains several adjacent inline formulas, represent each logical formula as its own inline MathType object or as styled Word math text only if the visual result is identical and stable. Do not merge a sequence into one oversized inline object when that changes punctuation, wrapping, or meaning.
- For inline boundary or parameter conditions split by MathType objects, verify the whole condition visually, not just each object. Reject rendered text such as `phi =, phi0` when the source says `phi = phi0`, and reject literal machine-translated condition labels such as `(для) m = 0` when the target prose requires localized ordinary text like `при m = 0`. If the MathType objects themselves are correct, repair only the surrounding Word text/run order and render-check the affected line.
- After source-map repairs that add or split inline formulas, inspect the placeholder DOCX text before running Word/MathType: surrounding words, spaces, commas, conjunctions, and punctuation must already be correct.

Repeatable inline check:

1. Extract or list all inline MathType objects and styled math-like Word runs on the affected page.
2. Compare them left-to-right with the source PDF sentence.
3. Check symbol identity, index/script placement, prime/accent placement, bold/italic/upright style, spacing, and punctuation.
4. Fix the expression or surrounding prose, then re-render the page.

### Integral Templates

Do not assume MathML import renders the same visual template as manual MathType editing.

Known safe pattern:

- If a double integral must look like nested/full-size MathType integral templates, generate with MathType TeX input (`SetMTTeXData`) or copy a user-corrected MathType OLE sample.
- A double or repeated integral created by typing two integral glyphs next to each other is not acceptable when the source shows full-size nested integral templates.
- A MathML-imported double integral that renders smaller, clipped, or visually thinner than the accepted sample is a hard `REVISE`, even if the mathematical text extraction is correct.
- Avoid optional TeX line spacing like `\\[7pt]` in `SetMTTeXData` strings; MathType can render `[7 pt]` as visible text.
- If `SetMTData(MathML)` creates smaller or clipped integral glyphs, mark the formula `REVISE` even if the expression is mathematically equivalent.

### Brace And Cases Templates

For piecewise/cases formulas:

- Use a real MathType brace template with a slot, not a typed curly brace.
- Put a vector/column template inside the brace slot when the PDF shows stacked rows.
- Keep the left-hand expression, equals sign, and brace structure as one coherent MathType expression.
- Keep each cases row as a complete row; do not assemble rows from unrelated fragments that can drift apart.
- Keep following or neighboring definition rows continuous unless the source PDF explicitly separates them.
- If a user-corrected sample used a brace-with-slot containing a vector/column, future pages must copy that structural pattern. A similar-looking glyph brace, one-cell brace, or matrix trick is still wrong.

Reject:

- small or stray-looking curly braces;
- text labels inside MathType;
- equation numbers inside MathType;
- `lhs`, `=`, and `rhs` split into separate stretched internal slots;
- cases columns that only look aligned because of accidental spacing.

### Matrices And Stretching Delimiters

For determinants, norms, bracketed vectors, and parenthesized matrices:

- Use a real MathType delimiter template around the whole matrix or array.
- Build the matrix/vector first, then wrap it with the delimiter template from the outside.
- For generated MathType TeX, prefer explicit outer delimiters such as `\left| ... \right|`, `\left[ ... \right]`, or `\left( ... \right)` around an `array`/matrix when the automatic matrix environment does not stretch correctly.
- The delimiter height must span the full matrix/vector, including all rows and nested fractions.
- Do not type separate vertical bars, brackets, or parentheses into individual cells or rows.
- Do not accept short bars that cover only one row or one cell of a determinant.

Reject:

- determinant bars that are only as tall as one matrix row;
- a bracket or bar repeated per cell instead of wrapping the complete object;
- matrices split into several MathType objects only to imitate delimiters;
- visually correct delimiters produced by plain Word characters outside MathType.

### Wide Equals-Gap Rule

Wide gaps before `=` are usually MathType-template defects.

Use source rows where each row contains a complete equation fragment.

Accepted pattern:

- each row keeps its left side, relation symbol, and right side in the same logical row;
- alignment templates are used only for real multi-row alignment, not to create accidental horizontal gaps;
- nested matrices or arrays are avoided unless the source is genuinely a matrix or array;
- a relation symbol that appears far from the left-hand expression after rendering is a defect, even if the formula is mathematically readable.

For generated sources, prefer `\begin{array}{l}` or another structure that keeps each equation row complete. Do not split `lhs`, `=`, and `rhs` across internal cells unless the PDF truly has a tabular equation.

## Exemplar Patterns

Use these as reusable patterns, not hardcoded targets.

### Native Double Integral Plus Continuous Equals Row

Problem encountered:

- one sample had correct-looking nested double integrals but put the left side in a separate internal cell;
- another sample fixed the equals row but reverted to smaller MathML-import integrals.

Accepted pattern:

- build or copy one editable OLE object that satisfies both requirements;
- use MathType TeX input when native integral templates matter;
- validate by rendering the final page and inspecting both the integral glyphs and the spacing around `=`.

### Brace-With-Slot Plus Vector Column

Problem encountered:

- a curly brace looked like a loose character or wrong template;
- the stacked cases were not inside a proper brace slot;
- a neighboring equation had its symbol separated from `=`.

Accepted pattern:

- insert a MathType brace-with-slot template;
- insert a two-row vector/column inside the slot;
- keep the equation before the brace continuous;
- keep the neighboring definition row continuous.

### One-Object Manual Samples

Problem encountered:

- a comparison DOCX had both a reference object and a target object, and the reference object was easy to copy by mistake.

Accepted pattern:

- create a one-object sample DOCX for fragile manual fixes;
- document `source sample -> inline shape index -> target formula` in the repo pipeline;
- render the sample preview before using it;
- update both the full builder and the targeted patcher.

## Error Prevention Ledger

Treat each recurrence as `REVISE`.

| Mistake to prevent | Symptom | Prevention |
|---|---|---|
| Treating OMML as final output | Final answer points to OMML or scratch DOCX | Final output must be editable MathType OLE DOCX plus rendered preview and validation |
| Treating a stage PASS as final PASS | Worker closes a chunk after prepare-only or writer-only evidence | Require verdict wording to name the stage; full skill PASS needs rendered source-PDF/layout/inline review |
| Self-accepting generated output | Same worker generates/converts a chunk and marks it final PASS | Generator may emit only candidate or scoped stage result; separate current-render review owns final PASS |
| Trusting stale QA reports | Old report says an issue was fixed, but current PDF still shows the defect | Re-render or inspect the current final candidate and recheck every listed prior blocker |
| Multiplying a systematic defect | Later chunks repeat a known broken brace/integral/layout/source-map pattern | Freeze that pipeline, update rule/script, repair the failing example, then continue |
| Rebuilding everything for one formula, layout, or figure/caption defect | Long Word/MathType run starts while blockers are local or non-formula | Stop the full run, use no-Word or targeted OLE repair, render affected pages, and promote only accepted targets |
| Starting writer before non-Word blockers close | Word/MathType conversion runs while source-map, layout, figure/caption, or typography defects are still unresolved | Finish source-map/layout/figure/typography repair first; writer is allowed only for initial conversion, broad formula refresh, or justified stale OLE state |
| Uncontrolled Word/MathType writer lanes | Word/MathType warnings, stuck COM, orphan `WINWORD.EXE -Embedding` | Use one active writer lane for DOCX mutation unless repo evidence proves a higher safe limit |
| Formula number inside MathType | The visible equation number is editable as part of the equation | Move number to ordinary text number cell |
| Figure/caption drift | Caption separates from figure | Group figure and caption in one stable Word structure |
| Figure and caption remain separate top-level blocks | DOCX has an image paragraph followed by a caption paragraph | Replace with one grouped figure table and keep caption editable as Word text |
| Formula table merges with other table | Extra columns or visible table artifacts after Word save | Separate neighboring tables with a tiny normal paragraph and suppress borders at table and cell level |
| Inserted display tables merge with neighbors | Two formulas or formula plus figure become one multi-cell table | Insert a tiny normal separator paragraph before/after inserted tables and verify XML cell counts after Word save |
| Equation number wraps inside number cell | Closing parenthesis drops to a separate line, for example `(52a` then `)` | Widen the number cell, use fixed table layout, and split multi-number displays with explicit line breaks or paragraphs |
| Source prose between formulas is lost | An unnumbered identity and the following numbered equation are merged, or the linking sentence disappears | Keep the unnumbered formula, linking prose, and numbered formula as separate Word-flow structures |
| Advancing queue after writer-only success | Next chunk starts after clean MathType/OLE counts while current chunk has no current coverage rows or source-page ledger | Record rendered-PDF/source coverage, source-map/source coverage or source-page ledger, visual comparison, and any exception before moving to the next chunk |
| Text labels inside MathType | Region names or prose conditions appear inside OLE | Move labels to Word text; keep MathType math-only |
| Oversized body text | Page looks like a poster or all-bold block | Restore book typography and source-like hierarchy |
| Mechanically converted overlay typography | Target PDF has many more pages, large sans/body text, unindented paragraphs, or captions styled as body | Normalize against the accepted exemplar/source before visual review |
| Inconsistent page typography | One page uses different font, spacing, or heading style from the accepted exemplar | Derive styles from exemplar/source and apply consistently |
| Figure/caption separated | Figure moves to one page and caption to another | Put image and caption in one borderless table with keep-with-next behavior |
| Figure image cropped after grouping | Caption is stable but the figure itself lost top/bottom/side content compared with source PDF | Replace or re-extract the figure image from the source crop before accepting the grouped figure |
| Figure caption clipped after grouping | The image is clean but the rendered caption stops mid-caption or loses source-equivalent legend/material text | Allow the caption row/cell to grow, remove fixed-height clipping, widen or split the caption text, and render the affected page before acceptance |
| Grouped figure table splits because image is too tall or starts too low | Image and caption are in one table but still render on different columns/pages, or a blank/caption-only page appears | Keep the group intact, constrain table width to the effective column, scale the image proportionally, and insert only source-faithful column/page flow controls before the group; re-render the exact candidate |
| Formula preview overlaps equation number | MathType OLE/media are present and source topology is correct, but the VML preview extends into the ordinary Word-text number cell | After source line-break/content proof, proportionally constrain the preview/table geometry without rebuilding unrelated OLE objects; render-check that the number cell is separated and the formula is not clipped |
| Connector prose after merged formula rows | A `where`/`где`/`with`/`Let` connector appears after two formulas even though the source places it between them, or a roots/condition sentence loses its formula reference outside MathType | Split the merged formula table or move the connector/reference as ordinary Word text to the source-flow position; preserve OLE/media bytes when the formulas themselves are already correct, then render-check the affected page |
| Inline condition punctuation/OCR residue | A boundary or parameter condition split by inline MathType objects renders with punctuation before the final object, or with source-language/machine words such as `(for)`/`(для)` in the wrong place | Inspect the Word run order around all inline objects in the condition, preserve correct OLEs, localize condition words as ordinary Word text outside MathType, and render-check the full sentence against the source PDF |
| Bad technical term translation | Domain term becomes nonsense | Verify against source context and use a consistent glossary |
| TOC/page-number drift | Contents use local chunk pages instead of book page numbers | Preserve source/global page numbers unless user asks otherwise |
| Inline math loses style | Greek/indexed/vector symbols look like plain text | Convert to inline MathType or explicitly style Word text |
| Inline formula remains as plain caret text | Rendered prose contains markers such as `Y^<`, `Y^>`, or unstyled indexed families | Split into real inline MathType objects or correctly styled Word math runs before writer conversion |
| Inline formula sequence is merged into one object | Several source formulas, conjunctions, and punctuation become one large inline object | Split by logical formula and keep prose/punctuation as Word text |
| Inline punctuation jumps | Comma/parenthesis moves around OLE in preview | Rewrite sentence or keep tiny symbols as styled Word text |
| MathType size mismatch | Formula appears too small/large | Rescale consistently and visually check preview |
| MathType baseline mismatch | Inline formulas float above or below text | Adjust inline object/template and verify rendered baseline |
| Formula font/style mismatch | Variables, functions, vectors, or operators have wrong italic/bold/upright style | Correct MathType styles or styled Word runs against the source PDF |
| Index copied by pattern instead of PDF | Formula has plausible but wrong subscript/superscript, prime, or Greek/Latin index | Recheck every base and script against the rendered source PDF, character by character |
| Similar glyph substitution | `ν/v`, `μ/u`, `φ/ψ`, `k/K`, `0/O`, or another near-lookalike is swapped | Use source crop/zoom and record ambiguity instead of guessing |
| Body font / size drift vs exemplar | Body uses Arial 10.5pt while exemplar uses TNR 11pt; headings 1-2pt oversized | Merge full exemplar `word/styles.xml` into the chunk's styles.xml, preserving chunk-specific pandoc styles (FirstParagraph, Compact, Bibliography, SourceCode/* tokens, CaptionChar, Figure, VerbatimChar, Table, Author, Date, etc.) |
| Body page label banners | Body flow contains `Страницы NN-MM` Title and `Страница NN` Heading paragraphs that source PDF does not show | Remove the paragraphs from `word/document.xml`, preserve bookmark Starts/Ends, drop service `страница-*` bookmark ids and reattach semantic bookmark Ends to surviving paragraphs |
| ALL CAPS section headings | Heading text in `word/document.xml` is uppercase Cyrillic, e.g. `9. МЕТОД ОБОБЩЕННОЙ МАТРИЦЫ РАССЕЯНИЯ` | Apply Russian sentence case while preserving number prefix and 2-4 char Latin acronyms; multi-run text-runs must be merged + redistributed carefully without losing `<w:rPr>` (bold/italic) |
| Multi-number formula cell concatenation | Right cell contains `(N)(N+1)(N+2)` joined by `<w:br/>` instead of separate paragraphs | Split each numbered label into its own `<w:p>` inside the same right `<w:tc>`, preserving paragraph properties and right-justification |
| Multi-row OLE display left untouched after multi-number split | Right cell now has N labels but left cell still has ONE merged OLE rendering all N equations as one image | Defer to writer-bound Phase 4 OLE rebuild; do not promote as visually correct |
| Stale manifest status | Project's release manifest reports `status: PASS` (or equivalent) but the chunk has unresolved skill defects | Reconcile manifest after every cleanup pass; project-defined status values must map honestly to the gate state the chunk actually passed (full skill review with render evidence is a different state than no-Word cleanup pass; do not coalesce them) |
| Skipping no-Word cleanup sweep before promote | Chunk lands in release as writer-only state, no body page label / inline punctuation / heading case / typography fixes applied | Always run the no-Word cleanup sweep against the project's defect-class catalogue (where one exists; otherwise enumerate Classes A/B/C/G/H/I/L/M below as the minimum) before promote; chunks with skipped sweep stay flagged for follow-up |
| Render gate skipped after no-Word edits | Phase 2/3 audits show "structurally clean" but no render evidence that page-flow, table-merge, figure-grouping behave correctly | Render at least one representative chunk through Word ExportAsFixedFormat and compare against source PDF before claiming render-validated PASS |
| Accents or primes drift | Prime, hat, bar, transpose, conjugate, or overline attaches to the wrong base or index | Rebuild the MathType script/accent template and re-render |
| Hat rendered as loose mark | A unit vector or hatted variable shows a small detached hat instead of a single accented MathType symbol | Use a MathType accent-template slot or explicit MathML `mover accent="true"` with the base inside the slot |
| Template symbol assembled from loose glyphs | Hat, tilde, overline, arrow, radical, brace, bracket, determinant bar, norm, or matrix delimiter looks short, detached, miscentered, or attached to only one row/cell | Rebuild with the corresponding MathType template and place the whole intended expression inside the template slot |
| Replacement glyphs in math | Black diamonds, boxes, or wrong brackets appear in a formula or inline expression | Rebuild the affected MathType/styled math using explicit delimiter templates or source-faithful symbols and re-render |
| Visible formula-table rule | A horizontal line appears below a formula table even though the source has no rule | Remove inherited table/cell borders or table style artifacts and verify in rendered PDF |
| Bold vector becomes slanted | Latin vector or dyadic letters render bold italic after MathML import | Postprocess MathML to upright bold Latin or use a verified MathType TeX/manual sample |
| Existing OLE mutated in place | A formula appears duplicated, merged, or repeated after a targeted patch | Delete and replace the target OLE object, then set MathType data once |
| Wrong manual OLE copied | Reference object replaces target formula | Use one-object samples and exact mapping |
| No source-PDF comparison | Formula looks plausible but differs from PDF | Compare edited formula and nearby inline math against source PDF |

## Validation Checklist

Before claiming PASS:

1. Render the affected final preview page and inspect it visually.
2. Compare the edited area against the source PDF.
3. Confirm body text, headings, captions, contents, and page numbers match the accepted book-style exemplar.
4. Confirm display formulas are in borderless two-column tables with MathType left and ordinary text number right.
5. Confirm figures and captions are grouped in stable borderless tables or another accepted non-drifting structure.
6. Confirm changed formulas are editable MathType OLE (`Equation.DSMT4`).
7. Confirm formula numbers, labels, captions, and prose are outside MathType.
8. Confirm MathType display and inline object sizes/baselines match the surrounding page.
9. Confirm vector, dyadic, field, unit-vector, and basis/test symbols match source bold/italic/upright style, and scalar components or coefficients were not accidentally vector-bolded.
10. Confirm every changed subscript, superscript, left script, prime, accent, and index grouping was checked against the source PDF, not inferred from a neighboring formula.
11. Confirm zero OMML and zero placeholders if touching a final DOCX.
12. Confirm inline math style and punctuation match the source PDF around the edited area.
13. Confirm no plain-text formula markers remain where source math requires MathType or styled Word math.
14. Confirm the current candidate, not a stale earlier PDF, was reviewed.
15. Confirm the generator did not self-accept the artifact as final PASS.
16. Confirm known systematic defects are not being propagated to later chunks.
17. Run the repo-relevant script syntax check or tests for changed scripts.
18. Run whitespace/diff hygiene checks such as `git diff --check`.
19. Confirm no Word/MathType automation process remains unless the user intentionally has Word open.
20. Confirm `word/styles.xml` Normal style font/size matches the accepted exemplar (Class L typography normalization) and no chunk-specific pandoc styles were lost in the merge.
21. Confirm no heading paragraph (Heading1-5, Title, Subtitle) contains 8+ consecutive uppercase Cyrillic characters that should be in sentence case (Class M).
22. Confirm no body-flow `Страница NN` or `Страницы NN-MM` paragraphs remain (Class G page label residue).
23. Confirm the project's release manifest `status` reflects the actual gate state for the chunk (full source-PDF visual review with render evidence is a different state than no-Word cleanup pass; do not coalesce them).
24. Confirm per-chunk skill review record names the exact OLE/media byte-identity check, the styles.xml merge audit, and the heading-case audit.
25. If the chunk contains a code listing (monospace runs `w:rFonts w:ascii="Courier"`/`Consolas`, `pStyle` resolving to a SourceCode/Verbatim family, or a printed listing caption such as `Листинг N` / `Program N` / `Listing N`), confirm a provenance pointer to the project's verified-source root is present in a caption or sidenote immediately adjacent to the listing block (Class N — operational form of the global `Results-table provenance discipline`).
26. Confirm the queue/status artifact for sequential chunk work records current coverage evidence for this chunk before the next chunk is started.

## Defect Class Index

The minimum defect-class catalogue this skill enforces. Where the project maintains its own catalogue (for example `docs/translation-defect-checklist.md` in the project), that document is authoritative for pattern evidence and confirmed examples; the table below is the in-skill summary the worker keeps front-of-mind during a pass.

| Class | Surface | Repair lane |
|---|---|---|
| A | Inline punctuation around MathType OLE | no-Word XML, surgical text-run edits |
| B | Bilingual name corruption (Latin + Cyrillic hybrid) | no-Word XML, full Latin or full Cyrillic |
| C | Word-order calque / OCR garbage in prose | no-Word XML |
| D | Greek letter substitutions in prose (`p` vs `ρ`, `v` vs `ν`, `u` vs `μ`) | no-Word XML for prose; writer-bound for OLE internals |
| E | Inner-product brackets `⟨ ⟩` vs `( )` | no-Word XML for prose; writer-bound for OLE |
| F | Unit-vector hat / dyadic bar / accent loss | writer-bound OLE rebuild |
| G | Page count drift and body-flow page labels (`Страница NN`) | no-Word XML for labels; writer/layout for page drift |
| H | Multi-number formula cell merging in number cells | no-Word XML for split; writer-bound for merged-OLE display image |
| I | Figure / caption ungrouping (top-level drawing + separate caption paragraph) | no-Word XML, wrap in borderless 1-col 2-row table |
| J | English `<mtext>` inside MathType OLE (`otherwise`, `at nodes`, `on S_0`) | writer-bound OLE rebuild |
| K | Source-correct equation reference numbering in prose | no-Word XML, requires source-PDF cross-check |
| L | Typography normalization against exemplar (`word/styles.xml`) | no-Word XML, full exemplar styles merge |
| M | Heading case normalization (Russian sentence case, no ALL CAPS) | no-Word XML, multi-run text edit |
| N | Code listing provenance pointer to project's verified-source root (operational form of global `Results-table provenance discipline` for program listings) | no-Word XML, adjacent caption / sidenote |

## Terms and Abbreviations

- DOCX: Microsoft Word document format.
- MathML: Mathematical Markup Language used as an interchange format for equations.
- MathType OLE: editable MathType equation object embedded in Word.
- OLE: Object Linking and Embedding; Word's container mechanism for embedded equation objects.
- OMML: Office Math Markup Language; Word's native equation format, not the final target here.
- PDF: Portable Document Format; the source and rendered preview authority for visual checks.
- QA: Quality Assurance; verification against the source PDF and accepted exemplar.
- REVISE: result state meaning the artifact must be corrected and checked again.
