"""Focused guards for the canonical Causal UI Continuity contract.

The contract is the semantic owner.  This module is only its executable
projection: it exercises the named guards, route/pointer topology, and planted
negative controls without introducing a runtime validator or framework policy.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
ENGLISH = ROOT / "shared" / "references" / "ui-transition-continuity.md"
RUSSIAN = ROOT / "shared" / "references" / "ru" / "ui-transition-continuity.md"
README = ROOT / "README.md"
INSTALL = ROOT / "INSTALL.md"
INSTALLER = ROOT / "scripts" / "production_installer.py"

TRANSITION_CLASSES = (
    "exact-replay",
    "value-status",
    "structural",
    "adaptive",
    "intentional",
    "corrective",
    "lifecycle",
)
DIMENSIONS = (
    "spatial",
    "semantic-object",
    "model",
    "render-object",
    "interaction",
    "item-metric",
    "accessibility/status",
    "motion",
)
FAILURE_IDS = (
    "UI-CONTINUITY-INPUT-UNACCOUNTED",
    "UI-CONTINUITY-OWNER-COLLISION",
    "UI-CONTINUITY-SETTLED-UNPROVEN",
    "UI-CONTINUITY-CAUSALITY-BREACH",
    "UI-CONTINUITY-PARTIAL-COMMIT",
    "UI-CONTINUITY-KEY-CONFLICT",
    "UI-CONTINUITY-STATE-LOSS",
    "UI-CONTINUITY-INVALID-STATE",
    "UI-CONTINUITY-A11Y-MISMATCH",
    "UI-CONTINUITY-ADAPTATION-BLOCKED",
    "UI-CONTINUITY-NOT-SETTLED",
    "UI-CONTINUITY-TRANSIENT-UNOBSERVED",
    "UI-CONTINUITY-CONTRACT-DRIFT",
    "UI-CONTINUITY-DOC-DRIFT",
    "UI-CONTINUITY-RU-SEMANTIC-DRIFT",
)
SCENARIO_IDS = (
    "exact-replay",
    "value-status-progress",
    "structure-change",
    "responsive-adaptation",
    "font-locale-adaptation",
    "interaction-anchor",
    "status-announcement",
    "explicit-layout-intent",
    "corrective-invalidation",
    "lifecycle-recreation",
    "reduced-motion",
    "premature-settlement",
)
ROLES = (
    "ux-designer",
    "frontend-engineer",
    "qt-ui-engineer",
    "model-view-engineer",
    "ui-test-engineer",
    "qa-engineer",
    "accessibility-reviewer",
    "ux-reviewer",
    "architecture-reviewer",
)
ROLLOUT_PATHS = frozenset(
    {
        "shared/references/ui-transition-continuity.md",
        "shared/references/ru/ui-transition-continuity.md",
        "shared/references/README.md",
        "README.md",
        "INSTALL.md",
        "RELEASE_NOTES.md",
        "scripts/production_installer.py",
        "scripts/skill_pack_validator_runtime.py",
        "src.codex/skills/lead/scripts/validate-skill-pack.py",
        "src.claude/agents/scripts/validate-skill-pack.py",
        "tests/test_ui_transition_continuity_contract.py",
        "tests/test_python_validator_runtime.py",
        *(f"src.codex/skills/{role}/SKILL.md" for role in ROLES),
        *(f"src.claude/agents/{role}.md" for role in ROLES),
    }
)


@dataclass(frozen=True)
class _Transition:
    declared_input: bool = True
    permissions: frozenset[str] = frozenset()
    causal_scope: frozenset[str] = frozenset()


def _read_required(path: Path, failure_id: str, label: str) -> str:
    if not path.is_file():
        pytest.fail(f"{failure_id}: missing {label}: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def _english() -> str:
    return _read_required(
        ENGLISH,
        "UI-CONTINUITY-CONTRACT-DRIFT",
        "normative English contract surface",
    )


def _russian() -> str:
    return _read_required(
        RUSSIAN,
        "UI-CONTINUITY-RU-SEMANTIC-DRIFT",
        "non-authoritative Russian mirror surface",
    )


def _assert_tokens(text: str, tokens: tuple[str, ...], failure_id: str) -> None:
    folded = " ".join(text.casefold().split())
    missing = [
        token
        for token in tokens
        if " ".join(token.casefold().split()) not in folded
    ]
    assert not missing, f"{failure_id}: missing tokens: {missing}"


def _changed_dimensions(before: dict[str, object], after: dict[str, object]) -> set[str]:
    return {dimension for dimension in DIMENSIONS if before[dimension] != after[dimension]}


def _causal_verdict(
    before: dict[str, object],
    after: dict[str, object],
    transition: _Transition,
) -> str:
    if not transition.declared_input:
        return "UI-CONTINUITY-INPUT-UNACCOUNTED"
    changed = _changed_dimensions(before, after)
    if changed - transition.permissions or changed - transition.causal_scope:
        return "UI-CONTINUITY-CAUSALITY-BREACH"
    return "PASS"


def _adaptation_verdict(
    before: dict[str, object],
    after: dict[str, object],
    transition: _Transition,
    *,
    content_fits: bool,
) -> str:
    if not content_fits:
        return "UI-CONTINUITY-ADAPTATION-BLOCKED"
    return _causal_verdict(before, after, transition)


def _observation(**changes: object) -> dict[str, object]:
    observation = {dimension: f"stable:{dimension}" for dimension in DIMENSIONS}
    observation.update(changes)
    return observation


def _identity_verdict(
    before_keys: tuple[str, ...],
    after_keys: tuple[str, ...],
    before_state: dict[str, str],
    after_state: dict[str, str],
) -> str:
    if len(after_keys) != len(set(after_keys)) or set(before_keys) != set(after_keys):
        return "UI-CONTINUITY-KEY-CONFLICT"
    if before_state != after_state:
        return "UI-CONTINUITY-STATE-LOSS"
    return "PASS"


def _interaction_verdict(
    before: dict[str, str],
    after: dict[str, str],
    valid_targets: set[str],
    fallback: dict[str, str] | None,
) -> str:
    for state_name, old_target in before.items():
        new_target = after.get(state_name)
        if old_target in valid_targets and new_target != old_target:
            return "UI-CONTINUITY-STATE-LOSS"
        if old_target not in valid_targets:
            if fallback is None or fallback.get(state_name) != new_target:
                return "UI-CONTINUITY-STATE-LOSS"
            if new_target not in valid_targets:
                return "UI-CONTINUITY-INVALID-STATE"
    return "PASS"


def _settled_verdict(
    revision: str,
    owner_revisions: dict[str, str],
    late_revision: str | None = None,
) -> str:
    if any(owner_revision != revision for owner_revision in owner_revisions.values()):
        return "UI-CONTINUITY-SETTLED-UNPROVEN"
    if late_revision == revision:
        return "UI-CONTINUITY-SETTLED-UNPROVEN"
    return "PASS"


def _writer_verdict(
    writers: dict[str, tuple[str, ...]],
    required_dimensions: set[str],
    aggregate_settled: bool,
) -> str:
    if not aggregate_settled:
        return "UI-CONTINUITY-OWNER-COLLISION"
    for dimension in required_dimensions:
        if len(writers.get(dimension, ())) != 1:
            return "UI-CONTINUITY-OWNER-COLLISION"
    return "PASS"


def _trace_verdict(
    observations: tuple[dict[str, object], ...],
    revisions: tuple[str, ...],
) -> str:
    if len(observations) != len(revisions) or not observations:
        return "UI-CONTINUITY-TRANSIENT-UNOBSERVED"
    if len(set(revisions)) > 1:
        return "UI-CONTINUITY-PARTIAL-COMMIT"
    baseline = observations[0]
    if observations[-1] == baseline and any(
        observation != baseline for observation in observations[1:-1]
    ):
        return "UI-CONTINUITY-TRANSIENT-UNOBSERVED"
    return "PASS"


def _executor_route_verdict(
    platform: str,
    available_harnesses: frozenset[str],
    declared_owner: str | None = None,
) -> tuple[str, str]:
    if platform in {"Qt Widgets", "Qt Quick/QML"}:
        owner, harness = "ui-test-engineer", "qt"
    elif platform in {"web/React", "native mobile"}:
        owner, harness = "qa-engineer", platform
    else:
        return "UNVERIFIED", "UNVERIFIED"
    if declared_owner is not None and declared_owner != owner:
        return owner, "UNVERIFIED"
    if harness not in available_harnesses:
        return owner, "BLOCKED"
    return owner, "PASS"


def _canonical_inventory(text: str) -> None:
    _assert_tokens(
        text,
        (
            "UIContinuity/causal-transition-matrix",
            "UIContinuity/documentation-projection",
            *TRANSITION_CLASSES,
            *DIMENSIONS,
            *FAILURE_IDS,
            *SCENARIO_IDS,
        ),
        "UI-CONTINUITY-CONTRACT-DRIFT",
    )
    for heading in (
        "## Transition classes",
        "## Continuity dimensions",
        "## Required metamorphic scenarios",
    ):
        assert text.count(heading) == 1, (
            "UI-CONTINUITY-CONTRACT-DRIFT: canonical inventory section must occur "
            f"exactly once: {heading}"
        )


def _documentation_verdict(readme: str, install: str) -> str:
    common = (
        "contracts/ui-transition-continuity.md",
        "shared/references/ui-transition-continuity.md",
        "shared/references/ru/ui-transition-continuity.md",
        "normative English",
        "non-authoritative",
        "not installed",
        "full `shared/references/` tree is not installed",
        "no provider-specific semantic copy",
    )
    install_only = (
        "$HOME/.agents/contracts/",
        "<repo>/.agents/contracts/",
        "~/.claude/contracts/",
        "<repo>/.claude/contracts/",
        "`../../contracts/ui-transition-continuity.md`",
        "`../contracts/ui-transition-continuity.md`",
    )
    for text, tokens in ((readme, common), (install, (*common, *install_only))):
        if any(token.casefold() not in text.casefold() for token in tokens):
            return "UI-CONTINUITY-DOC-DRIFT"
    return "PASS"


def _mirror_verdict(english: str, russian: str) -> str:
    required = (*TRANSITION_CLASSES, *DIMENSIONS, *FAILURE_IDS, *SCENARIO_IDS)
    if any(token not in english or token not in russian for token in required):
        return "UI-CONTINUITY-RU-SEMANTIC-DRIFT"
    folded = russian.casefold()
    if "не является нормативным" not in folded or "огранич" not in folded:
        return "UI-CONTINUITY-RU-SEMANTIC-DRIFT"
    if "безусловное исключение" in folded or "полное исключение" in folded:
        return "UI-CONTINUITY-RU-SEMANTIC-DRIFT"
    return "PASS"


def _source_role_paths(provider: str) -> tuple[Path, ...]:
    if provider == "codex":
        return tuple(ROOT / "src.codex" / "skills" / role / "SKILL.md" for role in ROLES)
    return tuple(ROOT / "src.claude" / "agents" / f"{role}.md" for role in ROLES)


def _assert_role_routes() -> None:
    for provider, pointer in (
        ("codex", "../../contracts/ui-transition-continuity.md"),
        ("claude", "../contracts/ui-transition-continuity.md"),
    ):
        for path in _source_role_paths(provider):
            text = _read_required(path, "UI-CONTINUITY-CONTRACT-DRIFT", f"{provider} role")
            assert text.count(pointer) == 1, (
                "UI-CONTINUITY-CONTRACT-DRIFT: role must carry exactly one neutral "
                f"contract pointer: {path.relative_to(ROOT)}"
            )


def _run_isolated_install(provider: str, target: Path) -> Path:
    script = ROOT / "scripts" / f"install-{provider}.py"
    command = [
        sys.executable,
        str(script),
        "--target",
        str(target),
        "--force",
        "--allow-unsafe-target",
    ]
    if provider == "claude":
        command.append("--no-hypothesis-hook")
    environment = os.environ.copy()
    if provider == "codex":
        environment["CODEX_BIN"] = str(
            ROOT / "tests" / "fixtures" / "fake_codex_hooks_host.py"
        )
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, (
        f"UI-CONTINUITY-CONTRACT-DRIFT: {provider} isolated install failed\n"
        f"{result.stdout}\n{result.stderr}"
    )
    return target / (".agents" if provider == "codex" else ".claude")


def test_claim_01_causal_rule_is_not_pixel_or_api_freeze() -> None:
    contract = _english()
    _assert_tokens(
        contract,
        (
            "adaptive",
            "font scale",
            "localization",
            "structural",
            "not a universal pixel freeze",
            "neither banned nor approved by name",
        ),
        "UI-CONTINUITY-CONTRACT-DRIFT",
    )
    baseline = _observation()
    for permissions in (
        {"spatial", "item-metric"},
        {"spatial", "accessibility/status"},
        {"model", "spatial"},
    ):
        changed = baseline | {dimension: f"changed:{dimension}" for dimension in permissions}
        transition = _Transition(True, frozenset(permissions), frozenset(permissions))
        assert _causal_verdict(baseline, changed, transition) == "PASS"
    moved = baseline | {"spatial": "unexplained"}
    assert _causal_verdict(baseline, moved, _Transition()) == "UI-CONTINUITY-CAUSALITY-BREACH"


def test_claim_02_exact_replay_is_baseline_plus_three_refreshes_across_eight_dimensions() -> None:
    contract = _english()
    _assert_tokens(contract, ("one baseline", "three post-baseline equivalent refreshes"), "UI-CONTINUITY-CONTRACT-DRIFT")
    baseline = _observation()
    replay = [baseline, dict(baseline), dict(baseline), dict(baseline)]
    assert len(replay) == 4
    assert all(_causal_verdict(replay[0], state, _Transition()) == "PASS" for state in replay[1:])
    for dimension in DIMENSIONS:
        mutated = dict(baseline)
        mutated[dimension] = f"mutated:{dimension}"
        assert _causal_verdict(baseline, mutated, _Transition()) == "UI-CONTINUITY-CAUSALITY-BREACH"


def test_claim_03_inputs_permissions_and_causal_scope_fail_closed() -> None:
    contract = _english()
    _assert_tokens(contract, (FAILURE_IDS[0], FAILURE_IDS[3], "positive permission", "causal scope"), "UI-CONTINUITY-CONTRACT-DRIFT")
    baseline = _observation()
    moved = baseline | {"spatial": "changed"}
    assert _causal_verdict(baseline, moved, _Transition(False)) == FAILURE_IDS[0]
    outside_permission = _Transition(True, frozenset(), frozenset({"spatial"}))
    outside_scope = _Transition(True, frozenset({"spatial"}), frozenset())
    assert _causal_verdict(baseline, moved, outside_permission) == FAILURE_IDS[3]
    assert _causal_verdict(baseline, moved, outside_scope) == FAILURE_IDS[3]


def test_claim_04_bounded_variants_reserve_capacity_and_adaptation_may_reflow() -> None:
    contract = _english()
    _assert_tokens(contract, ("reserved capacity", "unbounded content", FAILURE_IDS[9]), "UI-CONTINUITY-CONTRACT-DRIFT")
    assert "must not be clipped merely to" in contract, (
        "UI-CONTINUITY-ADAPTATION-BLOCKED: canonical adaptation guarantee missing"
    )
    baseline = _observation()
    bounded = baseline | {"accessibility/status": "progress:99%"}
    assert _causal_verdict(
        baseline,
        bounded,
        _Transition(True, frozenset({"accessibility/status"}), frozenset({"accessibility/status"})),
    ) == "PASS"
    reflow = baseline | {"spatial": "reflow", "item-metric": "wrapped"}
    assert _causal_verdict(
        baseline,
        reflow,
        _Transition(True, frozenset({"spatial", "item-metric"}), frozenset({"spatial", "item-metric"})),
    ) == "PASS"
    assert _adaptation_verdict(
        baseline,
        reflow,
        _Transition(True, frozenset({"spatial", "item-metric"}), frozenset({"spatial", "item-metric"})),
        content_fits=False,
    ) == FAILURE_IDS[9]
    unrelated = reflow | {"interaction": "focus-stolen"}
    assert _adaptation_verdict(
        baseline,
        unrelated,
        _Transition(True, frozenset({"spatial", "item-metric"}), frozenset({"spatial", "item-metric"})),
        content_fits=True,
    ) == FAILURE_IDS[3]


def test_claim_05_dimensions_are_independent_and_cannot_compensate() -> None:
    contract = _english()
    _assert_tokens(contract, DIMENSIONS, "UI-CONTINUITY-CONTRACT-DRIFT")
    baseline = _observation()
    for dimension in DIMENSIONS:
        mutated = dict(baseline)
        mutated[dimension] = "delta"
        compensator = DIMENSIONS[(DIMENSIONS.index(dimension) + 1) % len(DIMENSIONS)]
        mutated[compensator] = baseline[compensator]
        assert _causal_verdict(baseline, mutated, _Transition()) == "UI-CONTINUITY-CAUSALITY-BREACH"


def test_claim_06_semantic_identity_survives_lifecycle_recreation() -> None:
    contract = _english()
    _assert_tokens(contract, ("semantic identity", "lifecycle recreation", FAILURE_IDS[5], FAILURE_IDS[6]), "UI-CONTINUITY-CONTRACT-DRIFT")
    keys = ("item:a", "item:b")
    state = {"selection": "item:b", "scroll": "item:a"}
    assert _identity_verdict(keys, keys, state, dict(state)) == "PASS"
    assert _identity_verdict(keys, ("item:a", "item:a"), state, dict(state)) == FAILURE_IDS[5]
    assert _identity_verdict(keys, keys, state, {"selection": "item:a"}) == FAILURE_IDS[6]


def test_claim_07_interaction_state_uses_valid_targets_or_declared_fallback() -> None:
    contract = _english()
    _assert_tokens(contract, ("focus", "selection/current", "scroll anchor", "expansion", "input state", "deterministic fallback"), "UI-CONTINUITY-CONTRACT-DRIFT")
    before = {"focus": "row:2", "selection": "row:2", "scroll": "row:1", "expansion": "group:a", "input": "editor:a"}
    assert _interaction_verdict(before, dict(before), set(before.values()), None) == "PASS"
    valid = set(before.values()) - {"row:2"} | {"row:3"}
    after = dict(before) | {"focus": "row:3", "selection": "row:3"}
    fallback = {"focus": "row:3", "selection": "row:3"}
    assert _interaction_verdict(before, after, valid, fallback) == "PASS"
    assert _interaction_verdict(before, after, valid, None) == FAILURE_IDS[6]


def test_claim_08_accessibility_changes_are_bounded_not_blanket_exemptions() -> None:
    contract = _english()
    _assert_tokens(contract, ("font scale", "status announcement", "reduced-motion", "not a blanket exemption"), "UI-CONTINUITY-CONTRACT-DRIFT")
    baseline = _observation()
    cases = (
        {"spatial", "item-metric", "accessibility/status"},
        {"accessibility/status"},
        {"motion"},
    )
    for allowed in cases:
        changed = baseline | {dimension: f"allowed:{dimension}" for dimension in allowed}
        transition = _Transition(True, frozenset(allowed), frozenset(allowed))
        assert _causal_verdict(baseline, changed, transition) == "PASS"
        unrelated = changed | {"interaction": "focus-stolen"}
        assert _causal_verdict(baseline, unrelated, transition) == FAILURE_IDS[3]


def test_claim_09_intermediate_discontinuities_are_observed_even_with_equal_endpoints() -> None:
    contract = _english()
    _assert_tokens(contract, (FAILURE_IDS[4], FAILURE_IDS[11], "equal endpoints"), "UI-CONTINUITY-CONTRACT-DRIFT")
    assert (
        "Equal endpoints do not hide\nan intermediate discontinuity or partial commit."
        in contract
    ), "UI-CONTINUITY-TRANSIENT-UNOBSERVED: equal-endpoint guarantee missing"
    baseline = _observation()
    intermediate = baseline | {"spatial": "jump", "interaction": "focus-stolen"}
    final = dict(baseline)
    assert _trace_verdict(
        (baseline, intermediate, final),
        ("r2", "r2", "r2"),
    ) == FAILURE_IDS[11]
    assert _trace_verdict(
        (baseline, intermediate, final),
        ("r1", "r2", "r2"),
    ) == FAILURE_IDS[4]


def test_claim_10_settledness_is_revision_correlated_and_rejects_late_mutation() -> None:
    contract = _english()
    _assert_tokens(contract, ("revision-correlated", "fixed sleep", FAILURE_IDS[2]), "UI-CONTINUITY-CONTRACT-DRIFT")
    owners = {dimension: "r7" for dimension in DIMENSIONS}
    assert _settled_verdict("r7", owners) == "PASS"
    assert _settled_verdict("r7", owners, late_revision="r7") == FAILURE_IDS[2]
    assert _settled_verdict("r7", owners | {"motion": "r6"}) == FAILURE_IDS[2]


def test_claim_11_each_dimension_has_one_writer_and_one_aggregate_settlement() -> None:
    contract = _english()
    _assert_tokens(contract, ("one writer", "aggregate settled", FAILURE_IDS[1]), "UI-CONTINUITY-CONTRACT-DRIFT")
    writers = {dimension: (f"owner:{dimension}",) for dimension in DIMENSIONS}
    assert _writer_verdict(writers, set(DIMENSIONS), True) == "PASS"
    duplicate = writers | {"spatial": ("layout", "animation")}
    missing = {key: value for key, value in writers.items() if key != "motion"}
    assert _writer_verdict(duplicate, set(DIMENSIONS), True) == FAILURE_IDS[1]
    assert _writer_verdict(missing, set(DIMENSIONS), True) == FAILURE_IDS[1]
    assert _writer_verdict(writers, set(DIMENSIONS), False) == FAILURE_IDS[1]


def test_claim_12_portable_inventory_executor_routes_and_missing_harness_fail_closed() -> None:
    _assert_role_routes()
    contract = _english()
    _canonical_inventory(contract)
    _assert_tokens(
        contract,
        (
            "three post-baseline equivalent refreshes",
            "Qt Widgets",
            "Qt Quick/QML",
            "ui-test-engineer",
            "web/React",
            "native mobile",
            "qa-engineer",
            "BLOCKED",
            "UNVERIFIED",
            "missing required harness",
        ),
        "UI-CONTINUITY-CONTRACT-DRIFT",
    )
    assert (
        "A missing required harness is `BLOCKED` or `UNVERIFIED`; it is not permission to\n"
        "broaden the Qt-only role, substitute screenshots, or omit the gate."
        in contract
    ), "UI-CONTINUITY-CONTRACT-DRIFT: missing-harness fail-closed guarantee missing"
    qa_text = "\n".join(path.read_text(encoding="utf-8") for path in (_source_role_paths("codex")[5], _source_role_paths("claude")[5]))
    _assert_tokens(qa_text, ("web/React", "native mobile", "BLOCKED", "UNVERIFIED"), "UI-CONTINUITY-CONTRACT-DRIFT")
    assert _executor_route_verdict("Qt Widgets", frozenset({"qt"})) == (
        "ui-test-engineer",
        "PASS",
    )
    assert _executor_route_verdict("web/React", frozenset({"web/React"})) == (
        "qa-engineer",
        "PASS",
    )
    assert _executor_route_verdict("native mobile", frozenset({"native mobile"})) == (
        "qa-engineer",
        "PASS",
    )
    assert _executor_route_verdict("web/React", frozenset()) == (
        "qa-engineer",
        "BLOCKED",
    )
    assert _executor_route_verdict("native mobile", frozenset({"qt"})) == (
        "qa-engineer",
        "BLOCKED",
    )
    assert _executor_route_verdict(
        "web/React",
        frozenset({"web/React"}),
        declared_owner="ui-test-engineer",
    ) == ("qa-engineer", "UNVERIFIED")


def test_claim_13_allowed_surface_and_documentation_projection_reject_drift() -> None:
    readme = _read_required(README, "UI-CONTINUITY-DOC-DRIFT", "root README projection")
    install = _read_required(INSTALL, "UI-CONTINUITY-DOC-DRIFT", "root INSTALL projection")
    documentation_verdict = _documentation_verdict(readme, install)
    assert documentation_verdict == "PASS", documentation_verdict
    contract = _english()
    installer = _read_required(INSTALLER, "UI-CONTINUITY-CONTRACT-DRIFT", "production installer projection owner")
    assert len(ROLLOUT_PATHS) == 30
    assert not (ROOT / "src.codex" / "contracts").exists()
    assert not (ROOT / "src.claude" / "contracts").exists()
    assert [path.name for path in ROOT.glob("tests/test_ui_transition_continuity_contract*.py")] == ["test_ui_transition_continuity_contract.py"]
    _assert_tokens(installer, ("ui-transition-continuity.md", "shared", "references", "contracts"), "UI-CONTINUITY-CONTRACT-DRIFT")
    _assert_tokens(contract, ("no new workflow stage", "no new hook", "no new operator command", "no new dependency", "no documentation semantic owner"), "UI-CONTINUITY-CONTRACT-DRIFT")
    doc_mutations = [
        (readme.replace("contracts/ui-transition-continuity.md", "contracts/wrong.md"), install),
        (readme, install.replace("$HOME/.agents/contracts/", "$HOME/.agents/provider-contracts/")),
        (readme, install.replace("<repo>/.agents/contracts/", "<repo>/.agents/provider-contracts/")),
        (readme, install.replace("~/.claude/contracts/", "~/.claude/provider-contracts/")),
        (readme, install.replace("<repo>/.claude/contracts/", "<repo>/.claude/provider-contracts/")),
        (readme, install.replace("`../../contracts/ui-transition-continuity.md`", "`../../contracts/wrong.md`")),
        (readme, install.replace("`../contracts/ui-transition-continuity.md`", "`../contracts/wrong.md`")),
        (readme.replace("normative English", "normative Russian"), install),
        (readme.replace("full `shared/references/` tree is not installed", "full `shared/references/` tree is installed"), install),
        (readme.replace("no provider-specific semantic copy", "provider-specific semantic copy"), install),
    ]
    assert all(_documentation_verdict(*mutation) == "UI-CONTINUITY-DOC-DRIFT" for mutation in doc_mutations)


def test_claim_14_bilingual_live_pack_and_protected_projection_parity(tmp_path: Path) -> None:
    russian = _russian()
    english = _english()
    _canonical_inventory(english)
    assert _mirror_verdict(english, russian) == "PASS"
    assert _mirror_verdict(english, russian.replace("adaptive", "")) == FAILURE_IDS[14]
    assert _mirror_verdict(english, russian.replace("огранич", "безусловное исключение")) == FAILURE_IDS[14]
    assert _mirror_verdict(english, russian.replace(FAILURE_IDS[3], "UI-CONTINUITY-WRONG-MEANING")) == FAILURE_IDS[14]
    assert _mirror_verdict(english, russian.replace("premature-settlement", "")) == FAILURE_IDS[14]
    wording_only = russian + "\n<!-- Допустимая редакторская переформулировка без изменения контракта. -->\n"
    assert _mirror_verdict(english, wording_only) == "PASS"

    _assert_role_routes()
    for provider, role_root, pointer in (
        ("codex", Path("skills"), "../../contracts/ui-transition-continuity.md"),
        ("claude", Path("agents"), "../contracts/ui-transition-continuity.md"),
    ):
        target = tmp_path / f"{provider}-target"
        pack_root = _run_isolated_install(provider, target)
        leaf = pack_root / "contracts" / "ui-transition-continuity.md"
        assert leaf.read_bytes() == ENGLISH.read_bytes(), (
            f"UI-CONTINUITY-CONTRACT-DRIFT: {provider} installed leaf differs from English source"
        )
        assert [path.name for path in (pack_root / "contracts").iterdir()] == ["ui-transition-continuity.md"]
        for role in ROLES:
            role_file = pack_root / role_root / (f"{role}/SKILL.md" if provider == "codex" else f"{role}.md")
            role_text = role_file.read_text(encoding="utf-8")
            assert role_text.count(pointer) == 1
            assert (role_file.parent / pointer).resolve() == leaf.resolve()
        shutil.rmtree(target)
