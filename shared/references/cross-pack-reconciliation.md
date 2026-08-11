# Cross-Pack Reconciliation Manifest

When editing shared semantic content in either pack's contract docs, update the matching block in the other pack. Platform-specific packaging (routing patterns, per-role contracts, stage gates) is intentionally different and does NOT need cross-pack sync.

Shared design-only methodology references now live in `shared/references/`. Pack-specific reference trees should keep only pack-specific material plus thin compatibility pointers where stable legacy paths still matter.

## Why the docs differ

Claude Code loads role definitions dynamically via Agent tool → contract docs are compact routing references.
Codex loads skills statically → contract docs must be self-contained lead guides with inline role contracts.

~70% of the diff is intentional platform-specific packaging. This manifest tracks only the ~30% that expresses **shared semantics** and must stay aligned.

**Anchor convention.** Rows anchor to exact `##`/`###` heading texts (`§"Heading"`), never line numbers — headings survived every rewrite of these four files intact; line numbers died with the first edit above them. Renaming an anchored heading REQUIRES updating its manifest row in the same change. Raw line-number pointers are banned in this manifest.

## Shared semantic blocks — operating-model.md

| Block | Claude (`src.claude/agents/contracts/operating-model.md`) | Codex (`src.codex/skills/lead/operating-model.md`) | Notes |
|-------|----------------------------------------------------------|-----------------------------------------------------|-------|
| Isolation rule | §"Isolation rule" | §"Isolation rule" | Claude mentions Agent tool explicitly; Codex says "designated agent invocation mechanism" |
| Research admission filter | §"Research admission filter" | §"Research admission filter" | Identical semantics, identical 8-item list + 3 gate owners |
| Interaction types | §"Interaction types" table | §"Interaction types" table | Same 8 types; Claude has prose descriptions, Codex has compact table |
| Cross-domain escalation | §"Cross-domain escalation protocol" | §"Cross-domain escalation protocol" | Identical 4-step protocol; Claude adds target-domain mapping table |
| Adjacent-issue protocol | §"Adjacent-issue protocol" | §"Adjacent-issue protocol" | Identical semantics; Codex says "configured bug registry path" vs Claude's `work-items/bugs/` |
| Artifact invalidation | §"Artifact invalidation protocol" | §"Artifact invalidation protocol" | Claude has 3 detailed steps; Codex condensed to 3 points. Same dependency chain. |
| REVISE correction cap | §"REVISE iteration cap" | §"REVISE iteration cap procedure" | Both bindings cite the shared spine's consecutive same-role/same-artifact cap and escalation procedure; neither binding owns its numeric value |
| Periodic controls | §"Periodic controls" table | §"Periodic controls" | Claude has full 11-row control matrix; Codex defers to repo-defined matrix |
| How to instruct reviewers | §"How to instruct reviewers" | §"Review strategy selection" | Claude: 2 compact paragraphs. Codex: full strategy A/B with decision table. Semantics identical. |
| Common alias map | §"Common alias map" | §"Common alias map" | Identical mappings, different formatting |
| Artifact persistence | §"Artifact persistence protocol" | §"Artifact persistence protocol" | Claude: detailed 3-tier table + when-to-save rules. Codex: condensed 3-tier table. |
| Parallel execution | §"Parallel execution protocol" | §"Parallelism guidance" | Claude: 4-step protocol with integration owner. Codex: 3 brief bullets. |
| External role routing | External role substitution notes in `operating-model.md` | External role substitution notes in `operating-model.md` | Shared semantics: consultant stays advisory-only, worker covers every non-owner non-review lane, reviewer covers `Review + QA`, and team template JSON stays unchanged. |
| Design-panel and review-loop selection | §"Design-panel and review-loop selection" (before `## How to instruct reviewers`) | §"Design-panel and review-loop selection" (before `## Review strategy selection`) | New block (2026-07-10): names the two admitted design-panel triggers (high-surface sweep / open architecture choice), the generation-vs-verification difference from review-loop, and the binding path. Neither `operating-model.md` referenced review-loop before this change (verified zero-hit); this block introduces both pointers together. Selection/pointer only — does not duplicate either contract's DP1-DP8 / angle rules. |

