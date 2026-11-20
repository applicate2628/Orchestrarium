---
name: mathtype-book-page
description: "MathType book page: format DOCX math and verify PDF."
---

# MathType Book Page

## Purpose

Use this skill to bring translated technical-book DOCX pages to an accepted MathType-based format. The skill is repo-independent: discover local paths and scripts from the current repository instead of hardcoding drive letters, document segment names, UIDs, or machine-specific locations.

Use the currently accepted page in the active repo as an exemplar, but express every rule as a reusable pattern for other pages. Do not encode page numbers, formula numbers, formula identifiers, source document names, or one repository's directory layout into the skill body.

Applying this skill means closing the visual/template defects in the document, not merely reviewing them. A raw OMML/MathML-to-MathType conversion, an OLE count report, or a worker report that says formulas were converted is not skill application. If the rendered document still shows old defects such as small/clipped integrals, loose or wrong braces, short determinant bars, detached hats, artificial alignment cells, wide gaps before `=`, or text/formula numbers inside MathType, mark the chunk `REVISE` and route it to template/source repair before final review.

Applying this skill also means preserving the full translated source coverage. A formula-complete or figure-complete chunk that omits ordinary prose, section introductions, derivations, problem statements, footnotes, captions, table titles, listings, output blocks, references, or continuation text is `REVISE` even when every visible formula is editable MathType OLE.

## Source PDF Authority

Treat the original source PDF as the mathematical and layout authority for every final DOCX/PDF candidate. An accepted exemplar controls reusable formatting patterns, but it never overrides the current source PDF's formula content, indices, accents, inline math, equation references, captions, page numbering, or source-specific layout.

No chunk may receive final `PASS` until the current rendered candidate has been compared against the corresponding source PDF pages after the latest edit. This comparison must cover every changed display formula, every meaningful inline MathType object or styled Word math run, nearby punctuation, equation-number references in prose, figure captions, code/listing/output blocks, and any formula/table/layout region touched by the repair.

Before repairing a local formula/table/figure defect, verify the source-flow order on the rendered source page, not only the extracted paragraph order. A caption, figure crop, display formula, or prose connector can be extracted in the wrong stream order. If the candidate has a loose caption, a missing figure, or formulas appearing after later-numbered displays, compare the whole source spread visually and repair the Word flow so figures, captions, formulas, prose connectors, and equation numbers appear in source order. Do not move a grouped figure merely to the paragraph that first references it when the rendered source page visibly floats the figure after intervening formulas or connector prose; in that case preserve the visual source flow and keep the figure/caption grouped at that position.

When repairing a local formula template such as cases/braces, inspect the immediately preceding and following prose against the source PDF before promotion. A formula can have correct MathType OLE content but still be in the wrong Word flow order, for example sitting before the paragraph that introduces it. Repair that neighboring source-flow defect in the same targeted lane, without rebuilding unrelated formulas.

Correct XML order is not sufficient for source-flow acceptance. After moving connector prose, conditions, or labels around a display formula, render the exact candidate and check whether Word pagination or column flow visually separates the connector from its formula or places the formula before its introduction. If the connector and display no longer read in source order on the rendered page, treat it as a layout/page-flow blocker: fit or group the affected block with stable Word paragraph/table settings, or record the remaining visual-flow defect explicitly. Do not claim visual pass from paragraph/table indices alone.

After repairing a figure/caption block, inspect the immediately following prose and any numbered/bulleted list against the same source spread. A broken extraction can swallow the first body paragraph into the caption table, split one source paragraph across the wrong containers, or drop/merge list items. Captions must contain caption text only; explanatory prose and list items must be ordinary Word body/list paragraphs in source order, with their inline MathType/styled math preserved or rebuilt at the exact source positions.

Figure grouping is not enough to prove figure correctness. For each touched figure, compare the rendered candidate image against the rendered source PDF: all axes, tick labels, titles, legends, frames, curve endpoints, and source-visible labels must be present and inside the page/column. If the DOCX media part is already cropped, replace that media part from a source-backed crop; if the media is complete but the render clips it, reduce the drawing/table extent to fit the column. Do not rebuild MathType formulas for pure figure crop/extent defects.

After inserting, moving, or recropping a missing figure, inspect the next figure block on the same source spread before accepting the lane. A newly repaired float can expose an older cropped media part or stale `wp:extent` on the following figure; repair that figure by replacing only its image media and proportional display extent from a source-backed crop, keeping the editable Word caption, and do not rebuild unrelated MathType objects.

Rendered figure text is part of the translation gate even when it lives inside a bitmap and cannot be found by DOCX/PDF text extraction. Visually scan touched figures for accidental source-prose bands, OCR residue, and source-language legend labels. Repair only the affected media part when possible, preserving mathematical/node labels that are source symbols. If the original drawing dimensions control nearby column flow, prefer same-size whiteout/label replacement over cropping; any change to bitmap dimensions or `wp:extent` must be followed by a render check of the whole affected page because display formulas can migrate across columns. When a replaced image becomes clipped or too small, adjust the containing table/cell width and the drawing extents (`wp:extent` plus the matching drawing transform extent) together, then re-render; replacing the bitmap bytes alone is not sufficient evidence.

When inserting a new bitmap crop into an existing DOCX, prefer cloning a rendered image paragraph/table from the same current candidate and retargeting only its relationship, extents, and `docPr`/picture names. Handcrafted minimal DrawingML can parse and reserve page space in Word while exporting blank pages or missing image XObjects. After insertion, verify both visually and with a PDF image-object probe such as `pdfimages -list`; file existence, relationship validity, and ZIP/XML success are not enough. If the rendered page is blank or the expected image object is absent from the exported PDF, revise the insertion template before changing crop geometry or promoting the candidate.

When localizing bitmap labels, verify both translation and drawing integrity after render. Replacement labels must be scaled to the original figure, not to body text, and whiteout boxes must cover the old words without erasing meaningful geometry, axes, arrows, hatching, or curve data. If a rendered check shows either residual source-language fragments or oversized/truncated replacement labels, revise the media-part repair and render again before acceptance.

When text extraction from the PDF is noisy, render or crop the source page and compare visually. If the source PDF is ambiguous, record the ambiguity in the repo QA artifact and keep the chunk at `REVISE` or `CANDIDATE`; do not infer the formula from neighboring patterns or from the generated DOCX.

When old QA notes conflict with the current source render or a newer accepted chunk ledger, treat the old note as stale until revalidated. Do not "correct" OCR-like labels or references by visual similarity or inference (`4g` versus `49`, `80b`, and similar); verify the exact source glyph on the current rendered page and record contradictory stale artifacts instead of applying them.

Nearby source surfaces can intentionally disagree. Body prose, captions, legends, table headers, and neighboring paragraphs must each be checked against their own source line/crop; do not normalize a body value from a caption value, or a caption value from nearby prose, unless the source or user explicitly marks one as erroneous.

Translated prose is part of the source check. Do not leave accidental source-language technical terms inside target-language body text merely because formulas are correct; classify whether the term is a code token, bibliography title, figure-label text, or ordinary prose, then translate ordinary prose terms consistently. When a sentence contains paired inline substitutions, coordinate relations, or variable changes, verify the pair as one source unit; do not preserve one inline object if its sibling relation was dropped.

Body-font outliers can be source-flow defects, not only style defects. If one line of ordinary explanatory prose is rendered in code/listing size or monospaced style while the following line continues the same source sentence, compare the source page, merge the split text back into one body paragraph, and preserve any inline MathType OLE objects or styled math runs from the continuation. Do not merely enlarge the code-style paragraph if the source sentence was accidentally split; repair the paragraph flow and render the affected page.

Source tables must not be flattened into code/listing paragraphs. If a source-visible table is rendered as one or two monospaced lines, compare the source page visually, rebuild the area as a real Word table with source-faithful columns/rows, restore the table title/source note and any explanatory prose immediately before or after the table, and delete stray tail fragments created by the flattening. Keep table numeric text as ordinary Word text unless the source cell contains mathematical notation requiring inline MathType or styled math.

Font-size audits must be render-grounded. A DOCX text run can look like a font or missing-text defect when inline MathType OLE objects are omitted from text extraction, or when a chunk-level body-size baseline is skewed by references, index text, tables, or code. Before repairing a font outlier, inspect the rendered page against the source page and compare the paragraph with its immediate neighbors. If the rendered page is visually correct, record a scoped false-positive classification instead of changing styles.

Short OCR/flow fragments near formulas are translation blockers even when they are only one or two Latin characters. Scan rendered text and DOCX text for residues such as a stray `i-` after a bracketed citation before a display formula, then compare the full source line visually. Remove the fragment only when the current source PDF proves it is not a source-visible symbol or connector, and update the owner repair/generator so the next build cannot reintroduce it.

Do not clean OCR/provenance leaks by deleting marker paragraphs only. For appendix/listing/output failures, compare the rendered source flow, identify the full source-equivalent range from stable surrounding anchors, and remove the entire leaked OCR range before inserting translated prose, source-faithful listing/output blocks, or recorded source-image exceptions. A successful grep for a provenance/uncertainty marker is not enough: unmarked code fragments, source captions, page headers, or output tails can remain visible and must be checked in the rendered candidate.

Source-visible headings and section numbers are prose completeness gates. Compare the rendered source spread for missing headings, wrong heading level/style, all-caps drift, and headings merged into body paragraphs. Repair headings as ordinary Word heading paragraphs and render-check neighboring figures, captions, formulas, and body paragraphs for flow changes; do not rebuild MathType objects for a heading/style defect.

If the user explicitly accepts a visible or mathematical deviation from the source PDF, record it as a named human-approved exception in the chunk QA artifact and status ledger. Preserve the exact user acceptance wording, the donor/sample path, the rendered evidence path, and the remaining source mismatch. Such an exception may unblock the next local repair lane, but it is not source-PDF proof and must not be silently upgraded to final formula `PASS`.

Source negation and modality are source-critical text, not style noise. During translation/font audits, explicitly compare source words such as `not`, `not necessarily`, `only`, `except`, `unless`, `at least`, and `at most` with the translated sentence. A visually clean paragraph is `REVISE` if it drops a negation or reverses a constraint, even when font size, MathType objects, and formula numbering are correct. Repair the prose only, preserve nearby inline math/OLE objects, and render the affected line after the fix.

Reference and index headings are ordinary translatable document structure. Translate headings and running labels such as `REFERENCES` and `INDEX` unless the user approved a source-language facsimile, while preserving bibliography article/book titles, journal names, author names, code strings, and file names as source-language exceptions. Compact index entries may legitimately use smaller source-like font; classify them by rendered source comparison, not by body-text size heuristics alone.

After repairing or regenerating a references/bibliography tail, compare the rendered candidate against the source PDF for heading count, first/last item, and numbering range. Multiple independent references sections can be source-correct when a chunk crosses chapter or appendix boundaries, but a duplicated references heading with the same first bibliography item, a duplicated first item, or numbering shifted by one is a text-flow blocker even when formulas, OLE counts, and publication-token scans are clean. Repair the reference-tail owner so it removes stale existing references from the section heading, not from the second item or another mid-list anchor.

Formula-adjacent Word text is still translation text. Source-visible connectors or conditions between/next to MathType objects, such as `and`, `or`, `where`, `for TE modes`, and `for TM modes`, must be translated as ordinary Word text when they are outside the mathematical expression. Keep them out of MathType unless the source formula template requires the condition inside the equation object, and render-check that the translated connector does not shift or overlap the neighboring OLE previews.

Merged multi-number display blocks are `REVISE` when the source PDF has ordinary prose between the numbered displays. Source-visible connector phrases such as `where`, `with`, `in explicit form`, `in matrix form`, `therefore`, `provided that`, and their translated equivalents must appear in the same visual source-flow position as ordinary Word text outside MathType. A single MathType/table block with right-cell text `(N)(N+1)` is acceptable only after rendered source-PDF comparison proves the source itself is one aligned multi-line display with no intervening prose connector; otherwise split the display tables or move the connector before promotion.

Author-list connectors inside otherwise translated captions or body attribution are ordinary prose connectors. Translate an English `and` between two author surnames (a source caption form such as `<Surname1> and <Surname2>`) into the target-language conjunction unless the whole line is a bibliography entry, a source title, a journal name, or a user-approved facsimile. Preserve author names as source-visible Latin names when that is the document convention; translate the connector, not the names.

