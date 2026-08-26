from __future__ import annotations

import dataclasses
import importlib.util
import inspect
import os
import shutil
import sys
import threading
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "process_supervision" / "process_runner.py"
CHILD = ROOT / "tests" / "fixtures" / "process_supervision" / "child_helper.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "process_runner_windows_argv_admission_test", RUNNER_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _request(
    module,
    owner,
    argv: tuple[str, ...],
    profile_id: str,
    *,
    cwd: Path = ROOT,
):
    executable = Path(argv[0]).resolve()
    rows = tuple(
        module.EnvironmentRowV1(name, os.environ[name])
        for name in ("PATH", "SYSTEMROOT", "TEMP", "TMP")
        if name in os.environ
    )
    return module.ProcessRequestV1(
        schema_version=1,
        argv=(str(executable), *argv[1:]),
        resolved_executable=executable,
        cwd=str(cwd),
        environment=rows,
        stdin_bytes=None,
        deadline_monotonic=time.monotonic() + 10.0,
        capture_policy=module.CapturePolicyV1(
            "windows-argv-admission-test-v1", 1024 * 1024, 0, 0, 64 * 1024
        ),
        capture_sink_binding=owner.mint_memory_capture_sink(),
        settle_policy=module.SettlePolicyV1(5.0),
        windows_argv_profile_id=profile_id,
    )


def _admit(module, owner, request):
    lifecycle = owner._begin_lifecycle()
    try:
        admission = owner.windows_argv_admission_owner.admit(lifecycle, request)
        return lifecycle, admission
    except BaseException:
        lifecycle.finalize_once(time.monotonic() + 1.0)
        owner._release_lifecycle(lifecycle)
        raise


def _release(owner, lifecycle) -> None:
    lifecycle.finalize_once(time.monotonic() + 1.0)
    owner._release_lifecycle(lifecycle)


def _fake_kimi(module, path: Path, version: str = "0.38.0", *, duplicate: bool = False) -> Path:
    marker = module.KIMI_BUILD_INFO_MARKER_TEMPLATE_V1.format(version=version).encode("ascii")
    path.write_bytes(b"synthetic-prefix\0" + marker + (marker if duplicate else b"") + b"\0synthetic-suffix")
    return path


def _kimi_argv(module, executable: Path, prompt_file: Path) -> tuple[str, ...]:
    prompt_file.write_text(
        "---\ntools: []\nsubagents: []\n---\nGATE: PASS\n", encoding="utf-8"
    )
    skills = prompt_file.parent / "empty-skills"
    skills.mkdir(exist_ok=True)
    return (
        str(executable.resolve()),
        *module.KimiWindowsProfileV1.build_args(prompt_file, skills),
    )


def test_request_contract_removes_adapter_authored_attestation_fields() -> None:
    """A caller cannot supply requested-as-observed argv evidence on the request."""

    module = _load_runner()
    names = {item.name for item in dataclasses.fields(module.ProcessRequestV1)}

    assert "windows_argv_profile_id" in names
    assert "windows_argv_attestation" not in names
    assert "windows_argv_codec" not in names
    assert not hasattr(module, "WindowsArgvAttestationV1")
    assert "WindowsInternalProbeAdmissionV1" not in module.__all__
    assert hasattr(module.WindowsCreateOwnerV1, "create_internal_probe")
    assert hasattr(module.WindowsCreateOwnerV1, "create_task")


def test_admission_owner_has_no_direct_subprocess_escape_hatch() -> None:
    """Internal probes cannot bypass the lifecycle through subprocess helpers."""

    module = _load_runner()
    source = inspect.getsource(module.WindowsArgvAdmissionOwnerV1)
    assert "subprocess.run" not in source
    assert "subprocess.Popen" not in source
    assert "_bounded_probe_run" not in source


@pytest.mark.skipif(os.name != "nt", reason="Windows Kimi argv profile contract")
def test_kimi_profile_accepts_only_fixed_transport_and_binds_prompt_file(tmp_path: Path) -> None:
    module = _load_runner()
    owner = module.ProcessRunnerV1()
    neutral = tmp_path / "neutral root-Москва"
    neutral.mkdir()
    prompt = neutral / "prompt instructions.md"
    prompt.write_text("facts only\nGATE: PASS\n", encoding="utf-8")
    executable = _fake_kimi(module, tmp_path / "kimi.exe")
    request = _request(
        module,
        owner,
        _kimi_argv(module, executable, prompt),
        "kimi-sealed-bundle-text-v1",
        cwd=neutral,
    )

    lifecycle, admission = _admit(module, owner, request)
    try:
        assert admission.profile_id == "kimi-sealed-bundle-text-v1"
        assert admission.probe_kind == "kimi-sealed-bundle-v1"
        assert admission.prompt_file_canonical == str(prompt.resolve())
        assert admission.prompt_file_identity
        assert admission.prompt_file_sha256
        owner.windows_argv_admission_owner.consume(lifecycle, request, admission)
    finally:
        _release(owner, lifecycle)


