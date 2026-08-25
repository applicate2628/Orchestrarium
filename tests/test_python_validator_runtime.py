"""Single-owner Python runtime tests for the production pack validators."""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "scripts/skill_pack_validator_runtime.py"
VALIDATORS = (
    ROOT / "src.codex/skills/lead/scripts/validate-skill-pack.py",
    ROOT / "src.claude/agents/scripts/validate-skill-pack.py",
)
PROVIDER_RUNTIME_MIRRORS = (
    ROOT / "src.codex/skills/lead/scripts/skill_pack_validator_runtime.py",
    ROOT / "src.claude/agents/scripts/skill_pack_validator_runtime.py",
)
EXPECTED_SUMMARIES = (
    "PASS: 554  WARN: 0  FAIL: 0",
    "Checks: 470  |  Passed: 470  |  Warnings: 0  |  Errors: 0",
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        sys.modules[name] = module
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def test_work_items_checker_consumes_canonical_slug_predicate_explicitly(
    tmp_path: Path,
) -> None:
    checker = _load(ROOT / "scripts" / "check-work-items-state.py", "slug_owner_checker")
    lifecycle = checker.load_lifecycle_owner()
    predicate = lifecycle.is_valid_slug

    for slug in ("legacy-valid", "safe.dot", "v1.1"):
        assert predicate(slug), slug
    for slug in (
        "trailing.",
        "double..dot",
        "Uppercase",
        "under_score",
        "path/segment",
        "../traversal",
    ):
        assert not predicate(slug), slug

    work_items = tmp_path / "work-items"
    active = work_items / "active"
    archive = work_items / "archive"
    target = active / "safe.dot"
    target.mkdir(parents=True)
    item = active / "reader"
    item.mkdir()
    (item / "status.md").write_text(
        "Depends-on: safe.dot, trailing., double..dot, Uppercase, under_score\n",
        encoding="utf-8",
    )
    notes = checker.blocked_by_notes(item, tmp_path, lifecycle, predicate)
    assert notes == [
        "blocked-by: safe.dot (open Depends-on)",
        "invalid Depends-on: trailing., double..dot, Uppercase, under_score",
    ]

    resolver_calls: list[str] = []

    def resolve_epic_locations(_epics: Path, slug: str) -> dict[str, object]:
        resolver_calls.append(slug)
        return {"state": "missing", "locations": []}

    (item / "status.md").write_text("Epic: safe.dot\n", encoding="utf-8")
    assert checker.epic_link_notes(item, active, resolve_epic_locations, predicate) == [
        "dangling Epic: safe.dot (no matching work-items/epics/safe.dot.md "
        "or work-items/epics/archive/<YYYY-MM>/safe.dot.md)"
    ]
    assert resolver_calls == ["safe.dot"]

    for slug in ("trailing.", "double..dot", "Uppercase", "under_score"):
        (item / "status.md").write_text(f"Epic: {slug}\n", encoding="utf-8")
        assert checker.epic_link_notes(item, active, resolve_epic_locations, predicate) == [
            f"invalid Epic: {slug}"
        ]
    assert resolver_calls == ["safe.dot"]


def _run_validator(
    validator: Path,
    summary: str,
    *,
    cwd: Path,
    root: Path | None = ROOT,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PATH"] = ""
    command = [sys.executable, str(validator)]
    if root is not None:
        command.extend(("--root", str(root)))
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert summary in result.stdout
    return result


def _materialize_installed_pack(
    tmp_path: Path,
    provider: str,
) -> tuple[Path, Path]:
    target = tmp_path / f"{provider}-target"
    if provider == "codex":
        pack = target / ".agents"
        shutil.copytree(ROOT / "src.codex" / "skills", pack / "skills")
        shared = (ROOT / "shared" / "AGENTS.shared.md").read_text(encoding="utf-8")
        codex = (ROOT / "src.codex" / "AGENTS.codex.md").read_text(encoding="utf-8")
        (target / "AGENTS.md").write_text(
            "<!-- BEGIN ORCHESTRARIUM CODEX PACK -->\n"
            + shared.rstrip()
            + "\n\n"
            + codex.rstrip()
            + "\n<!-- END ORCHESTRARIUM CODEX PACK -->\n",
            encoding="utf-8",
        )
        scripts = pack / "skills" / "lead" / "scripts"
    else:
        pack = target / ".claude"
        shutil.copytree(ROOT / "src.claude", pack)
        shutil.copy2(ROOT / "shared" / "AGENTS.shared.md", pack / "AGENTS.md")
        scripts = pack / "agents" / "scripts"
    for name in (
        "agent-run-ledger.py",
        "agent-run-ledger.sh",
        "review_loop_state.py",
        "check-work-items-state.py",
        "check-work-items-state.sh",
        "validate-work-item-state.py",
        "validate-work-item-state.sh",
    ):
        shutil.copy2(ROOT / "scripts" / name, scripts / name)
    shutil.copy2(RUNTIME, scripts / RUNTIME.name)
    contract = pack / "contracts" / "ui-transition-continuity.md"
    contract.parent.mkdir()
    shutil.copy2(ROOT / "shared/references/ui-transition-continuity.md", contract)
    return target, scripts / "validate-skill-pack.py"


def _replace_directory_with_symlink(link: Path, target: Path) -> None:
    shutil.rmtree(link)
    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")
    assert link.is_symlink()
    assert link.is_dir()


@pytest.mark.parametrize(
    ("provider", "relative_instruction", "leak_text"),
    (
        (
            "codex",
            Path(".agents/skills/qa-engineer/SKILL.md"),
            "## Orchestrator upgrades "
            "(work-items/roadmaps/orchestrator-upgrades.md)",
        ),
        (
            "codex",
            Path(".agents/skills/qa-engineer/SKILL.md"),
            "## Orchestrarium-upgrade ledger",
        ),
        (
            "claude",
            Path(".claude/agents/qa-engineer.md"),
            "## Orchestrator upgrades "
            "(work-items/roadmaps/orchestrator-upgrades.md)",
        ),
        (
            "claude",
            Path(".claude/agents/qa-engineer.md"),
            "## Orchestrarium-upgrade ledger",
        ),
    ),
)
def test_reusable_instruction_guard_rejects_project_specific_upgrade_ledger(
    tmp_path: Path,
    provider: str,
    relative_instruction: Path,
    leak_text: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target, validator = _materialize_installed_pack(tmp_path, provider)
    instruction = target / relative_instruction
    instruction.write_text(
        instruction.read_text(encoding="utf-8")
        + f"\n{leak_text}\n",
        encoding="utf-8",
    )
    runtime = _load(RUNTIME, f"project_specific_ledger_guard_{provider}")

    result = runtime.validate_pack(
        script=validator,
        provider=provider,
        actions=(),
        maintainer_only_shared_reference_names=frozenset(),
        utility_skills=frozenset(),
        curated_role_skills=frozenset(),
        root=target,
        enforce_reusable_instruction_boundaries=True,
    )

    assert result.checks == 1
    assert result.passed == 0
    assert result.errors == 1
    output = capsys.readouterr().out
    assert "project-specific Orchestrarium upgrade-ledger obligation" in output
    assert instruction.name in output


def test_canonical_runtime_is_the_only_engine_and_exports_public_entrypoints() -> None:
    assert RUNTIME.is_file()
    assert all(not path.exists() for path in PROVIDER_RUNTIME_MIRRORS)
    runtime = _load(RUNTIME, "canonical_skill_pack_validator_runtime")
    assert callable(runtime.validate_pack)
    assert callable(runtime.run_validator_cli)


@pytest.mark.parametrize(
    ("content", "expected"),
    (
        (b"plain\nbody\n", "366c65d58ad0d90fdd93095d1c9ae82a13afbce33e4ca9e6e384d3c1e4b4f01f"),
        (b"plain\r\nbody\r\n", "366c65d58ad0d90fdd93095d1c9ae82a13afbce33e4ca9e6e384d3c1e4b4f01f"),
        (b"plain\rbody\r", "366c65d58ad0d90fdd93095d1c9ae82a13afbce33e4ca9e6e384d3c1e4b4f01f"),
        (b"---\r\nname: demo\r\n---\r\nbody\r\n", "9e2ec912af5dff2a72300863864fc4da04e81999339d9fac5c7590ba8a3f4e11"),
        (b"name: demo\r\nbody\r\n", "68d93eb64d12ffced451f894a644945b015e2de1df72c4a3faa6956e33b29850"),
        (b"---\r\nname: demo\r\nbody\r\n", "b4e972b2a859ff21d1694808d4698be7f8d445c8f3493f544996463ee288a003"),
    ),
)
def test_common_skill_body_digest_normalizes_newlines_and_frontmatter(
    content: bytes,
    expected: str,
) -> None:
    """Catches newline/frontmatter divergence in the one public digest owner."""
    runtime = _load(RUNTIME, f"common_skill_digest_{hashlib.sha256(content).hexdigest()[:8]}")
    operation = getattr(runtime, "common_skill_body_sha256", None)
    assert callable(operation), "canonical public common-skill body digest is missing"
    assert operation(content) == expected


def test_runtime_has_no_common_skill_policy_map_and_pin_check_uses_digest_owner() -> None:
    """Catches a surviving semantic map or a second normalization implementation."""
    tree = ast.parse(RUNTIME.read_text(encoding="utf-8"))
    assignments = {
        target.id
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (
            node.targets if isinstance(node, ast.Assign) else (node.target,)
        )
        if isinstance(target, ast.Name)
    }
    obsolete_policy_name = "COMMON_SKILL_BODY_" + "PINS"
    assert obsolete_policy_name not in assignments

    validator = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Validator"
    )
    pin_check = next(
        node
        for node in validator.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "check_common_skill_body_pin"
    )
    calls = {
        child.func.id
        for child in ast.walk(pin_check)
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
    }
    assert "common_skill_body_sha256" in calls
    assert "hashlib" not in ast.unparse(pin_check)


def _common_pin_actions(names: tuple[str, ...], candidate: Path) -> tuple[tuple[str, ...], ...]:
    expected = hashlib.sha256(b"body\n").hexdigest()
    return tuple(
        ("check_common_skill_body_pin", name, expected, str(candidate))
        for name in names
    )


@pytest.mark.parametrize(
    ("mutation", "expected_errors", "expected_fragment"),
    (
        ("matching", 0, None),
        ("missing", 1, "missing: windows-gui-manual-testing"),
        ("extra", 1, "extra: synthetic-common"),
        ("non-applicable-extra", 0, None),
    ),
)
def test_common_pin_completeness_uses_exact_applicable_action_names(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    mutation: str,
    expected_errors: int,
    expected_fragment: str | None,
) -> None:
    """Catches missing/extra pins and accidental inclusion of an inactive scope."""
    runtime = _load(RUNTIME, f"common_pin_completeness_{mutation}")
    agents_text = (ROOT / "shared/AGENTS.shared.md").read_text(encoding="utf-8")
    names = runtime.extract_roles(agents_text, "## Common skills")
    candidate = tmp_path / "SKILL.md"
    candidate.write_bytes(b"---\nname: fixture\ndescription: fixture\n---\nbody\n")
    applicable_names = names
    scoped_actions: tuple[tuple[str, object], ...] = ()
    if mutation == "missing":
        applicable_names = tuple(name for name in names if name != "windows-gui-manual-testing")
    elif mutation == "extra":
        applicable_names = (*names, "synthetic-common")
    elif mutation == "non-applicable-extra":
        scoped_actions = (
            (
                "installed",
                _common_pin_actions(("synthetic-common",), candidate),
            ),
        )

    result = runtime.validate_pack(
        script=VALIDATORS[0],
        provider="codex",
        actions=(
            ("direct", "common_pin_completeness", "common pin completeness"),
            *_common_pin_actions(applicable_names, candidate),
            *scoped_actions,
        ),
        maintainer_only_shared_reference_names=frozenset(),
        utility_skills=frozenset(),
        curated_role_skills=frozenset(),
        root=ROOT,
    )

    assert result.errors == expected_errors
    output = capsys.readouterr().out
    if expected_fragment is not None:
        assert expected_fragment in output


def test_layering_codex_derives_common_names_from_the_spine(tmp_path: Path) -> None:
    """Catches a layering exclusion still coupled to a stale runtime name map."""
    target, validator = _materialize_installed_pack(tmp_path, "codex")
    agents = target / "AGENTS.md"
    text = agents.read_text(encoding="utf-8")
    text, replacements = re.subn(
        r"(## Common skills.*?\bSet:\s*)",
        r"\1`$synthetic-common`, ",
        text,
        count=1,
        flags=re.DOTALL,
    )
    assert replacements == 1
    agents.write_text(text, encoding="utf-8")
    skill = target / ".agents/skills/synthetic-common/SKILL.md"
    skill.parent.mkdir()
    skill.write_text("B1 B2 B3\n", encoding="utf-8")

    runtime = _load(RUNTIME, "layering_codex_spine_common")
    result = runtime.validate_pack(
        script=validator,
        provider="codex",
        actions=(("direct", "layering_codex", "layering codex"),),
        maintainer_only_shared_reference_names=frozenset(),
        utility_skills=frozenset({"synthetic-common"}),
        curated_role_skills=frozenset(),
        root=target,
    )
    assert result.errors == 0


@pytest.mark.parametrize("validator", VALIDATORS)
def test_provider_adapter_has_no_bash_or_duplicated_engine_logic(
    validator: Path,
) -> None:
    text = validator.read_text(encoding="utf-8")
    assert "bash_runtime" not in text
    assert "resolve_bash" not in text
    assert "validate-skill-pack.sh" not in text
    assert 'with_suffix(".sh")' not in text
    assert "def _verdict" not in text
    assert "def _direct" not in text
    assert "validate_pack" in text
    assert "run_validator_cli" in text
    assert "validator-engine-not-found" in text


@pytest.mark.parametrize(
    ("validator", "summary"),
    tuple(zip(VALIDATORS, EXPECTED_SUMMARIES, strict=True)),
)
def test_source_validator_runs_directly_without_bash_on_path(
    validator: Path,
    summary: str,
) -> None:
    _run_validator(validator, summary, cwd=ROOT)


@pytest.mark.parametrize(
    ("validator", "summary"),
    tuple(zip(VALIDATORS, EXPECTED_SUMMARIES, strict=True)),
)
def test_extracted_style_source_loader_runs_with_root_canonical_engine(
    tmp_path: Path,
    validator: Path,
    summary: str,
) -> None:
    extracted = tmp_path / "extracted"
    adapter = extracted / validator.relative_to(ROOT)
    adapter.parent.mkdir(parents=True)
    shutil.copy2(validator, adapter)
    engine = extracted / "scripts" / RUNTIME.name
    engine.parent.mkdir(parents=True)
    shutil.copy2(RUNTIME, engine)
    _run_validator(adapter, summary, cwd=extracted)


@pytest.mark.parametrize(
    ("validator", "summary"),
    tuple(zip(VALIDATORS, EXPECTED_SUMMARIES, strict=True)),
)
def test_installed_sibling_loader_runs_fresh_validator(
    tmp_path: Path,
    validator: Path,
    summary: str,
) -> None:
    scripts = tmp_path / "installed" / validator.parts[-5] / "scripts"
    scripts.mkdir(parents=True)
    adapter = scripts / validator.name
    shutil.copy2(validator, adapter)
    shutil.copy2(RUNTIME, scripts / RUNTIME.name)
    _run_validator(adapter, summary, cwd=scripts)


@pytest.mark.parametrize(
    ("provider", "validator"),
    tuple(zip(("codex", "claude"), VALIDATORS, strict=True)),
)
def test_missing_engine_fails_with_stable_identifier(
    provider: str,
    validator: Path,
) -> None:
    scratch = ROOT / ".scratch"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f"validator-engine-collision-{provider}-",
        dir=scratch,
    ) as temporary:
        isolated = Path(temporary)
        collision_depth = 2 if provider == "codex" else 1
        for index in range(collision_depth):
            isolated /= f"level-{index}"
        isolated.mkdir(parents=True)
        adapter = isolated / validator.name
        shutil.copy2(validator, adapter)
        source_depth = 4 if provider == "codex" else 3
        derived_source_root = adapter.resolve().parents[source_depth]
        assert derived_source_root == ROOT.resolve()
        assert (derived_source_root / "scripts" / RUNTIME.name).is_file()
        assert adapter.resolve() != validator.resolve()
        result = subprocess.run(
            [sys.executable, str(adapter), "--root", str(ROOT)],
            cwd=isolated,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    assert result.returncode != 0
    assert "validator-engine-not-found" in result.stdout + result.stderr


@pytest.mark.parametrize("validator", VALIDATORS)
def test_mutable_action_seam_detects_missing_required_content(
    tmp_path: Path,
    validator: Path,
) -> None:
    module = _load(validator, f"validator_negative_{validator.parent.parent.name}")
    candidate = tmp_path / "candidate.md"
    candidate.write_text("present but incomplete\n", encoding="utf-8")
    original_actions = module.ACTIONS
    module.ACTIONS = (
        (
            "check_contains",
            str(candidate),
            "required invariant",
            "representative required-content branch",
        ),
    )
    try:
        result = module.validate(ROOT)
    finally:
        module.ACTIONS = original_actions
    assert result.checks == 2
    assert result.passed == 1
    assert result.errors == 1


@pytest.mark.parametrize("validator", VALIDATORS)
def test_scoped_action_registry_keeps_source_only_maintainer_checks_out_of_installed_layout(
    validator: Path,
) -> None:
    module = _load(validator, f"validator_scope_inventory_{validator.parent.parent.name}")
    assert tuple(scope for scope, _ in module.ACTIONS) == (
        "all",
        "dev_repo",
        "dev_repo_nonstandalone",
        "installed",
    )
    source_only_actions = tuple(
        action
        for action in dict(module.ACTIONS)["dev_repo"]
        if module._is_source_only_maintainer_action(action)
    )
    assert source_only_actions
    assert any(
        any(str(value).startswith("@ROOT/docs/") for value in action)
        for action in source_only_actions
    )
    assert any(
        action[0] == "check_normalizer_strips_example_auto_providers"
        for action in source_only_actions
    )
    assert any(
        "@ROOT/shared/agents-mode.defaults.yaml" in action
        for action in source_only_actions
    )
    installed_actions = tuple(
        action
        for scope, actions in module.ACTIONS
        if scope in ("all", "installed")
        for action in actions
    )
    assert not any(
        module._is_source_only_maintainer_action(action)
        for action in installed_actions
    )


@pytest.mark.parametrize(
    ("provider", "expected_clean_result", "installed_label"),
    (
        (
            "codex",
            "VALIDATION PASSED\n",
            "installed work-item state validator enforces evidence for PASS",
        ),
        (
            "claude",
            "  RESULT: PASS\n",
            "installed work-item state validator enforces evidence for PASS",
        ),
    ),
)
@pytest.mark.parametrize("cwd_mode", ("source", "target"))
def test_installed_validator_uses_script_layout_and_runs_installed_actions(
    tmp_path: Path,
    provider: str,
    expected_clean_result: str,
    installed_label: str,
    cwd_mode: str,
) -> None:
    target, validator = _materialize_installed_pack(tmp_path, provider)
    cwd = ROOT if cwd_mode == "source" else target
    environment = os.environ.copy()
    environment["PATH"] = ""
    result = subprocess.run(
        [sys.executable, str(validator)],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert expected_clean_result in result.stdout
    assert installed_label in result.stdout
    assert "dev repo validator unavailable in installed layout" not in result.stdout
    assert "agents-mode reference defines canonical maintenance" not in result.stdout
    assert "root Python installer default dispatch is Codex plus Claude only" not in result.stdout


@pytest.mark.parametrize(
    ("skill_name", "owned", "expected_warnings", "expected_errors"),
    (
        ("user-added-invalid", False, 1, 0),
        ("owned-invalid", True, 0, 1),
    ),
)
def test_installed_codex_layering_checks_only_orchestrarium_owned_skills(
    tmp_path: Path,
    skill_name: str,
    owned: bool,
    expected_warnings: int,
    expected_errors: int,
) -> None:
    target, validator = _materialize_installed_pack(tmp_path, "codex")
    adapter = _load(validator, f"installed_ownership_adapter_{skill_name}")
    skill = target / ".agents" / "skills" / skill_name / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text("B1 B2 B3\n", encoding="utf-8")

    runtime = _load(RUNTIME, f"layering_ownership_{skill_name}")
    passed, unresolved = runtime.layering_ids_resolve(skill)
    assert not passed
    assert unresolved == ("B1", "B2", "B3")
    utility_skills = adapter.UTILITY_SKILLS
    if owned:
        utility_skills |= frozenset({skill_name})

    result = runtime.validate_pack(
        script=validator,
        provider="codex",
        actions=(
            ("direct", "orphan_codex", "orphan_codex"),
            ("direct", "layering_codex", "layering_codex"),
        ),
        maintainer_only_shared_reference_names=frozenset(),
        utility_skills=utility_skills,
        curated_role_skills=frozenset(),
        root=target,
    )

    assert result.warnings == expected_warnings
    assert result.errors == expected_errors


@pytest.mark.parametrize(
    (
        "provider",
        "linked_subtree",
        "root_document",
        "required_marker",
        "stale_marker",
        "expected_clean_result",
        "expected_label",
    ),
    (
        (
            "codex",
            "skills",
            "AGENTS.md",
            "## Role index",
            "## Stale role index",
            "VALIDATION PASSED\n",
                "installable skill/agent instructions contain no project-specific Orchestrarium upgrade-ledger obligation",
        ),
        (
            "claude",
            "agents",
            ".claude/CLAUDE.md",
            "agents-design-panel.md",
            "agents-stale-panel.md",
            "  RESULT: PASS\n",
            "CLAUDE.md dispatch index exposes the design-panel command",
        ),
    ),
)
def test_installed_validator_prefers_logical_root_across_provider_subtree_symlink(
    tmp_path: Path,
    provider: str,
    linked_subtree: str,
    root_document: str,
    required_marker: str,
    stale_marker: str,
    expected_clean_result: str,
    expected_label: str,
) -> None:
    logical_home = tmp_path / "logical"
    physical_home = tmp_path / "physical"
    logical_home.mkdir()
    physical_home.mkdir()
    logical_root, logical_validator = _materialize_installed_pack(
        logical_home,
        provider,
    )
    physical_root, physical_validator = _materialize_installed_pack(
        physical_home,
        provider,
    )
    pack_name = ".agents" if provider == "codex" else ".claude"
    logical_subtree = logical_root / pack_name / linked_subtree
    physical_subtree = physical_root / pack_name / linked_subtree
    _replace_directory_with_symlink(logical_subtree, physical_subtree)
    try:
        logical_document = logical_root / root_document
        physical_document = physical_root / root_document
        assert required_marker in logical_document.read_text(encoding="utf-8")
        physical_text = physical_document.read_text(encoding="utf-8")
        assert required_marker in physical_text
        physical_document.write_text(
            physical_text.replace(required_marker, stale_marker),
            encoding="utf-8",
        )
        assert required_marker not in physical_document.read_text(encoding="utf-8")
        assert logical_validator.absolute() != logical_validator.resolve()
        assert logical_validator.resolve() == physical_validator.resolve()

        runtime = _load(RUNTIME, f"logical_layout_runtime_{provider}")
        layout = runtime.detect_layout(logical_validator, provider)
        assert layout.root == logical_root.resolve()
        assert layout.pack == logical_root / pack_name

        result = _run_validator(
            logical_validator,
            expected_clean_result,
            cwd=ROOT,
            root=None,
        )
        assert expected_label in result.stdout
        assert f"FAIL  {expected_label}" not in result.stdout
    finally:
        logical_subtree.unlink(missing_ok=True)


@pytest.mark.parametrize(
    ("provider", "source_validator"),
    tuple(zip(("codex", "claude"), VALIDATORS, strict=True)),
)
@pytest.mark.parametrize("requested_layout", ("source", "installed"))
def test_explicit_root_wins_over_conflicting_script_ancestry(
    tmp_path: Path,
    provider: str,
    source_validator: Path,
    requested_layout: str,
) -> None:
    target, installed_validator = _materialize_installed_pack(tmp_path, provider)
    runtime = _load(RUNTIME, f"explicit_installed_runtime_{provider}")
    if requested_layout == "source":
        script = installed_validator
        requested_root = ROOT
        expected_root = ROOT
        expected_dev_repo = True
    else:
        script = source_validator
        requested_root = target
        expected_root = target
        expected_dev_repo = False
    layout = runtime.detect_layout(script, provider, requested_root)
    assert layout.root == expected_root.resolve()
    assert layout.dev_repo is expected_dev_repo


@pytest.mark.parametrize("provider", ("codex", "claude"))
def test_extracted_provider_source_is_detected_as_standalone(
    tmp_path: Path,
    provider: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    extracted = tmp_path / provider
    shared = extracted / "shared" / "AGENTS.shared.md"
    shared.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "shared" / "AGENTS.shared.md", shared)
    if provider == "codex":
        scripts = extracted / "src.codex" / "skills" / "lead" / "scripts"
        scripts.mkdir(parents=True)
        shutil.copy2(ROOT / "src.codex" / "AGENTS.codex.md", scripts.parents[2] / "AGENTS.codex.md")
    else:
        scripts = extracted / "src.claude" / "agents" / "scripts"
        scripts.mkdir(parents=True)
    validator = scripts / "validate-skill-pack.py"
    validator.touch()
    runtime = _load(RUNTIME, f"standalone_runtime_{provider}")
    layout = runtime.detect_layout(validator, provider)
    assert layout.root == extracted.resolve()
    assert layout.dev_repo
    assert layout.standalone
    cross_provider_target = extracted / "cross-provider-present.txt"
    cross_provider_target.write_text("must remain unobserved\n", encoding="utf-8")
    result = runtime.validate_pack(
        script=validator,
        provider=provider,
        actions=(
            (
                "dev_repo_nonstandalone",
                (
                    (
                        "check_absent",
                        str(cross_provider_target),
                        "must remain unobserved",
                        "cross-provider standalone exclusion sentinel",
                    ),
                ),
            ),
        ),
        maintainer_only_shared_reference_names=frozenset(),
        utility_skills=frozenset(),
        curated_role_skills=frozenset(),
    )
    assert result.checks == 0
    assert "cross-provider standalone exclusion sentinel" not in capsys.readouterr().out


def test_provider_extractor_includes_canonical_runtime() -> None:
    extractor = _load(
        ROOT / "scripts/extract-provider-branch.py",
        "validator_runtime_extractor_test",
    )
    for provider in ("codex", "claude"):
        assert extractor.include_from_main(
            "scripts/skill_pack_validator_runtime.py",
            provider,
        )


def test_production_installer_runtime_inventory_owns_canonical_engine() -> None:
    installer = _load(
        ROOT / "scripts/production_installer.py",
        "validator_runtime_installer_test",
    )
    assert RUNTIME.name in installer.RUNTIME_HELPERS


@pytest.mark.parametrize(
    "launcher",
    (
        ROOT / "src.codex/skills/lead/scripts/validate-skill-pack.sh",
        ROOT / "src.claude/agents/scripts/validate-skill-pack.sh",
    ),
)
def test_retained_posix_surface_is_only_a_thin_python_launcher(
    launcher: Path,
) -> None:
    text = launcher.read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 20
    assert "validate-skill-pack.py" in text
    assert 'exec "$PYTHON_CMD"' in text
    assert "check_contains" not in text
    assert "check_absent" not in text