Caption copyright and attribution boilerplate should not remain as source-language prose in an otherwise translated caption. Convert caption forms such as `<Author> et al. [N], copyright © YYYY by <Publisher>` to source-faithful target-language attribution such as `<Author> и др. [N], © YYYY <Publisher>` (or the repository's equivalent localized style), unless the user explicitly requests a verbatim source facsimile. Do not apply this rule blindly to bibliography entries or source titles; captions are the primary target.

## Gate Discipline For Workers

Never collapse stage-specific success into final acceptance.

| Stage | Allowed result | Not allowed |
|---|---|---|
| Source-map or no-Word repair | `PASS` only for the scoped source-map subset, with final chunk still `REVISE` | Claiming final MathType/layout/source-PDF acceptance |
| XML-only layout/table/figure repair | `CANDIDATE` only, until the exact scratch DOCX is rendered and compared with the source PDF | Treating clean DOCX XML, grouped figures, or fixed table counts as visual acceptance |
| Writer/OLE insertion | `PASS` only for mechanical conversion counts, exported DOCX/PDF, and zero placeholders | Treating OLE count, validation JSON, or exported PDF existence as skill PASS |
| Skill review | `PASS` only after full source-text coverage review, rendered visual review, source-PDF formula proofread, inline proofread, layout review, and figure/caption review | Accepting spot checks, formula-only checks, stale reports, or worker summaries |

Before any worker starts a chunk, require a quick anti-false-pass scan:

1. Locate the source PDF, final DOCX/PDF candidate, validation JSON, formula checklists, and existing review/spec artifacts.
2. Check whether the final candidate is missing, stale, mechanically converted only, or already marked `REVISE`.
3. Compare source OCR/text length and candidate rendered-PDF text length as a rough coverage sanity check; investigate low ratios before touching MathType.
4. Inspect the DOCX structure for formula tables, table cell counts, OLE/object counts, drawing/image paragraphs, caption paragraphs, obvious font/justification drift, and remaining OMML/placeholders. Use live counts from the current DOCX package for release-state evidence; older validation JSON may describe a pre-repair writer pass and must not override the current package's OLE/media/object counts.
5. Inspect the rendered PDF visually enough to catch missing prose blocks, oversized body text, loose figures/captions, table merges, clipped formulas, and obvious inline-math corruption.
6. Compare current findings with prior QA artifacts, but do not let an older report close the gate. Old `PASS` or `REVISE` rows are evidence to recheck against the current rendered DOCX/PDF.
7. If any required skill surface is unchecked, mark the chunk `REVISE` and write a repair/spec artifact instead of advancing the queue.

Workers must state the scope of their verdict. Use phrases such as `PASS for no-Word source-map repair only` or `PASS for mechanical writer conversion only`. Do not write bare `PASS` unless the full skill review gate has passed.

## Full-Text Coverage Gate

Before final `PASS`, prove that the candidate represents the whole source chunk, not just formulas and figures. This is the quantitative omission check; it is complementary to the Translation Completeness Gate (which checks that each visible unit is translated and in source flow) and does not replace it.

Required coverage checks:

1. Build or update a source-page ledger for the chunk. For each source page, record the section/problem range, important prose anchors, figures/tables, footnotes, captions, and numbered formulas that must appear in the candidate.
2. Extract text from the rendered candidate PDF and compare it with the source OCR/text as a rough falsification check. For normal prose-heavy technical-book chunks, an output/source character ratio below `0.85` is a hard `REVISE` unless the QA artifact explains a source-specific reason such as OCR garbage, mostly-image pages, very dense formulas, or intentional scope exclusion approved by the user. A high ratio is not a PASS by itself.
3. Visually inspect the rendered candidate pages against the rendered source pages after the latest edit. Confirm that prose blocks have not been skipped between formulas, across page breaks, after figures/tables, or at chapter/section boundaries.
4. Check continuation areas explicitly: text before the first formula, text after the last formula, text between consecutive display formulas, problem lists, footnotes, and captions that wrap across lines.
5. Record the coverage result in the QA artifact. If the chunk is formula-only by admitted scope, state that scope explicitly; otherwise formula-only output is defective.

Do not advance to the next chunk when the current chunk is missing ordinary text. Freeze the pipeline, mark the affected chunk `REVISE`, and repair the coverage defect before producing more chunks unless the user explicitly parks the repair.

For sequential chunk production, treat the previous chunk's full-coverage closure as a prerequisite for the next chunk. Do not start the next chunk from formula/OLE success alone: the current chunk's QA or status artifact must contain fresh evidence for rendered-PDF/source text coverage, source-map/source coverage or an equivalent source-page ledger, visual source comparison, and any source-specific exception. If a low-ratio repair required adding ordinary prose, update the reusable source-map or builder pattern before continuing so the omission does not propagate.

## Defect Blocking Gate

Treat this skill as a quality gate, not a generator prompt. A worker may produce only a repair candidate while any hard blocker remains. It must not advance a chunk, start a batch, or claim final acceptance.

Hard blockers:

- no current source-PDF render or accepted exemplar was consulted;
- no current candidate DOCX/PDF was rendered after the latest edit;
- any display formula, meaningful inline formula, or formula reference is unchecked against the source PDF;
- in a translated deliverable, any source-visible heading, body paragraph, list item, caption, table text, formula-table Word label, natural-language formula connector/condition, explanatory prose between display formulas, contents row, reference heading/item, footnote/endnote, listing caption, or output caption is missing, left in the source language by accident, untranslated, OCR-like, semantically reversed, or unchecked against the source PDF;
- any OCR/PDF-flow residue remains in visible prose: corrupted reference brackets (`{24|`, `{15}`, `|24]`, `|3-5]`), missing punctuation inside multi-reference citations (`[1 2]` when the source shows `[1, 2]`), interval delimiters misread as pipes/angle text (`|a,<]` instead of a source interval), or source line-break hyphenation preserved as separate translated paragraphs (`preобра-` / continuation-word style splits);
- any source-visible mathematical condition or relational operator in prose near a display formula is weakened, normalized, or OCR-flattened (`≪` becoming `<`, `≤` becoming `<`, `≈` becoming `=`, etc.). Treat these prose operators as mathematical content, not typography, and verify them against the source render before accepting the neighboring formula;
- any source-visible bracketed reference or citation that introduces a display formula is dropped, duplicated, moved into the equation object, or left as an orphan line when it should read with the introducing sentence. Keep it as ordinary Word text in the source position and render-check the line break;
- any duplicate tail paragraph appears because source-flow extraction repeated the end of a sentence after an inline formula or display formula. Remove the duplicated paragraph only after comparing the whole source sentence, and preserve the inline MathType/styled math objects in the remaining paragraph;
- any bibliography/reference-list numbering collapses across a page or column break: source-numbered entries must not render as bullets, unnumbered body paragraphs, or merged entries without the visible reference number; repair as text/list structure and source-check the affected reference page before final acceptance;
- any body paragraph or connector after a numbered formula inherits list numbering from a nearby source list and renders a stray bullet, dash, or stretched number before an inline formula. Remove the inherited numbering from that paragraph, keep only source-visible numbering, and render-check the affected line because XML text order can look correct while Word adds a visible marker;
- any source-visible numbered prose list is restored with the source item numbers and readable list alignment. Do not leave list items fully justified if that stretches `1.` or `2.` away from the item text; use stable left alignment for the list item paragraphs while preserving surrounding book-style body justification;
- any known defect pattern from an earlier page/chunk recurs: clipped integrals, wrong braces/cases, short bars, detached hats, artificial alignment cells, wide gaps before `=`, wrong bold/italic/upright math style, wrong indices, text inside MathType, formula numbers inside MathType, loose figure/caption blocks, merged formula tables, or plain-text formula markers;
- any targeted MathType repair makes a display formula wider or taller than the source layout, causing overlap with the equation-number cell, clipping, or cramped scaling. Compare the source line breaks before fitting: when the source breaks a long product, matrix chain, derivation, or transformation across lines, rebuild the MathType object with source-faithful row breaks and continuation markers instead of shrinking the whole formula or accepting overlap. Keep the equation number outside MathType and render-check the full page, not just a tight crop;
- any inline or display function name from the source (`sin`, `cos`, `cosh`, `exp`, etc.) renders as glued italic variable letters or loses the source spacing around neighboring variables; use native MathType/operator templates or explicit MathML operator/function structure, then render-check the affected line;
- any source-visible numeric power, tolerance, or accuracy expression in prose/captions (`10^{-6}`, `10^-6`, `O(r^{-2})`, etc.) is rendered as OCR-like punctuation/text, loses its exponent, or is separated from the source sentence; repair the prose completeness first, then represent the expression as inline MathType or stable styled math in the source position;
- any source-visible inline exponential, decay, phase, or propagation factor (`e^{-α Δl}`, `e^{-jβz}`, `e^{jωt}`, etc.) is split into raw text plus one-letter OLE objects, loses Greek/spacing/script placement, or makes the translated sentence semantically wrong. Repair the whole source sentence and the whole inline expression together; do not patch only the visible letter or exponent fragment. If a temporary styled Word fallback is used, record it as scoped `CANDIDATE`, remove superseded OLE/media parts, and do not call it final MathType `PASS`;
- any source-visible inline coordinate, operator, or differential expression in prose/captions (`R cos alpha`, `R sin alpha`, `dR d alpha`, etc.) is flattened into OCR-like glued text (`Rcosa`, `Rsin a`, `dR da`) or loses Greek symbols/spaces/operator styling; repair the Word prose and inline math at the source position before accepting the page;
- any accidental source-language prose hybrid remains in a translated paragraph, heading, list item, or caption outside intentional code, source labels, bibliography titles, or user-approved terminology exceptions;
- any source-visible section heading, subsection heading, or numbered heading is missing, styled as ordinary body text, merged into the following paragraph, or translated with the wrong hierarchy;
- the candidate changes unrelated formulas/pages without an explicit accepted reason;
- the worker cannot name exactly what changed, what stayed untouched, which pages were rendered, and which source-PDF regions were compared.

The agent that generated or converted a chunk must not issue final `PASS` for that same artifact. It may report `CANDIDATE`, `REVISE`, or a scoped stage result. Final `PASS` requires a separate current-render review by the main/integration gate or an explicitly assigned reviewer.

If a defect is systematic in one chunk, freeze the same pipeline for later chunks until the rule/script is updated and the failing example has a rendered repair candidate. Do not multiply known-bad output.

## Defective-Chunk Repair Workflow

For any defective chunk, read and execute `references/defective_chunk_repair.md` before changing files. That reference is mandatory when the task is to fix a bad chunk, not optional background reading.

Minimum repair loop:

1. Classify the chunk state: missing final candidate, mechanical-conversion candidate, source-map defect, translation/prose-completeness defect, localized formula/template defect, inline-math defect, layout/typography defect, figure/caption defect, table-structure defect, or systematic pipeline defect.
2. Choose exactly one repair lane for the next pass and write the expected artifact: source-map patch, targeted OLE patch, layout candidate, figure/caption grouping candidate, or justified full writer.
3. Create a scratch candidate first; do not overwrite the final DOCX/PDF before the repaired area renders correctly.
4. Render the affected pages and compare them with the source PDF plus the accepted exemplar.
5. Record changed formulas/pages, untouched formulas/pages, current blockers, and the next gate.

If the worker cannot complete these steps, it must return `REVISE` with a defect ledger instead of producing more converted output.

## Targeted Repair First

Do not run a full Word/MathType writer pass when the active defects are layout, figure/caption grouping, typography, grammar, punctuation, source-map review, or one-to-few formula/template defects. For local formula defects, replace only the defective formulas or inline objects and leave accepted formulas untouched. A full rebuild is the last step for broad source-map changes or stale OLE state, not the default repair tool.

Use this order:

1. Audit the current final DOCX/PDF and source PDF to identify the exact affected pages, formulas, inline objects, tables, or paragraphs.
2. For translation, text, layout, table, figure/caption, TOC, grammar, or punctuation defects, repair the DOCX layout/source structure first without invoking MathType conversion for unrelated formulas.
3. For a small number of formula defects, create or reuse a one-object MathType sample and replace only the affected OLE objects in a scratch candidate. Do not reconvert unrelated formulas just to validate the repaired ones.
4. For source-map defects, run no-Word prepare-only and payload audits first; do not start Word/MathType until the map is writer-ready.
5. Render only the affected pages first and compare them against the source PDF and accepted exemplar.
6. Promote the targeted candidate only after visual/source-PDF checks pass for the repaired area.

If a no-Word text or inline repair corrects prose emitted by a source-map owner, generator, or targeted repair script, update that owner as well as the current scratch candidate. A candidate-only XML replacement is not durable when the next reproducible run can regenerate the same bad sentence, label, punctuation, or connector. The repair must identify the owning source, constrain text replacements to the exact expected occurrence count, render the affected line/page, and record both the current candidate and owner-script change in the artifact.

When multiple scratch candidates exist for one chunk, always identify and continue from the newest verified candidate lineage that contains the accepted formula/OLE repairs. Do not run a layout/style normalizer against an older final release if later scratch OLE candidates corrected formula content. Rebase layout-only repairs onto the latest accepted OLE candidate, or explicitly prove that the final release already contains those OLE changes before promotion. A visually neat candidate based on stale formulas remains `REVISE`.

Apply the same lineage check to targeted repair scripts. Before running a one-off formula, inline, table, or figure repair, inspect the script's default input candidate and compare it with the newest status ledger or current handoff. If the default is stale, pass the current candidate explicitly or update the script default before accepting output. The repair artifact must record the actual base DOCX used; a clean render from a stale base is `REVISE` because it can silently discard later accepted repairs.

If a stale-base run has already produced later candidates, repair the lineage before continuing review. Find the newest verified base that still contains all previously accepted repairs, then reapply only the missing later targeted patches in dependency order. After rendering, probe at least one marker from every repair that could have been dropped, such as a prior formula-template fix, figure/caption move, heading insertion, inline-math repair, and the newest repaired formula. Do not patch only the visible symptom on the stale candidate; that preserves the regression. Update the one-off script defaults or invocation notes so the next run starts from the cumulative candidate.

After a source-map repair changes any formula payload, split, order, or inline object, any older MathType OLE output for that changed object is stale even if the previous writer run was mechanically clean. Route it to targeted OLE replacement or a justified chunk-local writer only after non-Word blockers are closed.

An existing MathType OLE object can also be stale or visually partial even when package counts, validation JSON, and source-map identifiers look clean. If a rendered formula shows only a tail fragment, missing left side, wrong row order, missing display number, or source-inconsistent residue, treat that object as defective current evidence. Replace only the affected object or source-flow block from a source-backed donor; do not use clean OLE counts as acceptance evidence for the visible formula.

Preserving inline OLE objects by ordinal is not source proof. When rebuilding a mixed prose/inline-math paragraph, verify every preserved inline object or styled math run against the rendered source PDF for symbol identity, script/accent placement, and style. This includes visually similar source variables (`u`/`v`, `ν`/`v`, `μ`/`u`), repeated inline functions such as `v(s)` around a display equation, and indexed one-symbol references such as `v_i`; a paragraph can have correct punctuation while still carrying the wrong preserved OLE or a flattened plain-text index. If a preserved object is the wrong symbol or index, replace only that object with a source-backed donor or stable styled Word math, remove the superseded OLE/media relationships when they become unused, and update the owner script so the next assembly cannot reintroduce the stale object.

Treat lost inline superscript signs and star substitutions as high-risk OCR defects. If the source sentence has symbols such as `a^-`, `b^+`, `d^+`, or `R_m''` and the translation shows plain `a`, `b*`, detached punctuation, or a wrong prime/star, repair the inline object as source-faithful styled math or editable MathType at the exact text position. Verify the rendered baseline and the source sentence before accepting the prose.

Reject prose/OLE residue blocks where inline symbols from one source sentence have been split into separate blank-looking MathType paragraphs between the prose and the following display formula. Compare the source sentence visually, rebuild the whole sentence with inline MathType or styled inline math at the correct positions, remove the orphan residue paragraphs and their package parts, then render-check that the following display formula still starts immediately after the source-equivalent prose.

Inline lists of indexed variables are source-critical as a group, not as independent glyphs. When the source enumerates paired or repeated indexed terms such as `(l_{1a}, l_{2a}), (l_{1b}, l_{2b}), (l_{1c}, l_{2c})`, verify the whole sequence against the rendered source PDF: all pairs, suffixes, commas, parentheses, and continuation prose must be present. A candidate that collapses the group to one pair plus an ellipsis, loses pair suffixes, swaps indices, or leaves punctuation before the inline objects is `REVISE` even if the remaining objects are editable MathType. Repair with targeted inline MathType donors when practical; for tiny scalar/index sequences, a source-backed styled Word math fallback is allowed only when recorded in the QA artifact and rendered against the source.

When an existing inline MathType OLE has correct mathematical content but leaves a visible gap before punctuation, do not downgrade it to styled Word math as the first fix. Move punctuation into ordinary Word text at the source-correct side of the object, then try tightening only the inline preview geometry (`v:shape` width or equivalent render-box metadata) while preserving the OLE/media bytes. Render the affected line to prove the comma/period/semicolon is visually attached and the formula is not clipped. Replace the OLE only if the source formula itself is wrong or the preview geometry cannot be made source-faithful.

If the punctuation is source-correct but Word still wraps a comma/period away from a very short inline OLE, treat it as a typography defect. Prefer tightening the preview box or a styled Word math replacement for simple symbols; when preserving the OLE is required and the visual result is otherwise correct, a local no-break punctuation grouping may be used, but it must be recorded in the QA artifact and visually checked because PDF text extraction may expose the invisible joiner.

Inline punctuation repairs must include a full-sentence source check. A comma or period defect around an inline formula often coexists with missing source-visible continuation text after later inline objects in the same paragraph. Compare the entire rendered paragraph with the source PDF and restore any missing prose, conditions, numeric lists, references, or natural-language formula connectors as Word text plus inline MathType or stable styled math in the source position.

For prose lists containing several inline MathType objects, verify the whole source sentence, not just the first comma. A source pattern like `three ratios, i.e., L/K = 29/9, 28/10, and 27/11` must render as localized prose plus ordinary Word punctuation between inline objects: colon or introductory comma before the first object only when grammatically required, comma+space between list items, the localized conjunction before the last item, and the sentence comma/period after the completed inline object. Reject `отношения:, <math> <math> и. <math>`, `при, <math>`, `выбрано, <math> что`, or `близко к. <math>` style outputs even if each individual inline object is mathematically correct.

Plain text around formulas can carry the same source-math defects even when all OLE counts are clean. If a rendered sentence contains formula-like Latin letters, stars, region labels, indices, or OCR substitutes as ordinary prose, compare the full sentence with the source PDF before deciding it is translation. Rebuild the sentence as target-language Word prose plus source-faithful inline MathType or styled Word math for each mathematical token, including subscripts, superscripts, region letters, accents, and punctuation placement. Update the owner script; a candidate-only text replacement is not durable.

Single-letter inline variables in prose are high-risk OCR targets. Source `I`, `l`, `1`, `F`, `P`, `U`, Greek letters, or indexed one-letter symbols can appear in the candidate as `/`, `|`, blank OLE gaps, dropped bases, or punctuation-like fragments while text extraction remains misleading. Verify the rendered source crop and candidate line visually before accepting or rejecting. For simple scalar symbols, use source-faithful styled Word math when it preserves baseline and spacing; for indexed/accented/vector forms use inline MathType unless a rendered styled fallback is explicitly recorded. Keep surrounding grammar and punctuation in ordinary Word text.

Cases and piecewise displays need the same source/translation check. Do not silently replace source-visible natural-language conditions such as "if ..." or "otherwise" with math-only inequalities, or vice versa, unless the source, accepted exemplar, or user explicitly approves that normalization. In translated chunks, translate condition words when they are part of the formula's visible meaning. Keep them inside the MathType object only when they belong to the cases layout; otherwise move connector text to stable Word runs outside MathType. Render-check the full cases block after any change.

Right-side boundary-condition braces are the same defect class as left-side cases braces. When the source groups two or more equations with a right curly brace before a condition, build it as a real delimiter/array MathType template such as an equation array with a right brace slot, not as flattened aligned text or a typed curly glyph. Keep the equation number outside MathType and render-check the brace height against the source PDF.

Do not put translated Cyrillic condition text through MathType's TeX import path (`SetMTTeXData`). On some MathType installs the TeX path preserves large brace/templates correctly but renders Cyrillic text as mojibake (for example CP1251-looking Latin glyphs such as `äëÿ`) or red raw text. For translated condition words inside cases, prefer MathML `mtext` via `SetMTData`; when MathML breaks the fragile brace layout, use the TeX path for the math-only MathType object and place the translated condition words as ordinary Word text in a stable formula-cell layout outside MathType. In both variants, render the donor and the target page before accepting the repair.

After an XML-only repair changes layout, table structure, figure/caption grouping, page markers, or number cells while preserving OLE binaries, the output is a structural candidate only. It must be exported/rendered from that exact scratch DOCX and checked against the source PDF before promotion or final review. If the render rejects the structure, update the repair rule or template instead of rerunning the same XML patch.

XML parse success and ZIP integrity are not enough for XML-only candidates. Before handing a candidate to the render gate, run a semantic OpenXML sanity check for Word-openability defects introduced by serialization: every prefix listed in `mc:Ignorable` must be declared in the same root scope; bookmark/comment/permission/proofing/move range starts and ends must be balanced or proven unchanged from a Word-openable base; typed attributes must not be serialized as empty strings, especially numeric spacing/indent values such as `w:before=""` or enum values such as `w:jc w:val=""`; `sectPr` must remain body-level and final; table cells must have terminal block content; object/image relationships must resolve to existing parts; OLE/VML shape IDs and drawing IDs must remain coherent. A candidate with missing `mc:Ignorable` namespace declarations, invalid empty typed attributes, orphaned range markers, dangling relationship targets, or malformed object anchors is `REVISE` even if every XML part parses.

For every newly inserted MathType donor object, explicitly verify both relationship and shape identity: the `o:OLEObject` relationship must point to the inserted embedding part, the preview image relationship must point to the inserted media part, and `o:OLEObject/@ShapeID` must match the sibling `v:shape/@id`. If mismatches already exist in the base, record them as inherited for a scoped donor/intermediate candidate; do not add new mismatches. Before promoting a cumulative candidate to the next review gate, either synchronize inherited `ShapeID` mismatches with an XML-only package-coherence repair that preserves OLE/media bytes, or keep the candidate at `REVISE` with the mismatch count and affected objects recorded. Do not let "inherited" mean "acceptable in the current gate" when a reviewer blocks on package identity coherence.

When inserting the same donor MathType object more than once, treat donor XML runs as single-use. Retargeting helpers normally mutate `r:id`, `r:embed`, and shape identifiers in the run being inserted, so each insertion must start from a fresh deep copy of the original donor run. Reusing an already retargeted run can point the next insertion at release-document relationships that do not exist in the donor package, or duplicate shape/relationship identity.

When a defective formula is one row of a shared multi-number display table, replace only that row's formula OLE and its relationships/media. Preserve the sibling rows, sibling equation numbers, and accepted OLE objects in the same table. Do not collapse the shared table into a single object or rebuild neighboring formulas just because the number cell text contains several labels.

When replacing a numbered display with a full source-backed donor, inspect immediately adjacent textless unnumbered tables. A stale unnumbered table with one MathType OLE can render as a duplicate first or last fragment of the same formula after the numbered donor is replaced. If the source PDF has no separate display there and the new donor contains the duplicated fragment, remove only the stale unnumbered table plus its OLE/media relationships, then render the affected page.

Before any bounded or full Word/MathType writer uses a prepared placeholder/source DOCX, run a direct Word-openability probe on that exact DOCX. If Word refuses to open it before any placeholder replacement or `SetMTData` call, classify the lane as `REVISE: source package openability defect`, not as a formula-import or MathType defect. Do not rerun the same writer slice until the package owner is repaired or a Word-openable base is selected. For one-to-few targeted formula fixes, a standalone one-object MathType donor may still be built in a fresh Word document and inserted into the current Word-openable release candidate, with the source-package openability defect recorded separately.

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

### Word COM Render Output Path Discipline

Any call to Word COM `ExportAsFixedFormat` (or equivalent render/export API) **must** specify an explicit, absolute `OutputFileName` argument pointing to a path under `.scratch/<worker_topic>_<date>/`. Never rely on the default path: Word saves the PDF next to the source DOCX when no output path is given, which contaminates the release folder boundary.

Required form:

```python
doc.ExportAsFixedFormat(
    OutputFileName=str(scratch_dir / "chunk_NN_post_<op>_render.pdf"),
    ExportFormat=17,  # wdExportFormatPDF
    ...
)
```

Release folder rule: the repo's accepted release DOCX folder must contain only its canonical release files (the chunk DOCX set and, where the variant produces them, a rendered-PDF subfolder) per the project's own naming convention. Any `.pdf`, `.tmp`, `~$*`, `.bak`, or other non-canonical file produced by a render/export run is a stray and must be moved to the repo's scratch area or deleted. Keep the concrete release-folder path and canonical filename pattern in the repo pipeline/runbook, not in this skill.

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

For very large source-backed display templates such as dense matrices, do not keep retrying a hung MathType `SetMTData` MathML import. First prove the source payload order and dimensions from the current source-map or existing OLE payloads; if a one-object MathML import stalls, record the progress point and process cleanup, then try a compact MathType TeX donor (`SetMTTeXData`) built from the same verified rows/cells before falling back to layout-only strategies. The donor must render as one editable `Equation.DSMT4` object with a continuous delimiter/template, and the target repair must replace only the defective formula object's OLE/media parts while preserving unrelated protected parts byte-identically. Do not accept VML/XML rotation of MathType OLE previews unless the exact donor and target DOCX render proves the formula is visible, scaled, and source-faithful; a rotation property that exports blank or clipped output is a failed lane, not a candidate.

## One-Object MathType Import Smoke Gate

Before using Word/MathType automation to create donor OLE objects for a targeted repair, run or reuse a bounded one-object smoke that imports a simple inline symbol and reaches a saved DOCX/PDF artifact. The smoke must use the same initialization path as the accepted writer: configure MathType/MathPage library discovery, call the MathType API initialization macro such as `IsDLLVersionOK`, record the result, insert a blank MathType object, then call the import macro such as `SetMTData`. A smoke that skips the initialization macro is not valid evidence of a global MathType import failure.

A progress log that records successful API initialization, then stops at `before_set_mathml` and never records an `after_set_mathml` or saved-object event is a MathType import failure, even when the source MathML/TeX is trivial.

Every donor must pass a rendered donor gate before it can be transplanted into a chunk. MathType `SetMTTeXData` may accept a payload but render raw control text such as `\begin{aligned}`, `&`, or `\end{...}` as visible red text. If the donor PDF shows raw TeX/MathML residue, reject that donor and switch to an explicit MathML template, a simpler source-faithful split, or a manual MathType sample. Do not let a clean `Equation.DSMT4` count override the visible donor render.

If a simple inline donor stalls in the same MathType import path:

- stop only the Word/MathType/Python processes owned by that smoke;
- do not rerun the full writer or repeat the same donor-generation path for a larger formula set;
- classify the lane as `REVISE: MathType import environment blocked` unless a visually verified existing editable MathType OLE donor can be reused;
- continue only with source-PDF proofread, XML/layout repairs, or targeted replacement from existing verified donors;
- record the failed import path, last progress event, process cleanup, and chosen fallback in the repair artifact.

A fallback made from styled Word text, split inline runs, or a hybrid of existing OLE plus Word superscript/subscript may be used only as an explicitly recorded temporary candidate when it visually matches the source and no editable one-object donor can currently be generated. Do not call such a fallback final MathType `PASS`.

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

Repo-local repair scripts must accept repo-relative scratch/candidate output paths and resolve them to absolute paths before writing files or formatting `relative_to` reports. A script that writes a valid candidate and then fails only because a relative output path is not under an absolute repository root is a pipeline defect; fix the path handling before handing the script to workers.

If a repository has no runbook, no exemplar, no sample directory, no validation JSON, or no scratch convention, create only the minimum repo-local working area needed for the current task, document the new convention in the repo pipeline, and keep this skill free of those local names.

## Translation Completeness Gate

A translated technical-book chunk cannot pass on formulas, MathType counts, or layout alone. The worker must prove that the visible source text was translated and preserved in source flow.

Before final review, build or inspect a prose ledger for the current chunk:

- title/chapter/article blocks, author/affiliation blocks, headings, contents rows, body paragraphs, lists, footnotes/endnotes, captions, table text, reference headings/items, listing/output captions, and prose around formulas;
- Word-text labels inside formula tables, side-by-side comparison labels, and natural-language connectors or conditions such as `where`, `or`, `for`, `if`, `with`, `respectively`, and their localized equivalents;
- figure legends or data-table labels that are source text rather than image-only graphics.

For each source-visible unit, the candidate must contain a target-language equivalent at the source-equivalent position. Missing prose, untranslated source-language body text, duplicated source plus translation, machine-OCR residue, invented explanatory text, and semantic reversal are all `REVISE`, even when every formula is editable MathType.

Do not mechanically translate mathematical notation, program source code, file names, command lines, numeric output, author names, standard acronyms, or source-language bibliography titles when the repo convention preserves them. Those are exceptions only when the surrounding prose/caption is translated and the QA artifact records why the source-language token remains.

Author names remain as names, but affiliation/organization/location lines in title blocks are ordinary source-visible prose. Translate the role/location words into the target language, preserve official institution/company names when that is the repo convention, and record any intentionally preserved source-language institution name as a translation exception. A chapter title block with translated title and untranslated affiliation prose is `REVISE`.

Translation repair is normally a no-Word XML/source-owner lane: update the generator/source-map/translation block that produced the bad text, not only the final DOCX. Render the affected pages after the repair and compare the source PDF visually. A worker report must explicitly state whether the translation-completeness gate was checked; if it only says formulas were converted or visually repaired, the chunk remains `REVISE`.

Every chunk handoff must include a short translation ledger, even when the assigned repair was formula-heavy. The ledger must name the source pages or rendered source crops checked, list the visible text regions covered, state any intentionally preserved source-language tokens as exceptions, and list remaining unchecked or suspect text regions. A report with no translation ledger is not a complete skill result. Do not infer that text is acceptable from clean formula/OLE counts, page counts, or a formula-only visual review.

If the worker was asked to fix only formulas, it may return `CANDIDATE for formula repair only`, but it must still mark translation/text coverage as unchecked unless it actually performed the ledger pass. Such a candidate cannot be promoted to final chunk `PASS` until a later gate completes the translation ledger and repairs missing, untranslated, OCR-like, duplicated, or semantically reversed prose.

## Accepted Page Style

- Use book-like typography: normal body weight, justified paragraphs, restrained spacing, and source-like heading hierarchy.
- Keep section and subsection headings as standalone Word heading paragraphs. A numbered heading must not be merged with the first body sentence, silently dropped before the first body paragraph, or rendered as an unnumbered body paragraph. Fragile list autonumbering must not hide source numbering such as `3.1.` as a local `1.`. If autonumbering drifts, replace it with source-backed explicit heading text plus the correct Word heading style/outline level, then render-check that the heading is black/source-like and not accidentally inherited as hyperlink-colored or italic text.
- Treat missing source subsection headings as source-flow blockers, even when the surrounding prose reads grammatically. Compare the current candidate against the rendered source page before the first paragraph of a new section; if a heading such as `2.1` is absent, insert it as a standalone Word heading with explicit source numbering and render-check the page.
- Treat a section-introduction paragraph that appears before the preceding source formula block or before its own heading as a source-flow defect, even when extracted PDF text appears to support that order. Render the source spread visually, then order the Word body as source-visible formula/prose/heading flow. If the repair reveals OCR line-wrap paragraph splits in the moved section intro, merge only the affected prose paragraphs and preserve formula tables/OLE binaries.
- Reject OCR/PDF line-break paragraphs that preserve two-column source line wraps as separate Word paragraphs. If a normal prose sentence is split across adjacent body paragraphs without source paragraph intent (for example an adjective/noun split, missing final punctuation, or `following coupled` separated from `homogeneous equations` by a misplaced figure/caption), repair the whole source paragraph or list block in source order. Keep real headings, list items, figures/captions, and display formulas as separate structures, but do not let a figure/caption table interrupt the middle of one grammatical sentence unless the source page visibly does so.
- Preserve source list item count and list boundaries. If the source has several dash/bullet/numbered items, the candidate must not collapse them into one prose paragraph, merge two source items into one list item, or drop a short final item. Repair the whole list block in source order and render-check the transition into the following heading or paragraph.
- Preserve the visible labels of numbered lists, not only the item paragraphs. A list block is defective if a source item such as `2.` renders as an unnumbered body paragraph, restarts at the wrong number, or inherits a hidden/bullet style while neighboring items look correct. Compare source and candidate labels visually, inspect `w:numPr`/style inheritance for the affected paragraphs, and repair the smallest list block that restores the visible source numbering. For a pure list-numbering defect, preserve all formula OLE/media bytes and render-check the affected page before promotion.
- Keep every display formula in a borderless two-column table: MathType OLE formula in the left cell, equation number as ordinary Word text in the right cell.
- Classify a table's role before applying the display-formula two-column rule. Figure/caption groups, data tables, and source tables may legitimately contain inline MathType OLE objects in captions, headers, or cells; they are not defective display-formula tables merely because they contain OLE. Apply the two-column display contract to equation-display tables, not to grouped figures or gridded data/source tables.
- Treat reference/data tables that list formula numbers, shapes, Green functions, parameters, or source equation references as data tables, even when cells contain inline MathType OLE or equation-number text. Do not force such tables into the two-column display-formula contract unless the source PDF actually uses them as displayed equations.
- Preserve mathematical symbols in captions, table headers, section headings, and prose, not just body formulas. If the source says `Z Matrix`, `S-parameters`, field components, or similar symbol-bearing labels, the translated Word text must keep the symbol as editable text or styled inline math. A fragment such as `и -матрицы`, `-матрица`, or `-параметры` is a source-math omission when no immediately adjacent inline math/styled symbol supplies the missing label. If an inline MathType/styled symbol already renders the label, do not add a duplicate text symbol; render-check the spacing, style, punctuation, and run order instead. Repair any case where the rendered label drifts after a comma or prose token (for example, `матрицы, Z соответствующий`) by moving the inline symbol/run to the source-faithful position. Scan for known math-label nouns that begin with a bare hyphen after OCR/translation cleanup and verify each against the source PDF before release.
- Keep source reference/data tables with their captions as readable table blocks. After typography normalization, render-check that a table does not begin at the page bottom and continue with an orphan final row above the next caption or body section. Use `keepNext`, `cantSplit`, or an explicit source-faithful page break to keep the table/caption block readable before promotion.
- Reject source/data tables whose cell text is compressed by exact line spacing, narrow grids, zero margins, or fixed row heights until headers, rules, and body cells are readable in the rendered PDF. A table with `w:lineRule="exact"` and a line value smaller than normal single spacing is a layout defect even when XML rows/columns are correct. Widen the table to the effective page or column width, set stable column widths, use normal single spacing, preserve source-like horizontal rules, and render-check the whole table plus the following paragraph.
- Keep bibliography and references blocks as source-faithful numbered text, not inherited Word bullets or local autonumbering artifacts. Two-column source PDFs often extract references out of order or with missing/misread numbers; verify the rendered source page before repair, then make each visible reference number ordinary Word text or a stable numbered style with the correct source number. Reject `_`, `-`, `•`, restarted list numbers, and merged multi-reference paragraphs when they replace source reference numbers.
- Preserve source bibliography/reference headings as standalone unnumbered Word headings before the first reference item. In translated documents, use the repo's accepted localized heading (for example `Литература`) unless the source-language heading is intentionally preserved. A correct numbered reference list is still `REVISE` if the heading is absent or glued into the first reference item.
- In multi-column layouts, each display-formula table must fit inside the effective text column, not the full page body. The equation-number cell must render inside the same column as the formula and must not overlap the column gutter, body text, or page edge. A full-body-width formula table inside a two-column section is a blocker even when the XML still has two cells and a Word-text equation number.
- Before repairing page-count or page-flow inflation, compare the source PDF page geometry with the current DOCX section geometry: page orientation, page size, margins, and column count/spacing. If the source render is a landscape two-column spread and the DOCX is portrait or single-column, repair `sectPr` first on a scratch candidate and render that exact file before changing formula sizes, figure crops, or writer output. Use an adjacent accepted page setup only as a template after verifying it matches the current source geometry. After page setup changes, re-normalize display-formula and figure/caption tables to the effective column width; old full-body widths can remain in table XML and still cause page-flow defects.
- Keep equation numbers out of MathType. The number cell owns the visible source equation number as ordinary Word text.
- Keep prose labels out of MathType. Region labels, conditions in words, figure labels, and explanations are ordinary Word text. In translated documents, localize those labels as ordinary target-language Word text unless the source intentionally requires an English technical token.
- Moving prose, conditions, or labels out of MathType is not complete if the same text still remains embedded in the MathType object. Adding a corrected Word-text condition beside a stale OLE creates duplicate content and remains `REVISE`; repair the source-map/OLE so the text exists only in the source-faithful Word position.
- When a boundary/domain condition is externalized as a complete Word-text label before or beside a display, reduce the MathType OLE to the math assertion it owns. Do not leave a residual condition fragment inside the OLE such as `|x| < w/2 y = d+t` after adding a Word label `При |x| < w/2 и y = d+t:`; that is duplicate condition content and a source-map/template defect.
- The source-faithful Word position includes whether a condition belongs before or after the display. Do not use a generic "insert before display" or "insert after display" rule for `where`, `if`, region labels, or connector text; inspect the rendered source page and place the text on the same side of the formula, before any following heading or paragraph that the source places later.
- Keep prose connectors and natural-language conditions between equivalent display forms outside MathType and localized as target-language Word text in translated documents. If the source has words such as `or`, `where`, `for`, `if`, `source`, `Green's function`, or localized equivalents between formulas, split the display into separate MathType placeholders and put the connector/condition as Word text in the formula cell; do not bury it inside one opaque MathType OLE. Preserve true mathematical operators and conventional symbols such as `sin`, `cos`, `exp`, `grad`, `curl`, `div`, `TE`, `TM`, and variable names when the source uses them as notation rather than prose.
- If the source shows numbered display rows followed by an unnumbered `where`/`где` definition row, do not attach the next equation number to the definition row. Split the block into source-order rows: each numbered equation gets its own MathType display and right-cell Word number, the connector word stays ordinary localized Word text, and the definition row has an empty number cell. A visually plausible definitions row labelled as `(N)` is a hard source-numbering defect even if the following formula numbers remain sequential.
- For short inline condition sentences, reject padded one-object OLE fragments that create source-language words or spaced punctuation such as `if`, `l = n ,`, or `W_i ,`. Use source-faithful styled Word math for simple relations and symbols (`l = n`, `W_i`, `x_>`, `x_<`) when that preserves typography and keeps punctuation tight; remove the superseded OLE/media relationships and render-check the exact line.
- Do not leave detached one-word or one-letter connector residues before a display formula. If a cleanup or source-map split leaves a fragment such as a lone preposition, conjunction, or translated initial word before the display, reconstruct the full source connector phrase around the formula and render-check the neighboring formula rows. The repair target is a grammatical source-flow sentence, not just removal of the visible residue.
- If a source connector such as `let`, `with`, `where`, `or`, or an equivalent localized word visually belongs between rows of one multi-row display table, keep it as ordinary Word text in the display/formula cell at that source position. Do not move that connector into MathType, drop it into a detached body paragraph, or rebuild unrelated formula OLE objects when an XML-only insertion can preserve the current MathType binaries.
- Case-condition rows are a special high-risk exception. If the rendered source PDF places natural-language condition phrases as rows inside a brace/cases formula, keep those conditions inside the same source-equivalent cases structure or aligned in the same formula cell; do not replace them with a detached summary paragraph above or below the display. In translated documents, localize the condition text. If the condition text stays inside MathType, use a rendered-proven path such as MathML `<mtext>`; reject any donor that mojibakes non-ASCII text or turns the brace into a small typed curly symbol instead of a stretched cases template.
- In composite comparison blocks, preserve source grouping and equation-number ownership from the rendered source page. Side-by-side cases, alternative boundary conditions, and transformation-matrix comparisons may have several nearby formula rows, connectors, and labels; the visible number belongs to the source-aligned row group, not to the nearest previous formula object. If the source number aligns with a following transformation matrix or grouped result, create or move the numbered display table so that the number cell owns that group, leave preceding derivation or solution rows unnumbered, and remove any raster remnants only after editable MathType replacements exist.
- For side-by-side comparison blocks, keep comparison labels as ordinary Word text outside MathType in the same source-flow table cell as the formula column they label. Build each side as its own editable MathType object or source-backed formula stack, separated by a stable Word table column/rule when the source uses a vertical divider; do not flatten both sides into one wide MathType object or into English/source-language labels inside MathType. Apply `keepNext` from each label row/paragraph to the following formula row and `cantSplit` on the comparison rows so a label such as `DN`, `ND`, `DD`, or `NN` cannot orphan at the bottom of a page. Render the exact candidate pages after the keep-together change, because XML table validity does not prove the label/formula block stayed readable.
- Every numbered display visible in the source PDF must exist as its own source-faithful display row in the candidate unless a repo QA artifact records an explicit source ambiguity. A prose reference such as `from (N)` or `where (N)` does not satisfy the display requirement. If a numbered formula is missing from the candidate, insert a MathType display table at the source-flow point and keep the equation number as ordinary Word text.
- A correct MathType OLE in the wrong place does not satisfy the numbered-display gate. When a donor/probe contains the source-faithful formula but it was anchored after a nearby earlier formula, move or transplant only that display row to the source-visible prose/figure position, remove any OCR residue that occupied the slot, and update the source-map/generator anchor so the next writer cannot recreate the wrong order. Render-check that no duplicate copy remains at the old anchor.
- When a formula appears as a stale raster/table near the correct prose anchor, do not delete it as "junk" until source flow proves where the editable MathType/OLE version is. First search the current DOCX for the same equation number and verify whether an existing OLE row is misplaced before or after the anchor. If a correct OLE row exists, move that row to the source-correct position, preserve its OLE/media bytes, then remove only the obsolete raster duplicate. If no correct OLE row exists, the raster is evidence of a missing formula and must be replaced by a source-backed MathType object, not deleted.
- When one display line contains adjacent coordinate relations, alternatives, or side-by-side equalities, preserve the visible separator between them. A formula that renders `...x\cos\theta v=...` or otherwise joins the last symbol of the first equality to the first variable of the second equality is `REVISE` even when it is a valid editable MathType object.
- Removing source-language prose from a MathType object is a move operation, not deletion. Reinsert the source-equivalent localized word or phrase as ordinary Word text in the same formula-flow position, then render-check the whole line. A formula or prose sentence that is mathematically plausible but lost a source word such as `requiring`, `where`, `for`, `or`, `if`, `respectively`, `source`, or `function` remains `REVISE`.
- For aligned boundary-condition or comparison blocks, a condition such as `for all x` / `for all i` is not the same as the trailing variable `x` / `i`. If a text-payload cleanup strips the words and leaves only the variable inside MathType, the formula is still defective. Split the affected block into math-only MathType objects and place the localized condition as ordinary Word text in the same visible row/column of the formula cell, or use another rendered-proven Word-text structure that preserves the source alignment. Do not delete detached condition paragraphs until the rendered candidate proves the condition has been reattached at the source-equivalent row.
- Remove stray inline/OLE residue only after source comparison proves it is not part of the source sentence. Typical residue is a dangling word plus partial formula fragment between a display formula and the next figure, caption, or paragraph while the correct prose appears elsewhere. Delete the residue and any now-unused OLE/media parts from the scratch candidate, then render-check the neighboring display, figure, and prose.
- Treat natural-language integral limits such as `ith element`, `on S`, or `at nodes` as high-risk. Prefer a source-defined symbolic domain (`s \in S`, `S_i`, `\Gamma_i`, etc.) when it preserves the source meaning. If no source-defined symbol exists and the text is genuinely part of the integral limit, it may remain inside the MathType template only as localized target-language text, with the exception recorded in QA; never leave the source-language prose label inside the OLE of a translated document.
- When localized non-ASCII text must remain inside a MathType template, do not rely on TeX import until a rendered donor proves it. Prefer MathML with explicit `<mtext>` inserted through MathType's MathML import path, or a manually verified one-object MathType sample. Always render the donor and final candidate and scan for mojibake, replacement glyphs, or clipped text. If localized text cannot be imported stably, use a source-backed symbolic condition instead and record the substitution in QA.
- Keep figures and captions together in one grouped Word structure, usually a table, so they do not drift apart.
- Distinguish true figure captions from prose figure references before blocking or repairing. A body sentence such as `Рис. N показывает...`, `Рис. N дает...`, or `Рис. N представляет...` is usually a prose reference and may remain ordinary body text when the source uses it that way. A caption-like paragraph such as `Рис. N. ...` or `Fig. N ...` must either live inside the grouped figure/caption structure or be repaired.
- Prose figure references must also keep body typography. If the source sentence before a figure is ordinary body prose, do not inherit italic/caption styling just because it begins with `Рис. N` or `Figure N`. Repair only the affected run/paragraph style, preserve nearby inline math, and render-check that the sentence no longer looks like a loose caption.
- When merging split figure captions inside a grouped table, preserve Word-openable table structure: remove the entire now-empty caption row or leave a valid empty paragraph in every table cell. Never delete the only paragraph from a cell and leave `<w:tc>` with no terminal block content; ZIP/XML parse success is not enough, Word may reject the file as corrupted.
- After replacing or re-cropping a figure image, scan the adjacent body paragraphs on the rendered candidate against the source page. Axis labels, graph legends, running headers, copyright fragments, or OCR leftovers can leak into prose near the figure; removing the crop defect is incomplete if surrounding prose still contains the leaked label or dropped source sentences.
- Treat a caption-like paragraph with no grouped nearby figure image as a hard missing-media blocker, not as a harmless loose-caption warning. Verify against the source PDF render: if the source page has a figure and the candidate has only the caption or OCR residue from labels, restore the figure from a source-backed media artifact or crop, group it with the caption, remove the OCR residue from body text, then render-check page flow.
- A caption-only repair is not complete merely because the caption text is translated. The actual source-visible figure must be present in the rendered candidate, and the restored bitmap crop must exclude source-language captions, running headers, page numbers, and unrelated page furniture when those are represented as editable Word text elsewhere.
- A source-backed figure crop must contain the figure content, not surrounding page furniture. Running headers, page numbers, appendix/chapter headers, neighboring body text, and unrelated formula fragments visible inside the figure image are crop defects even when the figure/caption are grouped. Repair the media crop or clean only the page-furniture region while preserving canvas/layout when possible, then render-check the affected page.
- When a loose caption is near formula-order anomalies, treat it as a possible source-flow defect before applying a local caption fix. The correct repair may be to restore a missing source figure from a crop, group it with the caption, and move the formula tables back to their source-flow position rather than merely deleting or wrapping the caption.
- A grouped figure can still be a page-flow blocker if its image is so large that it forces the previous page to render mostly blank or pushes the next section before/after the wrong caption. Compare the source spread, move the grouped figure to the source-faithful flow position, and scale the source-backed image with preserved aspect ratio until the figure, caption, and surrounding prose render as a readable book page. Do not ungroup the caption or crop away source content to solve the page break.
- Treat captions glued to short OCR/axis/header residue as the same hard figure/caption defect, even when the paragraph does not start with `Рис.` / `Fig.`. Patterns such as `-20 Рис. N...`, `ЧАСТОТА (ГГц) Рис. N...`, source running headers, graph-axis labels, or legend fragments before the caption mean the source image/text extraction leaked into body flow. Remove or relocate the residue, restore/group the actual source-backed figure if missing, and keep the caption as clean editable Word text.
- Reject source-caption legend text that remains as a raster strip after a translated editable caption. If an imported figure image includes the source PDF's caption tail or legend line below the graph while the DOCX also has a translated caption, crop/remove the raster strip and translate the legend into the editable Word caption. Keep true in-figure axis labels/curve labels inside the image unless the repo has an explicit editable-redraw requirement.
- In multi-column layouts, figure/caption groups must also fit inside the effective text column. The grouping table and caption cell must not use full-body width inside a two-column section; otherwise captions can clip at the page edge or overlap the next column even though the figure and caption are technically grouped.
- Keep program listings, pseudocode, and printed console/output examples as source-faithful monospaced blocks. Preserve line breaks, indentation, column alignment, and blank lines; do not flatten them into justified prose. If OCR/text extraction is unreliable and no verified editable source exists, a source-PDF crop is allowed only as an explicitly recorded listing/output image exception with crop evidence, rendered visual comparison, and no claim that the block is editable text.
- A listing that preserves line breaks can still fail the layout gate if it renders as tiny, faint, or mostly unused-page whitespace. For editable listing/output blocks, verify the final PDF visually: use a dark monospaced font, enough point size and exact line height for human reading, and table/column widths that keep the source-like columns legible without excessive wrapping. Do not accept 6pt-style `SourceCode` blocks or low-contrast OCR-like code merely because the text is technically present; repair listing style/spacing/table geometry and render-check the affected listing pages. Do not rebuild MathType formulas for listing readability defects.
- Remove source page furniture from editable listings and output blocks. Running heads, page numbers, appendix/chapter headers, and source spread titles are not listing statements; if they appear inside the code/output flow, delete or move them to a true page-header/footer structure before acceptance. Render and grep the exact candidate for repeated source headers after the repair.
- Use editable MathType OLE (`Equation.DSMT4`) as the final formula format. OMML, LaTeX, images, and scratch DOCX files are auxiliary unless the user explicitly changes the target format.
- When transplanting donor MathType OLE runs into several target positions, create a fresh retargeted OLE run for every visible occurrence. In lxml/OpenXML editing, appending the same run element twice moves it from the first position to the last one, which silently drops earlier inline math. Blind deep-copying an already-retargeted OLE run can leave duplicate VML shape ids or reused relationships. Correct repair code must either call the repository's retarget/import helper per occurrence or provide distinct donor objects per occurrence, then verify `o:OLEObject/@r:id` uniqueness and that any duplicate `v:shape/@id` values are pre-existing from the base, not newly introduced.
- When replacing an existing MathType OLE in a targeted OpenXML patch, delete or skip the old embedding/media parts and their document relationships unless the same relationship is still referenced elsewhere. Otherwise the package accumulates stale `oleObject*.bin` and WMF parts that no longer correspond to visible formulas. Verify live `Equation.DSMT4` references, OLE relationship ids that are actually used in `word/document.xml`, embedding part counts, missing relationship targets, and any removed parts in the repair artifact. A relationship target that exists in the ZIP is not enough evidence; if its `rId` is absent from `document.xml`, the relationship and part are stale. Count every Office relationship attribute on visible document elements, including `r:id`, `r:embed`, `r:link`, and legacy `o:relid`; a regex that checks only `r:id` can misclassify live preview images or miss the real orphan.
- Before replacing a display MathType OLE, inventory the full visible content owned by that old OLE against the source PDF and the adjacent rendered rows. A stale object can contain several source rows even when only one row is visibly wrong. If the old object contains a keeper row before or after the defective fragment, the donor must preserve or recreate that keeper row in the same source order; never replace a multi-row object with a partial donor that fixes one line and silently drops neighboring equations. After replacement, render-check at least the row before the target, the target rows, and the row after the target.
- For matrix, determinant, and operator-table displays, proofread every source-visible corner and boundary entry, not only the row or column that triggered the repair. Sign-only differences such as a bottom-right `-1` rendered as `1`, missing zero entries, swapped edge factors, or short determinant bars are mathematical blockers even when the OLE count, table layout, and equation number are correct. Record the exact source page/crop used for the corner-sign check before promotion.
- Formula tables and multi-row formula blocks must not split across a page in a way that separates the formula, its number, or its required explanatory prose from the source-flow block. For XML-only repairs, use row keep-together such as `cantSplit`, remove artificial blank paragraphs, or merge OCR-fractured prose paragraphs where the source has one paragraph. Do not use keep-together settings to hide a source-order error; first verify the rendered source order, then keep the repaired block readable.
- Do not use the MathType macro return value as the only import verdict. `SetMTTeXData` may return `None` while still populating a valid `Equation.DSMT4` object. Treat explicit `False`, no saved DOCX/PDF, an unchanged/empty shape, visible raw TeX, or a source-mismatched render as failure; treat `None` as `requires rendered donor proof`, not as automatic failure or success.
- Multi-line TeX `array` donors are high risk. If a `SetMTTeXData` donor renders visible raw commands such as `\begin{array}` / `\end{array}`, red TeX fragments, or literal alignment syntax, reject that route even when an OLE object was created. Rebuild the object through a rendered-proven MathML import path such as converter-produced MathML plus `SetMTData`, or copy a manually verified MathType sample, and record the rejected donor path in QA.
- For `SetMTTeXData` array/cases donors, do not use optional row-spacing syntax such as `\\[5pt]` unless that exact donor render proves MathType consumed it. Some MathType TeX imports render the bracketed spacing token as visible `[5pt]` text; use plain row breaks or a native/manual MathType sample instead, then render-check for raw spacing tokens before transplant.
- Do not assume MathType TeX import supports every accent command. If a command such as `\widetilde` renders as red raw TeX, rebuild that object through MathML import, a verified MathType accent-template donor, or a simpler source-faithful accent command that renders correctly. Always render the exact candidate and scan for visible raw TeX strings after any accent/template change.
- Check inline math in ordinary paragraphs: indexed symbols, Greek letters, primes, bars, bold/vector style, italic/upright style, operators, punctuation, and references to equations must match the source PDF.
- For composite inline MathType objects, source-check the entire expression, not just the surrounding punctuation or the first visible token. A single inline OLE may have stale subscript and superscript content even when its placement is correct. Compare function names, all primary and secondary indices, exponents, Greek/Latin lookalikes, parentheses, and scalar factors against the rendered source crop before accepting the line; if any part is wrong, build a rendered one-object donor and replace only that inline OLE/media pair.
- If one inline expression is repaired in a caption or body sentence, search the current rendered chunk and DOCX XML for the same visible expression class in captions, body prose, figure legends, and list items. A verified donor for one occurrence does not prove sibling occurrences are fixed; source-check and replace each stale OLE/media pair independently while preserving unrelated objects.
- Treat transliterated Greek/math names left as ordinary prose (`phi = alpha`, `theta_1`, `rho=a`, `Delta_i`, and similar) as inline-math defects in translated technical text. Repair them as editable inline MathType when the expression is nontrivial; for simple one-line symbols or equalities, styled Unicode Word text is acceptable only when it visually matches the source and remains stable after render. Do not leave Latin transliterations as body prose when the source uses Greek mathematical symbols.
- Treat literal source-map/script syntax in prose (`k_{mn}`, `J_n`, `j'_{mn}`, `theta_1`, `x_i`, and similar underscore/braced forms) as an inline-math defect. It must render as real subscripted math, either inline MathType or styled Word runs with proper subscript and italic conventions for simple symbols.
- Treat OCR-like symbol substitutions in prose as semantic inline-math defects, especially when Greek or indexed source symbols turn into ordinary words or lists (`β` becomes `b`, `ρ = a` becomes `p =a`, `c_1 and d_1` becomes `b, c, and d`, `ω` disappears after `frequency`, and similar). Digit/letter ambiguity such as a source indexed symbol becoming plain `7`, `1`, `I`, `l`, or punctuation-adjacent text is the same blocker; verify the source glyph visually and rebuild the inline run as styled math or inline MathType with the correct subscript/accent. If PDF text extraction itself reports the same Latin-looking residue, do not accept that as source proof; render/crop the source page and use the visible glyph as authority. Source-check the surrounding sentence, not just the visible symbol, because these defects often also move the period before a MathType OLE or truncate the phrase after an inline object.
- Treat OCR-like Latin lookalike swaps inside indexed inline lists as semantic defects, not typography nits. A source list such as `v_1, v_2 and Z_1, Z_2` must not render as plain `u1, u2 and Z1, Z2`, and a source `y_0` must not collapse to a bare `y` beside a correct `z_0`. Verify each base letter and numeric index against the rendered source, then rebuild the whole list as inline MathType or stable styled Word math with italic variables, true subscript/superscript runs, and ordinary Word punctuation/conjunctions.
- Treat a plain single Greek/Latin symbol as defective when the source shows the same base with a subscript, superscript, prime, hat, bar, vector mark, or grouped index. Do not accept the bare base symbol merely because the sentence remains grammatical; rebuild the full source-visible inline object as MathType or source-faithful styled Word math, then render-check the line.
- When repairing mixed prose/math inline paragraphs with styled Word runs, never clone the run properties from a math run onto surrounding prose. Build prose runs with neutral body formatting, then apply italic, bold/upright, subscript, superscript, prime, bar, hat, or Greek styling only to the mathematical symbol runs. Render-check the paragraph for italic/bold bleed because XML text extraction can miss this visual defect.
- When creating styled Word math from a former MathType/OLE preview run, strip inherited baseline and scaling properties such as `w:position`, character spacing, and other preview-specific offsets unless the source explicitly requires that offset. A non-empty styled math text run with inherited `w:position` can make commas and periods look like raised apostrophes even when XML text order is correct; audit for non-empty positioned text runs after compact-run repairs.
- Exclude source-faithful monospaced code/listing blocks from prose inline-math scanners. Identifiers such as `Omega`, `Beta`, `Homo`, `sigma1`, or `theta2` inside Fortran/BASIC/Pascal listings are code tokens, not MathType defects, as long as the listing itself preserves source line breaks, indentation, columns, and provenance/layout requirements. The same tokens in translated prose remain inline-math defects and must be checked against the source PDF.
- Keep punctuation around inline MathType objects as Word text on the source-correct side of the object. If an inline expression completes a phrase or sentence, the comma/period belongs after that inline object, not before it; verify the rendered line because text extraction can hide this defect.
- Apply the same inline punctuation and content checks in figure captions, table captions, headers, and other non-body paragraphs that contain inline MathType objects. A caption can have correct OLE objects but wrong separators around them, such as a period where the source has a semicolon or a sentence-ending period before the final inline interval object. Repair the caption text runs and preserve the OLE/media bytes when the objects themselves are correct.
- Figure/table captions with parameter lists must be source-checked symbol by symbol, including Greek letters, subscripts, primes, hats/bars, and the base symbol before each equals sign. Reject missing-symbol captions like `=, = 2.3`, OCR-substituted labels such as `L,=10`, or a repeated nearby parameter such as `a = 10d` when the source has a distinct symbol such as `d_l = 10d`. Use inline MathType or source-faithful styled Word math for short caption symbols, keep punctuation and separators as Word text, and render-check the whole caption after repair.
- For prose labels that introduce an inline expression, such as `where`, `где`, `if`, or localized equivalents, do not leave the sentence punctuation before the inline object. Reject `где. <B_{mn}=...>` when the source means `где <B_{mn}=...>.`; inspect the Word run order around the inline OLE, not only extracted text.
- When a source sentence wraps or is split across Word paragraphs around inline MathType objects, punctuation still belongs to the mathematical object it follows in the source. Do not move commas or periods to the previous prose run just because the next inline object starts a new paragraph; render-check sentence fragments that begin or end with OLE.
- If a source sentence is fractured into several Word paragraphs around short inline MathType objects and the rendered prose becomes ungrammatical or semantically incomplete, repair the whole source sentence, not just the visible punctuation. Rejoin the prose in source order, keep mathematical symbols at the exact source positions, and use styled Word math for short indexed/accented symbols when OLE padding caused the fracture. For XML-only DOCX repairs, preserve the original package namespace and markup-compatibility declarations; avoid whole-document `ElementTree` serialization that rewrites prefixes and can make Word reject an otherwise ZIP-valid candidate.
- When a prose paragraph introduces a display formula and the source has a closing parenthetical or phrase such as `may be written as`, verify that the translated prose still contains that connector before the display. A formula that appears after a dangling phrase like `за исключением` is a source-prose defect, even if the following display formula is correct. Likewise, do not leave a short inline expression stranded after a period when the source says `of <math>.`; put the expression inside the noun phrase and keep the period tight.
- In Russian technical prose, do not leave a comma between a preposition and the inline mathematical condition it governs. A run sequence such as `при,` + inline object + prose is a punctuation/order defect; it should render as `при <math>, ...` unless the source explicitly says otherwise.
- The same punctuation rule applies to inline variable/list introductions. Do not render `функция, <math>`, `z =, <math>`, or `с вычетами, <math>` when the source means `функция <math>`, `z = <math>`, or `с вычетами <math>`; place commas between list elements and after the final inline item when required by the source sentence.
- For inline boundary or parameter conditions split by MathType objects, verify the whole condition visually, not just each object. Reject rendered text such as `phi =, phi0` when the source says `phi = phi0`, and reject literal machine-translated condition labels such as `(для) m = 0` when the target prose requires localized ordinary text like `при m = 0`. If the MathType objects themselves are correct, repair only the surrounding Word text/run order and render-check the affected line.
- For inline definition sentences that mix prose, existing MathType objects, and styled Word math, verify the sentence as one source unit. Do not only remove the plain math marker: fix adjacent punctuation, conjunctions, missing variables/operators, and attachment to the next existing inline object so the rendered sentence still reads like the source definition.
- When `pdftotext` collapses a mixed prose/math sentence into patterns such as `и,, где` because inline OLE objects are omitted, inspect the actual run order. The first comma may belong between two inline expressions and the second comma may belong after the final expression before `где`; do not leave a comma after a conjunction like `и, <math>` when the source says `and <math>, <math>, where ...`.
- When two inline MathType objects are adjacent in one sentence, the source operator or punctuation between them must be explicit Word text or its own MathType object. A blank text run between adjacent inline OLE objects is a blocker if the source has a dot product, cross product, comma, semicolon, relation, or other separator; render-check the whole sentence because text extraction often collapses the missing operator into ordinary spacing.
- When a source sentence lists several inline symbols, source-check every index and separator in the list. A rendered list such as `<J_z(x)> <J_x(x)>` or `<E_z(x,d+t)> <E_x(x,d+t)>` is defective if the source has `J_{zk}(x), J_{xl}(x)` or `E_{z1}(x,d+t), E_{x1}(x,d+t)`: missing list commas/conjunctions and dropped secondary subscripts are semantic inline-math defects, not just spacing defects. Repair the whole list in source order, keep separators as Word text, and do not preserve a padded OLE if it visually omits the source index.
- For coordinate tuples or interval/list pairs built from multiple inline MathType objects, keep tuple punctuation in source order as Word text between and after the objects. Reject renders such as `(<x_i>), <y_i>.`, `(<x_i>,)<y_i>.`, or `[...,]<value>` when the source means `(<x_i>, <y_i>)` or `[<a>, <b>]`; `pdftotext` may show only `(,).`, so inspect the run/OLE order and the rendered line.
- For paired change-of-variable clauses or side-by-side inline relations in prose, verify both sides together. A sentence that renders only `x - x' = u` and drops `y - y' = v`, or separates the second relation from its variable, is an inline/prose defect even if the remaining OLE is editable. Repair the whole sentence with source-faithful styled math or targeted inline MathType, remove only the stale OLE/media pair that contained the wrong relation, and preserve unrelated inline objects by evidence rather than by ordinal alone.
- For paired delimiters that enclose multiple inline MathType objects, such as angle-bracket inner products, tuple brackets, norms, or interval bounds, the opening delimiter belongs before the first inline object, separators belong between objects, and the closing delimiter belongs after the final inline object. Reject renders such as `⟨<x>,⟩ <y>` or `⟨<R>,⟩ <R>` when the source means `⟨<x>, <y>⟩` or `⟨<R>, <R>⟩`. Repair the surrounding Word text/run order first and leave the existing inline OLE binaries untouched when the objects themselves are correct; then render-check the affected line against the source PDF.
- For simple symbolic prose compounds such as `Z-matrix` translated as `Z-матрица`, do not allow MathType OLE padding to create `Z -матрица`. If the source uses a single-letter symbolic prefix joined by a hyphen, a styled Word math run for the single letter plus ordinary hyphen text is acceptable and often preferable to a standalone inline OLE. Verify the rendered PDF text and the visual spacing; the result must read as one compound token.
- For standalone one-symbol Greek or Latin variables in prose, styled Word math is acceptable when an inline MathType OLE creates visible padding before punctuation, for example `β .` instead of `β.`. Preserve true MathType for nontrivial inline formulas, but do not keep a padded OLE for a single variable when it damages punctuation or reading flow.
- The same compact-run rule applies to simple subscripted port labels used as prose compounds, such as `p_a-порт`, `p_b-порт`, or short `q_1`/`r_1` references in a sentence. Plain `pa-порт`, `pb-порт`, `q1`, `r1`, and similar flattened labels remain defective even when PDF text extraction cannot distinguish the styled subscript. If inline OLE padding breaks punctuation, hyphens, or commas, use styled Word math runs with proper italic/subscript formatting and remove the old OLE relationships/parts. This is allowed for simple prose symbols only; nontrivial inline formulas still need editable MathType OLE unless a scoped QA artifact records a rendered styled-text exception.
- The compact-run exception may also apply to short function-like inline notation with only a symbol, simple subscript/superscript, parentheses, and scalar arguments, for example a generic pattern like `f_i(x,y)`. Use it only when the rendered MathType OLE visibly creates bad punctuation spacing such as `formula ,` and the styled Word result is visually source-faithful. Style variables italic, keep punctuation/parentheses ordinary, apply true Word subscript/superscript, remove only the superseded inline OLE/media pair, and record the exception in the repair artifact. Longer expressions, fractions, sums, integrals, accents, vectors, relations, or anything needing MathType templates remain MathType OLE.
- Short inline conditions, parameter assignments, or simple reciprocal definitions used as prose qualifiers, such as generic patterns `x = a`, `\phi = 0`, `\rho = b`, or `B_{mn} = 1/A_{mn}`, may use styled Word math when they are immediately followed by a comma, period, closing parenthesis, or hyphenated prose and the MathType OLE creates a visible punctuation gap. Keep the relation compact: italic variables and Greek symbols, true Word subscript/superscript, ordinary relation/operator and punctuation runs, preserved spaces around source-visible operators, and no extra space before the punctuation. When replacing a padded inline OLE after prose such as `при` or `с углом`, do not rely on a trailing space in the previous Word run; put the needed leading space in the first styled math run with preserved whitespace, then render-check for collapsed text such as `приρ` or `угломα`. Do not apply this exception to display equations, multi-term relations, fractions, or source-critical formula objects unless a source-checked repair artifact justifies it. A very short linear prose relation such as a generic `a+b+c=0` may be a justified exception only when the rendered MathType OLE visibly leaves a bad gap before punctuation and the styled Word result is source-checked.
- Short coefficient or variable lists in prose, such as generic patterns `A^e, A^h, ..., D^h`, may use styled Word math runs for each simple symbol when separate MathType OLE objects create visible spaces before commas, ellipses, or sentence text. Keep list punctuation as ordinary Word text in source order: comma and following space after each list item, comma before and after ellipsis when the source has it, and a normal prose space after the final item. Do not let removal of OLE padding collapse text into `Ae,Ah` or `Dhtext`; verify both the rendered line and the package text markers after repair.
- Short hatted or indexed prose symbols in lists, such as generic patterns `\hat{P}_{x}, \hat{P}_{z}` or `T,`, may use styled Word math runs when the existing inline MathType OLE visibly leaves a gap before a comma or period. Preserve the mathematical styling: italic base, true Word subscript/superscript, hat/prime/bar mark on the base only, and ordinary Word punctuation after the styled run. Do not use this exception for display formulas, long relations, or symbols whose source requires a MathType accent template for visual fidelity; if the styled hat/bar cannot match the source, build or reuse a compact inline MathType donor instead.
- Treat plain OCR-looking symbol text such as `W`, `W.`, `W!`, `Jz`, `Zij`, or similar punctuation-substituted or de-indexed math in prose as a hard inline-math defect when the source shows primes, subscripts, tildes, hats, or indexed variables. Verify the source glyph visually, then replace the plain text with inline MathType or styled Word math runs with true prime/superscript/subscript styling. Do not assume punctuation marks are literal, and do not accept a bare base symbol, when the source symbol next to explanatory prose is indexed or accented.
- Apply the same inline-source check to explanatory prose around figures and display formulas, not only to formula-heavy paragraphs. Source-visible compact symbols such as generic `x_e, y_e`, `S_i`, `b_i`, or `G_v^*` are defects if the candidate shows stale indexed objects, bare bases, OCR text, or wrong punctuation such as `b.` / `b,` / `Gj`. For simple symbol clusters, styled Word math is acceptable when visually source-faithful and tighter than a padded OLE; if replacing a stale inline OLE, remove its superseded embedding/media relationships and record the removed parts.
- If a short inline symbol immediately after a display formula renders as an oversized blank/ruled OLE preview, or makes the next prose line look underlined or separated from the sentence, treat it as an inline-math defect. For a simple source-visible symbol with scripts, such as a generic `\psi_n` prose reference, styled Word math is acceptable when it visually matches the source and is tighter than the OLE; remove the stale inline embedding/media pair and render-check the whole sentence.

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

When auditing DOCX styles, resolve effective paragraph formatting through the Word style hierarchy before declaring a body-style defect. Absence of a direct `w:jc` on a paragraph is not a blocker if the paragraph style inherits the accepted justification, font, spacing, or indentation from `Normal`/body styles and the rendered page matches the exemplar/source. A style audit should hard-block only on effective formatting drift or rendered visual drift, not on missing direct XML attributes that Word intentionally inherits.

### Page And Text

- Use the repo's existing page size, margins, headers/footers, page-number style, and section setup unless the source PDF forces a change.
- When the repo or user requires A4 release documents, verify both surfaces after the latest edit: every DOCX section `w:pgSz` must be A4 portrait or landscape, and every exported release PDF must report A4 page size (`595.44 x 841.68 pts` or swapped) through a direct PDF metadata probe. Near-A4, Letter, or custom landscape sizes are layout defects even when the pages look visually similar. Repair page size on a scratch DOCX first, render that exact candidate, visually check for obvious clipping/page-flow regressions, then promote both DOCX and PDF together.
- After any page-size repair, inspect the first and last rendered pages plus any pages whose content count changed. A mostly blank orphan page with a single formula, figure, caption, or paragraph is a page-flow regression; fix the section/table/paragraph layout on the A4 candidate rather than reverting to a non-A4 page size.
- Use a single book-style serif body font family and consistent body size derived from the exemplar or source PDF.
- Keep body paragraphs justified, readable, and not bold by default.
- Use source-like first-line indents, paragraph spacing, line spacing, and heading hierarchy.
- Do not create oversized headings, poster-like body text, decorative boxes, marketing layouts, or card-style sections.
- Keep section titles, figure captions, source notes, and contents entries as Word text with styles, not images.
- Preserve source chapter/article title blocks as complete semantic blocks: chapter number or article number, translated title, author names, affiliations, and the first body/section heading must appear in the same source order. Affiliation lines without the preceding author names are a hard source-flow defect. Do not silently drop a source-visible chapter number such as `5` or collapse authors into invisible metadata; render them as styled Word text, then compare the current page visually with the source PDF opening page.
- Major source-section starts are page-flow anchors. If the source begins a new chapter/article/major section on a fresh page, the translated DOCX must not leave that heading orphaned at the bottom of a preceding reference or bibliography page. Use a heading `pageBreakBefore` or an explicit source-faithful page break on the heading paragraph when needed, then render-check that the heading, author/title block, and first subsection flow match the source.
- Normalize accidental extra spaces, duplicated tabs, empty paragraphs, and manual line breaks that create uneven rivers or broken justification.
- Preserve source meaning and technical terminology; fix grammar and punctuation while checking against the original page.
- Do not preserve broken OCR/translation compounds such as `ближнеи дальнеполевые` when the source has paired adjectives like `near- and far-field`. Use a natural target-language phrase that preserves the meaning and renders cleanly under justified text, for example `ближнеполевые и дальнеполевые аппроксимации`; render-check the line for exaggerated spacing or malformed hyphenation.
- Treat suspicious transliterations of domain terms as translation defects, not harmless style choices. If the source uses terms such as `finlines`, `CPW`, `CPS`, `stripline`, or other microwave-structure labels, verify the source context and use a consistent Russian technical term or glossary form. Do not leave ad hoc renderings such as `финлайн`, `финлайны`, or `финлинии` in body text when a verified descriptive term is needed; scan the whole chunk for repeated forms and repair all occurrences in the same source-backed pass.

### Typography Normalization Against Exemplar (LOAD-BEARING)

Stale OMML→DOCX pipeline produces non-book defaults. Every chunk's `word/styles.xml` must be reconciled against the accepted exemplar's `word/styles.xml`, not left at the pipeline output. Confirmed defect pattern observed in a recent Russian-language technical-book DOCX translation before normalization (concrete sizes are an illustrative example, not a hardcoded target):

- Body Normal style: `Arial 10.5pt` (sz=21 half-points) instead of exemplar's `Times New Roman 11pt` default
- Title 18pt, Heading1 15.5pt, Heading2 13pt, Subtitle 14pt — all oversized relative to exemplar's Title 16pt / Heading1 14pt / Heading2 12pt / Heading3 11.5pt / Subtitle 12pt (sz is in half-points)
- Caption, TOC, FootnoteText, etc. all carried pipeline defaults rather than book typography

Procedure for typography normalization:

1. Extract exemplar `word/styles.xml`. Record full block of Normal style plus each Heading1..5, Title, Subtitle, Caption, TOC1..9, FootnoteText, Hyperlink, etc.
2. For every other chunk in release:
   - Read its `word/styles.xml`
   - Identify chunk-specific style IDs (pandoc styles like `FirstParagraph`, `Compact`, `Bibliography`, `BlockText`, `SourceCode` and its token children `KeywordTok` / `DataTypeTok` / etc., `CaptionChar`, `Figure`, `CaptionedFigure`, `VerbatimChar`, `Table`, `Author`, `Date`, `AbstractTitle`, `Abstract`, `TableCaption`, `ImageCaption`, `SectionNumber`, `FootnoteReference`, `FootnoteBlockText`, `DefinitionTerm`, `Definition`) — these are referenced by `<w:pStyle>` / `<w:rStyle>` in the chunk's `word/document.xml` and must stay
   - Replace styles.xml with exemplar styles.xml plus appended chunk-specific style blocks (merge, not wholesale replace)
3. Verify OLE/media byte-identity per chunk before/after via SHA-256
4. Render at least one representative chunk and confirm headings/body match exemplar visually
   - After adding a first-line body indent through `Normal`, recheck display-formula number cells. Right cells that inherit the body first-line indent can wrap `(166)` into `(16` / `6)` even though the XML text is still one token. Set number-cell paragraphs to `firstLine=0`, right-align them, and use a non-wrapping number cell before accepting the style pass.
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
   - Acronym preservation is two-tier; keep the concrete project allowlists in the repo pipeline/runbook, not in this skill:
     - **Tier 1 (canonical project acronym allowlist)**: a repo-supplied explicit allowlist of the source book's domain acronyms (an RF/microwave example list is `TLM, TE, TM, FEM, FDTD, MoM, CAD, MMIC, OMML, MathML, TEM, EM, SWG, SDM`). Mixed-case names like `MoM` and `MathML` retain their original casing when surrounded by non-letter characters.
     - **Tier 2 (heuristic preservation)**: any 2-4 char all-Latin upper token surrounded by non-letter characters is preserved uppercase. Example heuristic matches in microwave/EM literature: `LSM, LSE, DD, NN, PEC, PMC` and similar method/region abbreviations; `MoL` when surrounding context confirms it. The heuristic is intentional so a project may introduce new acronyms (mode names, boundary-condition labels) without an explicit allowlist update.
   - **Proper nouns**: capitalized via a repo-supplied surname-stem allowlist (an example Russian list is `Зоммерфельд, Пойнтинг, Грин, Гюйгенс, Рэлей, Ритц, Бессел, Фурье, Максвелл, Гаусс, Лаплас`) — stem first letter capitalized, inflected endings stay lowercase.
4. Apply transformation by editing the affected `<w:t>` elements; multi-run headings (text split across `<w:r>` elements) require careful merge / redistribute
5. Preserve text run styling (`<w:b/>`, `<w:i/>`, color) — only change text content, not run properties
6. Verify all OLE/media byte-identical after edit

Caveat: chapter-title chapter prefixes (`Глава 9. Метод обобщенной матрицы рассеяния`) and similar conventional patterns also need sentence-case body even if the number prefix carries chapter signal.

### Listing Provenance Pointer (Class N)

Program listings printed inside a translated technical-book chunk are OCR-cleaned samples from the source book; the verified, compilation-tested source typically lives separately in the project's verified-source root (commonly under a path such as `code/chapter_NN_*/restored/`, but the project's own convention controls). A chunk that prints or narratively references a program without a provenance pointer is a defect — a future reader cannot reproduce the run or distinguish the printed code from a cross-validated translation. This skill owns the "program listing" provenance requirement: verified executable source + input artifact + output file with a representative numeric fingerprint.

