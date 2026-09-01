from __future__ import annotations

import ctypes
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/process_supervision/posix_process_group.py"
SCANNER = ROOT / "scripts/universal-hooks/scripts/check-publication-safety.py"
SOURCE_SCANNERS = (
    SCANNER,
    ROOT / "src.codex/skills/lead/scripts/check-publication-safety.py",
    ROOT / "src.claude/agents/scripts/check-publication-safety.py",
)
TRACKED_HELPER_PROJECTIONS = (
    ROOT / "src.codex/skills/lead/scripts/process_supervision/posix_process_group.py",
    ROOT / "src.claude/agents/scripts/process_supervision/posix_process_group.py",
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


def _linux_child_subreaper_state() -> int:
    libc = ctypes.CDLL(None, use_errno=True)
    state = ctypes.c_int()
    if libc.prctl(37, ctypes.byref(state), 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_GET_CHILD_SUBREAPER")
    return state.value


def _set_linux_child_subreaper(value: int) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, value, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_SET_CHILD_SUBREAPER")


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux subreaper")
def test_owner_restores_exact_prior_subreaper_on_idempotent_spawn_failure_close() -> None:
    module = _load(HELPER, "posix_owner_prior_restore")
    initial = _linux_child_subreaper_state()
    try:
        for prior in (0, 1):
            _set_linux_child_subreaper(prior)
            owner = module.PosixProcessGroupOwnerV1.acquire()
            first = owner.close()
            second = owner.close()
            assert first == second
            assert first.process_group is None
            assert first.prior_child_subreaper == prior
            assert first.child_subreaper_restored
            assert first.lock_released
            assert first.complete
            assert _linux_child_subreaper_state() == prior
    finally:
        _set_linux_child_subreaper(initial)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux subreaper")
def test_linux_owner_serializes_process_global_subreaper_state() -> None:
    module = _load(HELPER, "posix_owner_serialization")
    first = module.PosixProcessGroupOwnerV1.acquire()
    acquired = threading.Event()
    released = threading.Event()

    def acquire_second() -> None:
        second = module.PosixProcessGroupOwnerV1.acquire()
        acquired.set()
        second.close()
        released.set()

    thread = threading.Thread(target=acquire_second)
    thread.start()
    try:
        assert not acquired.wait(0.1)
        first.close()
        assert acquired.wait(2.0)
        assert released.wait(2.0)
    finally:
        first.close()
        thread.join(timeout=2.0)
    assert not thread.is_alive()


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux subreaper")
def test_acquire_baseexception_restores_state_and_releases_global_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load(HELPER, "posix_owner_acquire_baseexception")
    initial = _linux_child_subreaper_state()

    class InjectedBaseException(BaseException):
        pass

    class FakePrctl:
        restype = None

        def __call__(self, operation, argument, *_unused):
            if operation == 37:
                ctypes.cast(argument, ctypes.POINTER(ctypes.c_int)).contents.value = initial
                return 0
            if operation == 36 and argument == 1:
                raise InjectedBaseException()
            return 0

    monkeypatch.setattr(
        module.ctypes,
        "CDLL",
        lambda *_args, **_kwargs: SimpleNamespace(prctl=FakePrctl()),
    )
    observed_locked = False
    try:
        with pytest.raises(InjectedBaseException):
            module.PosixProcessGroupOwnerV1.acquire()
        observed_locked = module._LINUX_SUBREAPER_LOCK.locked()
    finally:
        if module._LINUX_SUBREAPER_LOCK.locked():
            module._LINUX_SUBREAPER_LOCK.release()

    assert not observed_locked


def test_all_consumers_reuse_one_resolved_helper_module_identity() -> None:
    scanner = _load(SCANNER, "posix_owner_identity_scanner")
    validator = _load(
        ROOT / "scripts/skill_pack_validator_runtime.py",
        "posix_owner_identity_validator",
    )
    installer = _load(
        ROOT / "scripts/production_installer.py",
        "posix_owner_identity_installer",
    )

    assert scanner._POSIX_PROCESS_GROUP is validator._POSIX_PROCESS_GROUP
    assert validator._POSIX_PROCESS_GROUP is installer._POSIX_PROCESS_GROUP
    assert (
        scanner.PosixProcessGroupOwnerV1.acquire.__func__
        is installer.PosixProcessGroupOwnerV1.acquire.__func__
    )


@pytest.mark.parametrize(
    "consumer",
    (
        SCANNER,
        ROOT / "scripts/skill_pack_validator_runtime.py",
        ROOT / "scripts/production_installer.py",
    ),
)
def test_consumers_reject_wrong_shared_module_contract(consumer: Path) -> None:
    module_name = "_orchestrarium_posix_process_group_v1"
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = SimpleNamespace(
        POSIX_PROCESS_GROUP_MODULE_CONTRACT_V1="wrong-contract",
        posix_process_group_module_contract_v1=lambda: (),
        PosixProcessGroupOwnerV1=type("WrongOwner", (), {}),
        PosixProcessGroupError=type("WrongError", (RuntimeError,), {}),
    )
    try:
        with pytest.raises(
            RuntimeError, match="identity(?:-| )mismatch|contract"
        ):
            _load(consumer, f"wrong_contract_{consumer.stem}")
    finally:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux subreaper")
def test_scanner_spawn_baseexception_restores_shared_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scanner = _load(SCANNER, "posix_owner_scanner_spawn_baseexception")
    initial = _linux_child_subreaper_state()

    class InjectedBaseException(BaseException):
        pass

    monkeypatch.setattr(
        scanner.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(InjectedBaseException()),
    )
    with pytest.raises(InjectedBaseException):
        scanner._run_owned_process([sys.executable, "-c", "pass"])

    assert _linux_child_subreaper_state() == initial
    assert not scanner._POSIX_PROCESS_GROUP._LINUX_SUBREAPER_LOCK.locked()


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux subreaper")
def test_owner_reaps_exited_parent_sigterm_ignoring_descendant(tmp_path: Path) -> None:
    module = _load(HELPER, "posix_owner_adopted_descendant")
    ready = tmp_path / "ready"
    owner = module.PosixProcessGroupOwnerV1.acquire()
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import os,pathlib,subprocess,sys,time;"
            "code=\"import os,pathlib,signal,sys,time\\n"
            "signal.signal(signal.SIGTERM,signal.SIG_IGN)\\n"
            "[os.close(fd) for fd in (0,1,2)]\\n"
            "pathlib.Path(sys.argv[1]).write_text('ready',encoding='ascii')\\n"
            "time.sleep(60)\";"
            "child=subprocess.Popen([sys.executable,'-c',code,sys.argv[1]]);"
            "deadline=time.monotonic()+5;"
            "exec(\"while not pathlib.Path(sys.argv[1]).is_file():\\n"
            "    assert time.monotonic()<deadline\\n"
            "    time.sleep(0.01)\");"
            "print(child.pid,flush=True)",
            str(ready),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        **owner.popen_kwargs,
    )
    owner.bind_process_group(process.pid)
    assert process.stdout is not None
    descendant_pid = int(process.stdout.readline().strip())
    process.wait(timeout=2.0)

    closure = owner.settle(1.0, direct_process=process)

    assert closure.complete
    assert closure.group_absent
    assert descendant_pid in closure.reaped_pids
    assert closure.term_sent
    assert closure.kill_sent
    assert not Path(f"/proc/{descendant_pid}").exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups")
def test_owner_uses_bounded_term_then_kill_and_leaves_foreign_group_alive(
    tmp_path: Path,
) -> None:
    module = _load(HELPER, "posix_owner_term_kill")
    foreign = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        start_new_session=True,
    )
    ready = tmp_path / "owned.ready"
    owner = module.PosixProcessGroupOwnerV1.acquire()
    owned = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import pathlib,signal,sys,time;"
            "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
            "pathlib.Path(sys.argv[1]).write_text('ready',encoding='ascii');"
            "time.sleep(60)",
            str(ready),
        ],
        **owner.popen_kwargs,
    )
    owner.bind_process_group(owned.pid)
    deadline = time.monotonic() + 2.0
    while not ready.is_file():
        assert time.monotonic() < deadline
        time.sleep(0.01)
    started = time.monotonic()
    try:
        closure = owner.settle(0.75, direct_process=owned)
        assert time.monotonic() - started < 1.5
        assert closure.complete
        assert closure.term_sent
        assert closure.kill_sent
        assert foreign.poll() is None
    finally:
        foreign.kill()
        foreign.wait(timeout=2.0)


