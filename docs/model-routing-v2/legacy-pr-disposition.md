# Legacy PR disposition for the current-main V2 proposal

Baseline: main 68ad6e733e049ad3f86b37af59ea806e8d1a5b25 (2026-10-21).
This is a design consolidation, not a claim that all legacy production changes
are merged or verified. No old PR is closed by this proposal.

## Decisions

| PR | Decision | Preserved value and remaining work |
|---|---|---|
| #5 | Separate optional-feature candidate | Preserve bounded overlay parsing, explicit selection, exact target/lane checks, nonauthority and Ponytail isolation. Do not make its plugin/catalog mechanism a V2 prerequisite. Check existing composition and installer projection before adopting any code. |
| #6 | Supersede separate Astra selector in the V2 architecture | Keep task-specific evidence, model-local effort, bounds and negative-test requirements. Existing role/task policy remains sole eligibility owner; no competing per-model scheduler. A compatibility facade needs a demonstrated caller. |
| #7 | Supersede parallel generic-worker selector in V2 | Keep role/scope/host identity, request binding, explicit fallback and nonauthority requirements. Current resolver/adapter owns them; do not import old model-floor dictionaries or stale Luna methodology. |
| #8 | Retain and revise design/contracts/tests | This proposal uses its record invariants and negative tests, changes integration to current owners, and defers transferable-host machinery without weakening schema requirements. No runtime implementation or scientific performance result is asserted. |
| #9 | Independent platform-maintenance work remains open | Do not bury production/platform repairs in routing design. Source residuals below are not fixed by this documentation candidate. |
| #11 | Do not restore closed historical branch | Main already owns the model-policy migration. Preserve current policy rather than reapplying old defaults. |

## Current source residuals from #9

Static observations on the pinned main, not native reproductions:
- scripts/production_installer.py:5052-5061 still chmods the failed leaf and retries
  the callback. Its transaction-owned cleanup needs the bounded traversal/link
  analysis retained in #9, not mechanical replacement of the enlarged installer.
- scripts/install-hypothesis-hook.py:235-238 passes implicit sys.executable directly
  to validation. #9 resolves the implicit interpreter only, preserving strict
  explicit overrides. Preserve the newer require_script behavior when porting.
- scripts/provider_prompt.py:2390-2402 returns raw expected SDDL while the later
  verifier compares rendered descriptors. #9's normalization requires native
  Windows review while retaining exact DACL protection, principal and ACE checks.
- scripts/universal-hooks/scripts/check-publication-safety.py:2555-2565 checks
  consecutive config entries and the next index, not the complete indexed
  namespace. #9 contains whole-namespace validation. This is security-sensitive
  publication code: maintain canonical/mirror propagation and fresh gate evidence.
- Checkout bytes, platform-home selection, fixture portability and historical
  accepted-prior expectations remain separately reviewable. Do not replace modern
  fixtures or publication authority logic with September snapshots.

Resolution criteria: reproduce the relevant failure without launching providers,
port only surviving behavior to its current owner, preserve unrelated new logic,
run platform-specific regression tests and obtain the required independent review.
None of these criteria is satisfied merely by including this table.

## Exact source inventory and disposition

Every path below comes from the PR's paginated changed-file listing. Listing a
path is not a claim of full semantic audit. The PR-level disposition above applies
to each listed path; historical tests are retained evidence, not fresh passes.

### PR #5

Source: https://github.com/applicate2628/Orchestrarium/pull/5
Head: 51af71e0cf6374237dd3b9df4e791b32abde6a58.

- `RELEASE_NOTES.md`
- `docs/README.md`
- `docs/plans/2026-09-03-policy-overlays-ponytail-compatibility.md`
- `docs/policy-overlays.md`
- `src.codex/skills/policy-overlay/SKILL.md`
- `src.codex/skills/policy-overlay/agents/openai.yaml`
- `src.codex/skills/policy-overlay/policies/complexity-review.md`
- `src.codex/skills/policy-overlay/policies/lean-implementation.md`
- `src.codex/skills/policy-overlay/policy-overlays.v1.json`
- `src.codex/skills/policy-overlay/references/ponytail-compatibility.md`
- `src.codex/skills/policy-overlay/scripts/policy-overlays.py`
- `src.codex/skills/policy-overlay/scripts/policy_overlay_core.py`
- `tests/test_policy_overlay_boolean_contract.py`
- `tests/test_policy_overlay_config_boundary.py`
- `tests/test_policy_overlay_input_review.py`
- `tests/test_policy_overlay_metadata_compatibility.py`
- `tests/test_policy_overlay_resolution_hardening.py`
- `tests/test_policy_overlay_skill_contract.py`

### PR #6

Source: https://github.com/applicate2628/Orchestrarium/pull/6
Head: c4d1ec0a877427aa1e48ac1ba7e4165df13c1517.

- `docs/model-routing-audit-2026-09-04.md`
- `docs/superpowers/plans/2026-09-04-astra-model-routing-implementation.md`
- `docs/superpowers/specs/2026-09-04-astra-model-routing-design.md`
- `src.codex/skills/astra-routing/SKILL.md`
- `src.codex/skills/astra-routing/agents/openai.yaml`
- `src.codex/skills/astra-routing/scripts/resolve.py`
- `tests/test_astra_routing_v1.py`
- `tests/test_astra_routing_v1_effort_binding.py`
- `tests/test_astra_routing_v1_effort_floor.py`
- `tests/test_astra_routing_v1_hardening.py`
- `tests/test_astra_routing_v1_input_bounds.py`

### PR #7

