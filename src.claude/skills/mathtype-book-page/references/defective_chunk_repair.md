# Defective Chunk Repair Workflow

Use this reference whenever a MathType book-page chunk is already known or suspected to be defective. The goal is to repair the chunk, not to produce another mechanical conversion.

## Admission

Before editing, collect the current facts:

| Required fact | How to obtain |
|---|---|
| Source PDF and affected source pages | repository runbook, file search, rendered source pages |
| Current final DOCX/PDF candidate | final output directory or current task input |
| Existing validation and review artifacts | repository validation folder, reports, handoff queue |
| Current structural defects | repo structural audit if present, otherwise inspect DOCX XML for formula tables, OLE, OMML, placeholders, images, captions, and plain math markers |
| Current visual defects | render the current candidate or inspect existing current render |
| Accepted exemplar | accepted prior page/chunk or source PDF style if no exemplar exists |

The source PDF is the authority for formula content and source-specific layout. The accepted exemplar supplies reusable DOCX formatting patterns only; it does not override the source PDF. If the source page cannot be rendered or visually checked, the repair cannot progress beyond `REVISE: intake incomplete`.

If any required fact is missing, the output is `REVISE: intake incomplete`, plus the exact missing fact. Do not start Word/MathType writer to compensate for missing intake.

## State Classification

Classify the chunk before choosing a repair path.

| State | Symptom | Allowed next action |
|---|---|---|
| Missing final candidate | No final MathType DOCX/PDF exists | Build only after source-map and payload preflight pass; result is candidate until reviewed |
| Mechanical candidate | OLE counts and PDF exist but layout/source review is incomplete | Run structural/visual/source-PDF review and repair lanes; do not call it PASS |
| Full-text coverage defect | Candidate contains formulas/figures/tables but skips source prose, problem text, footnotes, captions, or page-continuation text | Coverage lane first; do not start the next chunk or claim PASS |
| Source-map defect | Missing/wrong formulas, wrong order, text in MathML, wrong split/merge before OLE | No-Word source-map repair, prepare-only, payload audits, checklist update |
| Translation/prose-completeness defect | Source-visible headings, body text, captions, labels, lists, reference text, formula connectors, or conditions are missing, untranslated, duplicated with source text, OCR-like, or semantically wrong | No-Word XML/source-owner translation repair; render affected pages and compare source PDF; do not run MathType conversion for unrelated formulas |
| Local formula/template defect | A small set of formulas has bad integrals, braces, hats, delimiters, style, indices, or gaps | One-object sample or targeted OLE replacement for only those formulas |
| Inline-math defect | Plain caret text, wrong scripts, punctuation drift, missing inline MathType or styled Word math | Split prose from math, repair inline OLE/styled runs, render affected lines |
| Layout/typography defect | Wrong font/size/spacing/justification/headings/page count | DOCX style/layout repair; no MathType conversion for unrelated formulas |
| Figure/caption defect | Figure and caption are separate blocks, can drift, or the rendered caption/legend is clipped | Group image plus caption in stable Word structure; caption stays editable Word text; verify the complete rendered caption against the source |
| Formula-table defect | Formula/number cells merged, extra cells, adjacent displays merged, number inside MathType | Repair table XML/layout, insert separators, keep number as ordinary text |
| Systematic pipeline defect | Same wrong pattern appears in multiple chunks or was found in the generator | Freeze later chunks, repair the rule/script on one example, render that example, then resume |

If more than one state applies, pick the highest upstream blocker first: source-map, then full-text coverage, then translation/prose completeness, then formula/template, then inline, then table/layout/figure, then final review.

## Repair Lanes

### Coverage Lane

Use when the candidate may be formula-complete but not text-complete. This is the quantitative omission lane; it is complementary to the Translation / Prose Completeness Lane (which checks that each visible unit is translated and in source flow) and does not replace it.

