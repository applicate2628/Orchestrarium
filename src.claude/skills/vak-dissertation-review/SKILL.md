---
name: vak-dissertation-review
description: Review a Russian dissertation (диссертация) and its autoreferat (автореферат) for a кандидат/доктор наук defense — нормоконтроль, научная новизна, ВАК-соответствие, заимствования, ссылки, публикации ВАК, степень разработанности. Use when the user names диссертация, автореферат, рецензия, замечания, нормоконтроль, защита, ВАК, диссовет, or asks to review an academic work for a Russian scientific degree.
---

# Рецензирование диссертации и автореферата (ВАК)

Methodology for reviewing a Russian dissertation + autoreferat ahead of a scientific-degree
defense. The output is a set of **рекомендательных** (advisory) review documents — never a
go/no-go verdict. You are an assisting reviewer / нормоконтролёр; the qualification decision
belongs to the диссертационный совет and ВАК.

This file is the map. Each `references/` file holds the depth — read the relevant one when you
reach that part of the work; don't load all of them up front.

- `references/verification-discipline.md` — the non-negotiable verification rules (read FIRST).
- `references/review-dimensions.md` — the full checklist: what to inspect, dimension by dimension.
- `references/vak-norms.md` — ПП РФ № 842, ГОСТ Р 7.0.11, ГОСТ Р 7.0.5, паспорт специальности,
  publication criteria. These change — verify the current redaction before relying.
- `references/deliverables-and-pipeline.md` — the 6-document deliverable set and the docx-js +
  MathType + table-borders build pipeline, with its gotchas.

## What you produce

A clustered set of advisory docx review lists (one per dimension-cluster), each carrying severity
labels and a proof under every note. The reference deliverable set is **6 documents**:

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
  documents, run an independent skeptic pass (a second model / agent) that tries to refute each
  finding and catch overclaim/wrong anchors. Merge only what survives.
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
4. **Boundary review-loop.** Send each finding batch through an independent adversarial gate; keep
   only confirmed, correctly-anchored items.
5. **Assemble** the docx via the generator pipeline (`references/deliverables-and-pipeline.md`):
   edit the canonical `gen_*.js` generators (never the output `.docx`), rebuild, add table borders,
   convert MathType placeholders to OLE for the formula-bearing lists, copy finals out.
6. **Verify the build.** Grep the extracted output text for the new markers (convergence by
   class-exhaustion: a class is closed when its grep count equals the expected count and stray
   classes are 0 — not after an arbitrary number of LLM passes). Confirm 0 unresolved `@@` formula
   placeholders and the expected OLE object counts.
7. **Reconcile and report.** State what was covered, what stays out of scope (see below), and write a
   session log. Keep the tone advisory.

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
