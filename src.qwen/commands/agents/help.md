---
description: Summarize the Qwen example-pack structure, role surface, and routing boundaries.
---

Read `QWEN.md`, `README.md`, `skills/README.md`, and `skills/lead/SKILL.md`.

Summarize:

- the current Qwen example-pack structure
- the role of `QWEN.md`
- the universal role-skill catalog under `skills/` (one skill per role)
- the role of `skills/lead/team-templates/` in the shared role principle
- why Orchestrarium keeps Qwen orchestration in the main session under the lead skill
- why external routing must check role eligibility before provider or CLI feasibility
- how the three external roles split advisory, worker-side, and review-side substitution
- how `externalPriorityProfile`, `reserveResolver`, `externalPriorityProfiles`, and `externalOpinionCounts` shape `auto` routing under the shipped `balanced` profile and any repo-local production profile
- how multi-opinion external lanes fail closed when the requested opinion count cannot be satisfied
- how `external-brigade` launches a bounded parallel helper set without turning `externalOpinionCounts` into a generic concurrency cap
- how the same external helper and provider may be reused across multiple disjoint brigade items when the runtime supports concurrent non-interactive execution
- which owner roles remain unsupported without a dedicated external owner adapter
- that shipped `externalProvider: auto` routing uses `codex | claude` only
- that this repository classifies Qwen as `WEAK MODEL / NOT RECOMMENDED`
- that explicit `externalProvider: gemini` or `externalProvider: qwen` remains a manual `WEAK MODEL / NOT RECOMMENDED` example or compatibility path only
- how `externalModelMode` distinguishes runtime-default provider selection from pinned production-provider execution
- how `externalCodexProfile: default | gpt-5.5-fast | gpt-5.5-xhigh | gpt-5.3-codex-spark` controls Codex-specific profile choice after provider resolution (where `gpt-5.5-fast` selects the fast Codex model tier with reasoning_effort still at `xhigh`, `gpt-5.5-xhigh` pins model `gpt-5.5` with `model_reasoning_effort = "xhigh"`, and `gpt-5.3-codex-spark` is the bounded mechanical-overflow path)
- how `reserve` works as an advisory/review-only symbolic candidate
- the role of `Qwen Code /init`, `.qwen/settings.json`, `.qwen/.agents-mode.yaml`, and `qwen-extension.json`
- the local command namespace