1. Render or locate the current source pages and candidate pages.
2. Build a page-by-page source ledger: headings, prose anchors, problem ranges, footnotes, captions, table titles/bodies, figure numbers, and formula numbers.
3. Extract text from the rendered candidate PDF and compare candidate/source character counts as a falsification check. For normal prose-heavy chunks, a rendered-candidate/source ratio below `0.85` is `REVISE` unless the artifact records a source-specific exception and visual reconciliation. A high ratio is only a sanity signal, not acceptance.
4. Identify exact missing source spans by page and local anchor, especially text before the first formula, between adjacent formulas, after the last formula, after figures/tables, at page breaks, and in problem lists.
5. Patch the source-map/writer content so the missing prose is represented as Word text while formulas remain editable MathType OLE.
6. Rebuild or patch the candidate, render it, and repeat the coverage and visual checks.

Exit: `CANDIDATE for coverage repair` after the repaired candidate renders, or `PASS for coverage ledger only` when no candidate was changed and final review is still pending.

### Source-Map Lane

Use when formula content, ordering, payload split, or text/prose separation is wrong before OLE insertion.

1. Patch the source-map owner or mapping data, not the final DOCX only.
2. Run prepare-only/no-Word generation.
3. Run payload audits for malformed MathML/OMML and text inside math.
4. When source prose connects two equivalent display forms, split the MathType payload into multiple placeholders and keep the connector as ordinary Word text in the formula cell. Do not keep connectors such as `or`, `where`, `if`, or localized equivalents inside one MathType object.
5. Regenerate formula checklists if the formula set changed; prepare-only output alone is not enough evidence that the review checklists saw inserted split formulas.
6. Do not run writer until the changed formulas have source-backed content and audits are clean.

Exit: `PASS for source-map repair only`, with final chunk still `REVISE`.

### Dense Matrix / Import-Stall Lane

Use when Word/MathType stops on a broad matrix, rotated display, dense `mtable`, or another oversized display before a `saved` event is written.

1. Preserve the stall evidence: command, stdout/stderr length, progress log ending at `before_set_mathml`, failed UID, and owned processes stopped.
2. Treat clean prepare-only and payload audits as insufficient. They prove XML validity, not MathType importability.
3. Compare the source PDF region and identify the visual invariant to preserve: row order, bracket continuity, delimiter size, internal matrix/array partition rules, equation-number ownership, and any rotated layout.
4. Rebuild the source map into smaller source-faithful display payloads or a verified editable MathType sample. Do not retry the same one-object payload.
5. Keep numbers, prose labels, and conditions outside MathType unless the source mathematically requires them inside the formula.
6. Run prepare-only and chunk-local payload audits.
7. Run only a bounded writer probe that crosses the repaired UID and any inserted split UIDs. Start a full writer only after the bounded probe succeeds.

Exit: `PASS for dense source-map repair only` after the no-Word checks, or `CANDIDATE for writer retry` only after the bounded probe converts the repaired region.

### Targeted OLE Lane

Use when a small number of existing MathType objects render incorrectly.

1. Create or reuse a one-object editable MathType sample for fragile templates.
2. Make a scratch copy of the current candidate.
3. Delete and replace only the affected OLE objects; do not mutate populated OLE objects in place.
4. Leave unrelated formulas untouched.
5. Render affected pages and compare against the source PDF.

Exit: `CANDIDATE for targeted OLE repair`, not final PASS.

### Inline-Math Lane

Use when body text contains formula-like text or inline objects with wrong style/baseline/punctuation.

1. Compare the sentence against the source PDF.
2. Keep prose and punctuation as Word text unless mathematically part of the expression.
3. Place punctuation on the source-correct side of each inline object. A period or comma that closes the expression must follow the inline MathType object in Word text, not precede it in the previous text run.
4. Convert indexed, accented, vector, fraction, relation, summation, or integral inline expressions to inline MathType unless styled Word text is visually identical and stable.
5. Verify baseline, line spacing, and punctuation after render; text extraction alone can omit inline objects and conceal misplaced punctuation.

Exit: `CANDIDATE for inline repair`.

