"""Unicode Windows hook paths, with real shells but never a provider process."""
from pathlib import Path
import base64
import json
import os
import subprocess
import sys
import pytest
from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = load_module(ROOT / "scripts/install-hypothesis-hook.py", "unicode_hook_installer")
HEALTH = load_module(ROOT / "scripts/check-hook-health.py", "unicode_hook_health")
LABELS = ("O\u2019Brien \u4e2d\u6587", "中文 目录", "日本語 パス", "한국어 경로", "العربية مسار",
          "हिन्दी पथ", "путь с пробелами", "Cafe\u0301 dossier", "项目 🧪", "O'Brien [资料] (x);,@={}")

@pytest.mark.parametrize("label", LABELS)
def test_unicode_tokens_preserve_exact_operand_boundaries(label):
    target = INSTALLER.HookTarget(
        f"D:/runtime {label}/python.exe", (f"E:/project {label}/check.py",))
    handler = INSTALLER.build_codex_entry(target, "windows")["hooks"][0]
    assert HEALTH._command_argv(handler, "codex", "windows") == [
        target.executable, *target.args]

def test_legacy_simple_command_bytes_remain_unchanged():
    target = INSTALLER.HookTarget("D:/runtime/python.exe", ("E:/project/check.py",))
    assert INSTALLER.build_codex_entry(target, "windows")["hooks"][0]["command"] == (
        "D:/runtime/python.exe E:/project/check.py")

@pytest.mark.parametrize("component", (
    "name$variable", "name%VARIABLE%", "name!VARIABLE!", "name"+chr(96)+"expression",
    "name&command", "name|command", "name>output", "name<input", 'name"quote',
    "name^escape", "name\nnewline", "name\rcarriage", "name\ttab", "name\x00nul",
))
def test_shell_expansion_and_control_tokens_refuse_before_execution(component):
    target = INSTALLER.HookTarget(
        "D:/runtime/python.exe", (f"E:/project/{component}/check.py",))
    with pytest.raises(ValueError, match="unsupported Windows"):
        INSTALLER.build_codex_entry(target, "windows")

@pytest.mark.skipif(os.name != "nt", reason="real Windows shell invocation")
@pytest.mark.parametrize("label", LABELS)
@pytest.mark.parametrize("shell_kind", ("cmd", "powershell", "pwsh"))
def test_native_shell_preserves_unicode_script_and_stdin(tmp_path, label, shell_kind):
    system = Path(os.environ["SYSTEMROOT"])
    shells = {
        "cmd": system / "System32/cmd.exe",
        "powershell": system / "System32/WindowsPowerShell/v1.0/powershell.exe",
        "pwsh": Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "PowerShell/7/pwsh.exe",
    }
    shell = shells[shell_kind]
    if not shell.is_file():
        pytest.skip(f"{shell_kind} is not installed")
    script = tmp_path / label / "capture.py"
    script.parent.mkdir()
    script.write_text(
        "import base64,json,sys\n"
        "print(json.dumps({'argv':sys.argv,'stdin':base64.b64encode(sys.stdin.buffer.read()).decode()}))\n",
        encoding="utf8",
    )
    target = INSTALLER.resolve_hook_target(
        str(script), "windows", "codex", python_executable=sys.executable)
    command = INSTALLER.build_codex_entry(target, "windows")["hooks"][0]["command"]
    env = {k:v for k,v in os.environ.items() if k.upper() in
           ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT")}
    env.update(HOME=str(tmp_path), USERPROFILE=str(tmp_path), TEMP=str(tmp_path),
               TMP=str(tmp_path), PATH=str(tmp_path / "absent"),
               PYTHONDONTWRITEBYTECODE="1")
    if shell_kind == "cmd":
        # Exact shell framing in pinned Codex command_runner.rs, not Codex execution.
        argv = subprocess.list2cmdline([str(shell), "/C"]) + ' "' + command + '"'
    else:
        argv = [str(shell), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command]
    payload = json.dumps({"synthetic": label}, ensure_ascii=False).encode("utf8") + b"\n"
    result = subprocess.run(argv, executable=str(shell), cwd=tmp_path, env=env,
                            input=payload, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=20)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert len(observed["argv"]) == 1
    assert Path(observed["argv"][0]).resolve() == script.resolve()
    assert observed["argv"][0].replace("\\", "/") == script.as_posix()
    assert observed["stdin"] == base64.b64encode(payload).decode()


@pytest.mark.parametrize("command", (
    'D:/"runtime space/python.exe" E:/check.py & echo foreign',
    'D:/"runtime space/python.exe" E:/check.py;other',
    'D:/"runtime $variable/python.exe" E:/check.py',
    'D:/"runtime space/python.exe"suffix E:/check.py',
    'D:/"unterminated/python.exe E:/check.py',
))
def test_noncanonical_mixed_quotes_cannot_claim_an_operand(command):
    with pytest.raises(ValueError):
        HEALTH._command_argv({"command": command}, "codex", "windows")

def test_unc_unicode_round_trip_is_lexical_not_network_qualification():
    target = INSTALLER.HookTarget(
        "//server/共享 目录/python.exe", ("//server/项目 空间/check.py",))
    handler = INSTALLER.build_codex_entry(target, "windows")["hooks"][0]
    assert HEALTH._command_argv(handler, "codex", "windows") == [
        target.executable, *target.args]


def test_unquoted_spaced_paths_are_not_guessed_into_owned_operands():
    handler = {"command": "D:/runtime space/python.exe E:/project space/check.py"}
    argv = HEALTH._command_argv(handler, "codex", "windows")
    assert argv != ["D:/runtime space/python.exe", "E:/project space/check.py"]
    assert HEALTH._invoked_script(argv) == (None, False)


@pytest.mark.parametrize("quote", (chr(0x201C), chr(0x201D), chr(0x201E)))
def test_powershell_smart_double_quotes_are_control_tokens(quote):
    target = INSTALLER.HookTarget("D:/runtime/python.exe", (f"E:/project/name{quote}literal/check.py",))
    with pytest.raises(ValueError, match="unsupported Windows"):
        INSTALLER.build_codex_entry(target, "windows")
    with pytest.raises(ValueError, match="unsupported Windows"):
        HEALTH._command_argv(
            {"command": f'D:/"runtime/name{quote}literal/python.exe" E:/check.py'},
            "codex", "windows")
