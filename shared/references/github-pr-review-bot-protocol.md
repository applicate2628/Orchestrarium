# GitHub Pull-Request Review Bot Protocol

This document is the canonical provider-neutral methodology for coordinating one hosted review run without misattributing another run's evidence. The installed Codex and Claude Code copies of `github-pr-review-bot/SKILL.md` remain self-contained operative bindings because this maintainer reference is not installed.

## Evidence identity

Every decision is bound to the hosted repository, pull request, current `headRefOid`, and exact `@codex review` issue-comment identifier. Local ancestry, remembered status, summary prose, and elapsed time are not substitutes for current complete hosted state.

On the Representational State Transfer (REST) issue-comment surface, use `IssueCommentOrder = (parsed UTC created_at, numeric stable REST issue-comment ID)` after complete pagination. This is an Orchestrarium total-order convention for that one surface, not a GitHub chronology guarantee. It selects the newest exact trigger and orders later issue-comment evidence, but it does not correlate an otherwise unbound result with one of several overlapping runs. Missing, malformed, duplicate, or incomplete ordering input makes the affected classification indeterminate.

Cross-surface timestamps do not inherit the REST tie-breaker. Same-time evidence from a REST review, REST issue comment, and Graph Query Language (GraphQL) review thread is incomparable unless that surface provides an independent exact correlation.

## Connector author identity

Use one author predicate for success, failure, finding, and in-progress evidence:

- REST objects require `user.login == "chatgpt-codex-connector[bot]"` and `user.type == "Bot"`.
- GraphQL objects require the exact same-node pair `author.login == "chatgpt-codex-connector"` and `author.__typename == "Bot"`, as returned by that queried surface.
- A numeric REST `user.id` may be recorded as evidence, but it is not a separately invented allowlist. Do not translate the REST `[bot]` suffix onto GraphQL, strip it from REST, or borrow an author field from another surface.

Absent, null, mismatched, or incompletely fetched author fields make that signal indeterminate. A generic "bot-authored" label is not sufficient identity evidence.

## Overlapping-run attribution

An intrinsically correlated signal, such as a reaction attached to one exact trigger, belongs to that trigger. Even then, it cannot make the whole head clean while another exact trigger on the same `(repository, pull request, headRefOid)` remains unresolved.

A submitted review or REST issue-comment result that carries no exact trigger identifier may bind only when complete hosted state leaves exactly one unresolved earlier exact trigger candidate on the same head. If two or more candidates remain, ordering the result after them does not identify its owner: leave the evidence and all affected runs indeterminate. Do not fail or dismiss a run, mutate retry state, or create another trigger until ownership is reconciled.

## Clean and failure semantics

A clean result is semantic, not phrase-pinned. Connector author identity, current-head reviewed-commit binding, post-trigger order, complete collections, explicit unambiguous final no-findings meaning, no current findings, and no unresolved current connector threads are all required. Wording, emoji, and boilerplate may change. Summary-only completion remains nonauthorizing.

Failure signatures are the opposite: each retryable or non-retryable terminal signature is an exact repo-local predicate with its normalized body, surface, connector author identity, current-head binding, ordering, and unresolved-trigger attribution. Error-like prose that is not exact-listed remains indeterminate.

## Retry lineage

A terminal failure and its authorized successor are one lineage with at most one successor trigger. Retry is never automatic. Before creation, bind explicit user authorization and record the creating transition. Count the retry only after a complete hosted refresh uniquely binds the successor trigger identifier, creation time, and unchanged head. A definite failed create requires proof that no successor exists; an ambiguous create enters reconciliation and cannot be repeated. A failed successor cannot authorize another successor.

## Terms and Abbreviations

- `GraphQL`: Graph Query Language.
- `PR`: Pull Request.
- `REST`: Representational State Transfer.
- `UTC`: Coordinated Universal Time.