## Shared semantic blocks — subagent-contracts.md

| Block | Claude (`src.claude/agents/contracts/subagent-contracts.md`) | Codex (`src.codex/skills/lead/subagent-contracts.md`) | Notes |
|-------|-------------------------------------------------------------|-------------------------------------------------------|-------|
| Handoff template | §"Handoff template" | §"Shared handoff template" | Identical structure; Codex has extra placeholder lines |
| Artifact gate | §"Artifact gate" | §"Artifact gate — no delegation without brief" | Identical rules; Codex adds "if the repository uses one" qualifier |
| status.md format | §"status.md format" | §"status.md format" | Identical format. Only diff: Codex says "role to invoke" vs Claude's "agent to launch" |
| Response format | §"Response format" | §"Shared response format" | Same 5-line format. Codex adds fact-first note and consultant exception inline |
| BLOCKED classification | §"BLOCKED classification" | §"BLOCKED classification" | Identical 2-class table. Codex: "configured bug registry path" vs Claude: `work-items/bugs/` |
| Interaction rules | §"Interaction rules" | §"Interaction rules" | Same 5 rules; minor wording adaptation |
| Test ownership boundary | §"Test ownership boundary" | — | **Claude only.** Codex has no equivalent. |
| Structured completion report | §"Structured completion report" | §"Structured completion report" | Identical 4-item format |
| Gate questions | §"Gate questions" | §"Gate questions" | Identical 7 questions |
| External role contracts | External role summaries + dispatch references in `subagent-contracts.md` | External role sections in `subagent-contracts.md` | Shared semantics: assigned internal role is provenance, not a restriction on universality; roles do not self-fallback to internal specialists; orchestrator may reroute after the external role is disabled. |

## Shared semantic blocks — external dispatch

| Block | Claude (`src.claude/agents/contracts/external-dispatch.md`) | Codex (`src.codex/skills/lead/external-dispatch.md`) | Notes |
|-------|-------------------------------------------------------------|-------------------------------------------------------|-------|
| Config file location | `.claude/.agents-mode.yaml` | `.agents/.agents-mode.yaml` | `agents-mode` is the only supported operator overlay surface on these lines. |
| Extended config schema | `consultantMode`, `delegationMode`, `parallelMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, `externalProvider`, `externalPriorityProfile`, `reserveResolver`, `externalPriorityProfiles`, `externalOpinionCounts`, production-provider workdir keys, shared `externalModelMode`, and any line-specific local fields | `consultantMode`, `delegationMode`, `parallelMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, `externalProvider`, `externalPriorityProfile`, `reserveResolver`, `externalPriorityProfiles`, `externalOpinionCounts`, production-provider workdir keys, shared `externalModelMode`, and optional `externalClaudeProfile` | `consultantMode` controls consultant; `reserve` is a symbolic supplemental advisory/review candidate inside `externalPriorityProfiles`, not a scalar provider key; `reserveResolver` binds it to `claude-sonnet`, `claude-wrapper`, `wrapper:<command>`, or `disabled`; `delegationMode`, `parallelMode`, and `mcpMode` are operator-level routing, fan-out, and tooling preferences; `externalProvider` allows explicit example providers but production `auto` uses only `codex | claude`; `externalPriorityProfile` selects the named production provider-order map; `externalPriorityProfiles` stores per-profile lane orderings without example-only providers and may include `reserve` only on advisory/review lanes; `externalOpinionCounts` raises specific lanes above the default single-opinion behavior; production-provider workdir keys stay separate and default `neutral`; shared `externalModelMode` distinguishes provider runtime-default execution from pinned production-provider policy; and `externalClaudeProfile` matters only on Codex when the resolved provider is primary Claude CLI. |
| Provider dispatch | Production provider universe with profile-driven `auto`; explicit `claude` is self-provider override only on Claude line | Production provider universe with profile-driven `auto`; explicit `codex` is self-provider override only on Codex line | `auto` no longer means a line-specific provider default. It resolves through the active production priority profile, must not silently self-bounce into the current host provider, and must not select example-only providers such as Gemini or Qwen. Explicit example-provider overrides are allowed only as manual demonstration or compatibility paths. |
| Provenance header | Execution role / assigned-replaced role / requested provider / resolved provider / requested consultant mode / actual execution path / model-profile / deviation reason | Execution role / assigned-replaced role / requested provider / resolved provider / requested consultant mode / actual execution path / model-profile / deviation reason | Keep wording semantically aligned even if command examples differ. |
| Fallback boundary | Role-level no internal fallback; orchestrator may reroute when the role choice is disabled | Role-level no internal fallback; orchestrator may reroute when the role choice is disabled | Avoid ambiguous bare use of the word `fallback`. |