@pytest.mark.skipif(os.name != "nt", reason="Windows Kimi argv profile contract")
@pytest.mark.parametrize(
    "mutate",
    (
        lambda argv: (*argv[:1], "-m", *argv[2:]),
        lambda argv: (*argv[:1], "--output-format", "text", "--model", "kimi-code/k3", *argv[5:]),
        lambda argv: (*argv, "--extra"),
        lambda argv: (*argv[:2], "other-model", *argv[3:]),
        lambda argv: (*argv[:4], "stream-json", *argv[5:]),
        lambda argv: (*argv[:6], argv[6] + " "),
    ),
)
def test_kimi_profile_rejects_argv_variants_without_probe(tmp_path: Path, mutate) -> None:
    module = _load_runner()
    owner = module.ProcessRunnerV1()
    neutral = tmp_path / "neutral"
    neutral.mkdir()
    prompt = neutral / "prompt.md"
    prompt.write_text("GATE: PASS\n", encoding="utf-8")
    executable = _fake_kimi(module, tmp_path / "kimi.exe")
    request = _request(
        module,
        owner,
        tuple(mutate(_kimi_argv(module, executable, prompt))),
        "kimi-sealed-bundle-text-v1",
        cwd=neutral,
    )
    lifecycle = owner._begin_lifecycle()
    try:
        with pytest.raises(module.ProcessSupervisionError) as caught:
            owner.windows_argv_admission_owner.admit(lifecycle, request)
        assert caught.value.failure_id == "PSV1-ARGV-CODEC-UNSUPPORTED"
    finally:
        _release(owner, lifecycle)


@pytest.mark.skipif(os.name != "nt", reason="Windows Kimi argv profile contract")
@pytest.mark.parametrize("version,duplicate", (("0.37.0", False), ("0.38.0", True)))
def test_kimi_profile_rejects_wrong_or_ambiguous_embedded_version(
    tmp_path: Path, version: str, duplicate: bool
) -> None:
    module = _load_runner()
    owner = module.ProcessRunnerV1()
    neutral = tmp_path / "neutral"
    neutral.mkdir()
    prompt = neutral / "prompt.md"
    prompt.write_text("GATE: PASS\n", encoding="utf-8")
    executable = _fake_kimi(module, tmp_path / "kimi.exe", version, duplicate=duplicate)
    request = _request(
        module,
        owner,
        _kimi_argv(module, executable, prompt),
        "kimi-sealed-bundle-text-v1",
        cwd=neutral,
    )
    lifecycle = owner._begin_lifecycle()
    try:
        with pytest.raises(module.ProcessSupervisionError) as caught:
            owner.windows_argv_admission_owner.admit(lifecycle, request)
        assert caught.value.failure_id == "PSV1-EXECUTABLE-UNRESOLVED"
    finally:
        _release(owner, lifecycle)


@pytest.mark.skipif(os.name != "nt", reason="Windows Kimi argv profile contract")
def test_kimi_profile_rejects_prompt_mutation_between_admit_and_consume(tmp_path: Path) -> None:
    module = _load_runner()
    owner = module.ProcessRunnerV1()
    neutral = tmp_path / "neutral"
    neutral.mkdir()
    prompt = neutral / "prompt.md"
    prompt.write_text("GATE: PASS\n", encoding="utf-8")
    executable = _fake_kimi(module, tmp_path / "kimi.exe")
    request = _request(
        module,
        owner,
        _kimi_argv(module, executable, prompt),
        "kimi-sealed-bundle-text-v1",
        cwd=neutral,
    )
    lifecycle, admission = _admit(module, owner, request)
    try:
        prompt.write_text("changed\nGATE: PASS\n", encoding="utf-8")
        with pytest.raises(module.ProcessSupervisionError) as caught:
            owner.windows_argv_admission_owner.consume(lifecycle, request, admission)
        assert caught.value.failure_id == "PSV1-ARGV-ATTESTATION"
    finally:
        _release(owner, lifecycle)


