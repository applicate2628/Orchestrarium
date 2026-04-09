# Cross-Pack Reconciliation Manifest

When editing shared semantic content in either pack's contract docs, update the matching block in the other pack. Platform-specific packaging (routing patterns, per-role contracts, stage gates) is intentionally different and does NOT need cross-pack sync.

Shared design-only methodology references now live in `shared/references/`. Pack-specific reference trees should keep only pack-specific material plus thin compatibility pointers where stable legacy paths still matter.

## Why the docs differ

Claude Code loads role definitions dynamically via Agent tool → contract docs are compact routing references.
Codex loads skills statically → contract docs must be self-contained lead guides with inline role contracts.

~70% of the diff is intentional platform-specific packaging. This manifest tracks only the ~30% that expresses **shared semantics** and must stay aligned.

## Shared semantic blocks — operating-model.md

| Block | Claude (`src.claude/agents/contracts/operating-model.md`) | Codex (`src.codex/skills/lead/operating-model.md`) | Notes |
|-------|----------------------------------------------------------|-----------------------------------------------------|-------|
| Isolation rule | §"Isolation rule" (L6–11) | §"Isolation rule" (L277–279) | Claude mentions Agent tool explicitly; Codex says "designated agent invocation mechanism" |
| Research admission filter | §"Research admission filter" (L31–43) | §"Research admission filter" (L262–275) | Identical semantics, identical 8-item list + 3 gate owners |
| Interaction types | §"Interaction types" table (L47–60) | §"Interaction types" table (L282–292) | Same 8 types; Claude has prose descriptions, Codex has compact table |
| Cross-domain escalation | §"Cross-domain escalation protocol" (L114–123) | §"Cross-domain escalation protocol" (L294–301) | Identical 4-step protocol; Claude adds target-domain mapping table |
| Adjacent-issue protocol | §"Adjacent-issue protocol" (L127–132) | §"Adjacent-issue protocol" (L303–310) | Identical semantics; Codex says "configured bug registry path" vs Claude's `work-items/bugs/` |
| Artifact invalidation | §"Artifact invalidation protocol" (L135–143) | §"Artifact invalidation protocol" (L314–319) | Claude has 3 detailed steps; Codex condensed to 3 points. Same dependency chain. |
| REVISE iteration cap | §"REVISE iteration cap" (L144–154) | §"REVISE iteration cap procedure" (L322–327) | Identical cap (3), identical escalation procedure |
| Periodic controls | §"Periodic controls" table (L62–78) | §"Periodic controls" (L243–248) | Claude has full 11-row control matrix; Codex defers to repo-defined matrix |
| How to instruct reviewers | §"How to instruct reviewers" (L93–96) | §"Review strategy selection" (L174–226) | Claude: 2 compact paragraphs. Codex: full strategy A/B with decision table. Semantics identical. |
| Common alias map | §"Common alias map" (L98–112) | §"Common alias map" (L397–410) | Identical mappings, different formatting |
| Artifact persistence | §"Artifact persistence protocol" (L168–211) | §"Artifact persistence protocol" (L329–341) | Claude: detailed 3-tier table + when-to-save rules. Codex: condensed 3-tier table. |
| Parallel execution | §"Parallel execution protocol" (L157–166) | §"Parallelism guidance" (L356–360) | Claude: 4-step protocol with integration owner. Codex: 3 brief bullets. |
| External role routing | External role substitution notes in `operating-model.md` | External role substitution notes in `operating-model.md` | Shared semantics: worker covers `Implement`, reviewer covers `Review + QA`, mandatory internal reviewers remain non-replaceable in risk-sensitive templates, and team template JSON stays unchanged. |

## Shared semantic blocks — subagent-contracts.md

