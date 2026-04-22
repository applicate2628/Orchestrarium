# N20 UI Interaction Rubric Design

Date: 2026-04-22
Owner: `$lead`
Status: `PASS`

## Purpose

Add a diagnostic UI implementation pilot after the role-fit scorecard showed that UI implementation
was still baseline-heavy.

## Scenario

`N20-ui-command-palette-interaction-gauntlet` tests command-palette keyboard state, filtering,
disabled-action handling, focus recovery, ARIA rendering, visible return cues, and CSS stability.

## Scoring

The binary verifier is authoritative for correctness. The post-run scorer adds a diagnostic rubric:

| Dimension | Points |
|---|---:|
| binary correctness | `40` |
| patch quality | `30` |
| elapsed proxy | `15` |
| output-size cost proxy | `15` |
