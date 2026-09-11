from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (
    ROOT
    / "src.codex"
    / "skills"
    / "lead"
    / "scripts"
    / "agents_mode_runtime.py"
)


def _runtime_module():
    spec = importlib.util.spec_from_file_location("agents_mode_runtime_under_test", RUNTIME)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_scalar_decodes_supported_quoted_yaml_scalars(tmp_path: Path) -> None:
    project = tmp_path / "project"
    home = tmp_path / "home"
    (project / ".agents").mkdir(parents=True)
    home.mkdir()
    (project / ".agents" / ".agents-mode.yaml").write_text(
        'delegationMode: "force"\nparallelMode: \'auto\'\n',
        encoding="utf-8",
    )

    runtime = _runtime_module()
    assert runtime.resolve_scalar("delegationMode", cwd=project, home=home) == "force"
    assert runtime.resolve_scalar("parallelMode", cwd=project, home=home) == "auto"
