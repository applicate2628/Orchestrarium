# Terra, Luna, Sol, and Astra Routing Audit

## Audit baseline

- Repository: `applicate2628/Orchestrarium`.
- Audited `main`: `ece04040627fcc0d0988128e44d401de53ff01fb`.
- Open pull requests reviewed: PR 4 and PR 5.
- PR 4 has unresolved review findings and is not a safe model-routing base.
- PR 5 is a separate Ponytail/policy-overlay change and has no model-routing file overlap; model routing stays in separate pull requests.

## Current defects

1. `shared/role-routing-policy.v1.json` places `mechanical`, `balanced`, `frontier`, and `apex` in one order even though Luna is a zero-authority mechanical execution class rather than a lower general-reasoning tier.
2. `apex-max` names the `apex` tier but still binds `gpt-5.6-sol`; the tier is therefore not a distinct model capability.
3. Model family and reasoning effort are stored separately but the runtime selection path is incomplete: native roles are static TOML bindings, while the policy's `allowedProfiles` are not a general per-dispatch selector.
4. Model identifiers are repeated across the role policy, native TOML, provider profile configuration, tests, and documentation.
5. There is no first-class total-route economics owner. Per-token price cannot account for Astra reducing output tokens, tool steps, retries, rework, repeated context, or time-to-accepted-result.
6. Availability, long-context pricing, maximum-effort approval, safety approval, automatic fan-out, fallback, and model-family independence are not one coherent model-selection decision.
7. Changing existing native role TOML or the shared policy requires exact stock-prior installer migration; a quick V1 patch must not bypass that ownership boundary.

## V1 decision

Add a new installable, create-only `astra-routing` skill instead of mutating existing native roles or the pinned V1 policy. The skill uses the already-supported explicit external Codex model-plus-effort flag path. Existing Terra, Sol, Luna, role, sandbox, and review defaults remain unchanged.

The narrow default is Astra `medium` for mathematical research, connected scientific workflows, and cross-system synthesis; critical recovery starts at `high`. `xhigh` requires evidence that `high` is insufficient, and `max` requires explicit human approval. Missing runtime availability fails with no silent fallback. Automatic Astra fan-out is one.

## V2 decision

V2 replaces linear model ranking with:

- execution class: `mechanical | general`;
- general capability: `balanced < frontier < apex`;
- exact model-effort profiles;
- a model catalog with per-model supported effort values;
- complete candidate-route economics measured as expected cost per accepted result;
- explicit availability, fallback, maximum-effort, safety, fan-out, and evidence-independence gates;
- a pure deterministic resolver that does not launch providers.

Luna remains mechanical-only. Terra maps to balanced, Sol to frontier, and Astra to apex. Mathematical and agentic-scientific V2 routes default to Astra `medium`, while routine or cleanly decomposable work remains on Terra or Sol unless complete route evidence proves Astra cheaper or an objective quality floor requires it.

## Pull-request interaction

- PR 4: model branches must be rebased or merge-tested only after its unresolved findings are fixed; expected conflicts are documentation/release-log related rather than model-policy ownership.
- PR 5: no current file overlap with this work. Its generic instruction-overlay feature may later carry `astra-routing`, but neither branch depends on the other.

## Terms and Abbreviations

- **PR:** Pull Request, a request to merge a branch.
- **TOML:** Tom's Obvious Minimal Language, the native-role configuration format.
- **V1/V2:** Orchestrarium Version 1 and Version 2 contracts.
