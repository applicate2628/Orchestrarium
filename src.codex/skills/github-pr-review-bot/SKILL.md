---
name: github-pr-review-bot
description: "Use when operating a GitHub pull-request loop with the Codex review bot: triggering review, polling reactions/reviews/threads, addressing findings, or proving a clean current-head result."
---

# GitHub PR Review Bot

Drive one GitHub-hosted Codex review loop to a terminal result on the current remote head. This skill observes and coordinates the bot; it does not own code decisions, publication approval, CI, or merge.

This is the installed binding of the provider-neutral review-coordination methodology in `shared/references/github-pr-review-bot-protocol.md`. That reference is not installed; this skill therefore keeps the complete operative rule needed at runtime.

## Binding contract

- Use hosted GitHub state, never local ancestry or remembered status.
- Bind every request and result to the current `headRefOid` and the exact `@codex review` comment ID.
- On the Representational State Transfer (REST) issue-comment surface, define `IssueCommentOrder = (parsed UTC created_at, numeric stable REST issue-comment ID)`. This is an Orchestrarium repo-local total-order convention, not a GitHub chronological guarantee; the numeric ID is only the stable tie-breaker for equal parsed timestamps on that one surface.
- Use `IssueCommentOrder` after complete pagination to select the newest exact `@codex review` trigger and to order post-trigger terminal and finding issue-comment evidence. Ordering proves only that an issue comment is later; it does not identify which overlapping same-head run produced an uncorrelated terminal comment. Malformed, missing, duplicate, or incomplete ordering fields make the run `indeterminate`; do not discard the malformed candidate and continue.
- Never bind an uncorrelated terminal comment by selecting the newest trigger. For terminal-failure classification, enumerate exact triggers on the same `(repository, pull request, headRefOid)` that precede the terminal comment and remain without an unambiguously bound terminal result. Ordering alone may bind the signature only when exactly one unresolved exact trigger candidate exists. Two or more unresolved same-head trigger candidates make the terminal evidence and affected runs `indeterminate`; do not record `failed`, dismiss a run, mutate a retry lineage, or authorize another trigger.
- Apply the same ownership rule to uncorrelated clean evidence. A submitted-review or REST issue-comment no-findings result may bind to a run only when complete hosted state leaves exactly one unresolved exact trigger candidate on the same `(repository, pull request, headRefOid)`. Two or more unresolved same-head exact trigger candidates mean that uncorrelated clean evidence remains `indeterminate`, even when its timestamp/order is later and its reviewed commit matches the head.
- Accept a reaction only when its author satisfies the connector author identity rule below and it is attached to that newest exact trigger. A reaction is intrinsically correlated to that trigger, but head-level `clean` additionally requires no other unresolved exact trigger on the same `(repository, pull request, headRefOid)`. An intrinsically correlated reaction does not erase another unresolved same-head run. Accept a review, review comment, or review thread only when its author satisfies the same rule, it is bound to the current head, and its own authoritative timestamp is strictly later than the trigger timestamp. Because the REST issue-comment tie-breaker does not transfer to another surface, same-time evidence from different surfaces is incomparable, including between REST issue comments and either REST reviews or GraphQL threads; the run remains `indeterminate`. An earlier same-head review or reaction can never produce `clean`.
- Trigger or resolve threads only with explicit user authorization or a standing authorization for that PR.
- Before asking again for publication confirmation or treating the cycle as unauthorized, read the publication-gate owner's latest genuine grant, stored binding, and revocation state. New consent uses the standalone genuine-user marker `[approve-pr-publication]`, raw or inside one balanced pair of single backticks or double asterisks. Only a current-turn marker initializes a binding; an active binding reuses existing permission for the same PR head branch and admitted scope, including ordinary corrective pushes, resolution of exact fixed threads, and the next review trigger. Do not ask again. Missing/corrupt binding state resets historical simple-marker consent. Fresh authorization is required for first publication or no active binding, another PR, remote, or head branch, widened scope, exact revocation, or a later genuine user no-push instruction. Existing exact Version 1 URL/Markdown/numeric grants remain supported compatibility input. A later genuine user no-push instruction stops push even without the exact revoke token. This continuity never bypasses current-head and PR/Git binding checks, branch protection, human review, or a fresh leak/range receipt.
- Do not start or rerun CI as part of this loop.
- Never retrigger solely because time elapsed. An `eyes` reaction whose author satisfies the connector author identity rule on the exact trigger is acknowledged/in progress, not clean; keep polling that run.
- Verify every success, failure, finding, and in-progress signal with the connector author identity rule; never substitute aggregate reaction counts.
- Fetch every REST collection with `gh api --paginate --slurp`, merge all page arrays, and only then filter or sort. Page-local `--jq`, first-page results, or a failed/incomplete page are indeterminate.
- Cursor-walk Graph Query Language (GraphQL) `reviewThreads` until `pageInfo.hasNextPage=false`; record the terminal cursor and unresolved current-head bot-thread IDs and count. If any page fails or is incomplete, classify the run as `indeterminate`.
- A substantive bot-authored current-head review-result may arrive on the submitted-review or REST issue-comment surface. Because that evidence carries no exact trigger identity, it qualifies for `clean` only when complete hosted state leaves exactly one unresolved exact trigger candidate on the same `(repository, pull request, headRefOid)`, with verified bot identity on that surface under the connector author identity rule, explicit and unambiguous final no-findings meaning, and a reviewed-commit binding that matches the full `headRefOid` or an unambiguous commit prefix that uniquely resolves to that same hosted head. A REST issue-comment review-result uses `IssueCommentOrder` and must be ordered after that bound exact trigger. Wording, emoji, and boilerplate may vary; clean classification must not use an exact body, signature, or phrase allowlist. Exact-body allowlisting remains exclusive to the failure classifier below.
- A summary-only issue comment remains nonauthorizing for `clean`; so do other summary comments and `gh pr view` review/comment fields. A `Completed` summary alone is never `clean`. Findings from the exact post-trigger review on the current head take precedence over summaries, reactions, and clean-review signals; classify `clean` only when complete collections show no current finding comments or unresolved current bot threads and the exact trigger has a `+1` whose author satisfies the connector author identity rule or a qualifying review-result above.