Source: https://github.com/applicate2628/Orchestrarium/pull/7
Head: 5ba5c02e1c419152ea78a91a996c6ae5a6518a9c.

- `RELEASE_NOTES.md`
- `docs/README.md`
- `docs/lead-contract-routing-audit-2026-09-04.md`
- `docs/routing-v1-operator-guide.md`
- `docs/superpowers/plans/2026-09-04-lead-worker-routing-v1-implementation.md`
- `docs/superpowers/specs/2026-09-04-lead-worker-routing-v1-design.md`
- `src.codex/skills/lead-worker-routing/SKILL.md`
- `src.codex/skills/lead-worker-routing/agents/openai.yaml`
- `src.codex/skills/lead-worker-routing/scripts/_resolver_base.py`
- `src.codex/skills/lead-worker-routing/scripts/resolve.py`
- `tests/test_lead_worker_routing_v1.py`
- `tests/test_lead_worker_routing_v1_deep_review.py`
- `tests/test_lead_worker_routing_v1_effort_policy.py`
- `tests/test_lead_worker_routing_v1_input_io.py`
- `tests/test_lead_worker_routing_v1_metadata_compatibility.py`
- `tests/test_lead_worker_routing_v1_model_provider_binding.py`
- `tests/test_lead_worker_routing_v1_private_entrypoint.py`
- `tests/test_lead_worker_routing_v1_provider_binding_public.py`
- `tests/test_routing_utility_installed.py`
- `tests/test_routing_v1_operator_guide.py`

### PR #8

Source: https://github.com/applicate2628/Orchestrarium/pull/8
Head: f5c7a07b2a16791e97c1ee9d562a986b8ebb4e52.

- `docs/README.md`
- `docs/adaptive-model-routing-v2-audit-2026-09-04.md`
- `docs/model-routing-v2/README.md`
- `docs/model-routing-v2/adaptive-routing-contracts.v2.schema.json`
- `docs/model-routing-v2/adaptive-routing-operational.v2.schema.json`
- `docs/model-routing-v2/deep-review-operational-hardening.md`
- `docs/model-routing-v2/effort-profile-evidence.md`
- `docs/model-routing-v2/examples.v2.json`
- `docs/model-routing-v2/operational-examples.v2.json`
- `docs/model-routing-v2/review-loop-closure.md`
- `docs/model-routing-v2/runtime-validation-obligations.md`
- `docs/superpowers/plans/2026-09-04-adaptive-lead-model-routing-v2-implementation.md`
- `docs/superpowers/specs/2026-09-04-adaptive-lead-model-routing-v2-design.md`
- `tests/test_adaptive_model_routing_v2_contracts.py`
- `tests/test_adaptive_model_routing_v2_cost_units.py`
- `tests/test_adaptive_model_routing_v2_documentation_alignment.py`
- `tests/test_adaptive_model_routing_v2_effort_profiles.py`
- `tests/test_adaptive_model_routing_v2_integrity.py`
- `tests/test_adaptive_model_routing_v2_operational.py`
- `tests/test_adaptive_model_routing_v2_profile_guidance.py`
- `tests/test_adaptive_model_routing_v2_result_boundary.py`
- `tests/test_adaptive_model_routing_v2_review_obligations.py`
- `tests/test_adaptive_model_routing_v2_scalar_boundaries.py`
- `tests/test_adaptive_model_routing_v2_validation_example.py`

### PR #9

Source: https://github.com/applicate2628/Orchestrarium/pull/9
Head: e3e122c9baec6f0083436ee431162e9ee422804e.

- `.gitattributes`
- `RELEASE_NOTES.md`
- `references-claude/ru/claude-md-structural-enforcement.md`
- `scripts/install-hypothesis-hook.py`
- `scripts/production_installer.py`
- `scripts/provider_prompt.py`
- `scripts/universal-hooks/scripts/check-publication-safety.py`
- `scripts/validate-claude-md.py`
- `shared/provider-prompt-projections.v1.json`
- `src.claude/CLAUDE.md`
- `src.claude/agents/scripts/check-publication-safety.py`
- `src.codex/skills/lead/scripts/check-publication-safety.py`
- `tests/fixtures/git_history.py`
- `tests/test_claude_checkout_contract.py`
- `tests/test_claude_md_size.py`
- `tests/test_claude_reference_mirror.py`
- `tests/test_git_history_fixtures.py`
- `tests/test_global_lead_accepted_prior.py`
- `tests/test_hook_health.py`
- `tests/test_install_hypothesis_hook.py`
- `tests/test_installer_global_home_platform.py`
- `tests/test_installer_readonly_cleanup.py`
- `tests/test_mutate_work_item.py`
- `tests/test_native_luna_corridor.py`
- `tests/test_native_role_slice_a.py`
- `tests/test_provider_prompt_projections.py`
- `tests/test_publication_safety_scanner.py`
- `tests/test_repository_local_boundaries.py`
- `tests/test_sessionstart_reminder_python_hooks.py`
- `tests/test_slice_a_detached_validation.py`
- `tests/test_windows_private_dacl.py`
- `tests/test_work_item_state_validator.py`
- `tests/test_wrapper_model_effort_guard.py`

## Integration boundaries

Use a current-main draft for the consolidated design rather than rebasing or
merging the old stack wholesale. Link this proposal from prior PRs only after
publication is authorized and no prohibited automatic run is triggered.
Do not claim supersession closes unported optional functionality or platform
repairs. Do not import root release notes or docs indexes from old branches.

## Terms and Abbreviations

PR: pull request. SDDL: Windows security descriptor definition language.
DACL: discretionary access-control list. ACE: access-control entry.
V2: the proposed second-version extension, not an installed runtime release.
