# Astra Model Routing Design

## Goal

Deliver an immediately usable, additive Orchestrarium Version 1 Astra route without changing pinned native-role defaults, then define a separate Version 2 model-selection contract that treats model capability, reasoning effort, complete-route economics, availability, safety, fallback, and review authority as separate dimensions.

## Version 1 architecture

Version 1 adds one provider-neutral canonical skill under `src.codex/skills/astra-routing/`; the existing installer projects canonical Codex skill trees to Claude Code. Its pure resolver accepts an admitted task class, observed model inventory, requested effort, stable effort evidence, maximum-effort approval, and requested fan-out. It returns exact Codex launch flags or a typed non-success decision. It neither launches a provider nor mutates operator configuration.

The Version 1 change does not edit `role-routing-policy.v1.json`, native role TOML, or the role manifest. Those objects are pinned into the create-only installer migration contract; changing them would turn a targeted upgrade into a broad migration.

## Effort semantics

The exact profile is the pair `model + effort`.

- mathematics, connected scientific work, and cross-system synthesis start at Astra `medium`;
- critical recovery starts at Astra `high`;
- an effort below the task default requires evaluation or measured-sufficient evidence;
- `high` above a medium default requires objective-failure or measured-gain evidence;
- `xhigh` requires evidence from high;
- `max` requires explicit human approval;
- `none` is forbidden for Astra.

Published maximum benchmark results are not treated as medium-effort measurements. The route may be selected because Astra is expected to reduce total calls, output tokens, tool steps, retries, rework, or latency, but savings are recorded as measured or forecast evidence rather than asserted from model identity alone.

## Version 2 architecture

Version 2 owns:

1. a strict model catalog;
2. a strict role/task routing policy;
3. a pure resolver and command-line interface;
4. a route-estimate schema that prices each model request separately;
5. a migration map preserving old Version 1 semantics.

Hard admissibility gates run before optimization. Automatic economics ranking requires the exact comparable candidate set declared by the task policy. The resolver rejects stale pricing, incomplete estimates, unknown availability, forbidden effort, unapproved maximum effort, unsafe critical-capability use, and Astra fan-out greater than one.

After hard gates and acceptance floors, selection is deterministic and transparent. It minimizes expected cost to an accepted result, then expected model calls, rework cycles, review cycles, tool calls, elapsed seconds, and finally profile name. The decision returns the complete comparison evidence and remains nonauthorizing.

## Migration semantics

The old Version 1 `apex-max` profile is Sol `max` despite its name. Its Version 2 migration alias therefore maps to `frontier-max`, not Astra `max`. Likewise, the old `pinned-top-pro` operator meaning remains a frontier/Sol policy until the operator explicitly selects an Astra-aware policy.

## Safety and independence

Astra may compress intellectual iteration, but it never removes independent review, security, QA, or human publication approval. Sol and Astra share the OpenAI evidence-independence group. Critical-security use of a critical-capability model requires explicit safety approval.

## Pull-request structure

- Version 1 PR: based on the current PR 4 hotfix branch.
- Version 2 PR: based on the final Version 1 branch.
- PR 5 policy overlays remain independent.
- No GitHub Actions workflow is added or used.

## Terms and Abbreviations

- **API — Application Programming Interface:** the programmatic model-access surface.
- **CLI — Command-Line Interface:** the terminal interface for the resolver.
- **QA — Quality Assurance:** independent implementation verification.
- **TOML — Tom's Obvious Minimal Language:** the native-role configuration format.