| Block | Claude (`src.claude/agents/contracts/subagent-contracts.md`) | Codex (`src.codex/skills/lead/subagent-contracts.md`) | Notes |
|-------|-------------------------------------------------------------|-------------------------------------------------------|-------|
| Handoff template | §"Handoff template" (L11–34) | §"Shared handoff template" (L7–34) | Identical structure; Codex has extra placeholder lines |
| Artifact gate | §"Artifact gate" (L38–43) | §"Artifact gate" (L37–43) | Identical rules; Codex adds "if the repository uses one" qualifier |
| status.md format | L47–88 | L46–88 | Identical format. Only diff: Codex says "role to invoke" vs Claude's "agent to launch" |
| Response format | §"Response format" (L92–103) | §"Shared response format" (L90–115) | Same 5-line format. Codex adds fact-first note and consultant exception inline |
| BLOCKED classification | §"BLOCKED classification" (L105–113) | §"BLOCKED classification" (L101–107) | Identical 2-class table. Codex: "configured bug registry path" vs Claude: `work-items/bugs/` |
| Interaction rules | §"Interaction rules" (L115–121) | §"Interaction rules" (L492–499) | Same 5 rules; minor wording adaptation |
| Test ownership boundary | §"Test ownership boundary" (L123–132) | — | **Claude only.** Codex has no equivalent. |
| Structured completion report | §"Structured completion report" (L134–143) | §"Structured completion report" (L501–510) | Identical 4-item format |
| Gate questions | §"Gate questions" (L148–155) | §"Gate questions" (L516–522) | Identical 7 questions |
| External role contracts | External role summaries + dispatch references in `subagent-contracts.md` | External role sections in `subagent-contracts.md` | Shared semantics: assigned internal role is provenance, not a restriction on universality; roles do not self-fallback to internal specialists; orchestrator may reroute after the external role is disabled. |

## Shared semantic blocks — external dispatch

