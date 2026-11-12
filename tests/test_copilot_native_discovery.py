"""Opt-in parser acceptance against the user's explicitly selected installed runtime."""
import json
import os
from pathlib import Path
import subprocess
import pytest
from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
REG = load_module(ROOT / "scripts/installation/copilot_registration.py", "native_discovery_registration")

@pytest.mark.skipif(not (os.environ.get("ORCHE_COPILOT_NATIVE") and os.environ.get("ORCHE_NODE")),
                    reason="Explicit native runtime and Node required; no automatic host launch")
def test_installed_runtime_discovers_generated_registration(tmp_path):
    native = Path(os.environ["ORCHE_COPILOT_NATIVE"]).resolve(strict=True)
    node = Path(os.environ["ORCHE_NODE"]).resolve(strict=True)
    project = tmp_path / "project space"
    bundle = project / "runtime bundle"
    # File-existence inputs for generation, never executable fixtures.
    for name in ("python/python.exe", "app/scripts/copilot-pre-tool-use.py",
                 "app/scripts/installation/copilot_transport.py",
                 "app/scripts/universal-hooks/hooks/check-machine-local-path.py",
                 "app/scripts/universal-hooks/hooks/check-no-trash-in-repo.py",
                 "app/scripts/universal-hooks/scripts/git_push_gate_preflight.py",
                 "app/scripts/universal-hooks/scripts/hook_common.py"):
        path = bundle / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"not executable: native discovery must not invoke hooks")
    desired = REG.bundled_advisory(project, Path("runtime bundle"))
    config = project / ".github/hooks/orchestrarium.json"
    config.parent.mkdir(parents=True)
    config.write_bytes(desired)
    invalid = tmp_path / "invalid"
    bad = invalid / ".github/hooks/invalid.json"
    bad.parent.mkdir(parents=True)
    bad.write_bytes(b"{")
    home = tmp_path / "home"
    (home / ".copilot/hooks").mkdir(parents=True)
    env = {"HOME":str(home), "USERPROFILE":str(home), "COPILOT_HOME":str(home / ".copilot"),
           "APPDATA":str(home / "appdata"), "LOCALAPPDATA":str(home / "local"),
           "TEMP":str(tmp_path), "TMP":str(tmp_path), "PATH":""}
    if "SystemRoot" in os.environ:
        env["SystemRoot"] = os.environ["SystemRoot"]
    result = subprocess.run([str(node), str(ROOT / "tests/fixtures/copilot_native_discovery.cjs"),
                             str(native), str(project), str(home), str(config), str(invalid)],
                            cwd=tmp_path, env=env, capture_output=True, timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    report = json.loads(result.stdout)
    assert report["hookExecutionRequested"] is False
    assert config.read_bytes() == desired