## Connector author identity

Use this one author predicate for every author-dependent signal, including reactions, findings, submitted reviews, review comments or threads, clean results, and terminal failures. Success and failure must not use different notions of "the bot."

- On a Representational State Transfer (REST) object, accept the author only when `user.login == "chatgpt-codex-connector[bot]"` and `user.type == "Bot"`.
- On a Graph Query Language (GraphQL) object, request both `author.login` and `author.__typename`. Accept only `author.login == "chatgpt-codex-connector"` with `author.__typename == "Bot"`, using the pair returned by that same queried surface. Do not synthesize the REST `[bot]` suffix on GraphQL, strip it from REST, or transfer an identity field from another surface.
- Record a returned numeric REST `user.id` as evidence when available, but do not invent or depend on a numeric-ID allowlist. Missing, null, mismatched, or incompletely fetched author fields make that signal `indeterminate`.

## State machine

| Hosted evidence | State | Action |
| --- | --- | --- |
| Head changed after the trigger | stale | Ignore old terminal claims; trigger once on the new head when authorized. |
| Current connector-authored finding issue comment ordered after the newest exact trigger by `IssueCommentOrder`, or a current unresolved connector-authored review thread strictly later on its own surface | findings | Findings take precedence over reactions and reviews. Verify each finding, fix and test, push, then resolve only the exact fixed threads and trigger one new review. |
| Exact-listed connector-authored terminal signature, unambiguously bound by the terminal-failure classifier to exactly one unresolved exact trigger on the current `headRefOid` and ordered after that trigger by `IssueCommentOrder` | failed | Record the bound terminal-failure fields below; this state is terminal and never `clean` or `in progress`. |
| Exact-listed terminal signature after two or more unresolved exact triggers on the same current head, without authoritative trigger correlation | indeterminate | Leave every candidate run unchanged; do not record failure, dismiss a run, mutate retry lineage, or post another trigger until ownership is reconciled. |
| Connector-authored `+1` on the newest exact trigger, head unchanged, no current finding comment, no unresolved current connector thread, and no other unresolved exact trigger on the same current head | clean | Record bot PASS; continue any separate human/publication gates. |
| Connector-authored `eyes` on the newest exact trigger, with no later terminal evidence or current finding | in progress | Poll reviews, reactions, and current unresolved threads; do not retrigger. |
| Substantive connector-authored current-head review-result, unambiguously attributable because exactly one unresolved exact trigger candidate remains on the same current head, with verified connector author identity, matching reviewed commit, explicit final no-findings meaning, complete collections, no current finding comments, and no unresolved current bot threads authored by the connector | clean | Record bot PASS; continue any separate human/publication gates. |
| Summary-only issue comment, `Completed` summary without the required `+1` or qualifying post-trigger review-result, incomplete collection, or no bot terminal output | indeterminate | Re-read authoritative state; do not invent a timeout or autonomous retrigger. |

## Terminal failure classifier

This classifier is an Orchestrarium repo-local coordinator convention, not official or guaranteed hosted Codex provider behavior.

Apply the connector author identity rule above to this issue-comment REST predicate. Record its returned numeric REST `user.id` as terminal evidence, but do not use that value as a separate author allowlist. A GraphQL display login and typename pair is not this predicate surface and cannot substitute for the REST fields.

Normalize the REST issue-comment `body` by applying only these operations, in order:

1. Convert Carriage Return followed by Line Feed (CRLF) to Line Feed (LF).
2. Then trim whitespace only from the end of the entire body.

Do not trim individual lines, collapse blank lines, case-fold, or use substring or prefix matching. After that normalization, the only currently recognized retryable terminal body is exactly:

```text
Codex Review: Something went wrong. Try again later by commenting "@codex review".
An unknown error occurred
```