@pytest.mark.skipif(os.name != "nt", reason="real Windows argv probe contract")
def test_python_profile_uses_real_child_json_argv_echo() -> None:
    """A real child, not the request builder, must establish Python argv equality."""

    module = _load_runner()
    owner = module.ProcessRunnerV1()
    argv = (
        str(Path(sys.executable).resolve()),
        str(CHILD),
        "identity",
        "",
        "two words",
        'quote"inside',
        'backslashes\\before"quote',
        "C:\\path with space\\",
        "Москва-测试",
    )
    request = _request(module, owner, argv, "python-validator-json-echo-v1")

    lifecycle, admission = _admit(module, owner, request)
    try:
        assert admission.profile_id == "python-validator-json-echo-v1"
        assert admission.probe_kind == "python-json-argv-echo-v1"
        assert admission.probe_requested_argv_sha256 == admission.probe_observed_argv_sha256
        assert admission.actual_argv_sha256 == module._json_argv_sha256(request.argv)
        assert admission.run_token_sha256 == lifecycle.token.sha256
    finally:
        _release(owner, lifecycle)


@pytest.mark.skipif(os.name != "nt", reason="real Windows argv probe contract")
def test_git_profile_uses_real_rev_parse_sq_quote_probe() -> None:
    """Git admission must parse Git's child-produced sq-quote result exactly."""

    located = shutil.which("git")
    if located is None:
        pytest.skip("Git executable is unavailable")
    module = _load_runner()
    owner = module.ProcessRunnerV1()
    argv = (
        str(Path(located).resolve()),
        "-C",
        str(ROOT),
        "status",
        "--short",
        "--",
        "two words",
        'quote"inside',
        "C:\\path with space\\",
        "Москва-测试",
    )
    request = _request(module, owner, argv, "git-rev-parse-sq-quote-v1")

    lifecycle, admission = _admit(module, owner, request)
    try:
        assert admission.profile_id == "git-rev-parse-sq-quote-v1"
        assert admission.probe_kind == "git-rev-parse-sq-quote-v1"
        assert admission.probe_requested_argv_sha256 == admission.probe_observed_argv_sha256
    finally:
        _release(owner, lifecycle)


@pytest.mark.skipif(os.name != "nt", reason="Windows argv profile contract")
@pytest.mark.parametrize(
    "profile_id",
    (
        "codex-native-safe-v1",
        "claude-native-safe-v1",
        "kimi-native-safe-v1",
        "grok-native-safe-v1",
        "unknown-native-v1",
        None,
    ),
)
def test_unavailable_profiles_deny_without_probe(
    monkeypatch: pytest.MonkeyPatch, profile_id: str | None
) -> None:
    """Every native, unknown, and missing profile creates no child process."""

    module = _load_runner()
    calls = []
    monkeypatch.setattr(module.subprocess, "run", lambda *_a, **_k: calls.append(1))
    owner = module.ProcessRunnerV1()
    request = _request(
        module,
        owner,
        (str(Path(sys.executable).resolve()), str(CHILD), "identity"),
        profile_id,
    )
    lifecycle = owner._begin_lifecycle()
    try:
        with pytest.raises(module.ProcessSupervisionError) as caught:
            owner.windows_argv_admission_owner.admit(lifecycle, request)
        assert caught.value.failure_id == "PSV1-ARGV-CODEC-UNSUPPORTED"
        assert calls == []
    finally:
        _release(owner, lifecycle)