For a final book-body DOCX/PDF, provenance must not be inserted as visible body text unless the source PDF itself contains it or the user explicitly requests a reviewer edition. Visible process/provenance/debug strings such as `Verified source:`, `OCR_UNCERTAIN`, `OCR_WARNINGS`, `Source book page`, `Replaces scanned PNG`, `listing_ocr_cleaned`, repo `code/...` paths, `Class N`, `Примечание к листингу`, or `Рабочая реконструкция...` are publication-token leaks and are hard blockers (Class V). Store the provenance triad in the chunk QA/review artifact, manifest, hidden/comment metadata if the repo has an accepted mechanism, or a clearly separate non-release appendix; do not let it print in the translated book flow.

Do not append agent/report glossary sections such as `Terms and Abbreviations`, `Термины и сокращения`, or lists explaining `DOCX`, `PDF`, `OLE`, `MathType`, `QA`, `SHA-256`, or local source filenames to the final translated book-body DOCX/PDF unless the source PDF itself has that glossary. The AGENTS documentation-glossary rule applies to QA artifacts, session logs, runbooks, and review documents; it must not leak into the book translation. If such a generated glossary is visible in a release DOCX/PDF, remove the whole source-absent glossary range and keep any needed abbreviations in the QA sidecar artifact.

The chapter-to-verified-code map is project-specific (e.g. one RF-engineering book mapped several chapters to specific Fortran and Pascal restorations under `code/chapter_NN_*/restored/`, with cross-language cross-validation for the chapter that had both Pascal and Fortran sources). When the project maintains a written defect-class catalogue (commonly `docs/translation-defect-checklist.md`), the chapter-to-path map, per-chapter compile/run invocations, and numeric fingerprints live there; the skill enforces the procedure regardless of where the map lives. Keep concrete chapter→path mappings, compile invocations, and output fingerprints in the repo pipeline/runbook, not in this skill.