## Shared design-only references

These documents should not be copied again into new pack trees. Current example provider packs, including Gemini and Qwen, should reuse them from `shared/references/` as the starting layer and keep only pack-specific overlays, wrappers, or vocabulary mapping locally where the shared text is not yet fully pack-agnostic.

| Canonical shared reference | Path | Pack-local expectation |
|-------|------|------|
| Evidence pipeline | `shared/references/evidence-based-answer-pipeline.md` | Keep only compatibility pointers if old pack-local links must stay valid |
| Workflow strategy comparison | `shared/references/workflow-strategy-comparison.md` | Pack-local diagrams and operating-model docs may link here directly |
| Workflow strategy comparison (ru) | `shared/references/ru/workflow-strategy-comparison.md` | Same as above for Russian docs |
| Subagent operating model core | `shared/references/subagent-operating-model.md` | Keep pack-local wrapper plus runtime/repository addendum |
| Subagent operating model core (ru) | `shared/references/ru/subagent-operating-model.md` | Same as above for Russian docs |
| Repository publication safety | `shared/references/repository-publication-safety.md` | Keep operational commands in root docs and runtime pack docs, not here |
| Repository publication safety (ru) | `shared/references/ru/repository-publication-safety.md` | Same as above for Russian docs |
| Design-panel methodology | `shared/references/design-panel-methodology.md` | Keep provider paths and CLI syntax out; those live in the pack bindings below |
| Design-panel methodology (ru) | `shared/references/ru/design-panel-methodology.md` | Same as above for Russian docs |

Intentional pack-local exceptions:

| Reference | Current home | Why it stays local for now |
|-------|------|------|
| Periodic control matrix | `references-codex/periodic-control-matrix.md`, `references-claude/periodic-control-matrix.md` and `ru` variants | Still depends on pack/runtime vocabulary, task-memory layout, and runtime-doc links; move it only after a generic shared skeleton exists |

## Design-panel binding (trunk + Claude + Codex; gemini/qwen deferred)

Shipped 2026-07-10, primary packs only (`src.claude`, `src.codex`); the `src.gemini`/`src.qwen` demo mirror is an explicit deferred follow-on, not shipped in this change.

| Layer | Path | Notes |
|-------|------|-------|
| Trunk | `shared/references/design-panel-methodology.md` (+ `ru/` mirror) | Provider-neutral; not installed; owns the stable `DP1`-`DP8` invariant IDs verbatim |
| Claude binding | `src.claude/agents/contracts/design-panel.md` + `src.claude/commands/agents-design-panel.md` | Self-contained installed contract + thin command; mirrors the `review-loop.md` / `agents-review-loop.md` split |
| Codex binding | `src.codex/skills/design-panel/SKILL.md` + `src.codex/skills/design-panel/agents/openai.yaml` | Self-contained skill; registered in `UTILITY_SKILLS`; stays under the unchanged Codex metadata cap |
| Operating-model selection block | See the "Design-panel and review-loop selection" row above | Selection/pointer only in both packs; does not duplicate `DP1`-`DP8` |

