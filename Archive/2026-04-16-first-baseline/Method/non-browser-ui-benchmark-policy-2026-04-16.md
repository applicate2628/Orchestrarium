Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

Move the benchmark's primary UI reading onto a non-browser basis.

The earlier package mixed:

- static UI review,
- UI implementation quality,
- and browser-runtime / Playwright behavior

inside the same effective UI family.

That made the UI rows too dependent on the **old browser version** of `G08` even though that historical lane was really a browser-runtime note, not the best primary measurement for general UI quality.

## Accepted policy

| Rule | Accepted meaning |
|---|---|
| primary UI scoring must be non-browser | UI ranking should come from static artifacts, structural patches, accessibility review, and visualization review rather than browser automation success |
| active `G08` is now non-browser | the active `G08` fixture is now a static UI evidence lane and may inform primary UI scoring |
| legacy browser `G08` is supplemental | the earlier Playwright/browser parity artifacts remain valuable as browser-runtime evidence, but they no longer define the active `G08` lane |
| browser failures must not silently drag down non-browser UI rows | a model can be weak on Playwright and still be judged separately on static UX, accessibility, or UI patch work |
| browser automation is now an auxiliary note family | if we need browser evidence, we read it as its own operational surface rather than as default UI scoring |

## Primary non-browser UI evidence set

| Family | Role in UI scoring |
|---|---|
| `G08` | static UI evidence triage and minimal fix-order reasoning |
| `G07` | static UI structure and bounded patch work |
| `G09` | accessibility and UX review quality |
| `G10` | static visual, visualization, and decorative review quality |
| `G11`, `G13` | UI-adjacent path discovery and path recall for bounded worker tasks |
| `M08`, `M09` | bounded implementation and debugging quality |

## Supplemental browser evidence

| Family | Role |
|---|---|
| legacy browser `G08` | browser-runtime / Playwright evidence only |

## UI lane replacement map

| Old reading | New primary reading |
|---|---|
| accessibility / UX / UI-test | accessibility / UX static review |
| browser-backed visual review | static visual / visualization review |
| visual rows partly influenced by `G08` | visual rows should now use `G10` unless the question is explicitly about browser-runtime behavior |

## Current implication

| Topic | Accepted read |
|---|---|
| redesigned `G08` | active `G08` now supports primary UI reading because the test itself is no longer browser-bound |
| Gemini on UI | current Gemini browser weakness stays localized to the legacy browser note instead of contaminating the active non-browser UI rows |
| benchmark package | default baseline and role-spectrum surfaces should reflect this split |
| `G08` status | active `G08` is now static; the older browser parity files are retained separately as legacy auxiliary evidence |
