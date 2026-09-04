"""Boolean policy decisions must not be inferred from caller-value truthiness."""
from __future__ import annotations

import importlib.util
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "src.codex/skills/policy-overlay"


@pytest.fixture(scope="module")
def api():
    spec = importlib.util.spec_from_file_location(
        "overlay_boolean_contract", SKILL / "scripts/policy-overlays.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def explicit_only_root(tmp_path):
    copied = tmp_path / "skill"
    shutil.copytree(SKILL, copied)
    path = copied / "policy-overlays.v1.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    catalog["overlays"]["lean-implementation"]["propagation"]["externalWorker"] = "explicit-only"
    path.write_text(json.dumps(catalog), encoding="utf-8")
    return copied


def _select(api, root, explicit):
    return api.resolve_selected_overlays(
        selection="lean-implementation", lane="worker.default-implementation",
        target="external-worker", provider="codex", policy_root=root, explicit=explicit,
    )


@pytest.mark.parametrize("invalid", ("false", "true", 0, 1, None, [], {}))
def test_explicit_only_requires_an_actual_boolean(api, explicit_only_root, invalid):
    with pytest.raises(api.PolicyOverlayError):
        _select(api, explicit_only_root, invalid)


@pytest.mark.parametrize("explicit,expected", ((False, ()), (True, ("lean-implementation",))))
def test_explicit_only_preserves_true_and_false_semantics(api, explicit_only_root, explicit, expected):
    resolved = _select(api, explicit_only_root, explicit)
    assert tuple(item.overlay_id for item in resolved) == expected


@pytest.mark.parametrize("invalid", (None, 0, "", [], {}, True, "false", 1))
def test_renderer_requires_exact_false_authority(api, invalid):
    resolved = _select(api, SKILL, True)
    with pytest.raises(api.PolicyOverlayError):
        api.render_overlay_instructions((replace(resolved[0], authorizing=invalid),))


def test_valid_resolution_renders_with_explicit_nonauthority(api):
    resolved = _select(api, SKILL, True)
    assert len(resolved) == 1 and resolved[0].authorizing is False
    rendered = api.render_overlay_instructions(resolved)
    assert "BEGIN_POLICY_OVERLAY lean-implementation" in rendered
    assert "These optional overlays are non-authorizing." in rendered


def test_empty_projection_remains_empty(api):
    assert api.render_overlay_instructions(()) == ""
