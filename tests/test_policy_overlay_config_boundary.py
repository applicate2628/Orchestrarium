"""Configuration parsing must never silently discard an owned restriction."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "src.codex/skills/policy-overlay/scripts/policy-overlays.py"
SPEC = importlib.util.spec_from_file_location("overlay_config_boundary", ENTRY)
assert SPEC is not None and SPEC.loader is not None
OVERLAY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OVERLAY)


@pytest.fixture
def layout(tmp_path):
    catalog_root = tmp_path / "skill"
    project = tmp_path / "project"
    home = tmp_path / "home"
    for directory in (catalog_root, project / ".orche", home / ".orche"):
        directory.mkdir(parents=True)
    catalog = {
        "schemaVersion": 1,
        "defaultSelection": "none",
        "selectionSyntax": "comma-separated-identifiers-v1",
        "conflictPolicy": "reject-selection",
        "precedence": list(OVERLAY.PRECEDENCE),
        "compatibilityPackages": {"ponytail": {
            "repository": "DietrichGebert/ponytail",
            "ownership": "external-host-managed", "required": False,
        }},
        "overlays": {"lean-implementation": {
            "source": {"kind": "builtin", "path": "instructions.md"},
            "providers": ["codex"], "lanes": ["implementation"],
            "targets": ["main-agent"],
            "propagation": {
                key: "lane-filtered" if target == "main-agent" else "never"
                for target, key in OVERLAY.PROPAGATION_KEY.items()
            },
            "conflicts": [], "order": 1, "authorizing": False,
        }},
    }
    (catalog_root / "policy-overlays.v1.json").write_text(json.dumps(catalog), encoding="utf-8")
    (catalog_root / "instructions.md").write_text("Keep the change narrow.\n", encoding="utf-8")
    (home / ".orche/config.yaml").write_text(
        "policyOverlays: [lean-implementation]\n", encoding="utf-8"
    )
    return {"project_root": project, "home": home, "policy_root": catalog_root}


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig"])
@pytest.mark.parametrize("separator", [":", " :", "\t:"])
@pytest.mark.parametrize("explicit", [False, True])
def test_project_restrictions_survive_bom_and_key_spacing(layout, encoding, separator, explicit):
    policy = layout["project_root"] / ".orche/policy.yaml"
    policy.write_text(f"deniedPolicyOverlays{separator} [lean-implementation]\n", encoding=encoding)
    with pytest.raises(OVERLAY.PolicyOverlayError, match="project policy rejects"):
        OVERLAY.resolve_from_config(
            **layout, provider="codex", lane="implementation", target="main-agent",
            explicit_selection="lean-implementation" if explicit else None,
        )


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig"])
@pytest.mark.parametrize("separator", [":", " :", "\t:"])
def test_user_selection_survives_bom_and_key_spacing(layout, encoding, separator):
    config = layout["home"] / ".orche/config.yaml"
    config.write_text(f"policyOverlays{separator} [lean-implementation]\n", encoding=encoding)
    resolved = OVERLAY.resolve_from_config(
        **layout, provider="codex", lane="implementation", target="main-agent"
    )
    assert [item.overlay_id for item in resolved] == ["lean-implementation"]
    assert all(item.authorizing is False for item in resolved)


@pytest.mark.parametrize("key", ["policyOverlays", "allowedPolicyOverlays", "deniedPolicyOverlays"])
def test_key_spacing_cannot_hide_duplicate_owned_key(tmp_path, key):
    path = tmp_path / "config.yaml"
    path.write_text(f"{key}: []\n{key} : [lean-implementation]\n", encoding="utf-8")
    with pytest.raises(OVERLAY.PolicyOverlayError, match="duplicate"):
        OVERLAY._config(path, frozenset({key}))


@pytest.mark.parametrize("value", ["lean-implementation", "\n  - lean-implementation"])
def test_spaced_owned_key_still_requires_inline_list(tmp_path, value):
    path = tmp_path / "config.yaml"
    path.write_text(f"deniedPolicyOverlays : {value}\n", encoding="utf-8")
    with pytest.raises(OVERLAY.PolicyOverlayError, match="inline YAML list"):
        OVERLAY._config(path, frozenset({"deniedPolicyOverlays"}))


def test_cli_bom_prefixed_project_denial_is_not_empty_success(layout):
    (layout["project_root"] / ".orche/policy.yaml").write_text(
        "allowedPolicyOverlays: []\n", encoding="utf-8-sig"
    )
    result = subprocess.run(
        [sys.executable, str(ENTRY), "--provider", "codex",
         "--project-root", str(layout["project_root"]), "--home", str(layout["home"]),
         "--policy-root", str(layout["policy_root"]), "--lane", "implementation",
         "--target", "main-agent", "--selection", "lean-implementation"],
        capture_output=True, text=True, encoding="utf-8", timeout=15,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert result.stdout == ""
    assert "E_POLICY_OVERLAY_INVALID" in result.stderr


def test_unrelated_and_nested_keys_are_still_ignored(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "# deniedPolicyOverlays: [lean-implementation]\n"
        "anotherKey: value\n"
        "nested:\n  deniedPolicyOverlays: [lean-implementation]\n"
        "deniedPolicyOverlays: [] # deliberate empty restriction\n", encoding="utf-8",
    )
    assert OVERLAY._config(path, frozenset({"deniedPolicyOverlays"})) == {"deniedPolicyOverlays": ()}


def test_documented_repository_command_points_to_the_actual_entrypoint():
    import re
    guide = (ROOT / "docs/policy-overlays.md").read_text(encoding="utf-8")
    command = re.search(r"^python ([^\s]+policy-overlays\.py) ", guide, re.MULTILINE)
    assert command is not None
    assert (ROOT / command.group(1)).resolve() == ENTRY.resolve()
    assert (ROOT / command.group(1)).is_file()


@pytest.mark.parametrize("key", ["policyOverlays", "allowedPolicyOverlays", "deniedPolicyOverlays"])
@pytest.mark.parametrize("quote", ["'", '"'])
def test_quoted_root_owned_key_is_rejected_not_silently_ignored(tmp_path, key, quote):
    path = tmp_path / "config.yaml"
    path.write_text(f"{quote}{key}{quote}: []\n", encoding="utf-8")
    with pytest.raises(OVERLAY.PolicyOverlayError, match="inline YAML list"):
        OVERLAY._config(path, frozenset({key}))


@pytest.mark.parametrize("quote", ["'", '"'])
@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("key,values", [
    ("allowedPolicyOverlays", ""),
    ("deniedPolicyOverlays", "lean-implementation"),
])
def test_quoted_project_restriction_cannot_become_success(layout, quote, explicit, key, values):
    policy = layout["project_root"] / ".orche/policy.yaml"
    policy.write_text(f"{quote}{key}{quote}: [{values}]\n", encoding="utf-8")
    with pytest.raises(OVERLAY.PolicyOverlayError, match="inline YAML list"):
        OVERLAY.resolve_from_config(
            **layout, provider="codex", lane="implementation", target="main-agent",
            explicit_selection="lean-implementation" if explicit else None,
        )
