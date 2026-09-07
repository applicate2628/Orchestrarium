# Astra Model Routing Design

## Goal

Deliver an additive Orchestrarium Version 1 Astra candidate selector without changing pinned native-role defaults, then define a separate Version 2 model-selection contract that treats model capability, reasoning effort, complete-route economics, availability, safety, fallback, and review authority as separate dimensions.

## Version 1 architecture

Version 1 adds one provider-neutral canonical skill under `src.codex/skills/astra-routing/`; the existing installer projects canonical Codex skill trees to Claude Code. Its pure resolver accepts an admitted task class, observed model inventory, requested effort, stable effort evidence, maximum-effort approval, and requested fan-out. It returns exact Codex launch flags or a typed non-success decision. It neither launches a provider nor mutates operator configuration. A usable end-to-end deployment additionally requires an admitted adapter and successful installed-runtime verification; candidate selection alone does not establish either.

The Version 1 change does not edit `role-routing-policy.v1.json`, native role TOML, or the role manifest. Those objects are pinned into the create-only installer migration contract; changing them would turn a targeted upgrade into a broad migration.

## Effort semantics

The exact profile is the pair `model + effort`.

- mathematics, connected scientific work, and cross-system synthesis start at Astra `medium`;
- critical recovery starts at Astra `high`;
- the operator minimum is `medium`; provider-supported `low` is not admitted, including evaluation downshifts;
- recovery may downshift from high to medium only with evaluation or measured-sufficient evidence;
- `high` above a medium default requires objective-failure or measured-gain evidence;
- `xhigh` requires objective high failure/contradiction or an already measured extra-high benefit; no wasted intermediate attempt is mandatory;
- `max` requires explicit human approval;
- `none` is forbidden for Astra.

Published maximum benchmark results are not treated as medium-effort measurements. The route may be selected because Astra is expected to reduce total calls, output tokens, tool steps, retries, rework, or latency, but savings are recorded as measured or forecast evidence rather than asserted from model identity alone.

## Version 2 ownership

The earlier cost-first Version 2 sketch in this document is superseded by the
provider-neutral adaptive portfolio design owned by PR #8. This Version 1
specification does not define a second Version 2 ranking algorithm.

Version 2 keeps quality, scope coverage, independent challenge, and evidence
quality ahead of whole-route cost and latency. It evaluates exact model-effort
profiles in task/harness/tool context. The one-instance Astra fan-out ceiling
belongs to this Version 1 selector, not to every future Version 2 portfolio.

## Migration semantics

The old Version 1 `apex-max` profile is Sol `max` despite its name. Its Version 2 migration alias therefore maps to `frontier-max`, not Astra `max`. Likewise, the old `pinned-top-pro` operator meaning remains a frontier/Sol policy until the operator explicitly selects an Astra-aware policy.

## Safety and independence

Astra may compress intellectual iteration, but it never removes independent review, security, QA, or human publication approval. Sol and Astra share the OpenAI evidence-independence group. Critical-security use of a critical-capability model requires explicit safety approval.

## Pull-request structure

- Version 1 PR: based on the current PR 4 hotfix branch.
- PR #7 owns the general Version 1 worker selector and is stacked on PR #6.
- PR #8 owns Version 2 design and is stacked on PR #7.
- PR 5 policy overlays remain independent.
- No GitHub Actions workflow is added or used.

## Terms and Abbreviations

- **API — Application Programming Interface:** the programmatic model-access surface.
- **CLI — Command-Line Interface:** the terminal interface for the resolver.
- **QA — Quality Assurance:** independent implementation verification.
- **TOML — Tom's Obvious Minimal Language:** the native-role configuration format.