How to find a listing in a chunk:

1. Grep `word/document.xml` for monospace run properties: `w:rFonts w:ascii="(Courier|Consolas|Lucida Console|Source Code)"`, `w:rStyle w:val="(VerbatimChar|SourceCode.*)"`, `pStyle w:val="(SourceCode.*|Verbatim.*)"`.
2. Grep for narrative references to programs: the named program identifier, language name (`Fortran`, `Pascal`, `Turbo Pascal`), or convention markers (`Листинг N`, `Program N`, `Listing N`).
3. Cross-reference the chunk's printed-listing or narrative mention against the project's `code/.../README.md` or equivalent index of verified source files for the verified file and source-book page range.

Procedure for adding the provenance pointer:

1. Locate the reference paragraph (listing block OR narrative mention of the program).
2. Read the corresponding compiled-and-run output file with the Read tool to extract one representative numeric line for the empirical fingerprint (a future re-run that produces a different number flags a regression even without diffing the full output).
3. Record the 3-line provenance block in the chunk QA artifact or other accepted non-printing trace surface:
   - `Verified source: <repo-relative-path-to-source-file> (<compile invocation>)`
   - `Input artifact: <repo-relative-path-to-input-file>` (omit when the program has no external input)
   - `Output: <repo-relative-path-to-output-file> (<one-line numeric summary>)`