| Block | Claude (`src.claude/agents/contracts/external-dispatch.md`) | Codex (`src.codex/skills/lead/external-dispatch.md`) | Notes |
|-------|-------------------------------------------------------------|-------------------------------------------------------|-------|
| Config file location | `.claude/.agents-mode` (legacy `.claude/.consultant-mode` fallback) | `.agents/.agents-mode` (legacy `.agents/.consultant-mode` fallback) | New writes target `agents-mode`; legacy file stays read-only migration input. |
| Extended config schema | `consultantMode`, `delegationMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer` | `consultantMode`, `delegationMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, optional `externalClaudeProfile` | `consultantMode` controls consultant; `delegationMode` and `mcpMode` are operator-level routing/tooling preferences; `externalClaudeProfile` matters only when the external provider is Claude CLI. |
| Provider dispatch | Codex CLI | Claude CLI | Each pack calls the other CLI as the external provider. |
| Provenance header | Requested mode / actual execution path / deviation reason | Requested mode / actual execution path / deviation reason | Keep wording semantically aligned even if command examples differ. |
| Fallback boundary | Role-level no internal fallback; orchestrator may reroute when the role choice is disabled | Role-level no internal fallback; orchestrator may reroute when the role choice is disabled | Avoid ambiguous bare use of the word `fallback`. |

## Shared design-only references

These documents should not be copied again into new pack trees. Future packs, including a Gemini pack, should reuse them from `shared/references/` as the starting layer and keep only pack-specific overlays, wrappers, or vocabulary mapping locally where the shared text is not yet fully pack-agnostic.

| Canonical shared reference | Path | Pack-local expectation |
|-------|------|------|
| Evidence pipeline | `shared/references/evidence-based-answer-pipeline.md` | Keep only compatibility pointers if old pack-local links must stay valid |
| Workflow strategy comparison | `shared/references/workflow-strategy-comparison.md` | Pack-local diagrams and operating-model docs may link here directly |
| Workflow strategy comparison (ru) | `shared/references/ru/workflow-strategy-comparison.md` | Same as above for Russian docs |
| Subagent operating model core | `shared/references/subagent-operating-model.md` | Keep pack-local wrapper plus runtime/repository addendum |
| Subagent operating model core (ru) | `shared/references/ru/subagent-operating-model.md` | Same as above for Russian docs |
| Repository publication safety | `shared/references/repository-publication-safety.md` | Keep operational commands in root docs and runtime pack docs, not here |
| Repository publication safety (ru) | `shared/references/ru/repository-publication-safety.md` | Same as above for Russian docs |

Intentional pack-local exceptions:

| Reference | Current home | Why it stays local for now |
|-------|------|------|
| Periodic control matrix | `references-codex/periodic-control-matrix.md`, `references-claude/periodic-control-matrix.md` and `ru` variants | Still depends on pack/runtime vocabulary, task-memory layout, and runtime-doc links; move it only after a generic shared skeleton exists |

## Codex-only sections (no Claude equivalent needed)

These exist in Codex because it must be self-contained. Claude distributes this content into individual role `.md` files.

| Codex section | Lines | Claude equivalent location |
|---------------|-------|---------------------------|
| Role map | subagent-contracts:117–141 | Distributed across `src.claude/agents/*.md` |
| Per-role contracts (PM through Consultant) | subagent-contracts:142–489 | Each in its own `src.claude/agents/<role>.md` |
| Canonical routing patterns (27 patterns) | operating-model:45–105 | Team templates JSON + decision tree in CLAUDE.md |
| Stage gates (all roles) | operating-model:107–133 | Distributed across role `.md` files |
| Lead quick checklist | operating-model:147–171 | `src.claude/agents/lead.md` |
| Review strategy selection + decision table | operating-model:174–226 | Compact version in operating-model + reviewer roles |
| Builder and blocker separation | operating-model:232–240 | Implicit in role index + template routing |
| Delivery loops | operating-model:7–25 | Implicit in template chain definitions |
| Change classification | operating-model:27–33 | In AGENTS.shared.md engineering hygiene |
| Fact-first workflow | operating-model:35–42 | In AGENTS.shared.md delegation principles |
| Re-intake and integration ownership | operating-model:349–354 | In AGENTS.shared.md + lead.md |
| Change-isolation guidance | operating-model:363–367 | In AGENTS.shared.md engineering hygiene |
| Governance artifacts list | operating-model:369–395 | In artifact persistence section |

## Claude-only sections (no Codex equivalent needed)

| Claude section | Lines | Why Claude-only |
|----------------|-------|-----------------|
| Template-based routing | operating-model:14–19 | Codex has no JSON team-template mechanism |
| Non-obvious routing pairs table | operating-model:82–91 | Codex inlines routing patterns instead |
| Test ownership boundary | subagent-contracts:123–132 | Could be added to Codex — see open item below |
| Detailed parallel execution protocol | operating-model:157–166 | Claude supports true parallel Agent tool calls |

## Sync procedure

When changing a shared semantic block:

1. Edit the block in the source pack
2. Find the matching row in this manifest
3. Open the other pack's file at the listed location
4. Apply the semantic change, adapting platform-specific language:
   - Claude: "Agent tool", "subagent_type", `.claude/agents/`, `work-items/bugs/`
   - Codex: "designated agent invocation mechanism", "role", `$CODEX_HOME/skills/`, "configured bug registry path"
5. Verify the no-mechanical-application rule: the change must be independently valid in the target context

## Open items

1. **Test ownership boundary** — exists in Claude's subagent-contracts but not in Codex. Consider adding to Codex `subagent-contracts.md` since test ownership is platform-neutral.
2. **Periodic controls detail level** — Claude has a full 11-row matrix; Codex defers to repo config. This is an intentional difference (Codex repos may define their own matrix), but if the control semantics change, both need updating.
3. **Parallel execution detail** — Claude has a 4-step protocol; Codex has 3 brief bullets. The semantic gap is real: Codex doesn't mention integration owner assignment for parallel work. Consider aligning.
