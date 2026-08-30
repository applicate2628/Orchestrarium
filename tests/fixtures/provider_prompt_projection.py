"""Materialize the runtime files required by detached provider-prompt fixtures."""

from __future__ import annotations

from pathlib import Path


_PROVIDER_PROMPT_RUNTIME_FILES = (
    Path("provider_prompt.py"),
    Path("process_supervision/process_runner.py"),
)
_PROVIDER_PROMPT_HOOK_FILES = (
    Path("universal-hooks/hooks/check-machine-local-path.py"),
)


def materialize_provider_prompt_runtime(root: Path, scripts: Path) -> None:
    for relative in _PROVIDER_PROMPT_RUNTIME_FILES:
        destination = scripts / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((root / "scripts" / relative).read_bytes())
    hooks = scripts.parent / "hooks"
    for relative in _PROVIDER_PROMPT_HOOK_FILES:
        destination = hooks / relative.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((root / "scripts" / relative).read_bytes())
    (scripts / "hook_common.py").write_bytes(
        (root / "scripts" / "universal-hooks" / "scripts" / "hook_common.py").read_bytes()
    )