4. When the source has cross-validated translations across multiple languages (e.g. an original Turbo Pascal and a Fortran restoration), include both source paths, both compile invocations, the cross-validation row count, the max absolute difference between the two outputs, and the per-language output filenames.
5. Do not insert the provenance block as visible Word paragraphs in the final release DOCX. If a reviewer edition needs visible provenance, keep it in a separate scratch/review copy and never promote it as the book-body release.
6. Preserve OLE/media byte-identity: the provenance block is text-only and never touches `<o:OLEObject>` or `<w:drawing>` elements; SHA-256 of `word/media/*` and `word/embeddings/*` must match PRE backup.
7. If the chunk references the listing narratively but the printed listing block is in a different chunk (e.g. a narrative-only mention of a program whose source pages fall in another chunk), still record the provenance in the QA artifact for that narrative site so the citation chain is intact.

Skip rule for provenance only: a chunk that contains only a numerical data table (e.g. parameter values styled with VerbatimChar) is NOT a listing — skip with rationale recorded in the project's audit JSON or equivalent. A trivial illustrative fragment with no verified-code counterpart is also skipped for the provenance-pointer requirement.

### Program Listing And Output Layout

Printed program listings, pseudocode, BASIC examples, and console/output examples are source-PDF layout objects even when they have no verified `code/` counterpart. The layout gate is separate from the provenance gate above.

Hard blocker pattern:

- source PDF shows a monospaced listing or output block with line breaks, numbered lines, prompts, tabular output, or aligned columns;
- translated DOCX/PDF flattens that block into ordinary justified paragraphs, merges multiple source lines, loses indentation, or wraps columns as prose.

Audit procedure:

1. Search the source PDF text and render for program cues: line numbers (`10`, `20`, `REM`, `NEXT`, `RUN`), language labels (`BASIC`, `Fortran`, `Pascal`), prompts, tabular numeric output, `Program` / `Listing` captions, and monospaced block geometry.
2. Inspect the current rendered candidate, not only `word/document.xml`. Text extraction can hide a flattened block if the visual line structure is wrong.
3. Confirm that every source listing/output line maps to a separate Word paragraph or stable line in a preformatted block. Use a monospaced font and preserve source indentation/columns.
4. If OCR is unreliable but the visual source block is important, use a source-PDF crop/image only as an explicitly recorded exception; otherwise repair as editable Word text.
5. Repair with no-Word XML/layout changes first. This lane must not trigger MathType writer/OLE rebuild unless the same page also has an independent formula defect.
6. Render only the affected pages first and compare against the source PDF before promotion. Recheck nearby formula tables and figure/caption grouping if the block changes page flow.

The provenance skip rule does not skip layout. A trivial BASIC fragment can omit a verified-source pointer but must still render as the source-like listing/output block.

Mixed prose/listing source spreads are not all code. When a scanned page or two-page spread contains ordinary book prose beside a program listing, table, output block, or scanned code image, split the source units before repair: translate the prose as normal body/heading/note text, keep actual code/listing lines in a monospaced code style, and use column or page breaks only to preserve source flow. Do not prefix prose with code comment markers such as `C`, do not keep source running headers as listing text, and do not accept a token-free cleanup if OCR residue such as random all-caps letter noise remains in the visible listing/prose flow. Source-visible prose can appear in the middle of a long code table after a running header or OCR separator; classify each block against the rendered source page before deciding it is listing text. Do not insert unconditional page breaks between repaired prose/listing blocks: render the exact candidate and remove or change breaks if they create blank half-pages, duplicate source pages, or move the next source unit away from its source-like flow. Render the exact candidate and compare the mixed spread visually against the source PDF before promotion.

For program listings, prefer editable verified code over source-crop images when the repository contains a compiled/restored counterpart that matches the book listing or is an approved language substitution. Preserve executable syntax and identifiers, but translate human-facing comments, prompts, headings, and output strings when doing so does not break the code contract; keep the compile/run provenance in QA artifacts, not in the visible book body. A source-crop listing image is only a fallback when OCR/editable reconstruction is unsafe or no verified equivalent exists; record the exception explicitly. Do not promote a chunk to final `PASS` merely because listing scans are source-backed if the user has requested translated comments and a verified editable code path exists or still needs a policy decision.

### Contents And Page Numbers

- Format contents as a real structured Word layout: aligned titles, aligned page numbers, consistent indentation, and source/global page numbering.
- Do not let local document page numbers replace book page numbers when the source contents uses global book pagination.
- Check contents entries after rendering; page-number drift is a formatting defect.

### Figures And Captions

