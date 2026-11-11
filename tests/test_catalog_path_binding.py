"""Observed path errors remain diagnostics, not uncaught exceptions."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import pytest

SOURCE = Path(__file__).resolve().parents[1] / "scripts/validate-codex-skill-catalog-budget.py"

@pytest.fixture
def fixture(tmp_path):
    spec = importlib.util.spec_from_file_location("catalog_binding", SOURCE)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    home = tmp_path / "home"
    pack = home / ".codex/skills"
    skill = pack / "alpha/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: alpha\ndescription: public sample\n---\n", encoding="utf-8")
    return m, home, pack

def payload(pack, root=None, relative="alpha/SKILL.md"):
    text = f"<skills_instructions>\n- `r1` = `{pack if root is None else root}`\n- alpha: public sample (file: r1/{relative})\n</skills_instructions>"
    return json.dumps([{"content": [{"type": "input_text", "text": text}]}])

@pytest.mark.parametrize("case", ["complete", "nul-root", "nul-relative", "parent", "missing"])
def test_binding_controls(fixture, case):
    m, _, pack = fixture
    kw = {"nul-root": {"root": str(pack) + "\0"}, "nul-relative": {"relative": "alpha\0/SKILL.md"},
          "parent": {"relative": "../alpha/SKILL.md"}, "missing": {"relative": "missing/SKILL.md"}}.get(case, {})
    r = m.parse_runtime_prompt_input(payload(pack, **kw), pack, pack)
    assert r.status == ("complete" if case == "complete" else "binding-failure")
    if case != "complete":
        assert r.diagnostic == "CATALOG-RUNTIME-BINDING"

@pytest.mark.parametrize("operation", ["resolve", "is_file", "is_dir"])
def test_filesystem_error_is_binding_diagnostic(fixture, monkeypatch, operation):
    m, _, pack = fixture
    original = getattr(Path, operation)
    def fail(path, *args, **kwargs):
        if operation != "resolve" or path.name == "foreign-root":
            raise PermissionError("injected filesystem refusal")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(m, "_pack_identities", lambda _: {"alpha": "alpha"})
    monkeypatch.setattr(Path, operation, fail)
    root = pack.parent / "foreign-root" if operation == "resolve" else pack
    r = m.parse_runtime_prompt_input(payload(pack, root=root), pack, pack)
    assert (r.status, r.diagnostic) == ("binding-failure", "CATALOG-RUNTIME-BINDING")

@pytest.mark.parametrize("case", ["complete", "nul-root", "nul-relative", "resolve-error"])
def test_cli_diagnostic_with_observed_fixture_no_client(fixture, case):
    _, home, pack = fixture
    kw = {"nul-root": {"root": str(pack) + "\0"}, "nul-relative": {"relative": "alpha\0/SKILL.md"}}.get(case, {})
    if case == "resolve-error":
        kw = {"root": str(pack.parent / "foreign-root")}
    raw = payload(pack, **kw)
    code = f"""import importlib.util,sys,os
from pathlib import Path
s=importlib.util.spec_from_file_location('catalog_cli_fixture',{str(SOURCE)!r})
m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
home=Path({str(home)!r});pack=Path({str(pack)!r})
os.environ['CODEX_HOME']=str(home/'.codex')
m.Path.home=classmethod(lambda cls: home)
m.DEFAULT_REPO_SKILLS=pack
m.shutil.which=lambda _: 'fixture-never-executed'
if {case!r} == "resolve-error":
    original_resolve=Path.resolve
    def denied(path,*args,**kwargs):
        if path.name == "foreign-root":
            raise PermissionError("injected CLI filesystem refusal")
        return original_resolve(path,*args,**kwargs)
    Path.resolve=denied
m.observe_runtime_catalog=lambda *args,**kwargs: m.parse_runtime_prompt_input({raw!r},pack,pack)
sys.exit(m.main([]))
"""
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code], capture_output=True, text=True)
    assert "Traceback" not in result.stderr
    assert result.returncode == (0 if case == "complete" else 1), result.stdout + result.stderr
    assert ("status=complete" if case == "complete" else "CATALOG-RUNTIME-BINDING") in result.stdout