@pytest.mark.skipif(os.name != "nt", reason="Windows argv admission consume contract")
def test_create_owner_rejects_forged_stale_cross_run_and_mismatched_admissions() -> None:
    """Only the exact opaque admission from this run/request may reach creation."""

    module = _load_runner()
    owner = module.ProcessRunnerV1()
    request = _request(
        module,
        owner,
        (str(Path(sys.executable).resolve()), str(CHILD), "identity"),
        "python-validator-json-echo-v1",
    )
    lifecycle, admission = _admit(module, owner, request)
    calls = []
    create_owner = module.WindowsCreateOwnerV1(
        owner.windows_argv_admission_owner,
        request,
        lambda: calls.append("create") or "created",
    )
    mutations = (
        (
            dataclasses.replace(admission, _seal=object()),
            "PSV1-ARGV-ATTESTATION",
            "request-validation",
        ),
        (
            dataclasses.replace(
                admission, expires_at_monotonic=time.monotonic() - 1.0
            ),
            "PSV1-DEADLINE",
            "deadline",
        ),
        (
            dataclasses.replace(admission, run_token_sha256="0" * 64),
            "PSV1-ARGV-ATTESTATION",
            "request-validation",
        ),
        (
            dataclasses.replace(admission, resolved_executable_identity="0" * 64),
            "PSV1-ARGV-ATTESTATION",
            "request-validation",
        ),
        (
            dataclasses.replace(admission, resolved_executable_version="0" * 64),
            "PSV1-ARGV-ATTESTATION",
            "request-validation",
        ),
        (
            dataclasses.replace(admission, profile_id="git-rev-parse-sq-quote-v1"),
            "PSV1-ARGV-ATTESTATION",
            "request-validation",
        ),
        (
            dataclasses.replace(admission, actual_argv_shape_sha256="0" * 64),
            "PSV1-ARGV-ATTESTATION",
            "request-validation",
        ),
        (
            dataclasses.replace(
                admission,
                probe_observed_argv_sha256=admission.probe_requested_argv_sha256,
                _child_evidence_seal=object(),
            ),
            "PSV1-ARGV-ATTESTATION",
            "request-validation",
        ),
    )
    try:
        for invalid, failure_id, terminal_stage in mutations:
            with pytest.raises(module.ProcessSupervisionError) as caught:
                create_owner.create_task(lifecycle, request, invalid)
            assert caught.value.failure_id == failure_id
            assert caught.value.terminal_stage == terminal_stage
        changed_request = dataclasses.replace(request, argv=(*request.argv, "changed"))
        with pytest.raises(module.ProcessSupervisionError):
            create_owner.create_task(lifecycle, changed_request, admission)
        assert calls == []
        assert create_owner.create_task(lifecycle, request, admission) == "created"
        assert calls == ["create"]
    finally:
        _release(owner, lifecycle)


@pytest.mark.skipif(os.name != "nt", reason="Windows internal probe lifecycle")
def test_probe_preserves_original_task_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Admission never replaces or extends the caller's absolute deadline."""

    module = _load_runner()
    owner = module.ProcessRunnerV1()
    request = _request(
        module,
        owner,
        (str(Path(sys.executable).resolve()), str(CHILD), "identity"),
        "python-validator-json-echo-v1",
    )
    original_deadline = request.deadline_monotonic
    observed: list[float] = []

    def backend(task_request, _lifecycle, _validated_cwd):
        observed.append(task_request.deadline_monotonic)
        return module._request_failure(
            task_request,
            module.ProcessSupervisionError("PSV1-INTERNAL", "execution"),
            time.monotonic(),
        )

    owner._backend_factory = lambda *_args: backend
    owner.run(request)

    assert observed == [original_deadline]


@pytest.mark.skipif(os.name != "nt", reason="Windows admission expiry classification")
def test_successful_probe_then_pre_task_expiry_is_typed_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expiry at task consume is DEADLINE/timed_out and never starts the task."""

    module = _load_runner()
    owner = module.ProcessRunnerV1()
    marker = tmp_path / "task-started.txt"
    request = _request(
        module,
        owner,
        (
            str(Path(sys.executable).resolve()),
            str(CHILD),
            "marker",
            "--marker",
            str(marker),
        ),
        "python-validator-json-echo-v1",
    )
    original_deadline = request.deadline_monotonic
    real_monotonic = module.time.monotonic

    class OneShotClock:
        expire_next = False

        def __call__(self) -> float:
            if self.expire_next:
                self.expire_next = False
                return original_deadline + 1.0
            return real_monotonic()

    clock = OneShotClock()
    original_create_task = module.WindowsCreateOwnerV1.create_task

    def expire_before_consume(create_owner, lifecycle, task_request, admission):
        clock.expire_next = True
        return original_create_task(
            create_owner, lifecycle, task_request, admission
        )

    monkeypatch.setattr(module.time, "monotonic", clock)
    monkeypatch.setattr(
        module.WindowsCreateOwnerV1,
        "create_task",
        expire_before_consume,
    )

    result = owner.run(request)

    assert request.deadline_monotonic == original_deadline
    assert result.failure_id == "PSV1-DEADLINE"
    assert result.terminal_stage == "deadline"
    assert result.timed_out is True
    assert result.target_exit_code is None
    assert result.tree.tree_empty
    assert result.resources_closed
    assert not marker.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows internal probe lifecycle")
def test_slow_probe_respects_original_deadline_and_never_starts_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A slow probe is killed and settled without borrowing a fresh timeout."""

    module = _load_runner()
    monkeypatch.setattr(
        module,
        "_PYTHON_ARGV_ECHO_HELPER",
        "import time;time.sleep(60)",
    )
    owner = module.ProcessRunnerV1()
    marker = tmp_path / "task-started.txt"
    request = _request(
        module,
        owner,
        (
            str(Path(sys.executable).resolve()),
            str(CHILD),
            "marker",
            "--marker",
            str(marker),
        ),
        "python-validator-json-echo-v1",
    )
    request = dataclasses.replace(
        request, deadline_monotonic=time.monotonic() + 0.25
    )

    started = time.monotonic()
    result = owner.run(request)

    assert time.monotonic() - started < 5.0
    assert result.failure_id == "PSV1-DEADLINE"
    assert result.tree.tree_empty
    assert result.resources_closed
    assert not marker.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows internal probe lifecycle")