### Translation / Prose Completeness Lane

Use when the translated chunk has correct-looking formulas but the surrounding book text is incomplete, untranslated, duplicated, or semantically wrong.

1. Compare the rendered source PDF and current candidate by visible text units: headings, body paragraphs, lists, captions, table labels, formula-table Word labels, formula connectors/conditions, references, footnotes/endnotes, listing/output captions, and contents rows.
2. Check the prose spans between neighboring display formulas separately from the formulas themselves. A formula-clean page is still `REVISE` if explanatory sentences, assumptions, boundary descriptions, or sampling/definition text between displays were skipped, compressed away, or left semantically unchecked.
3. Classify source-language tokens before editing. Preserve code, command lines, file names, numeric output, author names, standard acronyms, mathematical notation, and recorded bibliography-title exceptions; translate accidental source-language prose and formula labels.
4. Scan the candidate text and rendered page for OCR/PDF-flow residues before acceptance: bracketed references must be real source references (`[24]`, not `{24|` or `{24}`), intervals must use the source delimiters and symbols (`[a,∞]`, not pipe/angle substitutes), and source-page hyphenation must not survive as separate translated paragraphs.
5. Check inline MathType function names in captions and prose as formulas, not as decoration. Source `sin`, `cos`, `cosh`, `exp`, etc. must render as upright/operator function names with source spacing, not as glued italic variable letters.
6. Check numeric powers, tolerances, asymptotic orders, and accuracy claims in prose/captions as inline math. Source `10^{-6}`, `10^-7`, `O(r^{-2})`, and similar expressions must not degrade to OCR-like punctuation, parenthesized fragments, or plain text with lost exponents; restore any truncated surrounding sentence before inserting targeted inline MathType/styled math.
7. Repair the translation owner or source-map/generator block when one exists. Candidate-only XML text replacement is not durable if the next build can regenerate the same untranslated text.
8. Keep formula symbols and inline math at the source positions while translating the prose around them. Do not move punctuation away from inline MathType/styled math.
9. After a connector/condition is moved or localized, scan neighboring paragraphs/tables for stale duplicate prose/OLE blocks that still render the old connector. Remove only that stale block plus its relationships/media, and replace only the affected formula OLE if the old object still contains prose residue.
10. Render affected pages and visually compare the repaired text flow against the source PDF.
11. Write a translation ledger in the handoff: source pages/crops checked, text regions covered, source-language exceptions intentionally preserved, and unchecked/suspect regions. A formula-only or layout-only artifact with no ledger exits as scoped `CANDIDATE` at most, never final `PASS`.

Exit: `CANDIDATE for translation/prose repair`; final chunk remains `REVISE` until formula, inline, layout, figure/caption, and translation gates all pass.

### Layout And Figure Lane

Use when the document looks unlike the book or figures can drift.

1. Normalize body text, headings, captions, spacing, indents, and page markers against the exemplar/source.
2. Group each figure plus caption in a stable Word structure, usually a borderless table.
3. Keep captions editable as Word text.
4. If the figure bitmap contains source-caption residue or a caption fragment while the translated caption is missing or separate, clean/re-crop only the media, rebuild the caption as editable Word text with source-faithful inline math/units, and remove only the stranded caption paragraph after its content is merged.
5. Check the rendered caption row for clipping and page/column splitting. The figure lane remains `REVISE` if a table row, fixed frame, or page-flow repair hides later caption lines such as material/substrate/legend text, or if the next rendered page begins with a caption tail separated from the image.
6. After the caption itself is fixed, source-check the next body paragraph and any numbered/bulleted list on the same spread. If body prose was swallowed into the caption table or a list item was merged/dropped, split it back into ordinary Word body/list paragraphs before promotion.
7. Do not touch formula OLE objects unless the layout defect is inside the formula table.

Exit: `CANDIDATE for layout/figure repair`.

### Formula-Table Lane

Use when display formula structure is wrong even if the PDF looks acceptable.