Classify that signature as `failed` with `retryable=true` only when its REST issue comment has the exact author identity above, its `IssueCommentOrder` is greater than the bound exact trigger's order, the current `headRefOid` still equals the head bound to that trigger, and complete hosted state proves exactly one unresolved exact trigger candidate on the same `(repository, pull request, headRefOid)`. The recognized body has no trigger or provider run identifier, so two or more unresolved same-head trigger candidates remain `indeterminate` regardless of which trigger is newest. Otherwise it does not match this signature.

A different bot issue comment may be classified as `failed` with `retryable=false` only when its complete normalized body and exact REST author predicate are separately exact-listed in a future contract. No non-retryable terminal signature is currently exact-listed. Any other bot error-like prose is otherwise `indeterminate`; never infer either classification from error-like prose.

For every `failed` classification, record `headRefOid`, `triggerCommentId`, `triggerCreatedAt`, `terminalCommentId`, `terminalCreatedAt`, `terminalAuthorId`, `terminalAuthorLogin`, `terminalAuthorType`, `normalizedBodySha256`, `terminalSignatureId`, `retryable`, `retryAttemptCount`, `retryTransitionState`, `retryAuthorizationReference`, `successorTriggerCommentId`, `successorTriggerCreatedAt`, and `successorHeadRefOid`. `normalizedBodySha256` is the Secure Hash Algorithm 256-bit (SHA-256) digest of the normalized body. Allowed transition values are `not-requested | creating | created | creation-failed | reconciliation-required`. For the recognized signature above, set `terminalSignatureId=codex-review-unknown-error-retry-v1`, `retryable=true`, initial `retryAttemptCount=0`, `retryTransitionState=not-requested`, and the authorization and successor fields to null.

## Hosted probes

Use `gh pr view <pr> --repo <owner>/<repo> --json headRefOid,state,isDraft,mergeable,updatedAt,url` first. Then query:

- exact issue comments, including substantive review-result candidates, and reaction actors through `gh api repos/<owner>/<repo>/issues/<pr>/comments` and `.../issues/comments/<id>/reactions`;
- submitted-review candidates through `gh api repos/<owner>/<repo>/pulls/<pr>/reviews`;
- `reviewThreads { id isResolved isOutdated path line comments }` through the full GraphQL cursor walk.

Anchor each poll on the latest hosted head and unfiltered latest bot state. Time windows are secondary only.

## Finding lifecycle

Treat bot text as a hypothesis until reproduced or verified in source/runtime. Do not bulk-resolve. After the exact fix is present on the hosted head, re-read its thread, resolve that thread, and leave unrelated or still-valid threads open. One new head gets at most one active review trigger. Before posting any trigger, complete hosted preflight must find no unresolved exact trigger on the same `(repository, pull request, headRefOid)`; poll one existing run, or classify multiple overlapping runs as `indeterminate`, instead of adding another trigger.

There is no automatic retry. A `failed` run permits at most one subsequent retry, only when its exact-listed record says `retryable=true` and `retryAttemptCount=0`, after the authorization-continuity check proves active user or standing authorization, and after confirming through complete hosted collections that no newer trigger or bot run is active. Preserve one active run for the head and never create a duplicate review thread for the failed trigger.

The failed run and any authorized successor form one retry lineage. Apply this transition protocol:

1. Before creating anything, record `retryTransitionState=creating` and the durable authorization reference in `retryAuthorizationReference`, bound to the exact user or standing authorization. Keep `retryAttemptCount=0` and all successor fields null.
2. Submit exactly one `@codex review` issue comment. The create response alone is not confirmation.
3. On confirmed success, completely refresh the REST issue-comment collection, locate exactly one new exact trigger by `IssueCommentOrder`, confirm the current head is still the authorized head, then record `retryTransitionState=created`, its exact `successorTriggerCommentId`, `successorTriggerCreatedAt`, and `successorHeadRefOid`. Under this confirmed-success-only rule, increment `retryAttemptCount` from `0` to `1` only after those bindings are recorded.
4. Treat a create as an explicit creation failure only when the operation has a definitive failure result and a complete hosted refresh proves that no successor trigger exists. Then record `retryTransitionState=creation-failed`, keep `retryAttemptCount=0`, and require fresh explicit user authorization plus a new complete preflight before another create attempt.
5. For any ambiguous creation outcome, including a failed or interrupted response that might have created the comment, record `retryTransitionState=reconciliation-required`. It must not create another retry trigger; reconcile the existing attempt against complete hosted state until exactly one successor is bound as `created` or absence is proved as `creation-failed`.
6. The lineage has at most one successor trigger. The successor inherits `retryAttemptCount=1`; if it later fails, its terminal record keeps that count and must never authorize another successor.

No clean signal from this workflow authorizes merge or publication. Human review, leak scan, branch protection, and repository gates remain separate.

## Terms and Abbreviations

- **CI** — Continuous Integration.
- **CRLF** — Carriage Return followed by Line Feed, the two-character Windows-style line ending.
- **GraphQL** — Graph Query Language.
- **LF** — Line Feed, the single-character normalized line ending.
- **PR** — Pull Request.
- **REST** — Representational State Transfer.
- **SHA-256** — Secure Hash Algorithm 256-bit, used here to identify the exact normalized terminal body.
- **head SHA** — the hosted commit identifier in `headRefOid`.
