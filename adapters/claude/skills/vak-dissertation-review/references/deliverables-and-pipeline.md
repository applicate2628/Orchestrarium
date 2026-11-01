# Deliverables and build pipeline

## The deliverable set

Cluster findings into advisory documents, one per dimension-cluster, each with severity labels and a
proof under every note. A proven clustering is **6 documents** (adapt the split to the work):

| Document | Dimensions (see `review-dimensions.md`) | Formulas? |
|---|---|---|
| Замечания к диссертации | J formulas, K numbers, O figures, A structure, L references, P numbering | yes |
| Замечания к автореферату | same dimensions for the автореферат + Q PDF/metadata + identity | yes |
| Новизна / ВАК-аудит | B/C новизна, D степень разработанности, E паспорт, F ВАК, M публикации, N патенты | no |
| Русский язык и плагиат | H язык, G заимствования, I внутренние повторы | no |
| Сводная рецензия | executive summary + достоверность table + priority recommendations | no |
| Предложения по усилению работы | constructive forward-looking "how to strengthen" | no |

Severity labels: `[КРИТ]` / `[ВАЖНО]` / `[КОСМ]` (red / amber / green). Tone: рекомендательный.

Keep the canonical artifacts as **generators** (code that emits the docx), not hand-edited docx —
edit the generator and rebuild, never the output file (it is regenerated and edits are lost). Keep
plain-text working copies of the dissertation/autoreferat (per chapter) and the список литературы
beside the generators for finding-anchoring and for grep-verifying the build.

## Reference toolchain (one proven way — adapt freely)

The skill was developed with this toolchain; it is a recommendation, not a requirement. Any stack that
produces editable docx with real formulas and proof anchors works.

- **Layout:** a docx library (e.g. docx-js / python-docx). Define small helpers once — a run, a
  justified body paragraph, headings, a table, bullets/numbered — and a sub/superscript parser so
  `M_i`, `P_вх`, `Re ε` render correctly in body text. Tables: horizontal rules only (top/bottom + a
  rule under the header), no header fill, no verticals/grid. One unified font and size palette
  (body ≈ 11 pt; headings/title larger; footer smaller).
- **Formulas:** emit **editable** equations (e.g. MathType `Equation.DSMT4` OLE, or native OML/LaTeX),
  not images, so the author can edit them. A clean pattern: the generator writes text placeholders
  plus a `key → LaTeX` map; a converter swaps each placeholder for an OLE object. Scale the OLE to the
  body size (scale ≈ body_pt / native_pt) and width-cap display formulas.
- **Borders:** a post-pass that applies the horizontal-rule grid to every table.

### Transferable gotchas (if you use a docx-js + MathType OLE pipeline)

Each cost a debugging cycle and generalizes:

- If a generator **regenerates its formula map from inline source on every run**, edit the formula
  source in the generator, never the generated map JSON (it is clobbered on regen). If a generator
  does NOT regenerate its map, edit that JSON directly. Know which is which.
- **Placeholder keys that sit inside body text must avoid characters the sub/superscript parser eats**
  (e.g. `_`), or the placeholder breaks. Keys built outside the parser (display equations) are immune.
- A Word-COM converter needs **native absolute paths**; relative/forward-slash paths fail. Build those
  absolute paths by resolving a repo-relative scratch path to absolute **at call time** — do not hardcode
  a workstation path, and do not let the resolved absolute path (it carries a username / drive letter)
  land in a generated review doc, a committed generator, or a session log. Keep it scratch-local.
- Regenerating a base docx **wipes its OLE** — re-run the formula converter after any map/base change;
  OLE lives only in the final.

## Build & verify

1. Run the generators to produce the base docx.
2. Convert formula placeholders to editable objects (formula-bearing documents only).
3. Apply the table-border pass to every document with tables.
4. Copy the finals to the delivery folder.

**Verify the build — do not skip:**

- Extract each output's text (unzip `word/document.xml`, strip tags) and **grep the new markers** —
  a defect class is closed when its grep count equals the expected count (convergence by
  class-exhaustion, `verification-discipline.md` §8).
- Confirm **0 unresolved placeholders** and the expected **editable-formula count** in each
  formula-bearing document.

## Environment notes

Use the libraries the chosen toolchain needs (e.g. Node + a docx lib; Python + a Word-COM bridge +
MathType on Windows for OLE). Render-check formulas with a PDF rasterizer (`pdftoppm`); extract text
with a PDF/zip extractor. Keep the pipeline on a persistent disk (not a volatile RAM/temp drive).
Cyrillic search: Bash `grep`, not PowerShell `Select-String`; `pdftotext` mangles Cyrillic — grep
Latin tokens/digits only.

Keep all intermediate artifacts — extracted plain-text chapters, the список-литературы dump, `pdftoppm`
render crops, generated base docx, and any Word-COM export PDF — under a repo-local `.scratch/` working
area, never beside the source PDF or in the delivery folder. Any Word-COM `ExportAsFixedFormat` / render
call must pass an explicit absolute `OutputFileName` under that scratch area (the default path saves next
to the source and contaminates the delivery boundary). Copy only the final review docx set to the
delivery folder.