- Place each figure and its caption in one stable grouped Word structure, preferably a borderless one-column table with one image row and one caption row.
- Keep the figure table inline in the document flow unless the accepted repo format explicitly uses another stable non-floating structure.
- Keep the figure centered and scaled to the source-like visual width without stretching or cropping.
- Grouping a figure and caption is not sufficient if the embedded image itself is cropped or incomplete. Compare the rendered figure against the source PDF image area; if the source top, bottom, side labels, arrows, or subfigures are missing, repair the image extraction/source crop before acceptance.
- When replacing a missing or partial figure with a source crop, exclude source captions, page headers, page numbers, neighboring body text, and unrelated formulas unless they are part of the figure itself; keep the translated caption as editable Word text and render-check that scaling keeps all figure labels readable.
- If the embedded figure media already contains source-caption residue or a stranded caption fragment above/below the graph, clean or re-crop the media and put the translated caption in editable Word text. Do not leave the source caption inside the bitmap and then add a second translated caption in Word.
- Reject figure crops that preserve source gutter, scan margins, blank bands, or other non-figure page background. A crop that keeps all labels but visibly carries the book gutter or a broad dirty margin is still `REVISE`; re-crop the source image and preserve layout with a neutral canvas if needed.
- A figure-media replacement must preserve both content completeness and layout fidelity. If the replacement crop has a different aspect ratio from the existing media, either adjust the image extent and page flow intentionally, or place the source crop on a neutral canvas that preserves the current media dimensions without stretching the figure content. In both cases render the exact candidate and confirm that all axis labels, arrows, dimension markers, shaded regions, and subfigure labels remain visible and not too small.
- Keep captions centered, close to the figure, styled consistently, and on the same page as the image.
- Keep image row and caption row together; prevent a page break between them where the document model supports that.
- A grouped figure/caption table can still fail after render if the image row is too tall for the remaining column, the table begins too low on the page, or the section uses multi-column text. Use source-faithful flow controls such as `keepNext`, `cantSplit`, or a column/page break before the group, constrain the table to the effective column width, and scale the image proportionally so image plus editable caption render together. Do not ungroup the caption or crop away source figure content to force the page break.
- After any media crop, display-scale change, or caption merge, render the exact candidate page and the next page. The repair remains `REVISE` if the caption continues onto the next page/column while the image stays behind, or if the next page starts with a caption tail.
- For multi-part figures, keep all subfigures and the shared caption in one grouped structure, preserving source order and relative spacing.
- Place captions above or below the figure according to the source PDF or accepted exemplar; do not normalize all captions mechanically.
- Let long captions wrap as Word text inside the caption row rather than using images or text boxes.
- Preserve source-credit symbols in captions exactly. Copyright marks, registered/trademark symbols, author/source initials, and publisher credit punctuation are caption content, not decoration; if OCR or text extraction turns `©` into `@`, omits it, or drops adjacent punctuation, repair the editable Word caption text after checking the rendered source PDF.
- Preserve figure-label punctuation and subfigure letters exactly. If the source caption uses `Fig. N.` / localized `Рис. N.` or subfigure labels `(a)`, `(b)`, `(c)`, the translated caption must keep the number dot and source-visible letters. OCR substitutions such as `Рис. N Caption`, `Рисунок 56` for `Figure 5b`, `Рис, 5a`, or `(6)` for `(b)` are caption/prose blockers. Repair editable Word text only, then render-check the caption and nearby figure reference.
- Localize source-credit prose grammatically while preserving the source reference number. For English caption credits like `Reprinted with permission from Reference N`, do not render OCR-style Russian such as `из ссылки N`; use the accepted local wording such as `Перепечатано с разрешения из источника N` (or the repository's equivalent style) and keep `©`/publisher/year punctuation source-faithful.
- Verify the full rendered caption and legend/prose associated with the figure, not just the image crop. A grouped figure still fails if the caption row, table cell, or fixed-height frame clips the caption, leaves only the first caption line visible, or drops source-equivalent material/substrate/legend text.
- Do not leave a figure as a floating object if it can drift away from its caption.
- Do not put figure captions inside MathType, screenshots, or loose text boxes.
- If the source has a figure number and caption text, keep both as editable Word text.
- Preserve indexed/accented mathematical labels inside captions with the same rigor as body inline math. If the source caption says labels such as `B_i`, `M_i`, `S_i`, `e_z`, or `h_z`, the rendered DOCX must show true subscript/accent styling via existing inline MathType OLE or styled Word math runs; plain `Bi`, empty slots, duplicated text labels, or OCR residue after the caption are `REVISE`. When repairing a caption, preserve already-correct inline OLE objects instead of rebuilding them, add missing styled Word math only for the defective symbols, and render-check the complete caption against the source page.
- Reject a DOCX where figures are top-level image paragraphs and captions are separate following paragraphs. This is still a drift risk even when the rendered page happens to look acceptable.
- Reject captions or surrounding prose that lost inline formulas during conversion, such as blank spaces where symbols should be, plain caret notation, or formula-like text left outside MathType without correct Word math styling.
- If the rendered source page visually floats a grouped figure before a continuation paragraph, keep that visual order even when the extracted text stream or first textual mention suggests a different anchor. Move the whole figure/caption table as one block and re-render the affected page; do not split the image from its caption or leave the continuation prose above a source-preceding figure.

### Formula Tables

- Put each numbered display formula in its own borderless two-column table.
- Left cell: exactly one display MathType OLE object or one coherent display formula block.
- Right cell: ordinary Word text equation number only.
- Prefer fixed table layout or disabled autofit for formula tables.
- Use stable preferred widths derived from the accepted page geometry: the formula cell gets the usable width, and the number cell gets only enough width for the widest equation number.
- Reject normal single-number display tables whose formula and number columns are roughly equal width, or where the formula cell is only a half-page cell. That layout centers short OLE formulas inside the left half of the table and visually pushes them toward the margin while the number stays on the right. Normalize the table to a wide formula cell plus a narrow non-wrapping number cell, and center the OLE paragraph inside the formula cell; changing grid widths alone is insufficient if the formula paragraph remains left-aligned.
- Use small, consistent cell margins so formulas do not touch cell edges and numbers do not drift.
- Prevent a display formula row from breaking across pages unless the source formula itself is split across pages.
- Keep the paragraph containing the formula object and the paragraph containing the number together with their row where possible.
- Treat a rendered equation number stranded on a different page from its formula as a formula-table blocker even when DOCX XML still shows a valid two-column table. First try a scoped no-Word pagination repair such as row-level `cantSplit`, paragraph `keepNext`, or a source-faithful explicit page break; render the adjacent pages and accept only if the formula, connector text, and number move as one readable block.
- Keep both cells vertically centered for ordinary one-number display rows.
- For one MathType OLE that intentionally contains several source display lines with several Word-text numbers in the right cell, do not rely on vertical centering or default paragraph leading. Render/source-check every number against its own source line. If the number stack is shifted or compressed, keep OLE/media bytes intact and tune only the number cell first: set the number cell to top alignment, keep numbers as separate right-aligned non-wrapping paragraphs, set direct `firstLine=0`, and use exact line spacing matched to the OLE line rhythm. Re-render the affected pages and reject the repair if a heading/connector such as a region label becomes separated from its formula block or a following display moves to the wrong page-flow position.
- Apply the same non-wrapping-number rule to multi-number cells such as `(72)(73)` or `(113)(114)(115)`: set the number cell to no-wrap and set every equation-number paragraph to direct `firstLine=0`. A visually acceptable stack that depends on inherited indentation or Word auto-wrap is still a layout risk after later typography/style passes.
- Center the formula within the formula cell unless the source clearly uses left alignment for a long multiline block.
- Right-align the number within the number cell.
- Set equation-number paragraphs to direct `firstLine=0`; do not rely on inherited `Normal` paragraph settings. A number cell can look acceptable in one render while still inheriting a body first-line indent that later wraps or shifts `(166)`-style labels after typography/style normalization.
- Use stable column widths or fixed table layout so long formulas do not create extra columns, table wrapping artifacts, or a number pushed into the formula.
- Give the number cell enough width and explicit line breaks or separate paragraphs for multi-number displays. Do not rely on Word auto-wrapping to stack equation numbers; a number such as `(52a)` must never split into `(52a` and `)`.
- Suppress borders at table and cell level.
- Render formula tables after Word save and reject visible table borders, horizontal rules, or bottom lines that are not present in the source PDF. XML border settings alone are not enough because table style inheritance can still render lines.
- For multi-row formula tables, inspect conditional table-style flags such as `w:tblLook/@w:firstRow`. A table may have no explicit `w:tblBorders`, `w:tcBorders`, or `w:pBdr` and still render a horizontal rule from an inherited first-row style. Disable that conditional formatting or apply explicit no-border formatting on the affected formula table, then re-render the page.
- When replacing a formula-table OLE donor or clearing formula/number cells, preserve or reapply explicit no-border `w:tcBorders` on both cells, not only `w:tblBorders` on the table. Losing the cell-level `bottom none` override can make Word restore a horizontal rule from the table style even though package inspection shows no obvious paragraph border; fix the cell borders and re-render before accepting the candidate.
- Separate adjacent formula/figure/table structures with a small normal paragraph when Word would otherwise merge tables during save.
- For unnumbered display formulas, use the same stable layout but omit the number cell only if the repo's accepted format does so; otherwise use a blank number cell for alignment consistency.
- Preserve the source sequence of formula and prose blocks. If the PDF has an unnumbered identity, then explanatory prose such as "so that equation ...", then a numbered equation, keep those as separate Word structures: unnumbered formula table, ordinary prose paragraph, numbered formula table. Do not merge them into one MathType object or one numbered formula table.
- Preserve connector prose between adjacent display formulas even when the generator merged the formulas into one multi-row table. If the source shows a connector or row label such as `where`, `где`, `with`, `Let`, `so that`, `The corresponding ... is`, `Line k + 1`, or localized equivalents between two display rows, split the table or insert an ordinary Word-text connector at the source-flow position. Do not leave the connector dangling after both formulas, and do not move it inside MathType unless it is mathematical notation in the source.
- Reject accidental table merges after Word save. A single logical formula table must not become a multi-row or extra-cell table merely because two adjacent display tables were inserted without a separator.
- For multi-number displays, verify whether the source truly has one coherent multi-row formula. If the generated DOCX uses multiple numbers in one right cell or creates extra cells, inspect the rendered PDF and split or rebuild until each row/number relationship is unambiguous.
- A multi-number right cell is not automatically a defect. It may stay only when the source PDF shows one coherent aligned multi-line display, the left cell has one editable source-faithful MathType object or intentional row stack, each visible number is ordinary Word text aligned with its source line, and a current render/source comparison records that classification. If the source has independent formula rows or the generated table creates artificial rows/columns, split or rebuild the block instead of accepting the warning.
- Count structural rows, not just visible rows. A table that appears acceptable in the PDF can still fail if DOCX XML shows unexpected extra cells, merged grids, or a neighboring figure/formula table merged into it.
- For source displays that contain several adjacent expressions on one numbered row, the MathType object must include an explicit source-like visual gap between complete neighboring expressions. If extraction collapses them together or a donor omits the gap, replace only the numbered-row formula object and preserve surrounding `where` rows, number cells, and neighboring formula tables.
- For long split displays that continue across several formula-table rows or pages, compare the whole source block before any local replacement. If one old OLE contains two source equations and another source equation is missing entirely, the correct targeted repair is usually to insert the missing equation row and replace the stale combined OLE with a donor that still contains all equations formerly owned by that OLE. Validate the result by visual row order, not by OLE count alone.
- For row-level Pattern B transplants inside an existing `w:tbl`, insert replacement `w:tr` elements at the old row's real XML child index (`old_table.index(old_row)`), not at the row ordinal among `./w:tr` children. Inserting a row at child index `0` before `w:tblPr`/`w:tblGrid` can leave ZIP/XML parsing clean while Word refuses to open the DOCX.
- When selecting a bounded donor from a probe DOCX, prefer the exact donor row with one OLE and the requested number label. A probe table may contain an unconverted placeholder neighbor such as `(50)` beside the converted `(51)` row; table-level label matching can accidentally copy both rows or a placeholder. Use table-level donor matching only after row-level matching fails.
- When splitting a single multi-number display row into several numbered MathType rows, build the new `w:tr`/`w:tc` rows and cells from a clean table-row template or fresh WordprocessingML, with explicit no-border cells and terminal paragraphs. Do not deep-copy a sole first-row source row as the row template for every new formula: inherited first-row/table-style metadata, cell borders, and transient row/paragraph ids can make a DOCX that parses as XML but Word refuses to open, or can render stray horizontal borders between equations. After the split, run a Word-open/export probe before any visual acceptance.
- If a shared display table already has accepted sibling rows and only one row still contains multiple equation numbers, split only that stale row into fresh no-border rows and preserve the accepted sibling rows byte-for-byte where possible. Use row/cell evidence from the current DOCX package, not only table-level text: extraction can flatten a number cell such as `(86)` plus `(87)` into `(86)(87)` without a line break. The repair must verify after render that each new row has exactly one MathType OLE in the formula cell and one ordinary Word-text number in the number cell.

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
- If a formula looks too small after automatic import, rebuild or copy a better MathType template instead of accepting a shrunken object.
- Do not close a long-formula defect by shrink-to-fit alone when the source PDF uses a multi-line layout. Rebuild the affected OLE as a source-like multi-line MathType object, usually with one complete expression fragment per row, then render the donor and exact candidate. Keep the equation number as ordinary Word text in the table number cell. Avoid optional TeX row-spacing syntax such as `\\[3pt]`/`\\[7pt]` in `SetMTTeXData`; MathType can render the bracketed spacing literal as visible text.
- If a long display MathType object overruns its formula cell and collides with the Word-text number cell, compare the source line breaks before resizing anything. When the source uses multiple visual lines, rebuild only that display as a multiline MathType donor or a source-faithful split; do not hide the defect by shrinking the number cell, moving the number into MathType, or accepting a one-line object that still changes source layout.
- If the source render proves the display topology is already correct and the only rendered defect is that the Word/VML preview is wider than the effective formula cell, constrain the table/preview geometry before rebuilding MathType. Scale the whole preview shape proportionally, keep the equation number as ordinary Word text in the number cell, preserve OLE/media bytes, and render the exact scratch DOCX to prove the number no longer overlaps or clips. Do not use preview scaling for formulas whose source uses a multiline layout or whose formula content/style has not been source-checked.
- After a long-display donor changes line count or height, check neighboring page flow in the rendered candidate, not only the formula crop. The following source paragraph must not jump ahead of the next display/figure in the opposite column, and the next display must not move into the previous source-page column. If the source-backed donor is correct but too tall, scale the whole preview proportionally only after source topology is restored, and re-render the full affected page.
- Do not collapse a source multi-line definition block into one horizontal row. Preserve the source topology as a vertical MathType object or as separate display rows, with every row source-checked. When generating from TeX/MathML, prefer one complete equation or definition fragment per row over splitting `lhs`, `=`, and `rhs` into artificial cells that can create wide gaps.
- Validate baseline and size in both Word and exported PDF when possible; trust the exported PDF when they differ.
- Verify sizes visually in the exported preview PDF; OLE metadata alone is not enough.

### Mathematical Symbol Style

- Use MathType math style for variables and symbols, not plain Word text pasted into an equation object.
- Treat mathematical typography as semantic content, not decoration. A formula is wrong if symbol identity is correct but italic/upright, boldness, vector mark, index, accent, delimiter, or operator style differs from the source PDF.
- Do not substitute algebraically related notation for source-visible notation. If the source PDF shows a transpose, inverse, conjugate, prime, hat, bar, tilde, or other accent/operator explicitly, the final MathType object must show that same source notation unless a human reviewer has approved a documented correction.
- Preserve source distinctions between italic variables, upright function names, upright operators, bold/vector symbols, Greek letters, and ordinary prose.
- Keep multi-letter function/operator names upright when they are functions or operators; keep products of variables italic when they are variables.
- Keep differential symbols, domains, constants, and units in the style used by the source or accepted exemplar.
- Preserve boldness and vector style for fields, vectors, matrices, and basis/test functions.
- For Latin vector, field, dyadic, position, unit-vector, and basis/test symbols, verify whether the source uses bold upright, bold italic, arrow, hat, or another mark. Do not assume all bold Latin symbols are italic.
- Keep scalar components, modal coefficients, indices, and ordinary scalar variables in their source style. A bold vector field such as `H` can be upright while a scalar component such as `H_x` or a modal coefficient such as `H_{mn}` remains italic.
- Do not trust TeX `\mathbf` alone as visual proof. Some MathML routes convert Latin `\mathbf` to bold-italic Unicode that MathType renders slanted. If the source shows upright bold vectors, use a verified route such as MathML `mi mathvariant="bold"`, a MathType TeX sample that renders upright, or a user-corrected one-object sample.
- Build hats and other over-accents with native MathType accent templates, with the base symbol inside the accent slot. Do not accept a loose combining mark or typed caret that merely appears above or beside the base. For generated MathML, normalize combining-circumflex movers into explicit `mover accent="true"` hat templates when MathType otherwise renders a detached hat.
- Inline dyadic double-bars are a high-risk accent case. Nested MathML `mover` imports can render as detached marks, black artifacts, or separate-line fragments even when the payload text is correct. Use a rendered MathType TeX/manual donor with the double-bar template over the complete base symbol, then verify that the inline object stays on the text baseline and does not split the sentence.
- Generalize that rule to any mark, enclosure, or stretchy symbol that MathType represents as a template: tilde, bar/overline, vector arrow, dot/double-dot, wide hat, radical, brace/cases, determinant bars, brackets, parentheses, norms, and matrix/vector delimiters. Put the intended expression inside the MathType slot first, then render and compare. Do not assemble these from ordinary glyphs, short bars, separate text runs, or adjacent cells unless the source PDF truly shows separate symbols.
- For partitioned matrices/arrays, internal vertical and horizontal rules are part of the formula template. Do not trust MathML `rowlines`/`columnlines` attributes, TeX array specifications such as `cc|cc`, or `\hline` until a rendered MathType OLE proves the rules survived import; MathType automation can silently drop them. If the rules disappear, create a one-object manual MathType sample and copy that verified OLE into the target formula instead of rerunning the same import.
- If rendered math shows replacement glyphs, black diamonds, boxes, missing brackets, or wrong angle-bracket symbols, treat it as a MathType/font/template defect even when text extraction looks plausible. Rebuild the affected expression with explicit MathType delimiter templates or source-faithful math characters and re-render.
- If a black diamond or box appears above a barred, hatted, or overlined base where the source shows a normal accent, treat the accent template as broken. Rebuild the affected MathType object with native accent/overbar slots containing the complete base symbol and scripts; when the defect is one row of a shared display table, replace only that row and preserve sibling rows and number cells.
- Preserve primes, bars, hats, dots, arrows, overlines, superscripts, subscripts, and nested scripts.
- Verify indices against the source PDF character by character. Check base symbol, case, Greek/Latin identity, subscript, superscript, prime order, multi-character grouping, nesting, and attachment point. Do not infer that a repeated pattern has the same indices unless the PDF shows it.
- Preserve left pre-subscripts and other pre-scripts exactly. A source symbol such as `{}_{k}A` or `{}_{k}V_m^i` must not be normalized to `A_k` or `V_{m,k}^i`; the attachment side is semantic notation, not typography. Build the MathType object with a left-script template or source-equivalent TeX such as `{}_{k}A`, and verify the rendered glyph against the PDF. Apply the same rule to inline prose mentions of the same symbol.
- Treat a missing base before a superscript or exponent as a formula-content blocker, not a harmless OCR artifact. If a source entry such as generic `s^{-2N}` becomes only `-2N`, repair the source-map payload and replace the stale OLE for that display; clean conversion counts do not prove exponent/base fidelity.
- Treat source subscript letters in Bessel, wave-number, port, and modal formulas as high-risk content. Similar-looking items such as `n_s` versus `n_i`, `k_{mn_s}` versus `k_{mn_i}`, or inherited `B_{mn_s}=1/A_{mn_s}` versus `B_{mn}=1/A_{mn}` must be compared visually against the source PDF at each occurrence. Clean OLE/media counts or matching neighboring formulas do not prove the index is correct.
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
| Operator limits and domains | Every lower/upper limit and domain glyph, including inner versus outer bounds, uppercase/lowercase domain letters, finite bounds versus infinity, and visually similar symbols |
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

Do not downgrade a compact formula to a chain of styled Word runs when it contains function names, inverse powers, slash fractions, grouped denominators, radicals, delimiters around a multi-token expression, infinity, or multi-token relations. If MathType OLE padding caused a previous workaround, rebuild the expression as one inline MathType object and keep only punctuation as Word text. Do not split source-visible compact intervals into Word brackets plus a partial MathType object when a one-object donor is practical.

Short reciprocal definitions with inherited indices, such as `B_{mn}=1/A_{mn}` or the same pattern with an additional subscript letter, are still mathematical content. They may stay as styled Word math only when every base, subscript character, relation, slash, and punctuation mark is styled/source-checked and the reason is visible MathType OLE punctuation spacing. Missing inherited index characters are a blocker even when the plain text looks close.

Check inline math as a first-class formula surface:

- preserve italic/upright convention for variables, functions, constants, operators, and words;
- preserve bold/vector marks and distinguish scalar symbols from vector symbols;
- preserve subscript/superscript nesting, prime position, bars, hats, Greek letters, and punctuation spacing;
- verify every index from the PDF, including repeated inline occurrences that look similar but may differ by `m`, `n`, `i`, `j`, `\mu`, `\nu`, plus/minus, or prime marks;
- do not leave source-language words, captions, or condition labels inside MathType;
- verify equation references in prose point to the same visible numbers as the source PDF.

Inline math must read like part of the sentence:

- keep surrounding spaces and punctuation outside MathType unless punctuation is mathematically part of the expression;
- preserve the required Word text whitespace before conjunctions, prepositions, and ordinary words that follow an inline OLE. A run immediately after an inline MathType object often needs a leading preserved space before a word; without it the render can collapse into `<math>и`, `<math>в`, or `<math>с` even when extracted text looks almost readable. Do not add that leading space before a comma, period, closing parenthesis, colon, semicolon, or similar punctuation mark unless the source visibly requires a math space. Inspect the actual run order and render the line after repair;
- keep commas, periods, parentheses, brackets, and dashes visually attached to the correct words or formulas;
- If the source sentence says `... <inline formula>, ...` or `... <inline formula>. ...`, the comma/period belongs after the rendered inline formula object, not in the preceding text run. Source-backed repairs must move punctuation across the inline object rather than leaving patterns such as `в виде. <formula>`, `с помощью, <symbol>`, `матрицы, <symbol>`, or `вектора, <formula>`. After any such move, render the affected line; if a very short OLE creates unacceptable visible padding before punctuation, or if punctuation after an inline OLE wraps alone to the start of the next line in a caption/body sentence, tighten only that inline preview geometry or replace only that short symbol with verified styled Word math/tighter donor instead of rebuilding unrelated formulas. Do not accept renders that read as `math .`, `math ,`, `math )`, or a line-start `;`/`,` solely because the punctuation is technically outside MathType; the rendered sentence must have source-like punctuation spacing and wrapping.
- After moving punctuation across an inline object, scan the surrounding body children for leftover punctuation-only paragraphs/runs such as a standalone `.` or `,`. These are repair residue, not source content; remove them only after verifying the source page and render-checking the affected page.
- keep short linked inline-math phrases together across page breaks when splitting would strand the connector or final symbol on the next page; use no-break spacing or equivalent Word run controls only in the surrounding text runs, then render-check the affected line after export;
- avoid alternating text MathType text MathType for one compact symbol cluster when one inline object is cleaner;
- do not convert ordinary prose words to MathType just because they sit near a formula;
- check every inline occurrence after PDF export, especially Greek letters with indices, bold vectors, primes, superscripts, and references such as "from (n) into (m)".
- Use PDF text extraction only as a locator for inline/math defects. Extractors can flatten tildes, drop accent marks, merge MathType objects, or show acceptable inline sequences as collapsed text. A defect or rejection must be confirmed on the rendered page/crop against the source PDF before changing the document.
- Do not accept an inline repair from punctuation/text extraction alone. The rendered MathType object itself must match the source: a visually wrong prime/derivative/accent object in the correct sentence position is still a formula defect even when the surrounding text is fixed.
- When one inline MathType object is locally wrong and a neighboring rendered object is a source-verified donor for the same symbol, a targeted package repair may replace only the defective object's OLE/media bytes and display dimensions with the donor. Record the donor relationship targets, affected object/media parts, and rendered source comparison; leave unrelated formulas untouched.
- Reject plain-text formula placeholders or OCR-like markers left in prose, for example caret-only superscripts, `Y^<`/`Y^>`, `Y^*`, collapsed indexed families, or comma-separated formula lists that should be separate inline MathType objects.
- Reject OCR residue that stands where the source sentence has an inline mathematical object, including placeholder-like fragments, stray Latin syllables, malformed words, or symbols such as `*?`. Replace it with editable inline MathType or source-faithful styled math at the exact sentence position, then render-check baseline, spacing, and grammar.
- When one source sentence contains several adjacent inline formulas, represent each logical formula as its own inline MathType object or as styled Word math text only if the visual result is identical and stable. Do not merge a sequence into one oversized inline object when that changes punctuation, wrapping, or meaning.
- For comma-separated inline parameter lists, verify the rendered comma spacing and decimal values against the source PDF. MathType import can ignore MathML spacing hints such as `<mspace>` or comma-space `<mtext>` and render semantically different compact text like `2,10` instead of the source list `2, 10`, or a decimal-valued list like `1, 2.2, 4.34, 9.6` as a different visible sequence. If a full inline donor cannot preserve the visible list punctuation, split at the source punctuation: keep each compact mathematical core as MathType OLE or source-faithful styled math, and keep comma+space/conjunction text as ordinary Word runs between/after the objects. Record this as a targeted inline-punctuation repair and render-check the full sentence.
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
- If the source PDF shows condition phrases as rows in the cases stack, preserve that row structure. A detached prose paragraph that merely summarizes the cases is a defect, even when the math rows themselves are editable.
- Keep following or neighboring definition rows continuous unless the source PDF explicitly separates them.
- If a user-corrected sample used a brace-with-slot containing a vector/column, future pages must copy that structural pattern. A similar-looking glyph brace, one-cell brace, or matrix trick is still wrong.

Reject:

- small or stray-looking curly braces;
- ordinary prose labels inside MathType when the source does not place them inside a mathematical template;
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
- for generated MathML, avoid two-column `mtable` alignment that isolates the left-hand symbol or relation sign in a separate cell unless the source is genuinely tabular; prefer a one-column row structure where each row contains the complete `lhs = rhs` fragment;
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
| Caption glued to OCR/axis/header residue | A short graph label, axis tick, running header, or legend fragment appears before `Рис.` / `Fig.` in body flow | Remove or relocate the residue, restore/group the source-backed figure, and keep the clean caption editable |
| Body figure-reference styled as caption | A source body sentence such as `Figure N gives...` or `Рис. N дает...` renders italic/caption-like although the true caption is elsewhere | Compare the source line first; if it is body prose, remove only accidental caption/italic styling from that paragraph, preserve inline OLE/media, and leave real grouped captions untouched |
| Figure repair leaves empty table cells | Split-caption cleanup removed a caption paragraph but left a table cell with only `tcPr` and no paragraph/table child | Remove the whole obsolete row or add a valid terminal paragraph, then prove Word opens/renders the exact candidate |
| Formula table merges with other table | Extra columns or visible table artifacts after Word save | Separate neighboring tables with a tiny normal paragraph and suppress borders at table and cell level |
| Inserted display tables merge with neighbors | Two formulas or formula plus figure become one multi-cell table | Insert a tiny normal separator paragraph before/after inserted tables and verify XML cell counts after Word save |
| Equation number wraps inside number cell | Closing parenthesis drops to a separate line, for example `(52a` then `)` | Widen the number cell, use fixed table layout, and split multi-number displays with explicit line breaks or paragraphs |
| Source prose between formulas is lost | An unnumbered identity and the following numbered equation are merged, or the linking sentence disappears | Keep the unnumbered formula, linking prose, and numbered formula as separate Word-flow structures |
| Advancing queue after writer-only success | Next chunk starts after clean MathType/OLE counts while current chunk has no current coverage rows or source-page ledger | Record rendered-PDF/source coverage, source-map/source coverage or source-page ledger, visual comparison, and any exception before moving to the next chunk |
| Text labels inside MathType | Region names or prose conditions appear inside OLE | Move labels to Word text; keep MathType math-only |
| Condition text collapsed to a bare variable | Source row says `for all x` or similar, but the candidate row shows only `x` after the equality or as a stray MathType token | Treat as a failed text move. Rebuild or split the affected formula row so the math is MathType-only and the localized condition is ordinary Word text aligned with that source row; render before deleting any detached condition text |
| Oversized body text | Page looks like a poster or all-bold block | Restore book typography and source-like hierarchy |
| Mechanically converted overlay typography | Target PDF has many more pages, large sans/body text, unindented paragraphs, or captions styled as body | Normalize against the accepted exemplar/source before visual review |
| Inconsistent page typography | One page uses different font, spacing, or heading style from the accepted exemplar | Derive styles from exemplar/source and apply consistently |
| Source/data table text compressed | Table header/body text overlaps rules or neighboring columns because of too-small exact line spacing, narrow grid widths, or fixed row height | Treat as table-layout REVISE: widen to effective page/column width, use stable column widths, normal single spacing, readable row heights, and render-check the full table |
| Figure/caption separated | Figure moves to one page and caption to another | Put image and caption in one borderless table with keep-with-next behavior |
| Figure image cropped after grouping | Caption is stable but the figure itself lost top/bottom/side content compared with source PDF | Replace or re-extract the figure image from the source crop before accepting the grouped figure |
| Figure crop includes page header/footer | Figure image visibly contains source page furniture such as `APPENDIX`, book page number, running header, or nearby body text | Re-crop or media-clean the source-backed image so only figure content remains; preserve canvas dimensions if changing dimensions would disturb page flow; render-check the page |
| Source caption embedded in figure media | The graph image itself contains English/source caption residue, while the translated caption is separate, missing, or split into nearby body paragraphs | Clean or re-crop the media so only the figure remains, rebuild the caption as editable Word text with source-faithful inline math/units, remove stranded caption paragraphs, and render-check the figure page plus following page |
| Figure labels clipped at media edge | Source-backed figure content is correct, but right/left edge labels or legends are cut by table width, drawing extents, or zero image margin | Constrain table/grid/cell widths, scale drawings proportionally, and if the label is flush to the media edge add harmless white padding without cropping/redrawing source content; render-check image and caption together |
| Figure caption clipped after grouping | The image is clean but the rendered caption stops mid-caption or loses source-equivalent legend/material text | Allow the caption row/cell to grow, remove fixed-height clipping, widen or split the caption text, and render the affected page before acceptance |
| Figure separated from caption after flow repair | The image and caption both exist but render on different pages/columns or can drift independently | Keep figure plus caption in one stable structure or insert only source-faithful flow controls needed to keep them together; re-render the exact candidate before acceptance |
| Grouped figure table splits because image is too tall or starts too low | Image and caption are in one table but still render on different columns/pages, or a blank/caption-only page appears | Keep the group intact, constrain table width to the effective column, scale the image proportionally, and insert only source-faithful column/page flow controls before the group; re-render the exact candidate |
| Caption unit or short inline index omitted | Source caption includes unit words/symbols or a short indexed symbol such as `Ω`, `ohms`, or `L_0`, but the candidate omits the unit or preserves a stale inline object with a different subscript | Source-check the caption line itself; repair only the affected unit text or short inline object, using a MathType donor or stable styled Word math for simple symbols, and remove any superseded OLE/media pair before rendering |
| Formula preview overlaps equation number | MathType OLE/media are present and source topology is correct, but the VML preview extends into the ordinary Word-text number cell | After source line-break/content proof, proportionally constrain the preview/table geometry without rebuilding unrelated OLE objects; render-check that the number cell is separated and the formula is not clipped |
| Connector prose after merged formula rows | A `where`/`где`/`with`/`Let` connector appears after two formulas even though the source places it between them, or a roots/condition sentence loses its formula reference outside MathType | Split the merged formula table or move the connector/reference as ordinary Word text to the source-flow position; preserve OLE/media bytes when the formulas themselves are already correct, then render-check the affected page |
| Inline condition punctuation/OCR residue | A boundary or parameter condition split by inline MathType objects renders with punctuation before the final object, or with source-language/machine words such as `(for)`/`(для)` in the wrong place | Inspect the Word run order around all inline objects in the condition, preserve correct OLEs, localize condition words as ordinary Word text outside MathType, and render-check the full sentence against the source PDF |
| Orphan image-only formula tail | A textless paragraph/table immediately after a display formula contains only a drawing/blip and renders as a cropped duplicate or tail of an old formula, while OLE counts and `pdftotext` look clean | Treat it as a no-Word XML cleanup: verify the source PDF has no such extra display, confirm the block has no text/OLE/math and only image relationships, remove only that orphan block plus its relationship/media part, then render the affected pages before accepting |
| Stale unnumbered OLE formula fragment | A textless unnumbered table immediately before or after a numbered display contains one MathType OLE and renders as a duplicate first/last fragment of the same source formula | Verify against the source PDF that the numbered donor/table now contains the full formula; remove only the stale unnumbered table plus its OLE/media relationships, keep the numbered formula and neighboring formulas intact, then render the affected page |
| Unused object/media relationship in package | DOCX package has `word/_rels/document.xml.rels` entries for OLE or preview media whose ids are absent from all visible document relationship attributes | Treat it as package-hygiene REVISE: collect relationship ids from all Office relationship attributes such as `r:id`, `r:embed`, `r:link`, plus legacy `o:relid`; remove only unused relationship entries and target parts that are not referenced elsewhere; render the exact candidate before promotion |
| Formula-only or layout-only review skips translation | Worker reports MathType/OLE/layout success while source-visible headings, paragraphs, captions, table labels, references, formula connectors, or list items were not checked and translated | Keep the chunk at `REVISE`; run the Translation Completeness Gate, repair the translation/source owner, and render-check affected pages before any final PASS |
| Source-language prose remains in translated body | Body text, formula-table labels, captions, headings, conditions, or connectors remain as accidental source-language prose outside code/listing/bibliography exceptions | Localize the Word text at the source-flow position; preserve true notation, names, code, acronyms, and recorded bibliography exceptions; remove duplicated source-plus-translation text |
| Stale duplicate prose/OLE connector | After moving or localizing a connector/condition outside MathType, a neighboring paragraph or table still renders the old connector as a separate mixed prose/OLE line, so the sentence appears twice or source-language residue remains before the clean formula | Treat it as both translation and stale-OLE repair: update the source-map owner, remove the stale duplicate block plus relationships/media, replace only the affected formula OLE if it contains text residue, and render the affected page against the source PDF |
| Figure-axis/OCR prose leak | A graph axis label, unit, legend word, page header, or copyright fragment appears inside ordinary prose near a figure, often with source text omitted nearby | Compare the whole source spread, restore the missing translated source sentence(s), remove the leaked label from prose, and render-check the figure plus adjacent paragraphs |
| Figure media/extent crop | A grouped figure still loses a graph edge, axis label, title, legend, frame, or curve endpoint because the stored image is cropped or the drawing extent is wider than the page/column | Compare rendered candidate to a source crop; replace only the cropped media part or reduce only the drawing/table extent, then render the affected pages before promotion |
| Bad technical term translation | Domain term becomes nonsense | Verify against source context and use a consistent glossary |
| TOC/page-number drift | Contents use local chunk pages instead of book page numbers | Preserve source/global page numbers unless user asks otherwise |
| Inline math loses style | Greek/indexed/vector symbols look like plain text | Convert to inline MathType or explicitly style Word text |
| Inline math loses source script/accent | Source shows an indexed, primed, hatted, barred, or vector-marked symbol, but candidate renders only the bare base symbol | Rebuild the complete inline object as MathType or source-faithful styled Word math; do not accept the plain base symbol |
| Inline formula remains as plain caret text | Rendered prose contains markers such as `Y^<`, `Y^>`, or unstyled indexed families | Split into real inline MathType objects or correctly styled Word math runs before writer conversion |
| Inline MathType donor renders blank | A simple inline symbol imports with successful macro return and nonzero OLE size, but the donor PDF/candidate line shows an empty gap | Treat the rendered donor/candidate as authority, not the macro return. Regenerate the symbol through a different accepted import path such as MathML with explicit grouped scripts (`k_{y}` rather than bare `k_y`), or use a documented styled Word math fallback only for simple source-checked inline symbols. Render-check the line before promotion |
| Inline formula sequence is merged into one object | Several source formulas, conjunctions, and punctuation become one large inline object | Split by logical formula and keep prose/punctuation as Word text |
| Inline formula list loses comma spacing | Render shows `2,10`, `0.05,0.125`, or similar compact list where the source has comma+space-separated alternatives | Split list punctuation into ordinary Word text between compact MathType/styled math cores and render-check |
| Inline OLE collapses into following word | Render shows an inline formula glued to a following conjunction, preposition, or ordinary word | Preserve leading whitespace in the following Word text run, inspect run order around the OLE, and render-check the affected line |
| Paired inline delimiter closes too early | Angle-bracket inner product or tuple renders as `⟨<x>,⟩ <y>` instead of enclosing both inline objects | Move the closing delimiter to Word text after the final inline object; keep separators between objects and render-check the line |
| Inline punctuation jumps | Comma/parenthesis moves around OLE in preview | Rewrite sentence or keep tiny symbols as styled Word text |
| MathType size mismatch | Formula appears too small/large | Rescale consistently and visually check preview |
| MathType baseline mismatch | Inline formulas float above or below text | Adjust inline object/template and verify rendered baseline |
| Formula font/style mismatch | Variables, functions, vectors, or operators have wrong italic/bold/upright style | Correct MathType styles or styled Word runs against the source PDF |
| Index copied by pattern instead of PDF | Formula has plausible but wrong subscript/superscript, prime, or Greek/Latin index | Recheck every base and script against the rendered source PDF, character by character |
| Similar glyph substitution | `ν/v`, `μ/u`, `φ/ψ`, `k/K`, `0/O`, or another near-lookalike is swapped | Use source crop/zoom and record ambiguity instead of guessing |
| Body font / size drift vs exemplar | Body uses Arial 10.5pt while exemplar uses TNR 11pt; headings 1-2pt oversized | Merge full exemplar `word/styles.xml` into the chunk's styles.xml, preserving chunk-specific pandoc styles (FirstParagraph, Compact, Bibliography, SourceCode/* tokens, CaptionChar, Figure, VerbatimChar, Table, Author, Date, etc.) |
| Body page label banners | Body flow contains `Страницы NN-MM` Title and `Страница NN` Heading paragraphs that source PDF does not show | Remove the paragraphs from `word/document.xml`, preserve bookmark Starts/Ends, drop service `страница-*` bookmark ids and reattach semantic bookmark Ends to surviving paragraphs |
| Heading merged with body or local autonumber drift | Source has a standalone numbered section/subsection heading, but the candidate renders heading plus prose in one paragraph, loses the parent number (`3.1.` -> `1.`), or inherits hyperlink-like italic/color formatting | Split the heading from body prose; use source-backed explicit numbering when list numbering drifts; apply the correct Word heading style/outline level with direct black/bold/no-italic overrides if needed; render-check the source page and TOC/outline implications |
| ALL CAPS section headings | Heading text in `word/document.xml` is uppercase Cyrillic, e.g. `9. МЕТОД ОБОБЩЕННОЙ МАТРИЦЫ РАССЕЯНИЯ` | Apply Russian sentence case while preserving number prefix and 2-4 char Latin acronyms; multi-run text-runs must be merged + redistributed carefully without losing `<w:rPr>` (bold/italic) |
| Multi-number formula cell concatenation | Right cell contains `(N)(N+1)(N+2)` joined by `<w:br/>` or separate paragraphs | Treat as a visual-check warning first. It is acceptable only when the source has one aligned multi-line display, the left MathType object is editable and source-faithful, each number is ordinary Word text aligned with its source line, and render/source comparison passes. If labels are misaligned, paired with separate row formulas, or hide a merged wrong-order table, split/distribute labels per Class H. |
| Multi-row OLE display left untouched after multi-number split | Right cell now has N labels but left cell still has ONE merged OLE rendering all N equations as one image | If the source expects separate independent display rows, defer to writer-bound Phase 4 OLE rebuild; do not promote as visually correct. If the source expects one aligned multi-line display, keep it as a single verified MathType object and record the visual check. |
| Pattern A1 label distribution applied to an inverted-row table | Labels correctly distributed one per row, but each label now pairs with the WRONG formula (row order was inverted vs source PDF) | Before distributing labels, verify OLE binary content of each row against source PDF order; if inverted, apply A1+swap row-content swap first, then distribute labels. See H-A1-swap in Defect Class Index. |
| Pattern B split loses a prose connector | Rebuilt rows look mathematically correct, but source words such as `with`, `where`, `or`, or `if` before the following display are missing, left inside MathType, or orphaned as a standalone line at a page break | Restore the connector as localized ordinary Word text outside MathType, preferably in the same formula cell as the display it introduces. Render the affected pages and reject any repair where the connector is stranded away from the formula. |
| Formula-table Word labels left in source language | Display/table labels such as `ELECTRIC WALL:` and `MAGNETIC WALL:` remain as English Word text in a translated Russian book body | Keep the labels outside MathType, but localize them as ordinary target-language Word text unless the source intentionally uses an untranslated technical token. Render-check that the longer localized label still fits the formula row and does not push the formula/number out of alignment. |
| Localized formula labels duplicated below the display | A source-language formula-table label is localized in a later standalone paragraph while the original English label remains in the formula row | Treat this as one move/replace operation: localize the Word-label run at the source formula-flow position, then remove the standalone translated duplicate. Do not leave both the localized duplicate below and the source-language label in the table. Render-check the affected display after deletion because page flow can change. |
| Stale manifest status | Project's release manifest reports `status: PASS` (or equivalent) but the chunk has unresolved skill defects | Reconcile manifest after every cleanup pass; project-defined status values must map honestly to the gate state the chunk actually passed (full skill review with render evidence is a different state than a no-Word cleanup pass or a writer-only state; do not coalesce them) |
| Stale manifest source path | Manifest `source_pdf` points to a missing file or to a different source PDF than the current chunk was reviewed against | Reconcile the manifest to the current repo-relative source PDF path before using it as provenance. A final release gate must fail closed on missing or mismatched source paths because it can make source-PDF comparison evidence non-reproducible. |
| Skipping the no-Word cleanup sweep before promote | Chunk lands in release as a writer-only state, with no body page label / inline punctuation / heading case / typography fixes applied | Always run the no-Word cleanup sweep against the project's defect-class catalogue (where one exists; otherwise enumerate the in-skill class summary as the minimum) before promote; chunks with a skipped sweep stay flagged for follow-up |
| Render gate skipped after no-Word edits | Structural audits show "structurally clean" but there is no render evidence that page-flow, table-merge, and figure-grouping behave correctly | Render at least one representative chunk through Word `ExportAsFixedFormat` and compare against the source PDF before claiming a render-validated PASS |
| Accents or primes drift | Prime, hat, bar, transpose, conjugate, or overline attaches to the wrong base or index | Rebuild the MathType script/accent template and re-render |
| Hat rendered as loose mark | A unit vector or hatted variable shows a small detached hat instead of a single accented MathType symbol | Use a MathType accent-template slot or explicit MathML `mover accent="true"` with the base inside the slot |
| Template symbol assembled from loose glyphs | Hat, tilde, overline, arrow, radical, brace, bracket, determinant bar, norm, or matrix delimiter looks short, detached, miscentered, or attached to only one row/cell | Rebuild with the corresponding MathType template and place the whole intended expression inside the template slot |
| Replacement glyphs in math | Black diamonds, boxes, or wrong brackets appear in a formula or inline expression | Rebuild the affected MathType/styled math using explicit delimiter templates or source-faithful symbols and re-render |
| Partitioned matrix rules dropped | Source matrix/array has internal vertical or horizontal rules, but the rendered MathType object loses them after MathML/TeX import | Treat the rules as part of the matrix template; use a rendered one-object MathType donor with the internal rules present before transplanting |
| Visible formula-table rule | A horizontal line appears below a formula table even though the source has no rule | Remove inherited table/cell borders or table style artifacts and verify in rendered PDF |
| Bold vector becomes slanted | Latin vector or dyadic letters render bold italic after MathML import | Postprocess MathML to upright bold Latin or use a verified MathType TeX/manual sample |
| Existing OLE mutated in place | A formula appears duplicated, merged, or repeated after a targeted patch | Delete and replace the target OLE object, then set MathType data once |
| Partial donor drops keeper rows | A targeted replacement fixes one line but removes a neighboring source equation that was inside the old multi-row OLE | Inventory old OLE content against the source block first; build the donor for every source row still owned by that object and render-check surrounding rows |
| Wrong manual OLE copied | Reference object replaces target formula | Use one-object samples and exact mapping |
| No source-PDF comparison | Formula looks plausible but differs from PDF | Compare edited formula and nearby inline math against source PDF |
| Worker leaves Word COM render PDF in release folder (default path behavior) | Stray `.pdf` file appears next to the canonical `.docx` files in the release folder top level; not caught until manual inspection | Always pass an explicit `OutputFileName` under the repo's scratch area to `ExportAsFixedFormat`; never rely on Word's default save location; the review must run a stray-file check on the release folder |

## Validation Checklist

Before claiming PASS:

1. Render the affected final preview page and inspect it visually.
2. Compare the edited area against the source PDF.
3. Confirm body text, headings, captions, contents, and page numbers match the accepted book-style exemplar.
4. Confirm the Full-Text Coverage Gate and Translation Completeness Gate: rendered-candidate/source text coverage is recorded (with the character-ratio sanity check and any source-specific exception); every source-visible text unit has a target-language equivalent in source flow; any source-language token left in place is a recorded code/name/acronym/bibliography exception; and for sequential chunk work the queue/status artifact records current coverage evidence for this chunk before the next chunk is started.
5. Confirm display formulas are in borderless two-column tables with MathType left and ordinary text number right.
6. Confirm figures and captions are grouped in stable borderless tables or another accepted non-drifting structure, and that each touched figure image is complete: no source-visible axis, tick label, title, legend, frame edge, curve endpoint, or label is cropped by the media part, table, or drawing extent.
7. Confirm changed formulas are editable MathType OLE (`Equation.DSMT4`).
8. Confirm formula numbers, labels, captions, and prose are outside MathType.
9. Confirm MathType display and inline object sizes/baselines match the surrounding page.
10. Confirm vector, dyadic, field, unit-vector, and basis/test symbols match source bold/italic/upright style, and scalar components or coefficients were not accidentally vector-bolded.
11. Confirm every changed subscript, superscript, left script, prime, accent, and index grouping was checked against the source PDF, not inferred from a neighboring formula.
12. Confirm zero OMML and zero placeholders if touching a final DOCX.
13. Confirm inline math style and punctuation match the source PDF around the edited area.
14. Confirm no plain-text formula markers remain where source math requires MathType or styled Word math.
15. Confirm the current candidate, not a stale earlier PDF, was reviewed.
16. Confirm the generator did not self-accept the artifact as final PASS.
17. Confirm known systematic defects are not being propagated to later chunks.
18. Run the repo-relevant script syntax check or tests for changed scripts.
19. Run whitespace/diff hygiene checks such as `git diff --check`.
20. Confirm no Word/MathType automation process remains unless the user intentionally has Word open.
21. Confirm `word/styles.xml` Normal style font/size matches the accepted exemplar (Class L typography normalization) and no chunk-specific pandoc styles were lost in the merge.
22. Confirm no heading paragraph (Heading1-5, Title, Subtitle) contains 8+ consecutive uppercase Cyrillic characters that should be in sentence case (Class M).
23. Confirm no body-flow `Страница NN` or `Страницы NN-MM` paragraphs remain (Class G page label residue).
24. Confirm the project's release manifest `status` reflects the actual gate state for the chunk: a full-skill-review-with-render-evidence value only after full source-PDF visual review with render evidence; distinct values for a no-Word cleanup pass, earlier no-Word states, and a writer-only state. Project-defined status tokens must map honestly to the gate state and must not coalesce these states.
25. Confirm the manifest's source PDF, final DOCX, and release PDF entries are repo-relative paths that exist and match the exact source/current release files used for the review. A stale manifest path is a gate blocker even when the rendered source PDF was found by another script.
26. Confirm the per-chunk skill review record (per the repo's review-record convention) names the OLE/media byte-identity check and links to the per-class audit artifacts for every class applied to the chunk. This is a **review-record completeness check**, NOT the exhaustive per-class sweep — see the project's defect-class catalogue per-chunk usage procedure for the full sweep.
27. If the chunk contains a code listing block (monospace runs `w:rFonts w:ascii="Courier"`/`Consolas`, `pStyle` resolving to a SourceCode/Verbatim family, or a printed listing caption such as `Листинг N` / `Program N` / `Listing N`) OR a substantive narrative reference to a verified program (the named program identifier, a specific line count, or a chapter-level discussion of an algorithm that has a corresponding verified-source directory in the project), confirm a 3-line provenance block is present in the QA artifact or another accepted non-printing trace surface, citing: (a) verified source path with compile invocation, (b) input artifact path (if the program reads input), and (c) output path with a one-line numeric fingerprint from the output file. Mechanical test: if a chunk's prose names a verified-source algorithm by name, line-count, filename, or language AND a matching verified-source directory exists in the repo, the chunk has a substantive narrative reference and this item applies; otherwise, with no listing block present, it is vacuously satisfied. Confirm the final book-body DOCX/PDF does not visibly print provenance/process tokens such as `Verified source:`, `OCR_UNCERTAIN`, `OCR_WARNINGS`, `Source book page`, `Replaces scanned PNG`, `listing_ocr_cleaned`, repo `code/...` paths, `Class N`, `Примечание к листингу`, or `Рабочая реконструкция...` unless those strings are actually in the source PDF (Class N / Class V; this skill's program-listing provenance requirement).

28. If the source PDF contains a program listing, pseudocode, BASIC fragment, or printed console/output block, confirm the rendered candidate preserves the source-like monospaced block: one source line per visual line/paragraph where possible, source indentation and aligned columns preserved, no justified-prose flattening. A trivial listing with no verified-code counterpart may skip item 27 provenance, but it cannot skip this layout check.

29. Confirm the repo's release folder contains only its canonical release files (and the rendered-PDF subfolder where the variant produces one). List the release folder and confirm zero `.pdf`, `.tmp`, `~$*`, `.bak`, or other non-canonical files at the top level. If any stray is found, move it to the repo's scratch area before claiming PASS.

30. If any Word COM `ExportAsFixedFormat` render was performed during this work session, confirm the review note declares: `Render output path: <explicit .scratch path> (NOT release folder)`. A review note that omits this field or records only "PDF exported" without a path is incomplete for any session that touched Word COM rendering.

## Defect Class Index

The minimum defect-class catalogue this skill enforces. Where the project maintains its own catalogue (commonly `docs/translation-defect-checklist.md`), that document is authoritative for pattern evidence and confirmed examples (and for any project-specific class numbering beyond this summary); the table below is the in-skill summary the worker keeps front-of-mind during a pass. Concrete chunk/table identifiers in the examples are illustrative, not part of the portable rule.

| Class | Surface | Repair lane |
|---|---|---|
| A | Inline punctuation/operators around MathType OLE, including missing separators between adjacent inline OLE objects | no-Word XML, surgical text-run edits |
| B | Bilingual name corruption (Latin + Cyrillic hybrid) | no-Word XML, full Latin or full Cyrillic |
| C | Word-order calque / OCR garbage in prose | no-Word XML |
| D | Greek letter substitutions in prose (`p` vs `ρ`, `v` vs `ν`, `u` vs `μ`) | no-Word XML for prose; writer-bound for OLE internals |
| E | Inner-product brackets `⟨ ⟩` vs `( )` | no-Word XML for prose; writer-bound for OLE |
| F | Unit-vector hat / dyadic bar / accent loss | writer-bound OLE rebuild |
| G | Page count drift and body-flow page labels (`Страница NN`) | no-Word XML for labels; writer/layout for page drift |
| H | Multi-number formula cell merging in number cells | **Pattern A1** (rows have independent OLEs, row order matches source PDF; defect is stacked labels only): no-Word XML label distribution. **Pattern A1+swap** (rows have independent OLEs but are in inverted order vs source PDF): no-Word XML row-content swap + label redistribution. **Pattern B** (single OLE encodes N equations that should be separate source rows): writer-bound OLE rebuild. **Accepted multi-line display**: one editable MathType OLE plus multiple ordinary Word numbers is allowed when source PDF shows one aligned multi-line display and rendered number alignment is correct. See the project's Class H sub-classification (where one exists) for how to distinguish. |
| H-A1 | Multi-row formula table where each row already has its own OLE and row order matches source PDF; labels stacked in row 0 only | no-Word XML, distribute labels one per row; OLE objects unchanged |
| H-A1-swap | Multi-row formula table where each row has its own OLE but rows are in inverted order vs source PDF; labels stacked in row 0 (Pattern A1 surface), but plain label distribution would mis-pair labels with formulas | no-Word XML, swap left-cell paragraph contents between rows, then redistribute labels per source PDF order; OLE objects unchanged |
| H-B | Single OLE/WMF encodes N source equations together that should be independent display rows | writer-bound OLE rebuild; no XML split can produce separate editable formulas. Do not apply H-B to a source-faithful aligned multi-line display whose intended form is one editable MathType object with multiple ordinary Word numbers. After the split, source-check adjacent prose connectors and keep them as localized Word text outside MathType in the same source-flow row/cell as the display they introduce; do not leave a connector orphaned at a page break |
| I | Figure / caption ungrouping (top-level drawing + separate caption paragraph that is NOT a formula raster) | no-Word XML, wrap in borderless 1-col 2-row table. **First verify the image content is an actual figure/diagram — see I sub-rule below.** |
| I-sub | Raster formula masquerading as ungrouped figure: `<w:drawing>` references a PNG containing a formula display, not a figure | writer-bound formula OLE rebuild (MISSING_OLE lane), NOT figure-grouping. Read the PNG before classifying |
| J | English `<mtext>` inside MathType OLE payload (`otherwise`, `at nodes`, `on S_0`) — wrong label is inside OLE | writer-bound OLE rebuild |
| K | Source-correct equation reference numbering in prose | no-Word XML, requires source-PDF cross-check |
| L | Typography normalization against exemplar `word/styles.xml` (book-style serif body and sized heading hierarchy derived from the exemplar; e.g. TNR 11pt body, Title 16pt, Heading1 14pt, Heading2 12pt, Heading3 11.5pt, Subtitle 12pt as an illustrative profile — the project catalogue holds the full per-style values) | no-Word XML, full exemplar styles merge |
| M | Heading case normalization (Russian sentence case, no ALL CAPS) | no-Word XML, multi-run text edit |
| N | Code listing provenance pointer to the project's verified-source root | no-Word XML, adjacent caption / sidenote |
| N-layout | Program listing / pseudocode / BASIC / console-output visual fidelity: source monospaced blocks flattened into justified prose, merged lines, lost indentation/columns, or rendered as tiny/faint low-contrast code with mostly unused page area | no-Word XML layout/text repair of listing style/spacing/table geometry; source-PDF visual comparison; use an explicit source-image exception only when OCR/editable reconstruction is unsafe; MathType writer is out of scope unless an independent formula defect exists |
| O | Cross-page row spillover from formula/table rows (rotated `btLr` cell content, multi-row OLE display whose row height overflows the page break, leaving floating glyph fragments at the top of the next page) | writer-bound (page-setup change, landscape `sectPr`, OR matrix OLE split); `<w:cantSplit/>` alone is insufficient |
| P | Plain-text indexed math in captions/body (literal ASCII underscore `n_s` in a single `<w:r>/<w:t>` instead of subscript run with `<w:vertAlign w:val="subscript"/>`) | no-Word XML, run split + `<w:vertAlign>` |
| Q | Latin / OCR variable-label swap in prose adjacent to formulas (e.g., `f_` instead of `h_`, OCR-confused with phonetic neighbor); distinct from Class J because the swap is in prose `<w:t>`, not inside the OLE payload | no-Word XML, single-occurrence text substitution |
| R | Prose numeric / OCR corruption: digit `0` rendered as empty parentheses `()` in a prose `<w:t>` run (e.g., `y =()` for `y = 0`, `=().265` for `= 0.265`); distinct from Class A (no OLE follows) and Class P (no subscript/superscript context) | no-Word XML, text-run substitution after PDF verification |
| S | Investigation discipline — audit findings integrity: (S1) verify source PDF before any merge-table repair; (S2) source-map repair does not close release OLE blocker; (S3) canonical supersession note required after false-positive reversal | Governance: add `superseded_by`/`reason` fields to audit JSON; label reversed Markdown findings explicitly before closure |
| T | Missing text — a source PDF paragraph contains N sentences but the translation has fewer than N; specific sentence(s) absent (distinct from Class C calque and Class Q/R single-char OCR corruption) | no-Word XML (insert translated paragraphs at the correct anchor); source-PDF paragraph-count comparison required before repair |
| U | Formula reference mismatch — translated prose cites the wrong equation number or figure label vs source PDF (e.g., source `(43b)` rendered as `(43)`, or a visually similar figure label such as `4g`/`49`/`80b` guessed from OCR instead of the current source render) | no-Word XML text substitution only after current source-PDF visual cross-check; grep prose for `\((\d+[a-z]?)\)` and `Fig\.\s*\d+[a-z]?` patterns; if older QA notes conflict with the current source render/newest ledger, mark the old note stale and do not apply it |
| V | Added text not in source — translated DOCX contains sentences or process-metadata annotations (e.g., `Verified source:`, `OCR_UNCERTAIN`, `OCR_WARNINGS`, `Source book page`, `Replaces scanned PNG`, `listing_ocr_cleaned`, repo `code/...` paths, `Class N`, `Примечание к листингу`, `Рабочая реконструкция...`) absent from the source; translator over-generation or provenance-metadata leak into book body. Provenance belongs in QA/manifest/non-printing trace surfaces, not visible release body. Publication-safety flag required. | no-Word XML deletion of unauthorized text; preserve listing/source fidelity separately; triggers publication-safety scan before release |
| W | Bilingual label residue — source-language labels or full-word terms remain inside translated prose or formula-table Word-label flow where the target language should be used (e.g., "Region 4", "For TM-to-y:", "At y = h4:", `ELECTRIC WALL:`, `MAGNETIC WALL:`); distinct from Class B (hybrid Latin/Cyrillic within a single author name token) | no-Word XML text substitution; grep prose/table-label runs for source-language sequences (2+ chars) surrounded by target-language text outside math contexts |
| X | Paragraph order — translated paragraphs in a different sequence than the source PDF, or caption merged with the preceding body paragraph. Caveat: sometimes intentional — verify before repair | no-Word XML paragraph move or split; verify source-PDF logical flow before repair; check translator intent |
| Y | Truncated heading — section heading text cut off mid-word or mid-phrase in the translated DOCX (distinct from Class M which is a case defect) | no-Word XML heading-text extension to match the full source-PDF heading |
| Z | Semantic reversal mistranslation — the translation states the opposite of the source claim (e.g., "magnetic field transverse" rendered as "electric field transverse"). HIGH severity always. Require translator/domain-expert review before committing repair | no-Word XML text substitution after source-PDF verification AND translator/domain-expert review; never commit repair without expert sign-off |

## Terms and Abbreviations

- DOCX: Microsoft Word document format.
- MathML: Mathematical Markup Language used as an interchange format for equations.
- MathType OLE: editable MathType equation object embedded in Word.
- OLE: Object Linking and Embedding; Word's container mechanism for embedded equation objects.
- OMML: Office Math Markup Language; Word's native equation format, not the final target here.
- PDF: Portable Document Format; the source and rendered preview authority for visual checks.
- QA: Quality Assurance; verification against the source PDF and accepted exemplar.
- REVISE: result state meaning the artifact must be corrected and checked again.