`DP1`-`DP8` (pinned input, quorum, independence, candidate-is-input-only, mandatory comparison, sole advance gate, fail closed, one-shot-then-verify) are the conformance anchors: every binding carries the same stable IDs and semantics, with provider-condensed wording allowed (not verbatim prose); the pack validators check marker presence only, never independence or synthesis soundness (review territory).

## Codex-only sections (no Claude equivalent needed)

These exist in Codex because it must be self-contained. Claude distributes this content into individual role `.md` files.

| Codex section | Anchor (codex file) | Claude equivalent location |
|---------------|---------------------|---------------------------|
| Role map | subagent-contracts §"Role map" | Distributed across `src.claude/agents/*.md` |
| Per-role contracts (PM through Consultant) | subagent-contracts §"Product Manager" … §"Consultant" (consecutive role sections) | Each in its own `src.claude/agents/<role>.md` |
| Canonical routing patterns (27 patterns) | operating-model §"Canonical routing patterns" | Team templates JSON + decision tree in CLAUDE.md |
| Stage gates (all roles) | operating-model §"Stage gates" | Distributed across role `.md` files |
| Lead quick checklist | operating-model §"Lead quick checklist" | `src.claude/skills/lead/SKILL.md` (`agents/lead.md` is fail-closed only) |
| Review strategy selection + decision table | operating-model §"Review strategy selection" | Compact version in operating-model + reviewer roles |
| Builder and blocker separation | operating-model §"Builder and blocker separation" | Implicit in role index + template routing |
| Delivery loops | operating-model §"Delivery loops" | Implicit in template chain definitions |
| Change classification | operating-model §"Change classification" | In AGENTS.shared.md engineering hygiene |
| Fact-first workflow | operating-model §"Fact-first workflow" | In AGENTS.shared.md delegation principles |
| Re-intake and integration ownership | operating-model §"Re-intake and integration ownership" | In AGENTS.shared.md + `src.claude/skills/lead/SKILL.md` |
| Change-isolation guidance | operating-model §"Change-isolation guidance" | In AGENTS.shared.md engineering hygiene |
| Governance artifacts list | operating-model §"Governance artifacts to keep near the code" | In artifact persistence section |

## Claude-only sections (no Codex equivalent needed)

| Claude section | Anchor (claude file) | Why Claude-only |
|----------------|----------------------|-----------------|
| Template-based routing | operating-model §"Template-based routing" | Codex has no JSON team-template mechanism |
| Non-obvious routing pairs table | operating-model §"Non-obvious routing pairs" | Codex inlines routing patterns instead |
| Test ownership boundary | subagent-contracts §"Test ownership boundary" | Could be added to Codex — see open item below |
| Detailed parallel execution protocol | operating-model §"Parallel execution protocol" | Claude supports true parallel Agent tool calls |

## Sync procedure

When changing a shared semantic block:

1. Edit the block in the source pack
2. Find the matching row in this manifest
3. Open the other pack's file at the anchored heading
4. Apply the semantic change, adapting platform-specific language:
   - Claude: "Agent tool", "subagent_type", `.claude/agents/`, `work-items/bugs/`
   - Codex: "designated agent invocation mechanism", "role", `$CODEX_HOME/skills/`, "configured bug registry path"
5. Verify the no-mechanical-application rule: the change must be independently valid in the target context

## Open items

1. **Test ownership boundary** — exists in Claude's subagent-contracts but not in Codex. Consider adding to Codex `subagent-contracts.md` since test ownership is platform-neutral.
2. **Periodic controls detail level** — Claude has a full 11-row matrix; Codex defers to repo config. This is an intentional difference (Codex repos may define their own matrix), but if the control semantics change, both need updating.
3. **Parallel execution detail** — Claude has a 4-step protocol; Codex has 3 brief bullets. The semantic gap is real: Codex doesn't mention integration owner assignment for parallel work. Consider aligning.
