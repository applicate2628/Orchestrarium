# Research

## Accepted Findings

| Topic | Accepted finding |
|---|---|
| Current provider priorities | Provider order is hard-coded today as one shared lane-priority matrix. `externalProvider: auto` resolves through that matrix and there is no switchable priority profile in `agents-mode`. |
| Current multi-opinion behavior | The current model supports one resolved external provider per route plus parallel execution for independent lanes. It does not model `2+` independent external opinions for the same lane or provider fan-out in priority order. |
| Gemini today | Gemini is already a first-class provider in the shared universe. It is currently first for visual worker/review lanes, second for `advisory.repo-understanding`, and third for several non-visual lanes, but broader participation outside visual lanes requires explicit provider override because no multi-opinion fan-out contract exists. |
| Control-plane blockers | The schema owners are the shared/main `agents-mode` references plus the three pack-local `external-dispatch` contracts. The main textual blocker is repeated wording that a lead-managed batch ends with exactly one external consultant-check before closure. |
| Compatibility | Existing writers already preserve unknown keys when updating `.agents-mode`, so additive new keys are structurally compatible with the current file policy. |
| Mirror scope | The required rewrite surface spans shared/main governance and docs, then pack-local init/help/consultant/external-worker/external-reviewer/second-opinion/operating-model/subagent-contracts in `Orchestrarium/main` and standalone `codex`, `claude`, and `gemini`. |
| Validator implications | File inventories are already sufficient, but Codex and Claude validators pin shared-reference hashes, so any reference-doc changes will require hash updates. |

## Accepted Minimal Schema Direction

The smallest additive schema that covers the requested behavior without replacing the current scalar `externalProvider` meaning is:

| Key | Purpose |
|---|---|
| `externalPriorityProfile` | selects the active named provider-priority profile used when `externalProvider: auto` |
| `externalPriorityProfiles` | stores per-lane ordered provider lists for named profiles |
| `externalOpinionCounts` | declares how many distinct external opinions to collect for a lane under `externalProvider: auto` |

## Accepted Semantics Direction

| Case | Accepted direction |
|---|---|
| `externalProvider: auto` + opinion count `1` | keep current single-provider behavior |
| `externalProvider: auto` + opinion count `2+` | consume the active lane-specific provider list in order, skip unavailable providers and ordinary self-provider auto-bounce, and launch distinct eligible providers until the requested count is satisfied or the provider list is exhausted |
| explicit `externalProvider` override | remains a single-provider override unless a future explicit fixed-provider fan-out rule is added |
| Gemini outside visual-first lanes | becomes eligible automatically whenever the active profile ranks Gemini inside the first `N` providers for that lane |

## Files To Treat As Canonical Owners

- [agents-mode-reference.md](d:/dev/Orchestrator/Orchestrarium/docs/agents-mode-reference.md)
- [AGENTS.shared.md](d:/dev/Orchestrator/Orchestrarium/shared/AGENTS.shared.md)
- [AGENTS.md](d:/dev/Orchestrator/Orchestrarium/AGENTS.md)
- [external-worker-design.md](d:/dev/Orchestrator/Orchestrarium/docs/external-worker-design.md)
- [external-dispatch.md](d:/dev/Orchestrator/Orchestrarium/src.codex/skills/lead/external-dispatch.md)
- [external-dispatch.md](d:/dev/Orchestrator/Orchestrarium/src.claude/agents/contracts/external-dispatch.md)
- [external-dispatch.md](d:/dev/Orchestrator/Orchestrarium/src.gemini/skills/lead/external-dispatch.md)

## Required Downstream Rewrite Families

- shared/main governance and reference docs
- Codex init/consultant/external/second-opinion/lead contracts
- Claude init/help/consultant/external/second-opinion/contracts
- Gemini init/help/consultant/external/second-opinion/contracts
- standalone `codex`, `claude`, `gemini` mirrors
- Codex and Claude validator hash updates if shared references change
