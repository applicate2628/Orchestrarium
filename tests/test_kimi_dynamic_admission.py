from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
OWNER_PATH = ROOT / "scripts" / "provider_prompt.py"


def _load_owner():
    spec = importlib.util.spec_from_file_location("kimi_dynamic_admission_owner", OWNER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _channel(owner, version: str, payload: bytes, *, latest_location: str | None = None,
             manifest_location: str | None = None, manifest_body: bytes | None = None):
    filename = "kimi-code-win32-x64.exe"
    manifest = manifest_body or json.dumps(
        {
            "version": version,
            "tag": f"@moonshot-ai/kimi-code@{version}",
            "platforms": {
                "win32-x64": {
                    "filename": filename,
                    "checksum": hashlib.sha256(payload).hexdigest(),
                }
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")
    latest_cdn = "https://cdn.kimi.com/kimi-code/latest"
    manifest_code = f"https://code.kimi.com/kimi-code/binaries/{version}/manifest.json"
    manifest_cdn = f"https://cdn.kimi.com/kimi-code/binaries/{version}/manifest.json"
    responses = {
        owner.KIMI_LATEST_URL_V2: owner.KimiHttpResponseV2(
            302, {"location": latest_location or latest_cdn}, b""
        ),
        latest_cdn: owner.KimiHttpResponseV2(200, {}, (version + "\n").encode("ascii")),
        manifest_code: owner.KimiHttpResponseV2(
            302, {"location": manifest_location or manifest_cdn}, b""
        ),
        manifest_cdn: owner.KimiHttpResponseV2(200, {}, manifest),
    }

    def fetch(url: str):
        return responses[url]

    return fetch


def _probe(version: str):
    calls: list[tuple[str, ...]] = []

    def run(_path: Path, argv: tuple[str, ...], environment: dict[str, str], cwd: Path,
            _binding):
        calls.append(argv)
        assert environment["KIMI_CODE_HOME"] == str(cwd)
        assert environment["KIMI_CODE_NO_AUTO_UPDATE"] == "1"
        assert set(environment).issubset(
            {"KIMI_CODE_HOME", "KIMI_CODE_NO_AUTO_UPDATE", "SYSTEMROOT"}
        )
        if argv == ("--version",):
            return (version + "\n").encode("utf-8")
        assert argv == ("--help",)
        return b"Usage: kimi --agent-file --skills-dir --model --output-format --prompt\n"

    run.calls = calls
    return run


def _paths(tmp_path: Path, payload: bytes) -> tuple[Path, Path, Path]:
    home = tmp_path / "user"
    executable = home / ".kimi-code" / "bin" / "kimi.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(payload)
    runtime = home / ".codex" / "orchestrarium-runtime" / "kimi"
    return home, runtime, executable


def _private_runtime(owner, runtime: Path) -> None:
    runtime.mkdir(parents=True)
    if os.name == "nt":
        owner.WindowsPrivateObjectOwnerV1.protect_and_verify(
            runtime, directory=True
        )
    else:
        runtime.chmod(0o700)


def _admit(owner, home: Path, runtime: Path, fetch, probe, now: datetime,
           *, offline_policy: str = "disabled"):
    return owner.admit_kimi_executable_v2(
        home,
        runtime,
        fetcher=fetch,
        probe_runner=probe,
        now_utc=now,
        offline_policy=offline_policy,
        dry_run=False,
    )


def test_live_manifest_admits_new_release_without_source_hash_edit(tmp_path: Path) -> None:
    owner = _load_owner()
    payload = b"future-kimi-release-not-present-in-source"
    home, runtime, executable = _paths(tmp_path, payload)
    now = datetime(2026, 8, 30, tzinfo=timezone.utc)

    binding = _admit(owner, home, runtime, _channel(owner, "0.40.0", payload), _probe("0.40.0"), now)

    assert binding.path == str(executable)
    assert binding.size == len(payload)
    assert binding.sha256 == hashlib.sha256(payload).hexdigest()
    receipt = json.loads((runtime / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V2).read_text("utf-8"))
    assert receipt["schema"] == owner.KIMI_EXECUTABLE_BINDING_SCHEMA_V2
    assert receipt["version"] == "0.40.0"
    assert receipt["filename"] == "kimi-code-win32-x64.exe"
    assert receipt["manifestSha256"]
    assert receipt["versionProbeSha256"] and receipt["helpProbeSha256"]


def test_live_manifest_denies_downgrade_and_same_version_equivocation(tmp_path: Path) -> None:
    owner = _load_owner()
    current = b"current"
    home, runtime, executable = _paths(tmp_path, current)
    now = datetime(2026, 8, 30, tzinfo=timezone.utc)
    _admit(owner, home, runtime, _channel(owner, "0.40.0", current), _probe("0.40.0"), now)

    executable.write_bytes(b"older")
    with pytest.raises(ValueError, match="^E_KIMI_ADMISSION_DOWNGRADE$"):
        _admit(owner, home, runtime, _channel(owner, "0.39.1", b"older"), _probe("0.39.1"), now)

    executable.write_bytes(b"different-same-version")
    with pytest.raises(ValueError, match="^E_KIMI_ADMISSION_EQUIVOCATION$"):
        _admit(
            owner,
            home,
            runtime,
            _channel(owner, "0.40.0", b"different-same-version"),
            _probe("0.40.0"),
            now,
        )


@pytest.mark.parametrize(
    "latest_location,manifest_location",
    [
        ("http://cdn.kimi.com/kimi-code/latest", None),
        ("https://evil.example/kimi-code/latest", None),
        ("https://cdn.kimi.com:443/kimi-code/latest", None),
        (None, "https://cdn.kimi.com/kimi-code/binaries/0.40.0/other.json"),
    ],
)
def test_official_channel_rejects_redirect_authority_or_path_drift(
    tmp_path: Path, latest_location: str | None, manifest_location: str | None
) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    fetch = _channel(
        owner,
        "0.40.0",
        payload,
        latest_location=latest_location,
        manifest_location=manifest_location,
    )
    with pytest.raises(ValueError, match="^E_KIMI_OFFICIAL_CHANNEL_INVALID$"):
        _admit(owner, home, runtime, fetch, _probe("0.40.0"), datetime.now(timezone.utc))


@pytest.mark.parametrize(
    "manifest_body",
    [
        b'{"version":"0.40.0","version":"0.40.1","tag":"x","platforms":{}}',
        b'{"version":"0.40.0","tag":"@moonshot-ai/kimi-code@0.40.0","platforms":{"win32-x64":{"filename":"../kimi.exe","checksum":"' + b"0" * 64 + b'"}}}',
        b"\xff",
    ],
)
def test_manifest_duplicate_keys_path_escape_and_invalid_utf8_fail_closed(
    tmp_path: Path, manifest_body: bytes
) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    fetch = _channel(owner, "0.40.0", payload, manifest_body=manifest_body)
    with pytest.raises(ValueError, match="^E_KIMI_MANIFEST_INVALID$"):
        _admit(owner, home, runtime, fetch, _probe("0.40.0"), datetime.now(timezone.utc))


def test_checksum_and_probe_mismatch_fail_before_admission_receipt(tmp_path: Path) -> None:
    owner = _load_owner()
    payload = b"actual"
    home, runtime, _ = _paths(tmp_path, payload)
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="^E_KIMI_EXECUTABLE_IDENTITY_INVALID$"):
        _admit(owner, home, runtime, _channel(owner, "0.40.0", b"other"), _probe("0.40.0"), now)
    with pytest.raises(ValueError, match="^E_KIMI_PROBE_INVALID$"):
        _admit(owner, home, runtime, _channel(owner, "0.40.0", payload), _probe("0.39.1"), now)
    assert not (runtime / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V2).exists()


def test_v2_offline_window_accepts_only_exact_object_and_denies_expiry_or_clock_rollback(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, executable = _paths(tmp_path, payload)
    admitted = datetime(2026, 8, 30, tzinfo=timezone.utc)
    probe = _probe("0.40.0")
    _admit(
        owner,
        home,
        runtime,
        _channel(owner, "0.40.0", payload),
        probe,
        admitted,
        offline_policy="24h",
    )

    def offline(_url: str):
        raise owner.KimiOfficialChannelUnavailableV2()

    binding = _admit(owner, home, runtime, offline, probe, admitted + timedelta(hours=23), offline_policy="24h")
    assert binding.sha256 == hashlib.sha256(payload).hexdigest()
    with pytest.raises(ValueError, match="^E_KIMI_OFFLINE_EXPIRED$"):
        _admit(owner, home, runtime, offline, probe, admitted + timedelta(hours=25), offline_policy="24h")
    with pytest.raises(ValueError, match="^E_KIMI_CLOCK_ROLLBACK$"):
        _admit(owner, home, runtime, offline, probe, admitted - timedelta(seconds=1), offline_policy="24h")
    with pytest.raises(ValueError, match="^E_KIMI_CLOCK_ROLLBACK$"):
        _admit(
            owner,
            home,
            runtime,
            _channel(owner, "0.40.0", payload),
            probe,
            admitted - timedelta(seconds=1),
            offline_policy="24h",
        )
    executable.write_bytes(b"drifted")
    with pytest.raises(ValueError, match="^E_KIMI_EXECUTABLE_IDENTITY_INVALID$"):
        _admit(
            owner,
            home,
            runtime,
            offline,
            probe,
            admitted + timedelta(hours=23, minutes=1),
            offline_policy="24h",
        )


def test_v1_binding_never_authorizes_offline_v2_migration(tmp_path: Path) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, executable = _paths(tmp_path, payload)
    _private_runtime(owner, runtime)
    (runtime / "executable-binding-v1.json").write_bytes(
        json.dumps(
            {
                "schema": "orchestrarium.kimi-executable-binding.v1",
                "path": str(executable),
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n",
    )

    def offline(_url: str):
        raise owner.KimiOfficialChannelUnavailableV2()

    with pytest.raises(ValueError, match="^E_KIMI_LIVE_EVIDENCE_REQUIRED$"):
        _admit(
            owner,
            home,
            runtime,
            offline,
            _probe("0.40.0"),
            datetime.now(timezone.utc),
            offline_policy="7d",
        )


def test_existing_v2_verify_is_offline_nonauthorizing_and_byte_preserving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, executable = _paths(tmp_path, payload)
    now = datetime(2026, 8, 30, tzinfo=timezone.utc)
    probe = _probe("0.40.0")
    _admit(owner, home, runtime, _channel(owner, "0.40.0", payload), probe, now)
    receipt = runtime / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V2
    before = receipt.read_bytes()
    before_metadata = receipt.stat()
    monkeypatch.setattr(
        owner,
        "_fetch_kimi_https_once_v2",
        lambda *_args: pytest.fail("verify reached network"),
    )
    monkeypatch.setattr(
        owner,
        "_write_kimi_v2_receipt",
        lambda *_args: pytest.fail("verify reached persistent write"),
    )

    binding = owner.verify_kimi_executable_v2(
        home, runtime, probe_runner=probe
    )

    after_metadata = receipt.stat()
    assert binding.path == str(executable)
    assert receipt.read_bytes() == before
    assert (after_metadata.st_ino, after_metadata.st_size, after_metadata.st_mtime_ns) == (
        before_metadata.st_ino,
        before_metadata.st_size,
        before_metadata.st_mtime_ns,
    )


def test_dry_run_leaves_exact_persistent_inventory_unchanged(tmp_path: Path) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    assert not runtime.exists()
    owner.admit_kimi_executable_v2(
        home,
        runtime,
        fetcher=_channel(owner, "0.40.0", payload),
        probe_runner=_probe("0.40.0"),
        now_utc=datetime(2026, 8, 30, tzinfo=timezone.utc),
        dry_run=True,
    )
    assert not runtime.exists()


def test_dry_run_preserves_existing_receipt_bytes_and_identity(tmp_path: Path) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    probe = _probe("0.40.0")
    channel = _channel(owner, "0.40.0", payload)
    _admit(
        owner,
        home,
        runtime,
        channel,
        probe,
        datetime(2026, 8, 30, tzinfo=timezone.utc),
    )
    before = {
        path.name: (
            path.read_bytes(),
            path.stat().st_ino,
            path.stat().st_mtime_ns,
        )
        for path in runtime.iterdir()
    }

    owner.admit_kimi_executable_v2(
        home,
        runtime,
        fetcher=channel,
        probe_runner=probe,
        now_utc=datetime(2026, 8, 30, 1, tzinfo=timezone.utc),
        dry_run=True,
    )

    assert {
        path.name: (
            path.read_bytes(),
            path.stat().st_ino,
            path.stat().st_mtime_ns,
        )
        for path in runtime.iterdir()
    } == before

def test_max_observed_utc_advances_on_offline_use_and_blocks_rollback(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    admitted = datetime(2026, 8, 30, tzinfo=timezone.utc)
    probe = _probe("0.40.0")
    _admit(
        owner,
        home,
        runtime,
        _channel(owner, "0.40.0", payload),
        probe,
        admitted,
        offline_policy="24h",
    )

    def offline(_url: str):
        raise owner.KimiOfficialChannelUnavailableV2()

    owner.admit_kimi_executable_v2(
        home,
        runtime,
        fetcher=offline,
        probe_runner=probe,
        now_utc=admitted + timedelta(hours=2),
        offline_policy="24h",
        dry_run=False,
    )
    receipt = json.loads(
        (runtime / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V2).read_text("utf-8")
    )
    assert receipt["maxObservedUtc"] == "2026-08-30T02:00:00Z"
    with pytest.raises(ValueError, match="^E_KIMI_CLOCK_ROLLBACK$"):
        owner.admit_kimi_executable_v2(
            home,
            runtime,
            fetcher=offline,
            probe_runner=probe,
            now_utc=admitted + timedelta(hours=1),
            offline_policy="24h",
            dry_run=False,
        )


def test_max_observed_utc_advances_on_repeated_online_use(tmp_path: Path) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    probe = _probe("0.40.0")
    channel = _channel(owner, "0.40.0", payload)
    _admit(
        owner,
        home,
        runtime,
        channel,
        probe,
        datetime(2026, 8, 30, tzinfo=timezone.utc),
    )

    _admit(
        owner,
        home,
        runtime,
        channel,
        probe,
        datetime(2026, 8, 30, 3, tzinfo=timezone.utc),
    )

    receipt = json.loads(
        (runtime / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V2).read_text("utf-8")
    )
    assert receipt["maxObservedUtc"] == "2026-08-30T03:00:00Z"


def test_canonical_v1_is_reclaimed_only_after_v2_durable_readback(tmp_path: Path) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, executable = _paths(tmp_path, payload)
    _private_runtime(owner, runtime)
    v1 = runtime / "executable-binding-v1.json"
    v1.write_bytes(
        json.dumps(
            {
                "path": str(executable),
                "schema": "orchestrarium.kimi-executable-binding.v1",
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )

    _admit(
        owner,
        home,
        runtime,
        _channel(owner, "0.40.0", payload),
        _probe("0.40.0"),
        datetime(2026, 8, 30, tzinfo=timezone.utc),
    )

    assert (runtime / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V2).is_file()
    assert not os.path.lexists(v1)


def test_old_canonical_v1_migrates_after_new_installed_object_gets_live_admission(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    new_payload = b"new-official-current"
    old_payload = b"old-previously-enrolled"
    home, runtime, executable = _paths(tmp_path, new_payload)
    _private_runtime(owner, runtime)
    v1 = runtime / "executable-binding-v1.json"
    v1.write_bytes(
        json.dumps(
            {
                "path": str(executable),
                "schema": "orchestrarium.kimi-executable-binding.v1",
                "sha256": hashlib.sha256(old_payload).hexdigest(),
                "size": len(old_payload),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )

    binding = _admit(
        owner,
        home,
        runtime,
        _channel(owner, "0.41.0", new_payload),
        _probe("0.41.0"),
        datetime(2026, 8, 30, tzinfo=timezone.utc),
    )

    assert binding.sha256 == hashlib.sha256(new_payload).hexdigest()
    assert not os.path.lexists(v1)
    receipt = json.loads(
        (runtime / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V2).read_text("utf-8")
    )
    assert receipt["sha256"] == binding.sha256


def test_v1_is_preserved_when_v2_durable_publication_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, executable = _paths(tmp_path, payload)
    _private_runtime(owner, runtime)
    v1 = runtime / "executable-binding-v1.json"
    v1_payload = json.dumps(
        {
            "path": str(executable),
            "schema": "orchestrarium.kimi-executable-binding.v1",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8") + b"\n"
    v1.write_bytes(v1_payload)
    monkeypatch.setattr(
        owner,
        "_write_kimi_v2_receipt",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ValueError("E_KIMI_V2_RECEIPT_WRITE_FAILED")
        ),
    )

    with pytest.raises(ValueError, match="^E_KIMI_V2_RECEIPT_WRITE_FAILED$"):
        _admit(
            owner,
            home,
            runtime,
            _channel(owner, "0.40.0", payload),
            _probe("0.40.0"),
            datetime(2026, 8, 30, tzinfo=timezone.utc),
        )

    assert v1.read_bytes() == v1_payload
    assert not (runtime / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V2).exists()


def test_customized_v1_fails_before_persistent_mutation(tmp_path: Path) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, executable = _paths(tmp_path, payload)
    _private_runtime(owner, runtime)
    v1 = runtime / "executable-binding-v1.json"
    v1.write_text(
        json.dumps(
            {
                "schema": "orchestrarium.kimi-executable-binding.v1",
                "path": str(executable),
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "custom": True,
            }
        ),
        encoding="utf-8",
    )
    before = {path.name: path.read_bytes() for path in runtime.iterdir()}

    with pytest.raises(ValueError, match="^E_KIMI_V1_STATE_CUSTOMIZED$"):
        _admit(
            owner,
            home,
            runtime,
            _channel(owner, "0.40.0", payload),
            _probe("0.40.0"),
            datetime(2026, 8, 30, tzinfo=timezone.utc),
        )

    after = {
        path.name: path.read_bytes()
        for path in runtime.iterdir()
        if path.name != owner.KIMI_EXECUTABLE_ADMISSION_LOCK_FILENAME_V2
    }
    assert after == before
    assert (
        runtime / owner.KIMI_EXECUTABLE_ADMISSION_LOCK_FILENAME_V2
    ).read_bytes() == owner.KIMI_ADMISSION_LOCK_MARKER_V2


@pytest.mark.skipif(os.name != "nt", reason="Windows private-state DACL contract")
def test_existing_unprotected_kimi_state_root_fails_closed(tmp_path: Path) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    runtime.mkdir(parents=True)

    with pytest.raises(ValueError, match="^E_KIMI_PRIVATE_STATE_INVALID$"):
        _admit(
            owner,
            home,
            runtime,
            _channel(owner, "0.40.0", payload),
            _probe("0.40.0"),
            datetime(2026, 8, 30, tzinfo=timezone.utc),
        )


@pytest.mark.skipif(os.name != "nt", reason="Windows private-state DACL contract")
def test_kimi_root_and_v2_receipt_use_shared_private_object_owner(tmp_path: Path) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    _admit(
        owner,
        home,
        runtime,
        _channel(owner, "0.40.0", payload),
        _probe("0.40.0"),
        datetime(2026, 8, 30, tzinfo=timezone.utc),
    )

    owner.WindowsPrivateObjectOwnerV1.verify_existing(runtime, directory=True)
    owner.WindowsPrivateObjectOwnerV1.verify_existing(
        runtime / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V2,
        directory=False,
    )


@pytest.mark.parametrize(
    "failure_event",
    (
        "after-switch",
        "after-target-protect",
        "after-target-readback",
    ),
)
def test_post_switch_failure_restores_exact_prior_without_transaction_residue(
    tmp_path: Path, failure_event: str
) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    probe = _probe("0.40.0")
    first = _channel(owner, "0.40.0", payload)
    _admit(owner, home, runtime, first, probe, datetime(2026, 8, 30, tzinfo=timezone.utc))
    receipt = runtime / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V2
    prior = receipt.read_bytes()

    def fail(event: str) -> None:
        if event == failure_event:
            raise OSError("injected post-switch failure")

    with pytest.raises(ValueError, match="^E_KIMI_V2_RECEIPT_WRITE_FAILED$"):
        owner.admit_kimi_executable_v2(
            home,
            runtime,
            fetcher=first,
            probe_runner=probe,
            now_utc=datetime(2026, 8, 30, 1, tzinfo=timezone.utc),
            dry_run=False,
            _transaction_hook=fail,
        )

    assert receipt.read_bytes() == prior
    assert not tuple(runtime.glob(".kimi-v2-receipt.*"))


def test_rollback_failure_is_indeterminate_and_all_readers_deny(tmp_path: Path) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    channel = _channel(owner, "0.40.0", payload)
    probe = _probe("0.40.0")
    _admit(owner, home, runtime, channel, probe, datetime(2026, 8, 30, tzinfo=timezone.utc))

    def fail(event: str) -> None:
        if event in {"after-switch", "rollback-start"}:
            raise OSError("injected rollback failure")

    with pytest.raises(ValueError, match="^E_KIMI_V2_RECEIPT_STATE_INDETERMINATE$"):
        owner.admit_kimi_executable_v2(
            home,
            runtime,
            fetcher=channel,
            probe_runner=probe,
            now_utc=datetime(2026, 8, 30, 1, tzinfo=timezone.utc),
            dry_run=False,
            _transaction_hook=fail,
        )
    with pytest.raises(ValueError, match="^E_KIMI_V2_RECEIPT_STATE_INDETERMINATE$"):
        owner.verify_kimi_executable_v2(home, runtime, probe_runner=probe)


@pytest.mark.parametrize("phase", ("prepared", "switched-predecision"))
def test_interrupted_transaction_recovery_is_rollback_only(
    tmp_path: Path, phase: str
) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    channel = _channel(owner, "0.40.0", payload)
    probe = _probe("0.40.0")
    _admit(owner, home, runtime, channel, probe, datetime(2026, 8, 30, tzinfo=timezone.utc))
    target = runtime / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V2
    prior = target.read_bytes()
    candidate = prior.replace(b'"maxObservedUtc":"2026-08-30T00:00:00Z"', b'"maxObservedUtc":"2026-08-30T09:00:00Z"')
    txn = owner.KimiReceiptTransactionV2(runtime)
    txn._write_private(txn.candidate, candidate)
    txn._write_private(txn.rollback, prior)
    txn._write_private(
        txn.record, txn._record_payload("PREPARED_ROLLBACK", prior, candidate)
    )
    if phase == "switched-predecision":
        os.replace(txn.candidate, target)

    txn.recover_if_needed()

    assert target.read_bytes() == prior
    assert not tuple(runtime.glob(".kimi-v2-receipt.*"))


@pytest.mark.parametrize("failure_event", ("after-op-8", "after-op-9"))
def test_failure_after_commit_decision_forward_settles_candidate(
    tmp_path: Path, failure_event: str
) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    channel = _channel(owner, "0.40.0", payload)
    probe = _probe("0.40.0")
    _admit(owner, home, runtime, channel, probe, datetime(2026, 8, 30, tzinfo=timezone.utc))

    def fail(event: str) -> None:
        if event == failure_event:
            raise OSError("crash after commit decision")

    binding = owner.admit_kimi_executable_v2(
        home,
        runtime,
        fetcher=channel,
        probe_runner=probe,
        now_utc=datetime(2026, 8, 30, 1, tzinfo=timezone.utc),
        dry_run=False,
        _transaction_hook=fail,
    )

    assert binding.sha256 == hashlib.sha256(payload).hexdigest()
    assert not tuple(runtime.glob(".kimi-v2-receipt.*"))


def test_failed_offline_high_water_advance_preserves_prior_bytes(tmp_path: Path) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    probe = _probe("0.40.0")
    _admit(
        owner,
        home,
        runtime,
        _channel(owner, "0.40.0", payload),
        probe,
        datetime(2026, 8, 30, tzinfo=timezone.utc),
        offline_policy="24h",
    )
    receipt = runtime / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V2
    prior = receipt.read_bytes()

    def offline(_url: str):
        raise owner.KimiOfficialChannelUnavailableV2()

    with pytest.raises(ValueError, match="^E_KIMI_V2_RECEIPT_WRITE_FAILED$"):
        owner.admit_kimi_executable_v2(
            home,
            runtime,
            fetcher=offline,
            probe_runner=probe,
            now_utc=datetime(2026, 8, 30, 1, tzinfo=timezone.utc),
            offline_policy="24h",
            dry_run=False,
            _transaction_hook=lambda event: (
                (_ for _ in ()).throw(OSError("fail"))
                if event == "after-switch"
                else None
            ),
        )
    assert receipt.read_bytes() == prior


@pytest.mark.skipif(os.name != "nt", reason="Windows legacy ACL migration corridor")
@pytest.mark.parametrize("with_runs", (False, True))
def test_live_legacy_inherited_acl_migrates_with_optional_empty_runs(
    tmp_path: Path, with_runs: bool
) -> None:
    owner = _load_owner()
    new_payload = b"new-current"
    old_payload = b"old-release"
    home, runtime, executable = _paths(tmp_path, new_payload)
    runtime.mkdir(parents=True)
    v1 = runtime / "executable-binding-v1.json"
    v1.write_bytes(
        json.dumps(
            {
                "path": str(executable),
                "schema": "orchestrarium.kimi-executable-binding.v1",
                "sha256": hashlib.sha256(old_payload).hexdigest(),
                "size": len(old_payload),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode() + b"\n"
    )
    if with_runs:
        (runtime / "runs").mkdir()

    _admit(
        owner,
        home,
        runtime,
        _channel(owner, "0.41.0", new_payload),
        _probe("0.41.0"),
        datetime(2026, 8, 30, tzinfo=timezone.utc),
    )

    assert not os.path.lexists(v1)
    owner.WindowsPrivateObjectOwnerV1.verify_existing(runtime, directory=True)
    if with_runs:
        owner.WindowsPrivateObjectOwnerV1.verify_existing(
            runtime / "runs", directory=True
        )
        _admit(
            owner,
            home,
            runtime,
            _channel(owner, "0.41.0", new_payload),
            _probe("0.41.0"),
            datetime(2026, 8, 30, 1, tzinfo=timezone.utc),
        )


@pytest.mark.skipif(os.name != "nt", reason="Windows legacy ACL migration corridor")
def test_nonempty_legacy_runs_is_busy_without_mutation(tmp_path: Path) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, executable = _paths(tmp_path, payload)
    runtime.mkdir(parents=True)
    v1 = runtime / "executable-binding-v1.json"
    v1.write_bytes(json.dumps({"path": str(executable), "schema": "orchestrarium.kimi-executable-binding.v1", "sha256": hashlib.sha256(b"old").hexdigest(), "size": 3}, sort_keys=True, separators=(",", ":")).encode() + b"\n")
    runs = runtime / "runs"
    runs.mkdir()
    (runs / "evidence.txt").write_text("keep", encoding="utf-8")
    before = {str(p.relative_to(runtime)): p.read_bytes() for p in runtime.rglob("*") if p.is_file()}

    with pytest.raises(ValueError, match="^E_KIMI_V1_MIGRATION_BUSY$"):
        _admit(owner, home, runtime, _channel(owner, "0.40.0", payload), _probe("0.40.0"), datetime(2026, 8, 30, tzinfo=timezone.utc))
    after = {
        str(p.relative_to(runtime)): p.read_bytes()
        for p in runtime.rglob("*")
        if p.is_file()
        and p.name != owner.KIMI_EXECUTABLE_ADMISSION_LOCK_FILENAME_V2
    }
    assert after == before
    assert not (runtime / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V2).exists()


def test_v1_reclaim_failure_is_pending_verify_works_and_retry_reclaims(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, executable = _paths(tmp_path, payload)
    _private_runtime(owner, runtime)
    v1 = runtime / "executable-binding-v1.json"
    v1.write_bytes(json.dumps({"path": str(executable), "schema": "orchestrarium.kimi-executable-binding.v1", "sha256": hashlib.sha256(b"old").hexdigest(), "size": 3}, sort_keys=True, separators=(",", ":")).encode() + b"\n")
    channel = _channel(owner, "0.40.0", payload)
    probe = _probe("0.40.0")

    with pytest.raises(ValueError, match="^E_KIMI_V2_RECLAIM_PENDING$"):
        owner.admit_kimi_executable_v2(home, runtime, fetcher=channel, probe_runner=probe, now_utc=datetime(2026, 8, 30, tzinfo=timezone.utc), dry_run=False, _reclaim_hook=lambda: (_ for _ in ()).throw(OSError("fail")))
    owner.verify_kimi_executable_v2(home, runtime, probe_runner=probe)
    assert v1.exists()
    _admit(owner, home, runtime, channel, probe, datetime(2026, 8, 30, 1, tzinfo=timezone.utc))
    assert not v1.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows legacy hardening retry")
@pytest.mark.parametrize(
    "failure_event",
    ("after-root-hardening", "after-v1-hardening", "after-runs-hardening"),
)
def test_legacy_hardening_step_failure_preserves_v1_and_retry_is_idempotent(
    tmp_path: Path, failure_event: str
) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, executable = _paths(tmp_path, payload)
    runtime.mkdir(parents=True)
    v1 = runtime / "executable-binding-v1.json"
    v1_payload = json.dumps({"path": str(executable), "schema": "orchestrarium.kimi-executable-binding.v1", "sha256": hashlib.sha256(b"old").hexdigest(), "size": 3}, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    v1.write_bytes(v1_payload)
    (runtime / "runs").mkdir()

    with pytest.raises(ValueError, match="^E_KIMI_PRIVATE_STATE_INVALID$"):
        owner.admit_kimi_executable_v2(home, runtime, fetcher=_channel(owner, "0.40.0", payload), probe_runner=_probe("0.40.0"), now_utc=datetime(2026, 8, 30, tzinfo=timezone.utc), dry_run=False, _hardening_hook=lambda event: (_ for _ in ()).throw(OSError("fail")) if event == failure_event else None)
    assert v1.read_bytes() == v1_payload
    assert not (runtime / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V2).exists()

    _admit(owner, home, runtime, _channel(owner, "0.40.0", payload), _probe("0.40.0"), datetime(2026, 8, 30, 1, tzinfo=timezone.utc))
    assert not v1.exists()


def test_strict_verify_absent_v2_is_invalid_without_opening_lock_or_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, executable = _paths(tmp_path, payload)
    runtime.mkdir(parents=True)
    v1 = runtime / "executable-binding-v1.json"
    v1.write_bytes(json.dumps({"path": str(executable), "schema": "orchestrarium.kimi-executable-binding.v1", "sha256": hashlib.sha256(b"old").hexdigest(), "size": 3}, sort_keys=True, separators=(",", ":")).encode() + b"\n")
    before = v1.read_bytes()
    monkeypatch.setattr(
        owner.KimiAdmissionLockV2,
        "acquire",
        classmethod(
            lambda _cls, *_args, **_kwargs: pytest.fail("lock open reached")
        ),
    )
    monkeypatch.setattr(
        owner, "_read_kimi_v2_receipt", lambda *_args: pytest.fail("receipt read reached")
    )
    monkeypatch.setattr(
        owner,
        "_observe_kimi_executable_v2",
        lambda *_args: pytest.fail("executable observation reached"),
    )
    monkeypatch.setattr(owner, "_default_kimi_probe_runner_v2", lambda *_args: pytest.fail("probe reached"))

    with pytest.raises(ValueError, match="^E_KIMI_V2_RECEIPT_INVALID$"):
        owner.verify_kimi_executable_v2(home, runtime)
    assert v1.read_bytes() == before
    assert not (runtime / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V2).exists()
    assert not (runtime / owner.KIMI_EXECUTABLE_ADMISSION_LOCK_FILENAME_V2).exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows persistent admission lock")
def test_strict_verify_valid_v2_without_rendezvous_fails_before_receipt_or_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, executable = _paths(tmp_path, payload)
    _admit(
        owner,
        home,
        runtime,
        _channel(owner, "0.40.0", payload),
        _probe("0.40.0"),
        datetime(2026, 8, 30, tzinfo=timezone.utc),
    )
    receipt = runtime / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V2
    receipt_before = receipt.read_bytes()
    executable_before = executable.read_bytes()
    lock = runtime / owner.KIMI_EXECUTABLE_ADMISSION_LOCK_FILENAME_V2
    lock.unlink()
    monkeypatch.setattr(
        owner, "_read_kimi_v2_receipt", lambda *_args: pytest.fail("receipt read reached")
    )
    monkeypatch.setattr(
        owner,
        "_observe_kimi_executable_v2",
        lambda *_args: pytest.fail("executable observation reached"),
    )
    monkeypatch.setattr(owner, "_default_kimi_probe_runner_v2", lambda *_args: pytest.fail("probe reached"))

    with pytest.raises(ValueError, match="^E_KIMI_ADMISSION_LOCK_MISSING$"):
        owner.verify_kimi_executable_v2(home, runtime)

    assert receipt.read_bytes() == receipt_before
    assert executable.read_bytes() == executable_before
    assert not lock.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows persistent admission lock")
def test_strict_verify_lock_disappearance_race_is_lock_missing_without_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    _admit(
        owner,
        home,
        runtime,
        _channel(owner, "0.40.0", payload),
        _probe("0.40.0"),
        datetime(2026, 8, 30, tzinfo=timezone.utc),
    )
    receipt = runtime / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V2
    receipt_before = receipt.read_bytes()
    lock = runtime / owner.KIMI_EXECUTABLE_ADMISSION_LOCK_FILENAME_V2
    original_acquire = owner.KimiAdmissionLockV2.acquire

    def disappear_before_open(_cls, root: Path, *, create: bool):
        assert create is False
        lock.unlink()
        return original_acquire(root, create=False)

    monkeypatch.setattr(
        owner.KimiAdmissionLockV2,
        "acquire",
        classmethod(disappear_before_open),
    )
    monkeypatch.setattr(
        owner, "_read_kimi_v2_receipt", lambda *_args: pytest.fail("receipt read reached")
    )
    monkeypatch.setattr(owner, "_default_kimi_probe_runner_v2", lambda *_args: pytest.fail("probe reached"))

    with pytest.raises(ValueError, match="^E_KIMI_ADMISSION_LOCK_MISSING$"):
        owner.verify_kimi_executable_v2(home, runtime)

    assert receipt.read_bytes() == receipt_before
    assert not lock.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows persistent admission lock")
def test_strict_verify_receipt_disappearance_after_lock_is_invalid_without_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    _admit(
        owner,
        home,
        runtime,
        _channel(owner, "0.40.0", payload),
        _probe("0.40.0"),
        datetime(2026, 8, 30, tzinfo=timezone.utc),
    )
    receipt = runtime / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V2
    lock = runtime / owner.KIMI_EXECUTABLE_ADMISSION_LOCK_FILENAME_V2
    lock_before = lock.read_bytes()
    original_acquire = owner.KimiAdmissionLockV2.acquire

    def remove_receipt_after_open(_cls, root: Path, *, create: bool):
        held = original_acquire(root, create=create)
        assert held is not None
        receipt.unlink()
        return held

    monkeypatch.setattr(
        owner.KimiAdmissionLockV2,
        "acquire",
        classmethod(remove_receipt_after_open),
    )
    monkeypatch.setattr(owner, "_default_kimi_probe_runner_v2", lambda *_args: pytest.fail("probe reached"))

    with pytest.raises(ValueError, match="^E_KIMI_V2_RECEIPT_INVALID$"):
        owner.verify_kimi_executable_v2(home, runtime)

    assert not receipt.exists()
    assert lock.read_bytes() == lock_before


@pytest.mark.skipif(os.name != "nt", reason="Windows persistent admission lock")
def test_strict_verify_holds_rendezvous_through_both_probes(tmp_path: Path) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    base_probe = _probe("0.40.0")
    _admit(
        owner,
        home,
        runtime,
        _channel(owner, "0.40.0", payload),
        base_probe,
        datetime(2026, 8, 30, tzinfo=timezone.utc),
    )

    def probe_while_locked(*args):
        with pytest.raises(ValueError, match="^E_KIMI_ADMISSION_BUSY$"):
            owner.KimiAdmissionLockV2.acquire(runtime, create=False)
        return base_probe(*args)

    owner.verify_kimi_executable_v2(home, runtime, probe_runner=probe_while_locked)
    assert base_probe.calls[-2:] == [("--version",), ("--help",)]


def test_legacy_extra_child_fails_before_admission(tmp_path: Path) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, executable = _paths(tmp_path, payload)
    runtime.mkdir(parents=True)
    (runtime / "executable-binding-v1.json").write_bytes(json.dumps({"path": str(executable), "schema": "orchestrarium.kimi-executable-binding.v1", "sha256": hashlib.sha256(b"old").hexdigest(), "size": 3}, sort_keys=True, separators=(",", ":")).encode() + b"\n")
    (runtime / "extra.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="^E_KIMI_PRIVATE_STATE_INVALID$"):
        _admit(owner, home, runtime, _channel(owner, "0.40.0", payload), _probe("0.40.0"), datetime(2026, 8, 30, tzinfo=timezone.utc))
    assert not (runtime / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V2).exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows persistent admission lock")
def test_admission_lock_contention_is_busy_before_network_or_mutation(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    _private_runtime(owner, runtime)
    held = owner.KimiAdmissionLockV2.acquire(runtime, create=True)
    try:
        with pytest.raises(ValueError, match="^E_KIMI_ADMISSION_BUSY$"):
            owner.admit_kimi_executable_v2(
                home,
                runtime,
                fetcher=lambda *_args: pytest.fail("network reached"),
                probe_runner=lambda *_args: pytest.fail("probe reached"),
                dry_run=False,
            )
    finally:
        held.close()
    assert tuple(runtime.iterdir()) == (held.path,)


@pytest.mark.skipif(os.name != "nt", reason="Windows persistent admission lock")
def test_verify_active_lock_is_read_only_busy(tmp_path: Path) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    _admit(
        owner,
        home,
        runtime,
        _channel(owner, "0.40.0", payload),
        _probe("0.40.0"),
        datetime(2026, 8, 30, tzinfo=timezone.utc),
    )
    held = owner.KimiAdmissionLockV2.acquire(runtime, create=False)
    assert held is not None
    try:
        with pytest.raises(ValueError, match="^E_KIMI_ADMISSION_BUSY$"):
            owner.verify_kimi_executable_v2(
                home,
                runtime,
                probe_runner=lambda *_args: pytest.fail("probe reached"),
            )
    finally:
        held.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows persistent admission lock")
def test_persistent_lock_survives_success_and_reacquires_as_stale(tmp_path: Path) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    channel = _channel(owner, "0.40.0", payload)
    probe = _probe("0.40.0")

    _admit(owner, home, runtime, channel, probe, datetime(2026, 8, 30, tzinfo=timezone.utc))
    lock = runtime / owner.KIMI_EXECUTABLE_ADMISSION_LOCK_FILENAME_V2
    assert lock.read_bytes() == owner.KIMI_ADMISSION_LOCK_MARKER_V2
    before = lock.stat()
    _admit(owner, home, runtime, channel, probe, datetime(2026, 8, 30, 1, tzinfo=timezone.utc))
    after = lock.stat()
    assert lock.read_bytes() == owner.KIMI_ADMISSION_LOCK_MARKER_V2
    assert (after.st_ino, after.st_size) == (before.st_ino, before.st_size)


@pytest.mark.skipif(os.name != "nt", reason="Windows persistent admission lock")
def test_active_persistent_lock_blocks_second_writer_and_verify(tmp_path: Path) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    _admit(
        owner,
        home,
        runtime,
        _channel(owner, "0.40.0", payload),
        _probe("0.40.0"),
        datetime(2026, 8, 30, tzinfo=timezone.utc),
    )
    held = owner.KimiAdmissionLockV2.acquire(runtime, create=False)
    assert held is not None
    try:
        with pytest.raises(ValueError, match="^E_KIMI_ADMISSION_BUSY$"):
            owner.admit_kimi_executable_v2(
                home,
                runtime,
                fetcher=lambda *_args: pytest.fail("network reached"),
                probe_runner=lambda *_args: pytest.fail("probe reached"),
                dry_run=False,
            )
        with pytest.raises(ValueError, match="^E_KIMI_ADMISSION_BUSY$"):
            owner.verify_kimi_executable_v2(home, runtime)
    finally:
        held.close()
    assert (runtime / owner.KIMI_EXECUTABLE_ADMISSION_LOCK_FILENAME_V2).exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows persistent admission lock")
def test_malformed_stale_lock_is_private_state_invalid(tmp_path: Path) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    _private_runtime(owner, runtime)
    lock = runtime / owner.KIMI_EXECUTABLE_ADMISSION_LOCK_FILENAME_V2
    lock.write_bytes(b"malformed\n")
    owner.WindowsPrivateObjectOwnerV1.protect_and_verify(lock, directory=False)

    with pytest.raises(ValueError, match="^E_KIMI_PRIVATE_STATE_INVALID$"):
        owner.admit_kimi_executable_v2(
            home,
            runtime,
            fetcher=lambda *_args: pytest.fail("network reached"),
            probe_runner=lambda *_args: pytest.fail("probe reached"),
            dry_run=False,
        )


@pytest.mark.skipif(os.name != "nt", reason="Windows persistent admission lock")
def test_persistent_lock_reacquires_same_object_after_child_hard_kill(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    payload = b"current"
    home, runtime, _ = _paths(tmp_path, payload)
    owner._ensure_kimi_private_root_v2(runtime, create=True)
    child_code = (
        "from pathlib import Path; import sys,time; "
        "from scripts.provider_prompt import KimiAdmissionLockV2; "
        "lock=KimiAdmissionLockV2.acquire(Path(sys.argv[1]),create=True); "
        "print('READY',flush=True); time.sleep(300)"
    )
    child = subprocess.Popen(
        [sys.executable, "-c", child_code, str(runtime)],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        assert child.stdout is not None
        assert child.stdout.readline().strip() == "READY"
        lock_path = runtime / owner.KIMI_EXECUTABLE_ADMISSION_LOCK_FILENAME_V2
        before = lock_path.stat()
        expected_marker = owner.KIMI_ADMISSION_LOCK_MARKER_V2
        with pytest.raises(ValueError, match="^E_KIMI_ADMISSION_BUSY$"):
            owner.KimiAdmissionLockV2.acquire(runtime, create=True)

        child.kill()
        assert child.wait(timeout=10) != 0
        after_kill = lock_path.stat()
        assert lock_path.read_bytes() == expected_marker
        assert (after_kill.st_dev, after_kill.st_ino) == (before.st_dev, before.st_ino)

        reacquired = owner.KimiAdmissionLockV2.acquire(runtime, create=True)
        try:
            assert reacquired.identity
            owner.KimiReceiptTransactionV2(runtime).recover_if_needed()
        finally:
            reacquired.close()
        post_recovery = lock_path.stat()
        with pytest.raises(ValueError, match="^E_KIMI_V2_RECEIPT_INVALID$"):
            owner.verify_kimi_executable_v2(home, runtime)
        assert lock_path.read_bytes() == expected_marker
        assert (post_recovery.st_dev, post_recovery.st_ino) == (
            before.st_dev,
            before.st_ino,
        )
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
        if child.stdout is not None:
            child.stdout.close()
        if child.stderr is not None:
            child.stderr.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows receipt phase crash recovery")
@pytest.mark.parametrize(
    ("next_phase", "expected"),
    (("COMMIT_DECIDED", b"prior\n"), ("SETTLED_COMMITTED", b"candidate\n")),
)
def test_phase_update_temp_child_crash_recovers_from_durable_old_phase(
    tmp_path: Path, next_phase: str, expected: bytes
) -> None:
    owner = _load_owner()
    runtime = tmp_path / "runtime"
    owner._ensure_kimi_private_root_v2(runtime, create=True)
    txn = owner.KimiReceiptTransactionV2(runtime)
    txn._write_private(txn.target, b"prior\n")
    child_code = (
        "from pathlib import Path; import os,sys; "
        "from scripts.provider_prompt import KimiReceiptTransactionV2; "
        "phase=sys.argv[2]; "
        "hook=lambda event: os._exit(91) if event == 'after-phase-update-temp-'+phase else None; "
        "KimiReceiptTransactionV2(Path(sys.argv[1]),hook).commit(b'candidate\\n')"
    )
    child = subprocess.Popen(
        [sys.executable, "-c", child_code, str(runtime), next_phase],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert child.wait(timeout=15) == 91
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
        if child.stdout is not None:
            child.stdout.close()
        if child.stderr is not None:
            child.stderr.close()

    update = runtime / owner.KIMI_V2_UPDATE_FILENAME
    assert update.is_file()
    owner.KimiReceiptTransactionV2(runtime).recover_if_needed()
    assert txn.target.read_bytes() == expected
    assert not any(
        os.path.lexists(runtime / name)
        for name in (
            owner.KIMI_V2_TRANSACTION_FILENAME,
            owner.KIMI_V2_CANDIDATE_FILENAME,
            owner.KIMI_V2_ROLLBACK_FILENAME,
            owner.KIMI_V2_UPDATE_FILENAME,
        )
    )
