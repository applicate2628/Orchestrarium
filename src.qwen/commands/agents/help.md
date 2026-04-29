---
description: Summarize the Qwen example-pack structure, role surface, and routing boundaries.
---

Read `QWEN.md`, `README.md`, `skills/README.md`, `skills/lead/SKILL.md`, and `agents/lead.md`.

Summarize:

- the current Qwen example-pack structure
- the role of `QWEN.md`
- the distinction between stable skills and explicit specialist subagents
- the role of `agents/team-templates/` in the shared role principle
- why Orchestrarium keeps Qwen orchestration in the main session under the lead skill
- why external routing must check role eligibility before provider or CLI feasibility
- how the three external roles split advisory, worker-side, and review-side substitution
- how `externalPriorityProfile`, `externalPriorityProfiles`, and `externalOpinionCounts` shape `auto` routing under the shipped `balanced` profile and any repo-local production profile
- how multi-opinion external lanes fail closed when the requested opinion count cannot be satisfied
- how `external-brigade` launches a bounded parallel helper set without turning `externalOpinionCounts` into a generic concurrency cap
- how the same external helper and provider may be reused across multiple disjoint brigade items when the runtime supports concurrent non-interactive execution
- which owner roles remain unsupported without a dedicated external owner adapter
- that shipped `externalProvider: auto` routing uses `codex | claude` only
- that this repository classifies Qwen as `WEAK MODEL / NOT RECOMMENDED`
- that explicit `externalProvider: gemini` or `externalProvider: qwen` remains a manual `WEAK MODEL / NOT RECOMMENDED` example or compatibility path only
- how `externalModelMode` distinguishes runtime-default provider selection from pinned production-provider execution
- how `externalClaudeApiMode` controls only the advisory/review `claude-secret` candidate
- the role of `Qwen Code /init`, `.qwen/settings.json`, `.qwen/.agents-mode.yaml`, and `qwen-extension.json`
- the local command namespace