def test_probe_capture_cap_is_active_and_reaps_before_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The 64 KiB probe cap terminates output instead of retaining full capture."""

    module = _load_runner()
    monkeypatch.setattr(
        module,
        "_PYTHON_ARGV_ECHO_HELPER",
        "import sys,time;sys.stdout.buffer.write(b'x'*65537);"
        "sys.stdout.buffer.flush();time.sleep(60)",
    )
    owner = module.ProcessRunnerV1()
    marker = tmp_path / "task-started.txt"
    request = _request(
        module,
        owner,
        (
            str(Path(sys.executable).resolve()),
            str(CHILD),
            "marker",
            "--marker",
            str(marker),
        ),
        "python-validator-json-echo-v1",
    )

    result = owner.run(request)

    assert result.failure_id == "PSV1-CAPTURE-LIMIT"
    assert result.tree.tree_empty
    assert result.resources_closed
    assert not marker.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows internal probe lifecycle")
def test_nonzero_probe_preserves_child_failure_evidence_and_never_starts_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A clean nonzero probe exit returns its settled evidence, not a generic shell."""

    module = _load_runner()
    monkeypatch.setattr(
        module,
        "_PYTHON_ARGV_ECHO_HELPER",
        "import sys;sys.exit(23)",
    )
    owner = module.ProcessRunnerV1()
    marker = tmp_path / "task-started.txt"
    request = _request(
        module,
        owner,
        (
            str(Path(sys.executable).resolve()),
            str(CHILD),
            "marker",
            "--marker",
            str(marker),
        ),
        "python-validator-json-echo-v1",
    )

    result = owner.run(request)

    assert result.outcome == "child-failure"
    assert result.failure_id is None
    assert result.target_exit_code == 23
    assert result.tree.backend == "windows-job-v1"
    assert result.tree.ownership_confirmed
    assert result.tree.tree_empty
    assert result.tree.direct_reaped
    assert result.resources_closed
    assert result.policy_id == "windows-internal-argv-probe-v1"
    assert result.stdout.observed_bytes == 0
    assert result.stderr.observed_bytes == 0
    assert not result.stdout.truncated
    assert not result.stderr.truncated
    assert not marker.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows internal probe settlement")