1. Keep every visible display formula row as formula cell plus number cell.
2. Move all numbers, prose labels, and captions out of MathType.
3. Split accidental adjacent table merges with a normal separator paragraph or equivalent stable structure.
4. Reinspect DOCX XML cell counts after Word save.
5. For XML-only DOCX package edits, validate semantic Word-openability, not just ZIP/XML parsing: `mc:Ignorable` prefix tokens must be declared, range markers such as bookmarks/comments/permissions must be balanced or unchanged from a known-openable base, typed OpenXML attributes must not be empty strings (`w:before=""`, `w:after=""`, `w:val=""` on enum elements), `sectPr` must stay final, table cells must keep terminal block content, and OLE/image relationships must resolve.
6. If a textless paragraph/table immediately after a display formula contains only drawing/image relationships and renders as a cropped duplicate formula tail, verify the source PDF has no corresponding extra display, then remove only that orphan block and its image relationship/media part. Do not rebuild MathType or replace the real formula OLE for this defect class unless the formula itself is also wrong.

Exit: `CANDIDATE for formula-table repair`.

### Full Writer Lane

Use only when explicitly justified:

- initial final MathType candidate does not exist;
- broad source-map changes affect many formulas;
- the OLE set is stale or structurally inconsistent across most of the chunk;
- targeted repair was evaluated and recorded as unsafe.

Before launch, record the justification, affected chunk, expected formula count, non-Word blockers already closed, batch/session limit, and cleanup command for Word/MathType processes. A full writer result is still only a mechanical candidate until rendered source-PDF review passes.

### Process-Ownership Lane

Use this rule whenever workers run in parallel with a writer or render job.

1. A worker may clean up only the Word, MathType, LibreOffice, Python, or PowerShell processes that it started, or processes that are demonstrably stale/orphaned after their owner has finished.
2. A worker must not kill another active lane's process to keep its own no-Word lane clean. If an active external writer is found, record the owner/command if visible and proceed with no-Word work, or return `REVISE/BLOCKED` if the active process makes safe work impossible.
3. If process ownership is ambiguous, prefer non-interference: report the ambiguity and ask the integration owner to decide.
4. If a writer attempt exits with a negative code, missing summary, or no traceback after parallel cleanup activity, classify that attempt as contaminated evidence and rerun only a bounded probe under clean ownership before diagnosing formula content.

## Required Repair Artifact

Every worker must leave a compact artifact with these fields:

| Field | Required content |
|---|---|
| State | One of the classified states above |
| Lane | The single repair lane used |
| Changed | Exact formulas, inline objects, pages, paragraphs, tables, or figures touched |
| Untouched | Important accepted formulas/pages deliberately left unchanged |
| Coverage | Page-by-page source coverage result, including any text-count sanity ratio and missing/proven source spans |
| Rendered | Candidate PDF/pages rendered after the latest edit |
| Source comparison | Source PDF pages/regions compared |
| Remaining blockers | Empty only for final review handoff; otherwise list concrete REVISE items |
| Verdict | `CANDIDATE`, `REVISE`, or scoped `PASS for ... only` |

No artifact may say final `PASS` unless a separate current-render review has verified all skill surfaces.

## Stop Conditions

Stop and return `REVISE` instead of generating more output when:

- source-PDF formula content is ambiguous and no crop/render evidence is recorded;
- the same defect recurs after one repair attempt;
- a repair would require touching unrelated accepted formulas without justification;
- Word/MathType automation produces a warning, hang, or orphan process;
- the current lane discovers an upstream source-map defect.

## Terms and Abbreviations

- DOCX: Microsoft Word document format.
- MathML: Mathematical Markup Language used as an equation interchange format.
- MathType OLE: editable MathType equation object embedded in Word.
- OLE: Object Linking and Embedding.
- OMML: Office Math Markup Language, Word's native equation format.
- PDF: Portable Document Format.
- QA: Quality Assurance.
- REVISE: gate state meaning repair and re-review are required.
