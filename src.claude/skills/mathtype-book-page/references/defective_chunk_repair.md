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
| Source-map defect | Missing/wrong formulas, wrong order, text in MathML, wrong split/merge before OLE | No-Word source-map repair, prepare-only, payload audits, checklist update |
| Local formula/template defect | A small set of formulas has bad integrals, braces, hats, delimiters, style, indices, or gaps | One-object sample or targeted OLE replacement for only those formulas |
| Inline-math defect | Plain caret text, wrong scripts, punctuation drift, missing inline MathType or styled Word math | Split prose from math, repair inline OLE/styled runs, render affected lines |
| Layout/typography defect | Wrong font/size/spacing/justification/headings/page count | DOCX style/layout repair; no MathType conversion for unrelated formulas |
| Figure/caption defect | Figure and caption are separate blocks, can drift, or the rendered caption/legend is clipped | Group image plus caption in stable Word structure; caption stays editable Word text; verify the complete rendered caption against the source |
| Formula-table defect | Formula/number cells merged, extra cells, adjacent displays merged, number inside MathType | Repair table XML/layout, insert separators, keep number as ordinary text |
| Systematic pipeline defect | Same wrong pattern appears in multiple chunks or was found in the generator | Freeze later chunks, repair the rule/script on one example, render that example, then resume |

If more than one state applies, pick the highest upstream blocker first: source-map, then formula/template, then inline, then table/layout/figure, then final review.

## Repair Lanes

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
3. Compare the source PDF region and identify the visual invariant to preserve: row order, bracket continuity, delimiter size, equation-number ownership, and any rotated layout.
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

### Layout And Figure Lane

Use when the document looks unlike the book or figures can drift.

1. Normalize body text, headings, captions, spacing, indents, and page markers against the exemplar/source.
2. Group each figure plus caption in a stable Word structure, usually a borderless table.
3. Keep captions editable as Word text.
4. Check the rendered caption row for clipping. The figure lane remains `REVISE` if a table row, fixed frame, or page-flow repair hides later caption lines such as material/substrate/legend text.
5. Do not touch formula OLE objects unless the layout defect is inside the formula table.

Exit: `CANDIDATE for layout/figure repair`.

### Formula-Table Lane

Use when display formula structure is wrong even if the PDF looks acceptable.

1. Keep every visible display formula row as formula cell plus number cell.
2. Move all numbers, prose labels, and captions out of MathType.
3. Split accidental adjacent table merges with a normal separator paragraph or equivalent stable structure.
4. Reinspect DOCX XML cell counts after Word save.
5. For XML-only DOCX package edits, validate semantic Word-openability, not just ZIP/XML parsing: `mc:Ignorable` prefix tokens must be declared, range markers such as bookmarks/comments/permissions must be balanced or unchanged from a known-openable base, typed OpenXML attributes must not be empty strings (`w:before=""`, `w:after=""`, `w:val=""` on enum elements), `sectPr` must stay final, table cells must keep terminal block content, and OLE/image relationships must resolve.

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
