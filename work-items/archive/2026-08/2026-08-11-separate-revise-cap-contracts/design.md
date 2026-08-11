# Design — separate REVISE cap contracts

Decision: `2026-08-11-separate-revise-cycle-and-review-round-caps` (proposed).

## Chosen approach

Keep two independent owners and delete the third, unsupported interpretation.

1. `shared/AGENTS.shared.md` remains the sole numeric owner of the generic Lead correction cap: 3 consecutive `REVISE` cycles for the same role and artifact.
2. Rename the review-loop engine's ambiguous `DEFAULT_CAP` to `REVIEW_LOOP_ROUND_CAP`; it remains 3 and continues to support explicit per-run `--cap` overrides.
3. Generic Lead skills, operating models, diagrams, commands, and comparisons cite the shared policy without retyping `3`.
4. Review-loop methodology and provider bindings retain self-contained `N = 3 rounds` text, mechanically checked against `REVIEW_LOOP_ROUND_CAP` by one dedicated contract test.
5. Delete `per stage` and the reconciliation claim that the two provider texts are semantically identical without naming their unit.

## Components and interactions

- **Generic owner:** one shared-spine sentence. Provider assemblies already install that spine as their universal minimum contract.
- **Round owner:** `review_loop_state.py`; `validate_v1`, `validate_v2`, CLI defaults, migration, and recovery all consume `REVIEW_LOOP_ROUND_CAP`.
- **Drift gate:** `tests/test_revise_cap_contracts.py` inventories every admitted generic and review-loop consumer, extracts numeric/unit language, and rejects unclassified live copies.
- **Reconciliation:** `shared/references/cross-pack-reconciliation.md` records that Claude/Codex generic bindings consume the same shared policy while the autonomous round cap is a separate review-loop contract.

## Change-Surface Contract

`{ intended change surface: review_loop_state.py, validate-review-loop-state.py, generic Lead cap prose consumers, review-loop cap prose consumers, cross-pack reconciliation, one new contract test, one release bullet, lifecycle artifacts; approved extension seams: existing shared spine owner, review-loop runtime constant, existing test suite; protected / must-not-touch surfaces: git-push p95 runner/installer/docs, publication hooks, provider launchers, agent-run schema, upstream runtime bugs, unrelated numeric limits; declared blast radius: governance wording and the unchanged default value/name used by review-loop validation }`

## Dependency direction

Generic provider docs depend conceptually on the installed shared spine. The review-loop wrapper imports its constant from the existing engine. Tests depend on both owners; neither owner depends on tests or provider prose.

## External and persisted contracts

No persisted-state or external behavior change. V1/V2 ledgers, explicit `--cap`, default value 3, escalation behavior, and installed skill identities remain compatible. The internal Python constant name changes without a compatibility alias; repository callers are updated atomically and a residue guard rejects `DEFAULT_CAP`.

## Failure modes and observability

| Failure mode | Observable discriminator |
| --- | --- |
| Generic numeric copy is reintroduced | `test_generic_lead_cap_has_one_numeric_owner` fails with the path |
| Provider text regains `per stage` scope | `test_generic_lead_cap_consumers_use_same_role_and_artifact_scope` fails |
| Review-loop prose drifts from runtime default | `test_review_loop_round_consumers_match_runtime_owner` fails with expected/actual value |
| Runtime code retains ambiguous owner name | `test_retired_ambiguous_cap_owner_is_absent` fails |
| Existing ledger behavior changes | focused `tests/test_review_loop_state_v2.py` regression fails |

## Security and reliability

No trust boundary or external process changes. Fail-closed validation remains unchanged. Separate owners prevent an unrelated policy edit from silently weakening the autonomous deadlock guard.

## Diff-invisible invariants

- **Named regression guard — explicit override:** run the review-loop state tests; a caller-supplied cap still overrides the default.
- **Named regression guard — generic scope:** dedicated contract test requires `same role and artifact` and `consecutive` in the canonical owner.
- **Named regression guard — provider parity:** both pack validators and shared spine validator remain PASS.
- **Named regression guard — p95 isolation:** staged diff inventory contains none of the parked runner/installer files.

## Alternatives

1. **One shared constant for both policies.** Rejected because one role/artifact correction cycle and one multi-angle round are different trace units; equal current values do not create shared semantics.
2. **Leave prose as-is and add only a hash pin.** Rejected because a pin would preserve the false `per stage` interpretation rather than correct it.
3. **Add a new machine-readable governance file imported everywhere.** Rejected as unnecessary runtime/config machinery: the generic policy has no runtime consumer, while the review-loop already has an owning engine constant.

## Claims

1. `{ guarantee: The generic Lead cap has exactly one numeric owner; single-owner: shared/AGENTS.shared.md generic REVISE sentence; enforcement-probe: test_generic_lead_cap_has_one_numeric_owner }`
2. `{ guarantee: The generic unit is consecutive cycles for the same role and artifact; single-owner: shared spine policy; enforcement-probe: test_generic_lead_cap_consumers_use_same_role_and_artifact_scope }`
3. `{ guarantee: The unsupported per-stage unit is absent from live cap prose; single-owner: C6 residue inventory; enforcement-probe: test_generic_lead_cap_consumers_use_same_role_and_artifact_scope }`
4. `{ guarantee: Autonomous review-loop default is named and owned as rounds; single-owner: review_loop_state.py::REVIEW_LOOP_ROUND_CAP; enforcement-probe: test_review_loop_round_consumers_match_runtime_owner }`
5. `{ guarantee: Review-loop provider prose matches the runtime default and round unit; single-owner: dedicated consumer inventory; enforcement-probe: test_review_loop_round_consumers_match_runtime_owner }`
6. `{ guarantee: Explicit --cap overrides remain supported; single-owner: review_loop_state CLI; enforcement-probe: existing review-loop-state V2 CLI tests }`
7. `{ guarantee: DEFAULT_CAP is deleted without alias residue; single-owner: review-loop engine constant namespace; enforcement-probe: test_retired_ambiguous_cap_owner_is_absent }`
8. `{ guarantee: Claude and Codex generic Lead bindings consume the same shared scope; single-owner: cross-pack reconciliation row; enforcement-probe: generic consumer inventory plus both pack validators }`
9. `{ guarantee: Parked p95 implementation files are untouched by this item; single-owner: Change-Surface Contract; enforcement-probe: staged name-status audit }`
10. `{ guarantee: No persisted ledger or exit behavior changes; single-owner: review_loop_state validation API; enforcement-probe: full tests/test_review_loop_state_v2.py }`

## Test strategy

Capture RED from the new exact inventory against current `per stage`, duplicate numbers, and `DEFAULT_CAP`. Make the smallest owner/prose changes, then run the new test, full review-loop-state tests, provider pack validators, spine/Claude binding checks, diff/C6 scans, QA, and architecture review.

## Gate decision

PASS.

## Terms and Abbreviations

- **C6:** the rule requiring obsolete live relationships to be removed.
- **CLI:** command-line interface.
- **PASS:** implementation may proceed through the accepted seams.
