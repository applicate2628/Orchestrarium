"""Opt-in complete bundle/root-owner/native-load/shell receiving; never a model."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ("ORCHE_COPILOT_BUNDLE", "ORCHE_COPILOT_NATIVE", "ORCHE_NODE")

@pytest.mark.skipif(os.name != "nt" or not all(os.environ.get(k) for k in REQUIRED),
                    reason="Explicit built Windows bundle, native parser and Node required")
def test_actual_bundled_root_registration_discovery_execution_and_relocation(tmp_path):
    source = Path(os.environ["ORCHE_COPILOT_BUNDLE"]).resolve(strict=True)
    native = Path(os.environ["ORCHE_COPILOT_NATIVE"]).resolve(strict=True)
    node = Path(os.environ["ORCHE_NODE"]).resolve(strict=True)
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    project = tmp_path / "original project"
    project.mkdir()
    bundle = project / "runtime bundle"
    shutil.copytree(source, bundle)
    members = ("install.py", "scripts/copilot-pre-tool-use.py",
               "scripts/installation/copilot_registration.py",
               "scripts/installation/copilot_transport.py",
               "scripts/universal-hooks/hooks/check-machine-local-path.py",
               "scripts/universal-hooks/hooks/check-no-trash-in-repo.py",
               "scripts/universal-hooks/scripts/git_push_gate_preflight.py",
               "scripts/universal-hooks/scripts/hook_common.py")
    pins = {}
    for name in members:
        actual = (bundle / "app" / name).read_bytes()
        assert actual == (ROOT / name).read_bytes(), name
        pins[name] = hashlib.sha256(actual).hexdigest()
    home = tmp_path / "home"
    (home / ".copilot/hooks").mkdir(parents=True)
    env = {"HOME":str(home), "USERPROFILE":str(home), "COPILOT_HOME":str(home / ".copilot"),
           "APPDATA":str(home / "appdata"), "LOCALAPPDATA":str(home / "local"),
           "TEMP":str(tmp_path), "TMP":str(tmp_path), "PATH":"",
           # Windows PowerShell classifies native executables using PATHEXT.
           "PATHEXT":".EXE",
           "SystemRoot":os.environ["SystemRoot"]}
    def run(argv, cwd, payload=b""):
        return subprocess.run(list(map(str,argv)), cwd=cwd, env=env, input=payload,
                              capture_output=True, timeout=60,
                              creationflags=subprocess.CREATE_NO_WINDOW)
    sibling = project / ".github/hooks/foreign.json"
    sibling.parent.mkdir(parents=True)
    foreign = b'{"version":1,"hooks":{}}\r\n'
    sibling.write_bytes(foreign)
    config = sibling.with_name("orchestrarium.json")
    command = [bundle / "python/python.exe", "-I", "-B", bundle / "launch.py",
               "--permanent-runtime", "--copilot-registration", "--project", ".",
               "--bundled-advisory-relative", "runtime bundle"]
    preview = run(command, project)
    assert preview.returncode == 0, preview.stderr
    assert not config.exists()
    applied = run([*command, "--apply"], project)
    assert applied.returncode == 0, applied.stderr
    assert json.loads(applied.stdout)["applied"] is True
    unchanged = run([*command, "--apply"], project)
    assert unchanged.returncode == 0, unchanged.stderr
    assert json.loads(unchanged.stdout)["action"] == "unchanged"
    registration = config.read_bytes()
    invalid = tmp_path / "invalid"
    malformed = invalid / ".github/hooks/invalid.json"
    malformed.parent.mkdir(parents=True)
    malformed.write_bytes(b"{")
    results = []
    def receive(directory):
        configuration = directory / ".github/hooks/orchestrarium.json"
        parsed = run([node, ROOT / "tests/fixtures/copilot_native_discovery.cjs",
                      native, directory, home, configuration, invalid], directory)
        assert parsed.returncode == 0, parsed.stderr
        report = json.loads(parsed.stdout)
        # Execute the exact command emitted by the real native parser, not a
        # parallel reconstruction. No model/session-manager/tool call occurs.
        spec = json.loads(report["positive"]["snapshot"]["hooks"][0]["specJson"])
        selected_command = spec["config"]["powershell"]
        assert spec["config"] == json.loads(registration)["hooks"]["preToolUse"][0]
        synthetic_path = "/".join(("C:", "Users", "alice", "fixture"))
        cases = [
            ({"cwd":str(directory), "toolName":"create_file",
              "toolArgs":{"filePath":"src/a","content":synthetic_path}}, 0, "[machine-local-path AUDIT]"),
            ({"cwd":str(directory), "toolName":"create",
              "toolArgs":'{"path":"src/a","content":"ordinary"}'}, 0, False),
            ({"cwd":str(directory), "toolName":"bash",
              "toolArgs":{"command":"git worktree add must-not-exist"}}, 0, "[stray-artifact AUDIT]"),
            ({}, 2, False),
        ]
        for payload, status, advisory in cases:
            result = run([powershell, "-NoProfile", "-NonInteractive", "-Command", selected_command],
                         directory, json.dumps(payload).encode())
            assert result.returncode == status, result.stderr
            if status == 0:
                output = json.loads(result.stdout)
                if advisory:
                    assert advisory in output["additionalContext"]
                else:
                    assert output == {}
                assert "permissionDecision" not in output
            else:
                assert result.stdout == b""
        assert not (directory / "must-not-exist").exists()
        assert (directory / ".github/hooks/foreign.json").read_bytes() == foreign
        results.append({"hookCount":report["positive"]["snapshot"]["hookCount"],
                        "positive":True,"command_advisory":True,"neutral":True,"malformed_exit":2})
        native_env = dict(env)
        native_env["PATH"] = str(powershell.parent)
        executed = subprocess.run([str(node), str(ROOT / "tests/fixtures/copilot_native_execution.cjs"),
                                   str(native), str(directory), str(home)], cwd=directory,
                                  env=native_env, capture_output=True, timeout=60,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
        assert executed.returncode == 0, executed.stderr
        assert json.loads(executed.stdout) == {"cases":4,"nativeHookExecution":True,
            "modelSessionCreated":False,"toolExecutionRequested":False,"lifecycleCompleted":True}
        return selected_command
    receive(project)
    relocated = tmp_path / "relocated O'Brien [project] 测试"
    project.rename(relocated)
    assert (relocated / ".github/hooks/orchestrarium.json").read_bytes() == registration
    selected_command = receive(relocated)
    executable = relocated / "runtime bundle/python/python.exe"
    retained = executable.with_name("python.exe.held")
    executable.rename(retained)
    try:
        missing = run([powershell,"-NoProfile","-NonInteractive","-Command",selected_command],
                      relocated,b"{}")
        assert missing.returncode != 0
    finally:
        retained.rename(executable)
    # Update via the real portable root entry, never by patching the hook.
    config = relocated / ".github/hooks/orchestrarium.json"
    previous = tmp_path / "selected-previous.json"
    previous.write_bytes(registration)
    replacement = relocated / "updated runtime bundle"
    (relocated / "runtime bundle").rename(replacement)
    root_command = [replacement / "python/python.exe", "-I", "-B", replacement / "launch.py",
                    "--permanent-runtime", "--copilot-registration", "--project", "."]
    update = [*root_command, "--bundled-advisory-relative", "updated runtime bundle"]
    refused = run([*update, "--apply"], relocated)
    assert refused.returncode == 2
    assert config.read_bytes() == registration
    assert not (relocated / "trash").exists()
    preview = run([*update, "--previous", previous], relocated)
    assert preview.returncode == 0, preview.stderr
    assert json.loads(preview.stdout)["action"] == "update"
    assert config.read_bytes() == registration
    assert not (relocated / "trash").exists()
    # A user edit after selection must not be overwritten or saved as ours.
    edited = registration + b"\n"
    config.write_bytes(edited)
    stale = run([*update, "--previous", previous, "--apply"], relocated)
    assert stale.returncode == 2
    assert config.read_bytes() == edited
    assert not (relocated / "trash").exists()
    config.write_bytes(registration)  # Fixture restores its own edit only.
    updated = run([*update, "--previous", previous, "--apply"], relocated)
    assert updated.returncode == 0, updated.stderr
    update_report = json.loads(updated.stdout)
    assert update_report["action"] == "update"
    assert Path(update_report["trash"]).read_bytes() == registration
    registration = config.read_bytes()
    receive(relocated)
    previous.write_bytes(registration)
    remove = [*root_command, "--remove", "--previous", previous]
    preview = run(remove, relocated)
    assert preview.returncode == 0 and config.read_bytes() == registration
    removed = run([*remove, "--apply"], relocated)
    assert removed.returncode == 0, removed.stderr
    remove_report = json.loads(removed.stdout)
    assert remove_report["action"] == "remove"
    assert Path(remove_report["trash"]).read_bytes() == registration
    assert not config.exists()
    parsed = run([node, ROOT / "tests/fixtures/copilot_native_discovery.cjs",
                  native, relocated, home, "-", invalid], relocated)
    assert parsed.returncode == 0, parsed.stderr
    assert json.loads(parsed.stdout)["positive"]["snapshot"]["hookCount"] == 0
    absent = run([*root_command, "--remove", "--apply"], relocated)
    assert absent.returncode == 0
    assert json.loads(absent.stdout)["action"] == "unchanged"
    assert (relocated / ".github/hooks/foreign.json").read_bytes() == foreign
    assert (replacement / "python/python.exe").is_file()
    (tmp_path / "receiving-result.json").write_text(json.dumps({
        "source_pins":pins, "registration_sha256":hashlib.sha256(registration).hexdigest(),
        "locations":results, "missing_runtime_exit":missing.returncode,
        "updateAndRemovalQualified":True, "priorBytesPreserved":True,
        "modelSessionCreated":False,"editorActivationQualified":False},indent=2))
