from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
REMOVED_PROVIDERS = ("gemini", "qwen")


def _load_script(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_removed_provider_surfaces_are_not_live() -> None:
    for relative in (
        "src.gemini",
        "src.qwen",
        "references-gemini",
        "references-qwen",
        "scripts/install-gemini.ps1",
        "scripts/install-gemini.sh",
        "scripts/install-qwen.ps1",
        "scripts/install-qwen.sh",
    ):
        assert not (ROOT / relative).exists(), relative

    schema = json.loads((ROOT / "shared" / "agents-mode.schema.json").read_text(encoding="utf-8"))
    assert schema["exampleOnlyProviders"] == []
    allowed = next(
        item["allowed"]
        for item in schema["scalarKeys"]
        if item["name"] == "externalProvider"
    )
    assert set(REMOVED_PROVIDERS).isdisjoint(allowed)


@pytest.mark.parametrize("provider", REMOVED_PROVIDERS)
@pytest.mark.parametrize(
    ("scalar_style", "quote"),
    (("unquoted", ""), ("single-quoted", "'"), ("double-quoted", '"')),
)
def test_legacy_provider_scalar_fails_closed_without_rewrite(
    tmp_path: Path, provider: str, scalar_style: str, quote: str
) -> None:
    normalizer = _load_script(
        f"normalize_agents_mode_{scalar_style}_removed_{provider}",
        "scripts/normalize-agents-mode.py",
    )
    target = tmp_path / ".agents-mode.yaml"
    yaml_value = f"{quote}{provider}{quote}"
    original = f"externalProvider: {yaml_value}\noperatorNote: preserve-me\n"
    target.write_text(original, encoding="utf-8")

    with pytest.raises(ValueError, match=rf"E_EXTERNAL_PROVIDER_REMOVED.*{provider}"):
        normalizer.normalize_file(
            str(ROOT / "shared" / "agents-mode.defaults.yaml"),
            str(target),
            "codex",
        )

    assert target.read_text(encoding="utf-8") == original


@pytest.mark.parametrize("yaml_value", ("'claude'", '"codex"'))
def test_nonremoved_quoted_provider_scalar_keeps_original_syntax(
    tmp_path: Path, yaml_value: str
) -> None:
    normalizer = _load_script(
        "normalize_agents_mode_nonremoved_quoted_provider",
        "scripts/normalize-agents-mode.py",
    )
    target = tmp_path / ".agents-mode.yaml"
    target.write_text(f"externalProvider: {yaml_value}\n", encoding="utf-8")

    normalized = normalizer.normalize_file(
        str(ROOT / "shared" / "agents-mode.defaults.yaml"),
        str(target),
        "codex",
    )

    provider_line = next(
        line for line in normalized.splitlines() if line.startswith("externalProvider:")
    )
    assert provider_line.split("  #", 1)[0] == f"externalProvider: {yaml_value}"


@pytest.mark.parametrize("provider", REMOVED_PROVIDERS)
def test_removed_provider_resolver_entry_fails_with_migration_diagnostic(
    provider: str,
) -> None:
    resolver = _load_script(
        f"resolve_agents_mode_removed_{provider}",
        "scripts/resolve-agents-mode.py",
    )

    with pytest.raises(ValueError, match=rf"E_EXTERNAL_PROVIDER_REMOVED.*{provider}"):
        resolver.resolve(provider, ROOT, ROOT, ROOT)
