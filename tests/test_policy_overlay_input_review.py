"""Behavioral regressions for strict catalog acquisition; no provider launches."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = ROOT / "src.codex/skills/policy-overlay/scripts/policy_overlay_core.py"


@pytest.fixture(scope="module")
def core():
    spec = importlib.util.spec_from_file_location("policy_overlay_review_core", CORE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def catalog(core, tmp_path):
    (tmp_path / "policy.md").write_bytes(b"Keep required checks.\r\n")
    value = {
        "schemaVersion": 1,
        "defaultSelection": "none",
        "selectionSyntax": "comma-separated-identifiers-v1",
        "conflictPolicy": "reject-selection",
        "precedence": list(core.PRECEDENCE),
        "compatibilityPackages": {
            "ponytail": {
                "repository": "DietrichGebert/ponytail",
                "ownership": "external-host-managed",
                "required": False,
            }
        },
        "overlays": {
            "lean-implementation": {
                "source": {"kind": "builtin", "path": "policy.md"},
                "providers": ["codex"],
                "lanes": ["implementation.main"],
                "targets": ["main-agent"],
                "propagation": {
                    "mainAgent": "lane-filtered",
                    "internalSubagent": "never",
                    "externalWorker": "never",
                    "externalReviewer": "never",
                    "consultant": "never",
                },
                "conflicts": [],
                "order": 1,
                "authorizing": False,
            }
        },
    }
    return tmp_path, value


def _write(root, value):
    (root / "policy-overlays.v1.json").write_text(json.dumps(value), encoding="utf-8")


def test_valid_catalog_retains_existing_contract(core, catalog):
    root, value = catalog
    _write(root, value)
    result = core._load_catalog(root)
    assert tuple(result) == ("lean-implementation",)
    assert result["lean-implementation"]["authorizing"] is False
    assert result["lean-implementation"]["providers"] == ("codex",)


@pytest.mark.parametrize("version", [True, 1.0, "1", None])
def test_catalog_version_is_exact_integer(core, catalog, version):
    root, value = catalog
    value["schemaVersion"] = version
    _write(root, value)
    with pytest.raises(core.PolicyOverlayError):
        core._load_catalog(root)


@pytest.mark.parametrize("value", [[], {}, ["never"]])
def test_invalid_propagation_returns_domain_error(core, catalog, value):
    root, document = catalog
    document["overlays"]["lean-implementation"]["propagation"]["mainAgent"] = value
    _write(root, document)
    with pytest.raises(core.PolicyOverlayError):
        core._load_catalog(root)


@pytest.mark.parametrize("duplicate", ["schemaVersion", "authorizing", "path"])
def test_duplicate_catalog_keys_are_rejected_at_every_depth(core, catalog, duplicate):
    root, value = catalog
    text = json.dumps(value)
    original = {
        "schemaVersion": '"schemaVersion": 1',
        "authorizing": '"authorizing": false',
        "path": '"path": "policy.md"',
    }[duplicate]
    text = text.replace(original, original + ", " + original, 1)
    (root / "policy-overlays.v1.json").write_text(text, encoding="utf-8")
    with pytest.raises(core.PolicyOverlayError):
        core._load_catalog(root)


def test_excessive_parser_nesting_returns_domain_error(core, tmp_path):
    (tmp_path / "policy-overlays.v1.json").write_text("[" * 2000 + "0" + "]" * 2000)
    with pytest.raises(core.PolicyOverlayError):
        core._load_catalog(tmp_path)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_nonstandard_constants_return_domain_error(core, catalog, constant):
    root, value = catalog
    value["compatibilityPackages"]["extra-package"] = "replace-constant"
    text = json.dumps(value).replace('"replace-constant"', constant, 1)
    (root / "policy-overlays.v1.json").write_text(text, encoding="utf-8")
    with pytest.raises(core.PolicyOverlayError):
        core._load_catalog(root)


def test_reader_requests_binary_mode_when_platform_exposes_it(core, tmp_path, monkeypatch):
    path = tmp_path / "policy.md"
    expected = b"first\r\nsecond\x1alast"
    path.write_bytes(expected)
    real_open = os.open
    native_binary_flag = getattr(os, "O_BINARY", 0)
    binary_flag = native_binary_flag or 0x40000000
    seen = []

    def capture_open(name, flags):
        seen.append(flags)
        # The synthetic flag models Windows availability without claiming a Windows run.
        return real_open(name, (flags & ~binary_flag) | native_binary_flag)

    monkeypatch.setattr(core.os, "O_BINARY", binary_flag, raising=False)
    monkeypatch.setattr(core.os, "open", capture_open)
    assert core._read_regular(path, 100, label="test policy") == expected
    assert seen and seen[0] & binary_flag


def test_reader_rejects_same_size_content_change(core, tmp_path, monkeypatch):
    path = tmp_path / "policy.md"
    path.write_bytes(b"before")
    before = path.stat()
    real_read = os.read
    changed = False

    def change_after_read(fd, count):
        nonlocal changed
        data = real_read(fd, count)
        if data and not changed:
            changed = True
            path.write_bytes(b"after!")
            os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 2_000_000_000))
        return data

    monkeypatch.setattr(core.os, "read", change_after_read)
    with pytest.raises(core.PolicyOverlayError):
        core._read_regular(path, 100, label="test policy")


def test_parser_failure_is_normalized(core, catalog, monkeypatch):
    root, value = catalog
    _write(root, value)

    def parser_failure(*args, **kwargs):
        raise RecursionError("parser depth budget")

    monkeypatch.setattr(core.json, "loads", parser_failure)
    with pytest.raises(core.PolicyOverlayError):
        core._load_catalog(root)
