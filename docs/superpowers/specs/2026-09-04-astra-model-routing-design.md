# Astra Model Routing Design

## Goal

Deliver an immediately usable, additive Orchestrarium 1.x Astra route without changing pinned native-role defaults, then define a full Version 2 model-selection contract that treats model capability, reasoning effort, route economics, availability, safety, and fallback as separate dimensions.

## V1 architecture

V1 adds one new provider-neutral canonical skill tree under `src.codex`; the existing installer projects that tree into the Claude Code pack. Its pure resolver accepts an admitted Astra-eligible task class, observed model availability, requested effort, stable effort evidence, maximum-effort approval, and fan-out. It returns exact Codex launch flags or a typed non-success decision. It neither launches a provider nor mutates existing configuration.

The V1 change deliberately does not edit `role-routing-policy.v1.json`, native role TOML, or the role manifest. Those objects are pinned into the create-only installer migration contract; changing them would turn a quick feature into a broad installer migration.

## V2 architecture

V2 owns three versioned files: model catalog, role-routing policy, and dated economics snapshot. A pure Python resolver validates exact schemas, applies hard admissibility gates first, and may minimize expected cost per accepted result only when the caller supplies a complete comparable candidate set. No model is selected by a single scalar score that could override security or role constraints.

## Effort semantics

Effort is profile-local. Astra supports `low`, `medium`, `high`, `xhigh`, and `max`; Terra, Sol, and Luna also support `none`. A higher effort on a lower capability model does not automatically dominate a lower effort on a higher capability model. Mathematical and connected scientific routes start at Astra `medium`; `low`, `high`, and `xhigh` require stable evidence matched to their purpose, while `max` requires explicit approval.

## Safety and independence

Astra may reduce iterations but never collapses author/reviewer or human publication gates. Sol and Astra share the OpenAI evidence-independence group. Critical security use requires explicit safety admission. Missing availability or evidence fails closed, and fallback is explicit.

## Testing

Tests cover exact provider parity for the V1 skill, effort defaults and escalation, unavailable/no-fallback behavior, fan-out, strict V2 schema handling, mechanical isolation, complete route economics, long-context pricing, safety, maximum effort, explicit fallback, and independence groups.
