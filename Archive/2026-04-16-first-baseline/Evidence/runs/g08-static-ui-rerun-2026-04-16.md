Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

Redesign the active `G08` lane itself so it no longer depends on Playwright or a live browser, then rerun the lane on the currently reachable model set.

The older browser parity artifacts remain preserved as historical runtime evidence only:

- `runs/g08-browser-parity-hidden-fixture-2026-04-14.md`
- `runs/g08-browser-parity-current-2026-04-15.md`

The active fixture is now:

- `fixtures/role-gap-pack-2026-04-14/G08-static-ui-evidence/`
- `runs/fixture-G08-top-path.txt`

## Active fixture redesign

| Area | Active change |
|---|---|
| runtime dependency | removed Playwright and live browser dependence from the active `G08` lane |
| inputs | the lane now uses static `HTML`, `CSS`, interaction contract, captured state note, and misleading triage notes |
| harder discriminator | the fixture now forces separation between layout ownership, hidden-state behavior, inline-vs-modal semantics, and ranking-copy semantics |
| anti-cheat / decoy pressure | the fixture explicitly baits two weak responses: `z-index: 9999` and "make it a real modal" |

## Rerun cohort

| Row | Target | Current rerun status | Note |
|---|---|---|---|
| `X1` | `gpt-5.4` | `PASS` | strong static diagnosis with fix-order discipline |
| `X2` | `gpt-5.3-codex-spark` | `PASS` | clean and concise; slightly less exhaustive than the top rows |
| `X3` | native `opus 4.6max` | `PASS` | strongest current response |
| `X4` | `Claude China` | `SKIPPED` | user explicitly parked `X4` as temporarily unavailable after wrapper repair |
| `X5` | `gemini-3-pro-high-explicit` | `BLOCKED` | even a later sequential no-MCP rerun with a `900s` timebox still timed out without a completed answer; later user verification on a clean laptop environment points to upstream Gemini responsiveness rather than this workstation |
| `X6` | `gemini-3.1-flash-lite-preview` | `PASS` | the shorter earlier attempts timed out, but a later sequential no-MCP rerun with a longer timebox returned a full valid answer |
| `Q1` | `qwen3-max` | `BLOCKED` | `401 invalid access token or token expired` on current `qwen-oauth` path |

## Adjudicated quality read

| Row | Verdict | Why |
|---|---|---|
| `X3` | `PASS` strongest | catches all core blockers, explicitly rejects weak explanations, and also surfaces the `aria-expanded` vs `hidden` contradiction |
| `X1` | `PASS` strong | catches the same core blockers with strong file-based support and disciplined fix order |
| `X2` | `PASS` | catches the main blockers and weak explanations correctly, but with a slightly lighter explanation set and less depth than `X1` / `X3` |
| `X6` | `PASS` | later sequential rerun catches the real blockers and preserves the right fix order, but stays a bit more generic than the top rows and does not force a top-tier reshuffle |

## Accepted findings

| Topic | Accepted finding |
|---|---|
| methodology | the active `G08` lane now measures non-browser UI reasoning rather than browser-stack availability |
| separations | the redesigned lane already cleanly separates the reachable top trio: `X3 > X1 > X2` |
| decoy handling | `X3`, `X1`, and `X2` all reject the planted `z-index` and full-modal detours, which is the core hardening goal of the redesign |
| provider blockers | the remaining live blockers are now `X5` and `Q1`, not `X6`; the active failures are provider-runtime or auth blockers rather than browser-lane failures |
| Gemini sequential recovery | `X6` recovered once the row was run alone with a longer timebox; this confirms the row is benchmark-capable on the redesigned non-browser lane even though the shorter earlier attempts timed out |
| Gemini top path boundary | `X5` remains more severely blocked right now: even the later sequential `900s` run still did not finish the `G08` prompt, and the user's later clean-laptop check suggests the latency is upstream rather than local-machine-specific |
| `X4` wrapper repair | the repo-canonical Claude wrapper no longer fails early on a missing `ANTHROPIC_API_KEY`; current `X4` unavailability is now a later runtime issue, and the user chose to park the row temporarily |

## Canonical current reading

| Question | Current answer |
|---|---|
| Is active `G08` still a browser-only lane? | no |
| Should the older browser parity artifacts be deleted? | no; keep them as historical auxiliary runtime evidence |
| Does the redesigned lane already support non-browser UI scoring? | yes |
| Did the redesign materially improve the benchmark? | yes; it now probes UI reasoning quality rather than Playwright reachability |
