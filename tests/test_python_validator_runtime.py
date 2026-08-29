"""Single-owner Python runtime tests for the production pack validators."""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

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
    "PASS: 548  WARN: 0  FAIL: 0",
    "Checks: 479  |  Passed: 479  |  Warnings: 0  |  Errors: 0",
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


def _copy_validator_runtime(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(RUNTIME, destination / RUNTIME.name)
    shutil.copytree(
        ROOT / "scripts" / "process_supervision",
        destination / "process_supervision",
        dirs_exist_ok=True,
    )


def _materialize_installed_pack(
    tmp_path: Path,
    provider: str,
) -> tuple[Path, Path]:
    target = tmp_path / f"{provider}-target"
    if provider == "codex":
        pack = target / ".agents"
        shutil.copytree(ROOT / "src.codex" / "skills", pack / "skills")
        schema_target = pack / "skills" / "lead" / "shared" / "schemas"
        schema_target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            ROOT / "shared" / "schemas" / "agent-runs.schema.json",
            schema_target / "agent-runs.schema.json",
        )
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
    _copy_validator_runtime(scripts)
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


def _create_directory_link(link: Path, target: Path) -> None:
    if os.name == "nt":
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode:
            pytest.skip(f"directory junctions are unavailable: {result.stderr}")
    else:
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            pytest.skip(f"directory symlinks are unavailable: {exc}")
    assert link.is_dir()


@pytest.mark.parametrize("legacy_kind", ("directory", "directory-link"))
def test_codex_global_split_layout_wins_over_stale_legacy_skills(
    tmp_path: Path,
    legacy_kind: str,
) -> None:
    home = tmp_path / "home"
    codex = home / ".codex"
    scripts = home / ".agents" / "skills" / "lead" / "scripts"
    scripts.mkdir(parents=True)
    codex.mkdir()
    (codex / "AGENTS.md").write_text("global codex contract\n", encoding="utf-8")
    validator = scripts / "validate-skill-pack.py"
    validator.touch()

    legacy_skills = codex / "skills"
    if legacy_kind == "directory":
        legacy_skills.mkdir()
    else:
        legacy_target = tmp_path / "stale-legacy-skills"
        legacy_target.mkdir()
        _create_directory_link(legacy_skills, legacy_target)

    runtime = _load(RUNTIME, f"global_split_layout_{legacy_kind}")
    layout = runtime.detect_layout(validator, "codex", home)

    assert layout.root == home.resolve()
    assert not layout.dev_repo
    assert layout.pack == codex
    assert layout.skills == home / ".agents" / "skills"
    assert layout.scripts == scripts
    assert layout.agents_text == "global codex contract\n"
    validator_runtime = runtime.Validator(layout)
    try:
        assert validator_runtime.logical_path(
            "@ROOT/src.codex/skills/manual-repo-transfer/SKILL.md"
        ) == str(layout.skills / "manual-repo-transfer" / "SKILL.md")
        assert validator_runtime.logical_path(
            "@ROOT/src.codex/contracts/ui-transition-continuity.md"
        ) == str(layout.pack / "contracts" / "ui-transition-continuity.md")
    finally:
        validator_runtime.close()


def test_codex_legacy_and_project_layouts_remain_compatible(tmp_path: Path) -> None:
    runtime = _load(RUNTIME, "legacy_and_project_layouts")

    legacy_root = tmp_path / "legacy"
    legacy_scripts = legacy_root / ".codex" / "skills" / "lead" / "scripts"
    legacy_scripts.mkdir(parents=True)
    (legacy_root / ".codex" / "AGENTS.md").write_text(
        "legacy codex contract\n", encoding="utf-8"
    )
    legacy_layout = runtime.detect_layout(
        legacy_scripts / "validate-skill-pack.py", "codex", legacy_root
    )
    assert legacy_layout.pack == legacy_root / ".codex"
    assert legacy_layout.skills == legacy_root / ".codex" / "skills"
    assert legacy_layout.scripts == legacy_scripts

    project_root = tmp_path / "project"
    project_scripts = project_root / ".agents" / "skills" / "lead" / "scripts"
    project_scripts.mkdir(parents=True)
    (project_root / "AGENTS.md").write_text(
        "project codex contract\n", encoding="utf-8"
    )
    project_layout = runtime.detect_layout(
        project_scripts / "validate-skill-pack.py", "codex", project_root
    )
    assert project_layout.pack == project_root / ".agents"
    assert project_layout.skills == project_root / ".agents" / "skills"
    assert project_layout.scripts == project_scripts


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