@pytest.mark.parametrize("case", ("resource-uncertain", "tree-nonempty", "truncated"))
def test_ineligible_probe_settlement_preserves_original_evidence_and_zero_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    """Ineligible settled probe evidence crosses the private handoff unchanged."""

    module = _load_runner()
    owner = module.ProcessRunnerV1()
    marker = tmp_path / "task-started.txt"
    request = _request(
        module,
        owner,
        (
            str(Path(sys.executable).resolve()),
            str(CHILD),
            "marker",
            "--marker",
            str(marker),
        ),
        "python-validator-json-echo-v1",
    )
    expected_tree_empty = case != "tree-nonempty"
    expected_resources_closed = case != "resource-uncertain"
    expected_uncertain = case == "resource-uncertain"
    expected_truncated = case == "truncated"
    expected_cleanup = (
        ("PSV1-RESOURCE-CLOSE",) if case == "resource-uncertain" else ()
    )

    def ineligible_result(_lifecycle, probe_request, _admission):
        base = module._request_failure(
            probe_request,
            module.ProcessSupervisionError("PSV1-INTERNAL", "execution"),
            time.monotonic(),
        )
        stdout = (
            module.StreamObservationV1(
                65537,
                65536,
                True,
                b"x",
                b"y",
                "d" * 64,
                "e" * 64,
            )
            if expected_truncated
            else module._empty_stream()
        )
        return dataclasses.replace(
            base,
            outcome="success",
            failure_id=None,
            terminal_stage="completed",
            target_exit_code=0,
            stdout=stdout,
            tree=module.TreeObservationV1(
                "windows-job-v1",
                True,
                "EMPTY" if expected_tree_empty else "NONEMPTY",
                expected_tree_empty,
                True,
                True,
                True,
            ),
            resources_closed=expected_resources_closed,
            cleanup_uncertain=expected_uncertain,
            cleanup_issues=expected_cleanup,
            policy_id="windows-internal-argv-probe-v1",
        )

    monkeypatch.setattr(
        owner.windows_argv_admission_owner,
        "_run_internal_probe",
        ineligible_result,
    )

    result = owner.run(request)

    assert result.outcome == "success"
    assert result.failure_id is None
    assert result.target_exit_code == 0
    assert result.tree.backend == "windows-job-v1"
    assert result.tree.tree_empty is expected_tree_empty
    assert result.resources_closed is expected_resources_closed
    assert result.cleanup_uncertain is expected_uncertain
    assert result.cleanup_issues == expected_cleanup
    assert result.stdout.truncated is expected_truncated
    assert result.stdout.observed_bytes == (65537 if expected_truncated else 0)
    assert result.policy_id == "windows-internal-argv-probe-v1"
    assert not marker.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows internal probe content")
def test_fully_settled_probe_content_mismatch_remains_argv_attestation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only eligible settlement reaches content parsing; malformed echo stays typed."""

    module = _load_runner()
    owner = module.ProcessRunnerV1()
    marker = tmp_path / "task-started.txt"
    request = _request(
        module,
        owner,
        (
            str(Path(sys.executable).resolve()),
            str(CHILD),
            "marker",
            "--marker",
            str(marker),
        ),
        "python-validator-json-echo-v1",
    )

    def eligible_but_empty(_lifecycle, probe_request, _admission):
        base = module._request_failure(
            probe_request,
            module.ProcessSupervisionError("PSV1-INTERNAL", "execution"),
            time.monotonic(),
        )
        return dataclasses.replace(
            base,
            outcome="success",
            failure_id=None,
            terminal_stage="completed",
            target_exit_code=0,
            tree=module.TreeObservationV1(
                "windows-job-v1", True, "EMPTY", True, True, True, True
            ),
            resources_closed=True,
            cleanup_uncertain=False,
            cleanup_issues=(),
            policy_id="windows-internal-argv-probe-v1",
        )

    monkeypatch.setattr(
        owner.windows_argv_admission_owner,
        "_run_internal_probe",
        eligible_but_empty,
    )

    result = owner.run(request)

    assert result.failure_id == "PSV1-ARGV-ATTESTATION"
    assert result.terminal_stage == "request-validation"
    assert result.outcome == "supervisor-failure"
    assert not marker.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows internal probe lifecycle")
def test_runner_close_cancels_and_reaps_active_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Runner close owns active-probe cancellation and settles within five seconds."""

    module = _load_runner()
    monkeypatch.setattr(
        module,
        "_PYTHON_ARGV_ECHO_HELPER",
        "import time;time.sleep(60)",
    )
    owner = module.ProcessRunnerV1()
    request = _request(
        module,
        owner,
        (str(Path(sys.executable).resolve()), str(CHILD), "identity"),
        "python-validator-json-echo-v1",
    )
    request = dataclasses.replace(
        request, deadline_monotonic=time.monotonic() + 30.0
    )
    results = []
    thread = threading.Thread(target=lambda: results.append(owner.run(request)))
    thread.start()
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        with owner._lock:
            lifecycles = tuple(owner._active.values())
        if lifecycles and any(
            "windows-probe-handle:process" in lifecycle.resource_names
            for lifecycle in lifecycles
        ):
            break
        time.sleep(0.01)
    else:
        pytest.fail("probe process did not enter the lifecycle")

    started = time.monotonic()
    close_result = owner.close()
    thread.join(5.0)

    assert time.monotonic() - started <= 5.0
    assert not thread.is_alive()
    assert close_result.outcome == "closed"
    assert results and results[0].failure_id == "PSV1-CANCELLED"
    assert results[0].tree.tree_empty
    assert results[0].resources_closed
