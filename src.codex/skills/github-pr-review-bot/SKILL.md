---
name: github-pr-review-bot
description: "Use when operating a GitHub pull-request loop with the Codex review bot: triggering review, polling reactions/reviews/threads, addressing findings, or proving a clean current-head result."
---

# GitHub PR Review Bot

Drive one GitHub-hosted Codex review loop to a terminal result on the current remote head. This skill observes and coordinates the bot; it does not own code decisions, publication approval, CI, or merge.

## Binding contract

- Use hosted GitHub state, never local ancestry or remembered status.
- Bind every request and result to the current `headRefOid` and the exact `@codex review` comment ID.
- For the current head, select the newest exact `@codex review` comment by `created_at` and stable comment ID. A later exact trigger supersedes every earlier same-head run; never classify the earlier run while that newer trigger exists.
- Accept a reaction only when it is bot-authored and attached to that newest exact trigger. Accept a review, finding comment, or review thread only when it is bound to the current head and strictly later than that trigger. An earlier same-head review or reaction can never produce `clean`.
- Trigger or resolve threads only with explicit user authorization or a standing authorization for that PR.
- Do not start or rerun CI as part of this loop.
- Never retrigger solely because time elapsed. A bot-authored `eyes` reaction on the exact trigger is acknowledged/in progress, not clean; keep polling that run.
- Verify reaction authors, not aggregate reaction counts.
- Fetch every REST collection with `gh api --paginate --slurp`, merge all page arrays, and only then filter or sort. Page-local `--jq`, first-page results, or a failed/incomplete page are indeterminate.
- Cursor-walk GraphQL `reviewThreads` until `pageInfo.hasNextPage=false`; record the terminal cursor and unresolved current-head bot-thread IDs and count. If any page fails or is incomplete, classify the run as `indeterminate`.
- Both summary comments and `gh pr view` review/comment fields are nonauthorizing for `clean`.
- A `Completed` summary alone is never `clean`. Findings from the exact post-trigger review on the current head take precedence over summaries, reactions, and clean-review signals; classify `clean` only when complete collections show no such finding and the exact trigger has a bot-authored `+1` or a same-head bot review strictly after it.

## State machine

| Hosted evidence | State | Action |
| --- | --- | --- |
| Head changed after the trigger | stale | Ignore old terminal claims; trigger once on the new head when authorized. |
| Current bot finding comment or unresolved current bot thread strictly after the newest exact trigger | findings | Findings take precedence over reactions and reviews. Verify each finding, fix and test, push, then resolve only the exact fixed threads and trigger one new review. |
| Bot `+1` on the newest exact trigger, head unchanged, no current finding comment, and no unresolved current bot thread | clean | Record bot PASS; continue any separate human/publication gates. |
| Bot `eyes` on the newest exact trigger, with no later terminal evidence or current finding | in progress | Poll reviews, reactions, and current unresolved threads; do not retrigger. |
| Current-head bot review strictly after the newest exact trigger, with no current finding comment and no unresolved current bot thread | clean | Record bot PASS; continue any separate human/publication gates. |
| `Completed` summary without the required `+1` or same-head post-trigger review, incomplete collection, or no bot terminal output | indeterminate | Re-read authoritative state; do not invent a timeout or autonomous retrigger. |

## Hosted probes

Use `gh pr view <pr> --repo <owner>/<repo> --json headRefOid,state,isDraft,mergeable,updatedAt,url` first. Then query:

- exact issue comments and reaction actors through `gh api repos/<owner>/<repo>/issues/<pr>/comments` and `.../issues/comments/<id>/reactions`;
- submitted reviews through `gh api repos/<owner>/<repo>/pulls/<pr>/reviews`;
- `reviewThreads { id isResolved isOutdated path line comments }` through the full GraphQL cursor walk.

Anchor each poll on the latest hosted head and unfiltered latest bot state. Time windows are secondary only.

## Finding lifecycle

Treat bot text as a hypothesis until reproduced or verified in source/runtime. Do not bulk-resolve. After the exact fix is present on the hosted head, re-read its thread, resolve that thread, and leave unrelated or still-valid threads open. One new head gets at most one active review trigger.

No clean signal from this workflow authorizes merge or publication. Human review, leak scan, branch protection, and repository gates remain separate.

## Terms and Abbreviations

- **CI** — Continuous Integration.
- **PR** — Pull Request.
- **head SHA** — the hosted commit identifier in `headRefOid`.