def _validator(runtime):
    return runtime.Validator(runtime.detect_layout(VALIDATORS[0], "codex", ROOT))


def _write_python(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_validator_capture_policy_is_the_single_exact_process_policy_owner() -> None:
    runtime = _load(RUNTIME, "validator_capture_policy_owner")
    policy = runtime.ValidatorCapturePolicyV1()
    process_policy = policy.to_capture_policy()

    assert process_policy.policy_id == "validator-bounded-v1"
    assert process_policy.aggregate_persisted_limit == 1024 * 1024
    assert process_policy.prefix_limit_per_stream == 64 * 1024
    assert process_policy.tail_limit_per_stream == 128 * 1024
    assert process_policy.chunk_size == 64 * 1024
    assert not hasattr(process_policy, "worker_count")
    assert not hasattr(process_policy, "poll_cadence")
    assert not hasattr(process_policy, "filesystem_write_limit")


def test_validator_runtime_has_no_direct_subprocess_or_tree_helper() -> None:
    tree = ast.parse(RUNTIME.read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        and any(alias.name == "subprocess" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
        for node in ast.walk(tree)
    )
    text = RUNTIME.read_text(encoding="utf-8")
    assert "ProcessRunnerV1" in text
    assert "taskkill" not in text.casefold()


def test_validator_process_adapter_preserves_exact_python_argv(tmp_path: Path) -> None:
    runtime = _load(RUNTIME, "validator_exact_argv")
    child = _write_python(
        tmp_path,
        "echo_argv.py",
        "import json, sys\n"
        "payload = json.dumps(sys.argv[1:], ensure_ascii=False).encode('utf-8')\n"
        "sys.stdout.buffer.write(payload)\n",
    )
    expected = (
        "",
        "two words",
        'quote"inside',
        "backslashes\\\\before\\\"quote",
        "C:\\path with space\\",
        "Москва-测试",
    )

    result = _validator(runtime)._run_python(
        child,
        *expected,
        timeout_seconds=10.0,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout) == list(expected)
    assert result.failure_id is None
    assert result.resources_closed
    assert result.tree_empty
    assert result.direct_reaped


@pytest.mark.skipif(os.name == "nt", reason="POSIX cwd ownership and mode contract")
def test_validator_process_adapter_uses_owned_private_posix_cwd_and_cleans_it(
    tmp_path: Path,
) -> None:
    runtime = _load(RUNTIME, "validator_private_posix_cwd")
    layout_root = tmp_path / "world-writable-layout"
    layout_root.mkdir()
    layout_root.chmod(0o777)
    base = runtime.detect_layout(VALIDATORS[0], "codex", ROOT)
    validator = runtime.Validator(
        runtime.Layout(
            root=layout_root,
            provider=base.provider,
            dev_repo=base.dev_repo,
            standalone=base.standalone,
            pack=base.pack,
            skills=base.skills,
            scripts=base.scripts,
            agents_text=base.agents_text,
        )
    )
    child = _write_python(
        tmp_path,
        "echo_cwd.py",
        "import json, os, stat\n"
        "metadata = os.stat(os.getcwd())\n"
        "print(json.dumps({\n"
        "    'cwd': os.getcwd(),\n"
        "    'mode': stat.S_IMODE(metadata.st_mode),\n"
        "    'owner': metadata.st_uid,\n"
        "    'effective_user': os.geteuid(),\n"
        "}))\n",
    )

    try:
        result = validator._run_python(child, timeout_seconds=10.0)
    finally:
        validator.close()

    assert stat.S_IMODE(layout_root.stat().st_mode) == 0o777
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["cwd"] != str(layout_root)
    assert observed["owner"] == observed["effective_user"]
    assert observed["mode"] & 0o077 == 0
    assert not Path(observed["cwd"]).exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX cwd ownership and mode contract")
@pytest.mark.parametrize(
    ("name", "body", "timeout_seconds", "timed_out"),
    (
        (
            "child_failure",
            "import os, sys\nprint(os.getcwd(), flush=True)\nsys.exit(7)\n",
            10.0,
            False,
        ),
        (
            "child_cancel",
            "import os, time\nprint(os.getcwd(), flush=True)\ntime.sleep(60)\n",
            0.2,
            True,
        ),
    ),
)
def test_validator_private_posix_cwd_cleans_after_failure_or_cancellation(
    tmp_path: Path,
    name: str,
    body: str,
    timeout_seconds: float,
    timed_out: bool,
) -> None:
    runtime = _load(RUNTIME, f"validator_private_posix_cwd_{name}")
    child = _write_python(tmp_path, f"{name}.py", body)
    validator = _validator(runtime)

    try:
        result = validator._run_python(child, timeout_seconds=timeout_seconds)
    finally:
        validator.close()

    child_cwd = Path(result.stdout.strip())
    assert result.returncode != 0
    assert result.timed_out is timed_out
    assert child_cwd != ROOT
    assert not child_cwd.exists()


def test_validator_process_adapter_bounds_infinite_output_and_settles(
    tmp_path: Path,
) -> None:
    runtime = _load(RUNTIME, "validator_infinite_output")
    child = _write_python(
        tmp_path,
        "infinite_output.py",
        "import os\nchunk = b'x' * 65536\nwhile True:\n    os.write(1, chunk)\n",
    )
    before = {path.name for path in tmp_path.iterdir()}
    started = time.monotonic()

    result = _validator(runtime)._run_python(child, timeout_seconds=0.5)

    assert time.monotonic() - started < 8.0
    assert result.returncode != 0
    assert result.failure_id in {"PSV1-CAPTURE-LIMIT", "PSV1-DEADLINE"}
    assert result.stdout_persisted_bytes + result.stderr_persisted_bytes <= 1024 * 1024
    assert len(result.stdout.encode("utf-8")) <= (64 + 128) * 1024
    assert result.resources_closed
    assert result.tree_empty
    assert result.direct_reaped
    assert result.primary_thread_closed
    assert result.job_handle_closed
    assert {path.name for path in tmp_path.iterdir()} == before


def test_validator_process_adapter_returns_typed_timeout_and_settles(
    tmp_path: Path,
) -> None:
    runtime = _load(RUNTIME, "validator_typed_timeout")
    child = _write_python(
        tmp_path,
        "sleep_forever.py",
        "import time\ntime.sleep(60)\n",
    )

    result = _validator(runtime)._run_python(child, timeout_seconds=0.2)

    assert result.returncode != 0
    assert result.failure_id == "PSV1-DEADLINE"
    assert result.timed_out
    assert result.resources_closed
    assert result.tree_empty
    assert result.direct_reaped
    assert result.primary_thread_closed
    assert result.job_handle_closed


def test_validator_process_adapter_reaps_output_retaining_grandchild(
    tmp_path: Path,
) -> None:
    runtime = _load(RUNTIME, "validator_output_retaining_grandchild")
    parent = _write_python(
        tmp_path,
        "retaining_parent.py",
        "import subprocess, sys\n"
        "code = \"import os, time\\nchunk = b'g' * 65536\\n"
        "while True:\\n    os.write(1, chunk)\\n    time.sleep(0.01)\"\n"
        "child = subprocess.Popen([sys.executable, '-c', code])\n"
        "print(f'GRANDCHILD={child.pid}', flush=True)\n",
    )
    started = time.monotonic()

    result = _validator(runtime)._run_python(parent, timeout_seconds=0.5)

    assert time.monotonic() - started < 8.0
    assert "GRANDCHILD=" in result.stdout
    match = re.search(r"GRANDCHILD=(\d+)", result.stdout)
    assert match is not None
    with pytest.raises(runtime._PROCESS_RUNNER.ProcessSupervisionError):
        runtime._PROCESS_RUNNER.get_process_start_marker(int(match.group(1)))
    assert result.returncode != 0
    assert result.failure_id in {"PSV1-CAPTURE-LIMIT", "PSV1-DEADLINE"}
    assert result.resources_closed
    assert result.tree_empty
    assert result.direct_reaped
    assert result.primary_thread_closed
    assert result.job_handle_closed


class _RecordingBinding:
    def bytes_for(self, _stream: str) -> bytes:
        return b""


class _RecordingRunner:
    def __init__(self) -> None:
        self.requests = []

    def mint_memory_capture_sink(self):
        return _RecordingBinding()

    def run(self, request):
        self.requests.append(request)
        stream = SimpleNamespace(
            observed_bytes=0,
            persisted_bytes=0,
            truncated=False,
            prefix_bytes=b"",
            tail_bytes=b"",
        )
        tree = SimpleNamespace(
            tree_empty=True,
            direct_reaped=True,
            primary_thread_closed=True,
            job_handle_closed=True,
            settlement_state="EMPTY",
        )
        return SimpleNamespace(
            outcome="success",
            target_exit_code=0,
            failure_id=None,
            timed_out=False,
            stdout=stream,
            stderr=stream,
            tree=tree,
            resources_closed=True,
            cleanup_uncertain=False,
        )

    def close(self):
        return SimpleNamespace(outcome="closed", failure_id=None)


@pytest.mark.skipif(os.name == "nt", reason="POSIX cwd ownership and mode contract")
def test_validator_private_posix_cwd_cleans_when_runner_raises(tmp_path: Path) -> None:
    runtime = _load(RUNTIME, "validator_private_posix_cwd_exception")

    class ExplodingRunner:
        def __init__(self) -> None:
            self.cwd: Path | None = None

        def mint_memory_capture_sink(self):
            return _RecordingBinding()

        def run(self, request):
            self.cwd = Path(request.cwd)
            metadata = self.cwd.stat()
            assert metadata.st_uid == os.geteuid()
            assert stat.S_IMODE(metadata.st_mode) & 0o077 == 0
            raise RuntimeError("runner-exploded")

        def close(self):
            return SimpleNamespace(outcome="closed", failure_id=None)

    runner = ExplodingRunner()
    validator = runtime.Validator(
        runtime.detect_layout(VALIDATORS[0], "codex", ROOT), process_runner=runner
    )
    child = _write_python(tmp_path, "never_started.py", "raise AssertionError\n")

    with pytest.raises(RuntimeError, match="runner-exploded"):
        validator._run_python(child, timeout_seconds=10.0)
    validator.close()

    assert runner.cwd is not None
    assert not runner.cwd.exists()


@pytest.mark.parametrize(
    ("budget_delta", "expected_launches"),
    ((-0.001, 0), (0.0, 1), (1.0, 1)),
)
def test_validator_sequence_budget_denies_below_and_accepts_exact_or_above(
    budget_delta: float,
    expected_launches: int,
) -> None:
    runtime = _load(RUNTIME, f"validator_sequence_budget_{budget_delta}")
    runner = _RecordingRunner()
    child_deadline = 1.0
    required = runtime.required_validator_sequence_budget((child_deadline,))

    result = runtime.validate_pack(
        script=VALIDATORS[0],
        provider="codex",
        actions=(("check_agent_run_ledger_contract", "sequence probe"),),
        maintainer_only_shared_reference_names=frozenset(),
        utility_skills=frozenset(),
        curated_role_skills=frozenset(),
        root=ROOT,
        process_runner=runner,
        child_timeout_seconds=child_deadline,
        outer_budget_seconds=required + budget_delta,
    )

    assert len(runner.requests) == expected_launches
    if expected_launches:
        assert result.errors == 0
        request = runner.requests[0]
        assert request.argv == (
            str(Path(sys.executable).resolve()),
            str(ROOT / "scripts/check-agent-run-ledger-contract.py"),
            "--root",
            str(ROOT),
        )
        if os.name == "nt":
            assert request.cwd == str(ROOT)
        else:
            assert request.cwd != str(ROOT)
            assert not Path(request.cwd).exists()
        assert request.environment == runtime.validator_environment_rows()
        assert tuple(row.name for row in request.environment) == tuple(
            name
            for name in runtime.VALIDATOR_ENVIRONMENT_ALLOWLIST
            if name in os.environ
        )
    else:
        assert result.errors == 1
        assert result.process_failure_id == "PSV1-DEADLINE-COMPOSITION"


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
    _copy_validator_runtime(engine.parent)
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
    _copy_validator_runtime(scripts)
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
    assert (
        "check_contains",
        "@ROOT/docs/agents-mode-reference.md",
        "## Canonical maintenance",
        "agents-mode reference defines canonical maintenance",
    ) in source_only_actions
    assert (
        "check_contains",
        "@ROOT/docs/agents-mode-reference.md",
        "Substantive task prompts are file-based by default",
        "agents-mode reference documents file-based external CLI prompts",
    ) in source_only_actions
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
            "VALIDATION PASSED (with warnings)\n",
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
    if provider == "codex":
        assert "dev repo validator unavailable in installed layout" in result.stdout
    else:
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
            "VALIDATION PASSED (with warnings)\n",
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
