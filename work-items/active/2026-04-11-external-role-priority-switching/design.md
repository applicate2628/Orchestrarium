# Design

## Decision

Adopt one additive `agents-mode` schema extension for all three packs, and make provider choice depend on a switchable named priority profile rather than a host-pack default. Keep the current scalar `externalProvider` meaning intact: explicit `codex`, `claude`, or `gemini` still force one provider; `auto` remains the only path that resolves through shared priority data.

Canonical owners for the change surface remain:
- [AGENTS.shared.md](d:/dev/Orchestrator/Orchestrarium/shared/AGENTS.shared.md#L29)
- [AGENTS.md](d:/dev/Orchestrator/Orchestrarium/AGENTS.md#L22)
- [agents-mode-reference.md](d:/dev/Orchestrator/Orchestrarium/docs/agents-mode-reference.md#L15)
- [external-worker-design.md](d:/dev/Orchestrator/Orchestrarium/docs/external-worker-design.md#L87)
- pack-local `external-dispatch` contracts in `src.codex`, `src.claude`, and `src.gemini`

## Proposed Schema

Add three additive keys to the existing canonical `agents-mode` schema:

| Key | Type | Purpose |
|---|---|---|
| `externalPriorityProfile` | scalar string | Selects the active named profile used when `externalProvider: auto` |
| `externalPriorityProfiles` | map of profile name -> lane -> ordered provider list | Stores switchable provider orders per lane |
| `externalOpinionCounts` | map of lane -> integer | Declares how many distinct external opinions to collect for that lane |

Defaulting rule:
- Missing `externalPriorityProfile` means `balanced`.
- Missing `externalPriorityProfiles.balanced` means the current shared lane matrix.
- Missing `externalOpinionCounts[lane]` means `1`.

This keeps the existing scalar `externalProvider` contract stable and avoids breaking current writers that already preserve unknown keys.

Guardrails for the new nested keys:
- keep the nesting capped at `profile -> lane -> ordered provider list`; do not introduce deeper role-level nesting
- reserve `balanced` as the implicit default profile name
- validate every provider entry against `codex | claude | gemini`
- treat the three new keys as the only approved multi-line exception to the older "one key per line" guidance
- require update tools to preserve these blocks verbatim rather than trying to flatten or partially rewrite them line-by-line

## Routing Algorithm

1. Classify the request into one of the existing lanes: advisory, worker, review, or owner.
2. Reject owner-role substitution unless the role is explicitly eligible for external routing.
3. Resolve the active provider order from `externalPriorityProfiles[externalPriorityProfile][lane]`.
4. If `externalProvider` is explicit, use that single provider and do not fan out.
5. If `externalProvider: auto`, walk the active ordered list, skip unavailable providers, skip ordinary self-bounce on the host line, and collect distinct eligible providers until `externalOpinionCounts[lane]` is satisfied.
6. If the requested opinion count cannot be satisfied, fail closed with `BLOCKED` and keep any collected opinions as evidence, but do not advance the gate.
7. For multi-opinion advisory or review lanes, any returned `REVISE` or `BLOCKED` verdict blocks gate advancement unless a stricter repo-local rule overrides it explicitly.

Gemini participates in broader advisory and review work by being ranked in the active profile for non-visual lanes, not by a special-case exception. The existing visual-first heuristic remains honest as a lane profile choice, not as a hidden provider default.

`claude-api` stays a Claude transport, not a provider. Once the resolved provider is Claude, `externalClaudeSecretMode` and `externalClaudeApiMode` apply in the existing order; no new fourth provider is introduced.

## Migration And Defaults

The migration path is additive:
- preserve `consultantMode`, `delegationMode`, `mcpMode`, `preferExternalWorker`, `preferExternalReviewer`, `externalProvider`, workdir modes, Claude transport modes, and `externalClaudeProfile`
- seed `externalPriorityProfile: balanced`
- seed `externalPriorityProfiles.balanced` with the current shared lane matrix
- seed `externalOpinionCounts` to `1` for all lanes unless a repo-local policy explicitly requests more opinions on a lane

Current closeout wording that says a batch ends with exactly one external consultant-check must be rewritten to “one or more external consultant-checks as required by the active lane policy.” The default remains one check, but the gate becomes pluralizable when the active profile or lane policy asks for it.

Recommended defaults:
- `externalPriorityProfile: balanced`
- `externalOpinionCounts` stays `1` by default on ordinary lanes, so the system remains quiet unless a lane explicitly asks for more than one external opinion
- repo-local policy may raise counts on higher-scrutiny advisory/review lanes without changing scalar `externalProvider`

## Alternatives

1. **Flat top-level priority keys instead of a profile map**
   - Considered because one external opinion argued that a flatter shape would feel safer for ecosystems with line-oriented config editing.
   - Rejected because profiles are a real policy dimension here, and flattening would either duplicate per-lane orders across many keys or reintroduce a second indirection mechanism under a different name.
   - The accepted mitigation is not flattening, but tightening the nested shape and explicitly treating the new blocks as approved multi-line control-plane exceptions.
2. **Single global opinion-count scalar**
   - Rejected because it cannot express different requirements for advisory, review, worker, and visual lanes.
3. **Per-provider booleans only**
   - Rejected because it preserves the old hidden priority matrix and cannot express switchable ordered fan-out.
4. **Separate routing file beside `agents-mode`**
   - Rejected because it duplicates control-plane state and forces writers/readers to keep two sources of truth in sync.

The chosen design is the smallest durable extension that preserves existing scalar behavior and makes the provider order honest and switchable.

## Boundaries And Extension Seams

The change should land only at the control-plane seams that already own routing policy:
- schema and examples in `agents-mode-reference.md`
- shared governance in `AGENTS.shared.md` and `AGENTS.md`
- pack-local `external-dispatch`, `consultant`, `external-worker`, `external-reviewer`, `second-opinion`, `init-project`, `help`, `operating-model`, and `subagent-contracts`
- standalone mirrors in `codex`, `claude`, and `gemini`

Do not move provider-choice logic into consumer-side wrappers or ad hoc heuristics in unrelated files.

## Failure Modes

- Unknown `externalPriorityProfile` must fail closed rather than silently falling back to a different profile.
- Insufficient available providers for the requested opinion count must produce `BLOCKED`, not a partial pretend-PASS.
- A provider being unavailable should skip that provider, but not invalidate the entire route unless the count cannot be met.
- Explicit provider overrides remain scalar and must not accidentally fan out.

## Observability And Validation

Record these fields in consultant/external artifacts and logs:
- active profile name
- lane name
- requested opinion count
- resolved provider order
- selected providers
- skipped providers and skip reasons
- final gate outcome

Validation impact:
- Codex and Claude validator hash pins for shared reference docs will need refresh if the shared reference text changes.
- The pack validators should continue to pass without changing file inventories.
- Add regression coverage for profile resolution, self-bounce exclusion, count shortfall blocking, multi-opinion gate aggregation, and preservation of explicit scalar override behavior.

## External Opinion Synthesis

Two independent external opinions were collected after the initial architecture pass:

| External source | Main takeaway | Accepted response |
|---|---|---|
| Claude transport (`claude-api`) | supported the profile-map design, but required explicit default-profile naming, count-vs-provider validation, and a deterministic multi-opinion aggregation rule | accepted |
| Gemini CLI | argued for a flatter line-oriented schema because `.agents-mode` has historically looked like a flat key/value file | partially accepted as a risk signal, but not as the final schema choice |

Lead resolution:
- keep the additive profile-map design
- add the explicit nesting, validation, and aggregation guards above
- keep the new keys narrow enough that update tools can preserve them safely without inventing deeper structure

## Recommended Implementation Slicing

1. Update shared/main schema docs and closeout wording first, with the canonical default profile and opinion-count semantics.
2. Update Codex pack mirrors and validators.
3. Update Claude pack mirrors and validators.
4. Update Gemini pack mirrors and validators.
5. Run a final validation sweep across all four trees, then let `$architecture-reviewer` inspect the combined control-plane diff.

## Claims

1. `externalProvider` remains a scalar and keeps its current meaning.
2. `claude-api` remains a Claude transport and does not become a fourth provider.
3. `externalPriorityProfile`, `externalPriorityProfiles`, and `externalOpinionCounts` are additive and do not require a breaking migration.
4. Gemini can participate in non-visual advisory and review lanes when the active profile ranks it inside the requested opinion count.
5. Lead closeout becomes pluralizable, but the default closeout still requires one external consultant-check.
6. No provider-selection logic moves outside the existing control-plane owner files.
7. Multi-opinion advisory and review lanes have an explicit fail-closed aggregation rule instead of ambiguous first-opinion wins semantics.
8. Shared/main and all three pack mirrors stay symmetric at the schema level, with differences expressed only as named profiles and explicit defaults.

## Adjacent Findings

None in admitted scope.

PASS