@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups")
def test_owner_never_uses_unscoped_waitpid(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load(HELPER, "posix_owner_scoped_waitpid")
    calls: list[int] = []
    real_waitpid = os.waitpid

    def scoped_waitpid(pid: int, options: int):
        calls.append(pid)
        return real_waitpid(pid, options)

    monkeypatch.setattr(
        module,
        "os",
        SimpleNamespace(
            **{
                name: getattr(os, name)
                for name in dir(os)
                if not name.startswith("__") and name != "waitpid"
            },
            waitpid=scoped_waitpid,
        ),
    )
    owner = module.PosixProcessGroupOwnerV1.acquire()
    process = subprocess.Popen(
        [sys.executable, "-c", "pass"], **owner.popen_kwargs
    )
    owner.bind_process_group(process.pid)
    process.wait(timeout=2.0)
    closure = owner.settle(0.5, direct_process=process)

    assert closure.complete
    assert calls
    assert set(calls) == {-process.pid}
    assert -1 not in calls


@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups")
def test_group_waitpid_is_deferred_until_direct_observer_is_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load(HELPER, "posix_owner_waitpid_gate")
    calls: list[int] = []

    class DirectObservation:
        returncode: int | None = None

        def poll(self):
            return self.returncode

    direct = DirectObservation()
    owner = module.PosixProcessGroupOwnerV1()
    owner._linux = True

    def waitpid(pid: int, options: int):
        calls.append(pid)
        return 0, 0

    monkeypatch.setattr(
        module,
        "os",
        SimpleNamespace(
            **{
                name: getattr(os, name)
                for name in dir(os)
                if not name.startswith("__") and name != "waitpid"
            },
            waitpid=waitpid,
        ),
    )

    owner._reap_group(31415, [], direct, time.monotonic() + 1.0)
    assert calls == []
    direct.returncode = 0
    owner._reap_group(31415, [], direct, time.monotonic() + 1.0)
    assert calls == [-31415]


@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups")
def test_group_waitpid_interrupted_retry_keeps_direct_observer_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load(HELPER, "posix_owner_waitpid_interrupted")
    calls: list[int] = []
    outcomes: list[object] = [InterruptedError(), (0, 0)]

    class DirectObservation:
        def poll(self):
            return 0

    def waitpid(pid: int, options: int):
        calls.append(pid)
        outcome = outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(
        module,
        "os",
        SimpleNamespace(
            **{
                name: getattr(os, name)
                for name in dir(os)
                if not name.startswith("__") and name != "waitpid"
            },
            waitpid=waitpid,
        ),
    )
    owner = module.PosixProcessGroupOwnerV1()
    owner._linux = True
    owner._reap_group(
        27182, [], DirectObservation(), time.monotonic() + 1.0
    )

    assert calls == [-27182, -27182]
    assert outcomes == []


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux subreaper")
def test_repeated_waitpid_interrupts_are_deadline_bounded_and_release_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load(HELPER, "posix_owner_waitpid_interrupt_deadline")
    initial = _linux_child_subreaper_state()
    calls = 0
    real_os = module.os

    def waitpid(_pid: int, _options: int):
        nonlocal calls
        calls += 1
        raise InterruptedError()

    monkeypatch.setattr(
        module,
        "os",
        SimpleNamespace(
            **{
                name: getattr(real_os, name)
                for name in dir(real_os)
                if not name.startswith("__") and name != "waitpid"
            },
            waitpid=waitpid,
        ),
    )
    owner = module.PosixProcessGroupOwnerV1.acquire()
    process = subprocess.Popen(
        [sys.executable, "-c", "pass"], **owner.popen_kwargs
    )
    owner.bind_process_group(process.pid)
    process.wait(timeout=2.0)

    started = time.monotonic()
    with pytest.raises(module.PosixProcessGroupError) as captured:
        owner.settle(0.02, direct_process=process)
    elapsed = time.monotonic() - started

    assert captured.value.failure_id == "POSIX-PROCESS-GROUP-REAP"
    assert calls > sys.getrecursionlimit()
    assert elapsed < 0.5
    assert not module._LINUX_SUBREAPER_LOCK.locked()
    assert _linux_child_subreaper_state() == initial


@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups")
def test_non_linux_posix_branch_retains_group_only_settlement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load(HELPER, "posix_owner_non_linux")
    monkeypatch.setattr(module, "sys", SimpleNamespace(platform="darwin"))
    owner = module.PosixProcessGroupOwnerV1.acquire()
    process = subprocess.Popen(
        [sys.executable, "-c", "pass"], **owner.popen_kwargs
    )
    owner.bind_process_group(process.pid)
    closure = owner.settle(0.5, direct_process=process)

    assert closure.complete
    assert closure.prior_child_subreaper is None
    assert closure.reaped_pids == ()


@pytest.mark.skipif(os.name != "nt", reason="Windows acquisition rejection")
def test_windows_owner_acquisition_rejects_without_process_creation() -> None:
    module = _load(HELPER, "posix_owner_windows_rejection")
    with pytest.raises(module.PosixProcessGroupError) as captured:
        module.PosixProcessGroupOwnerV1.acquire()
    assert captured.value.failure_id == "POSIX-PROCESS-GROUP-UNAVAILABLE"


def test_helper_runtime_projection_and_installer_inventory_are_exact(
    tmp_path: Path,
) -> None:
    assert HELPER.is_file()
    assert all(not path.exists() for path in TRACKED_HELPER_PROJECTIONS)
    installer = _load(ROOT / "scripts/production_installer.py", "posix_owner_installer")
    assert "process_supervision/posix_process_group.py" in installer.RUNTIME_HELPERS
    destinations = installer._runtime_file_destinations(
        ROOT, tmp_path / "installed-scripts"
    )
    assert (
        HELPER,
        tmp_path / "installed-scripts/process_supervision/posix_process_group.py",
    ) in destinations

    loaded = _load(SCANNER, "scanner_exact_posix_owner")
    assert loaded.PosixProcessGroupOwnerV1 is not None


@pytest.mark.parametrize("scanner", SOURCE_SCANNERS)
def test_scanner_source_layouts_resolve_only_canonical_helper(scanner: Path) -> None:
    module_name = "_orchestrarium_posix_process_group_v1"
    sys.modules.pop(module_name, None)
    try:
        loaded = _load(scanner, f"source_layout_{scanner.parent.parent.name}")
        assert loaded.PosixProcessGroupOwnerV1 is not None
        assert Path(loaded._POSIX_PROCESS_GROUP.__file__).resolve() == HELPER.resolve()
    finally:
        sys.modules.pop(module_name, None)


@pytest.mark.parametrize(
    "relative_scripts",
    (
        Path(".agents/skills/lead/scripts"),
        Path(".claude/agents/scripts"),
    ),
)
def test_scanner_installed_layouts_resolve_only_installed_sibling(
    tmp_path: Path, relative_scripts: Path
) -> None:
    module_name = "_orchestrarium_posix_process_group_v1"
    scripts = tmp_path / relative_scripts
    helper = scripts / "process_supervision/posix_process_group.py"
    scripts.mkdir(parents=True)
    helper.parent.mkdir(parents=True)
    scanner = scripts / SCANNER.name
    scanner.write_bytes(SCANNER.read_bytes())
    helper.write_bytes(HELPER.read_bytes())
    sys.modules.pop(module_name, None)
    try:
        loaded = _load(scanner, f"installed_layout_{relative_scripts.parts[0]}")
        assert Path(loaded._POSIX_PROCESS_GROUP.__file__).resolve() == helper.resolve()
    finally:
        sys.modules.pop(module_name, None)


@pytest.mark.parametrize("provider", ("codex", "claude"))
@pytest.mark.parametrize("mode", ("project", "global"))
def test_install_propagates_canonical_helper_and_reinstall_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    mode: str,
) -> None:
    installer = _load(
        ROOT / "scripts/production_installer.py",
        f"posix_owner_install_{provider}_{mode}",
    )
    install_root = tmp_path / f"installed-{provider}-{mode}"
    install_root.mkdir()
    arguments = ["--force", "--no-hypothesis-hook"]
    if mode == "project":
        arguments.extend(
            ["--target", str(install_root), "--allow-unsafe-target"]
        )
    else:
        monkeypatch.setenv("USERPROFILE", str(install_root))
        monkeypatch.setenv("HOME", str(install_root))
        arguments.append("--global")
    installed_scripts = (
        install_root / ".agents/skills/lead/scripts"
        if provider == "codex"
        else install_root / ".claude/agents/scripts"
    )
    installed_helper = installed_scripts / "process_supervision/posix_process_group.py"

    assert installer.install(provider, arguments) == 0
    assert installed_helper.read_bytes() == HELPER.read_bytes()
    first = installed_helper.stat()
    assert installer.install(provider, arguments) == 0
    assert installed_helper.read_bytes() == HELPER.read_bytes()
    second = installed_helper.stat()
    assert (second.st_size, second.st_mtime_ns) == (first.st_size, first.st_mtime_ns)


def test_scanner_helper_loader_fails_closed_on_zero_or_multiple_candidates(
    tmp_path: Path,
) -> None:
    installed_scripts = tmp_path / "installed" / "scripts"
    installed_scripts.mkdir(parents=True)
    installed_scanner = installed_scripts / SCANNER.name
    installed_scanner.write_bytes(SCANNER.read_bytes())
    with pytest.raises(RuntimeError, match="POSIX process-group helper"):
        _load(installed_scanner, "scanner_without_posix_owner")

    canonical_scripts = tmp_path / "canonical" / "scripts"
    scanner_dir = canonical_scripts / "universal-hooks" / "scripts"
    scanner_dir.mkdir(parents=True)
    ambiguous_scanner = scanner_dir / SCANNER.name
    ambiguous_scanner.write_bytes(SCANNER.read_bytes())
    for candidate in (
        scanner_dir / "process_supervision" / HELPER.name,
        canonical_scripts / "process_supervision" / HELPER.name,
    ):
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_bytes(HELPER.read_bytes())
    with pytest.raises(RuntimeError, match="POSIX process-group helper"):
        _load(ambiguous_scanner, "scanner_with_ambiguous_posix_owner")
