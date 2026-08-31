"""Contract tests for explicit runtime capabilities owned by test fixtures."""
from __future__ import annotations

import ast
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
CONSUMERS = {
    "tests/test_python_production_entrypoints.py": {
        "test_codex_production_entrypoint_creates_only_source_manifest_roles": None,
    },
    "tests/test_claude_subscription_guard.py": {},
    "tests/test_native_role_slice_a.py": {
        "test_fresh_codex_install_materializes_native_roles_v2_and_canonical_skills": None,
    },
    "tests/test_process_runner_cli.py": {},
    "tests/test_python_validator_runtime.py": {
        "test_validator_process_adapter_preserves_exact_python_argv": (
            "requires_windows_process_runner"
        ),
    },
    "tests/test_slice_a_detached_validation.py": {
        "test_slice_a_authorization_scope_polarity": "requires_windows_process_runner",
        "test_deep_evidence_directory_uses_a_bounded_workspace_worktree_path": (
            "requires_windows_process_runner"
        ),
        "test_explicit_untracked_exclusion_is_absent_from_detached_worktree": (
            "requires_windows_process_runner"
        ),
        "test_detached_manifest_always_nonauthorizing": (
            "requires_windows_process_runner"
        ),
    },
    "tests/test_slice_b_fix_controls.py": {
        "test_kimi_admission_failure_commits_nonauthorizing_terminal_without_downstream_side_effects": (
            "requires_windows_kimi"
        ),
    },
    "tests/test_wrapper_model_effort_guard.py": {
        "test_root_thin_wrapper_delivers_one_governance_frame_then_exact_task_bytes": (
            "requires_windows_process_runner"
        ),
        "test_default_profile_reaches_fake_provider_with_explicit_model_and_effort": (
            "requires_windows_process_runner"
        ),
        "test_full_profile_override_reaches_fake_provider_byte_for_byte": (
            "requires_windows_process_runner"
        ),
    },
}


def _function_nodes(tree: ast.AST) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _decorator_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return None


def _skipif_excluded_platforms(decorators: list[ast.expr]) -> set[str]:
    excluded: set[str] = set()
    for decorator in decorators:
        if not (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "skipif"
            and decorator.args
        ):
            continue
        condition = decorator.args[0]
        references_os_name = any(
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "os"
            and node.attr == "name"
            for node in ast.walk(condition)
        )
        if not references_os_name:
            continue
        expression = ast.Expression(body=condition)
        ast.fix_missing_locations(expression)
        compiled = compile(expression, "<runtime-capability-contract>", "eval")
        for platform in ("nt", "posix"):
            if eval(  # noqa: S307 - expression comes from tracked test decorators only.
                compiled,
                {"__builtins__": {}},
                {"os": SimpleNamespace(name=platform)},
            ):
                excluded.add(platform)
    return excluded


def test_runtime_capability_markers_skip_only_without_windows() -> None:
    from tests.fixtures.runtime_capabilities import (
        requires_windows_kimi,
        requires_windows_process_runner,
    )

    for marker in (requires_windows_process_runner, requires_windows_kimi):
        assert marker.mark.name == "skipif"
        assert marker.mark.args == (os.name != "nt",)
        assert marker.mark.kwargs["reason"]


def test_codex_hook_host_environment_is_copied_and_repo_bound(tmp_path: Path) -> None:
    from tests.fixtures.runtime_capabilities import codex_hook_host_env

    fixture = tmp_path / "tests" / "fixtures" / "fake_codex_hooks_host.py"
    fixture.parent.mkdir(parents=True)
    fixture.write_text("# fixture\n", encoding="utf-8")
    base = {"PRESERVED": "value"}

    environment = codex_hook_host_env(base, tmp_path)

    assert base == {"PRESERVED": "value"}
    assert environment is not base
    assert environment == {
        "PRESERVED": "value",
        "CODEX_BIN": str(fixture.resolve()),
    }


@pytest.mark.parametrize("relative_path", tuple(CONSUMERS))
def test_runtime_capability_consumers_import_the_canonical_owner(
    relative_path: str,
) -> None:
    tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "tests.fixtures.runtime_capabilities"
        for alias in node.names
    }
    required = {marker for marker in CONSUMERS[relative_path].values() if marker}
    if relative_path in {
        "tests/test_python_production_entrypoints.py",
        "tests/test_native_role_slice_a.py",
    }:
        required.add("codex_hook_host_env")
    if relative_path == "tests/test_claude_subscription_guard.py":
        required.add("requires_windows_process_runner")
    assert required <= imported


def test_success_paths_delegate_capability_gates_to_the_canonical_owner() -> None:
    for relative_path, expected_functions in CONSUMERS.items():
        tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
        functions = _function_nodes(tree)
        for function_name, expected_marker in expected_functions.items():
            decorators = {
                name
                for decorator in functions[function_name].decorator_list
                if (name := _decorator_name(decorator)) is not None
            }
            location = f"{relative_path}::{function_name}"
            if expected_marker is None:
                assert decorators.isdisjoint(
                    {"requires_windows_process_runner", "requires_windows_kimi"}
                ), location
            else:
                assert expected_marker in decorators, location


def test_listed_capability_gates_admit_at_least_one_platform() -> None:
    marker_platforms = {
        "requires_windows_process_runner": {"nt"},
        "requires_windows_kimi": {"nt"},
    }
    for relative_path, expected_functions in CONSUMERS.items():
        tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
        functions = _function_nodes(tree)
        for function_name, expected_marker in expected_functions.items():
            if expected_marker is None:
                continue
            admitted = marker_platforms[expected_marker] - _skipif_excluded_platforms(
                functions[function_name].decorator_list
            )
            assert admitted, f"{relative_path}::{function_name} has no admitted platform"


def test_consumers_do_not_assign_codex_bin_locally() -> None:
    for relative_path in CONSUMERS:
        tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
        assignments = []
        for node in ast.walk(tree):
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets.extend(node.targets)
            elif isinstance(node, ast.AnnAssign):
                targets.append(node.target)
            elif isinstance(node, ast.AugAssign):
                targets.append(node.target)
            for target in targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.slice, ast.Constant)
                    and target.slice.value == "CODEX_BIN"
                ):
                    assignments.append(target.lineno)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "setenv"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "CODEX_BIN"
            ):
                assignments.append(node.lineno)
        assert assignments == [], f"{relative_path}: local CODEX_BIN at {assignments}"
