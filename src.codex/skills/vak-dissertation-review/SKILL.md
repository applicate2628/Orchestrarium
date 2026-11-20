---
name: vak-dissertation-review
description: "Диссертация, автореферат, рецензия, нормоконтроль, ВАК; VAK dissertation review."
---

# Рецензирование диссертации и автореферата (ВАК)

Methodology for reviewing a Russian dissertation + autoreferat ahead of a scientific-degree
defense. The output is a set of **рекомендательных** (advisory) review documents — never a
go/no-go verdict. You are an assisting reviewer / нормоконтролёр; the qualification decision
belongs to the диссертационный совет and ВАК.
The review includes **нормоконтроль**: formatting control and normative-compliance control.

This file is the map. Each `references/` file holds the depth — read the relevant one when you
reach that part of the work; don't load all of them up front.

- `references/verification-discipline.md` — the non-negotiable verification rules (read FIRST).
- `references/review-dimensions.md` — the full checklist: what to inspect, dimension by dimension.
- `references/vak-norms.md` — ПП РФ № 842, ГОСТ Р 7.0.11, ГОСТ Р 7.0.5, паспорт специальности,
  publication criteria. These change — verify the current redaction before relying.
- `references/deliverables-and-pipeline.md` — the 6-document deliverable set and the docx-js +
  MathType + table-borders build pipeline, with its gotchas.

## What you produce

Return the requested advisory findings with severity labels and proof under every note. For a full review, the reference deliverable set is **6 documents**; use the document-build pipeline only when DOCX output is requested:

1. **Замечания к диссертации** — formulas (render-checked), numbers, figures/tables, structure,
   references, numbering.
2. **Замечания к автореферату** — same dimensions for the автореферат + PDF/metadata passport +
   автореферат↔диссертация identity.
3. **Новизна / ВАК-аудит** — научная новизна (form + substance), паспорт-специальности fit,
   ПП 842 compliance, publication/patent registry, **§ степень разработанности (ДО → приращение)**.
4. **Русский язык и плагиат** — language proofread + borrowings (заимствования) + internal repeats.
5. **Сводная рецензия** — executive summary + достоверность table + priority recommendations.
6. **Предложения по усилению работы** — constructive, forward-looking "how to strengthen" (outside
   the defect review).

Tone throughout: рекомендательный. Phrase findings as "рекомендуется…", not "обязан/провал".
Mark severity `[КРИТ]` / `[ВАЖНО]` / `[КОСМ]` (red / amber / green).

## Non-negotiable discipline (the hard-won rules)

These exist because each was learned by getting it wrong once. Full detail + the war stories are in
`references/verification-discipline.md`; the short form:

- **Proof under every note.** No finding ships without a verifiable anchor: `страница`, `формула
  (N.M)`, a named норма (ГОСТ/ПП пункт), a `DOI`/URL, or an instrumental check. A note without a
  proof is a hypothesis, not a finding — verify it or cut it.
- **Judge formula STRUCTURE by visual render, never by the OCR/text layer.** Cyrillic + math text
  layers are garbled; misreading them produces false "errors". Render the page (`pdftoppm`) and look.
- **No fabricated references.** Every reference you propose (DOI, first source for a borrowing, a
  предшественник) must be one you actually retrieved this session. Target: zero fabrications.
- **Verify arithmetic with a calculator/Wolfram**, not by eye — units, conversions, percentages,
  trig. Cite the provenance triad for any computed value (formula/model · code path · inputs).
- **Prior-art separates OWN from OTHERS'.** A result already published by the author is legitimate
  priority (required for a defense), NOT disqualification; a result owned by others is. Always read
  the dissertation's own список литературы — predecessors are often cited there already.
- **Adversarial review-loop at the boundary.** Before merging any batch of findings into the
  documents, use an independent, permission-scoped reviewer (human or separately authorized agent)
  to refute findings and catch overclaims or wrong anchors. Never transmit private source material
  or invoke a paid runner just because this workflow calls for independence. Without a permitted
  independent check, mark findings provisional and say independent readiness remains unverified.
- **Cyrillic search via Bash `grep`, not PowerShell `Select-String`** (Select-String mangles
  Cyrillic and em-dashes). `pdftotext` also mangles Cyrillic — grep Latin tokens only.

## Workflow

1. **Ingest.** Extract the dissertation and autoreferat text (per chapter), and the список
   литературы, into plain-text working files. Locate the source PDFs for render checks.
2. **Pass per dimension** (see `references/review-dimensions.md`). For each finding, capture the
   anchor as you go — you cannot reconstruct proofs later.
3. **Verify before writing.** Render formulas, run arithmetic, confirm each reference exists, check
   each norm against its current text. Treat agent / external-model output as a hypothesis until you
   verify it.
4. **Boundary review-loop.** Use an available, authorized independent reviewer; leave independently
   unverified findings provisional and retain the exact source anchors.
5. **Assemble** the DOCX only when requested, via the generator pipeline (`references/deliverables-and-pipeline.md`):
   edit the canonical `gen_*.js` generators (never the output `.docx`), rebuild, add table borders,
   convert MathType placeholders to OLE for the formula-bearing lists, copy finals out.
6. **Verify any DOCX build.** Check extracted markers against the expected counts, confirm
   0 unresolved `@@` formula placeholders and expected OLE object counts, then render and inspect
   affected pages. Counts check build completeness, not factual correctness of findings.
7. **Reconcile and report.** State what was covered, what stays out of scope (see below), and keep
   the tone advisory. When the current task has `work-items/active/<slug>/`, persist only the
   canonical VAK artifact there and return concise result/provenance for the root
   `agent-runs.jsonl`; do not duplicate it in `.reports/` or `.plans/`. With no active work-item, a
   meaningful standalone VAK result MAY use one `.reports/YYYY-MM/` summary; do not create a
   `.plans/` duplicate.

## Scope honesty

Some checks are **principally outside** a text/render/web review and need closed access or the
author — say so plainly instead of faking them: a full Антиплагиат.ВУЗ run, re-running the work's own
simulations or experiments, regenerating experimental data, full closed-database registries
(РИНЦ/Scopus/WoS over every publication), and co-author contribution verification. For prior-art and
reference existence, close them to the *feasible* limit (existence, completeness, open-source
priority) and label the residual as `ASSUMPTION (UNVERIFIED)`.

If the dissertation carries personal data, unpublished or embargoed results, or third-party confidential
material, keep verbatim excerpts minimal — only as much as a finding's proof needs — and never copy them
outside the user's own delivery channel (no external service, ticket, or log).
