"""Opt-in Windows composition fixture; not a production scanner entry point."""

import argparse
import asyncio
import ctypes
from ctypes import wintypes
import importlib.util
import os
from pathlib import Path
import sys
import uuid


def load_scanner(root):
    script = root / "scripts/universal-hooks/scripts/check-publication-safety.py"
    sys.path.insert(0, str(script.parent))
    spec = importlib.util.spec_from_file_location("_orche_owned_stage_fixture", script)
    scanner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = scanner
    spec.loader.exec_module(scanner)
    return scanner


async def drain_fixture_pipe(reader):
    # This bound is for a tiny, known test protocol, not for scanned inputs.
    try:
        await reader.readexactly(4096)
    except asyncio.IncompleteReadError as eof:
        return eof.partial
    raise AssertionError("fixture output exceeded its expected size")


async def observed_child(scanner, work, argv, env):
    process, owner, observation = await scanner._create_owned_async_process(
        argv, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, cwd=str(work), env=env,
    )
    try:
        async with asyncio.timeout(90):
            return await asyncio.gather(
                drain_fixture_pipe(process.stdout), drain_fixture_pipe(process.stderr),
                scanner._wait_owned_async_direct(process, observation, 90.0),
            )
    finally:
        settled = await scanner._settle_owned_async_process(process, owner, observation)
        assert settled, "worker not settled"


def exercise(scanner, fixture_root, binary):
    from scripts.provider_prompt import (
        _CaptureNamespaceBinding,
        WindowsPrivateObjectOwnerV1,
    )

    folder = fixture_root / ("fixture-custody-" + uuid.uuid4().hex)
    assert not folder.exists()
    stage = folder / "stage"
    namespace = _CaptureNamespaceBinding()
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = (ctypes.c_void_p,)
    kernel.LocalFree.restype = ctypes.c_void_p
    child = descriptor = None
    try:
        namespace.acquire(folder)
        namespace.validate()
        descriptor, expected = WindowsPrivateObjectOwnerV1.current_user_security_descriptor()
        child = WindowsPrivateObjectOwnerV1.open_relative(
            namespace.root_resource, stage.name, directory=True, create=True,
            security_descriptor=descriptor, read_control=True, collision_path=stage,
        )
        WindowsPrivateObjectOwnerV1.verify_handle_dacl(child, expected)
        allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT"}
        env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
        env["ORCHE_NATIVE_GIT_FIXTURES"] = str(stage)
        name = "mapped_normalized_stage_exclusively_owns_its_lines_and_cleanup"
        out, err, status = asyncio.run(observed_child(
            scanner, fixture_root, (str(binary), "--ignored", "--exact", name), env,
        ))
        assert status == 0 and not err and (name + " ... ok").encode() in out
        assert not tuple(stage.iterdir())

        # A pipe payload alone is not a successful operation.
        payload = 'print("fixture-provisional", flush=True); raise SystemExit(17)'
        out, err, status = asyncio.run(observed_child(
            scanner, fixture_root, (sys.executable, "-I", "-B", "-c", payload), env,
        ))
        assert status == 17 and b"fixture-provisional" in out and not err
        assert not tuple(stage.iterdir())
        namespace.validate()
    finally:
        try:
            if child is not None and not kernel.CloseHandle(child):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            try:
                if descriptor is not None and kernel.LocalFree(descriptor):
                    raise ctypes.WinError(ctypes.get_last_error())
            finally:
                assert not namespace.close()
    print("PASS: mapped Rust stage in an owned Windows scanner job; nonzero worker settled separately.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path,
                        help="Locally built publication_line_index test executable")
    parser.add_argument("--fixture-root", required=True, type=Path,
                        help="Existing disposable directory on local Windows storage")
    args = parser.parse_args()
    if not __debug__:
        parser.error("fixture assertions must be enabled")
    if os.name != "nt":
        parser.error("this fixture checks the Windows process and storage owners")
    if not args.binary.is_absolute() or not args.fixture_root.is_absolute():
        parser.error("both fixture paths must be absolute")
    if not args.binary.is_file() or args.binary.suffix.lower() != ".exe":
        parser.error("expected a Windows test executable")
    if not args.fixture_root.is_dir():
        parser.error("fixture root does not exist")
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root))
    exercise(load_scanner(root), args.fixture_root, args.binary)


if __name__ == "__main__":
    main()
