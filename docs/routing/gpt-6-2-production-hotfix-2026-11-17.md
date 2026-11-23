# GPT-6.2 production model refresh

## Scope

Replace current factory Sol and Astra model generations with `gpt-6.2-sol` and
`gpt-6.2-astra`. Preserve role/task eligibility, reasoning efforts, main-session
selection, Terra/Luna lanes, user customization, and existing launch consent.
External Sol 6.1 profiles migrate to the same effort on Sol 6.2; an explicit
transport flag remains literal rather than silently rewriting the actual request.

This hotfix does not enable Ultra on worker lanes, launch a model, change subscription
access, claim comparative local benchmarks, or advance the SDK/Rust rollout.

## Official evidence, checked 2026-11-17

- [Launch announcement](https://openai.com/index/introducing-gpt-6-2-astra-sol/)
- [Codex model documentation](https://learn.chatgpt.com/docs/models):
  exact CLI identifiers; default Codex context is 272,000 for Astra and 500,000 for
  Sol. Configurable larger windows are not a reason to overwrite user settings.
- [API migration guidance](https://developers.openai.com/api/docs/guides/latest-model):
  tool calls use Responses; `none` and `minimal` are not retained migration efforts.
- [Astra model](https://developers.openai.com/api/docs/models/gpt-6.2-astra):
  Standard short-context input/cached-input/output prices are $8/$0.40/$40 per
  million tokens. Pricing depends on context and processing tier.
- [Sol model](https://developers.openai.com/api/docs/models/gpt-6.2-sol):
  corresponding prices are $2/$0.10/$10 per million tokens.

The selected machine's existing Codex model cache independently advertised both
identifiers with low, medium, high, xhigh, max and ultra; no inference was launched.
Available provider effort is distinct from Orchestrarium's admitted worker efforts.

## Acceptance

Offline checks cover default transport selection, Astra consent, retained low/Ultra
restrictions, manifest/profile consistency, exact prior stock-role upgrade, customized
role preservation and idempotent configuration normalization. Installed verification
must preserve any existing SDK payload; a full replacement with pre-SDK source is not
authorized merely by this model refresh.

## Terms and Abbreviations

- API: application programming interface.
- CLI: command-line interface.
- QA: quality assurance.
- SDK: software development kit.
- Stock: exact shipped factory content, not a similarly named customized file.
