"""Acceptance tests for the S1 profile registry (BUILD-PLAN-v2.1.md Phase 1, item S1).

Run: python -m pytest Work/next-upgraded-pack/Tooling/tests/test_profiles.py -q

Covers two things: (1) the shipped `Instrument/profiles.yaml` itself lints clean and carries the
4 canonical C4-vocabulary tokens with the operator-specified provider/model/effort; (2) the linter
(`Tooling/lint-profiles.py`) correctly flags every violation class it claims to check.

`lint-profiles.py` is loaded via importlib because its filename carries a hyphen (matching the
BUILD-PLAN-v2.1.md-specified path) and is therefore not importable with a plain `import` statement.
"""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

TOOLING = Path(__file__).resolve().parents[1]
INSTRUMENT_DIR = TOOLING.parent / "Instrument"
REGISTRY_PATH = INSTRUMENT_DIR / "profiles.yaml"

_spec = importlib.util.spec_from_file_location("lint_profiles", TOOLING / "lint-profiles.py")
assert _spec is not None and _spec.loader is not None
lint_profiles = importlib.util.module_from_spec(_spec)
sys.modules["lint_profiles"] = lint_profiles
_spec.loader.exec_module(lint_profiles)

CANONICAL_TOKENS = lint_profiles.CANONICAL_TOKENS


def _valid_registry() -> dict:
    """A minimal, independently-constructed registry that satisfies every lint rule.

    Kept separate from the shipped profiles.yaml on purpose: this fixture pins down what the
    linter REQUIRES, while the shipped-file tests below pin down what the shipped file ACTUALLY
    contains (operator-specified providers/models). If the two ever diverge only one class of test
    fails, which localizes whether the break is in the linter's rules or the registry's content.
    """
    return {
        "schema": "profiles-v1",
        "profiles": {
            "systemic-mgmt": {
                "provider": "claude",
                "model": "some-opus-model",
                "effort": "xhigh",
                "construct": "Owner-level judgment under cross-cutting ambiguity.",
                "measurability": "assumption-unverified",
            },
            "stamina": {
                "provider": "claude",
                "model": "some-sonnet-model",
                "effort": "xhigh",
                "construct": "Sustained single-stream breadth under fixed depth.",
                "measurability": "pf-measurable",
            },
            "ultimate-depth": {
                "provider": "codex",
                "model": "some-sol-model",
                "effort": "xhigh",
                "construct": "Deep multi-step reasoning under ambiguity.",
                "measurability": "pf-measurable",
            },
            "working-audit": {
                "provider": "codex",
                "model": "some-terra-model",
                "effort": "xhigh",
                "construct": "Wide-shallow single-aspect blind audit.",
                "measurability": "assumption-unverified",
            },
        },
    }


# ---- shipped registry (Instrument/profiles.yaml) --------------------------------------------------

def test_registry_file_exists():
    assert REGISTRY_PATH.is_file(), f"expected registry at {REGISTRY_PATH}"


def test_shipped_registry_lints_clean():
    errors = lint_profiles.lint_file(REGISTRY_PATH)
    assert errors == []


def test_shipped_registry_has_exactly_the_four_canonical_tokens():
    data = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    assert set(data["profiles"].keys()) == set(CANONICAL_TOKENS)


@pytest.mark.parametrize(
    "token,expected_provider,expected_model",
    [
        ("systemic-mgmt", "claude", "claude-opus-4-8"),
        ("stamina", "claude", "claude-sonnet-5"),
        ("ultimate-depth", "codex", "gpt-5.6-sol"),
        ("working-audit", "codex", "gpt-5.6-terra"),
    ],
)
def test_shipped_registry_bindings(token, expected_provider, expected_model):
    data = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    entry = data["profiles"][token]
    assert entry["provider"] == expected_provider
    assert entry["model"] == expected_model
    assert entry["effort"] == "xhigh"
    assert isinstance(entry["construct"], str) and entry["construct"].strip()
    assert "\n" not in entry["construct"].strip("\n")


def test_cli_main_exits_zero_on_shipped_registry(capsys):
    rc = lint_profiles.main(["--file", str(REGISTRY_PATH)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "LINT-OK" in out


# ---- linter rule coverage (independent fixture, not the shipped file) -----------------------------

def test_valid_fixture_lints_clean():
    assert lint_profiles.lint(_valid_registry()) == []


def test_missing_token_flagged():
    data = _valid_registry()
    del data["profiles"]["stamina"]
    errors = lint_profiles.lint(data)
    assert any("missing required profile token" in e and "stamina" in e for e in errors)


def test_unknown_token_flagged():
    data = _valid_registry()
    data["profiles"]["luna-legacy"] = copy.deepcopy(data["profiles"]["stamina"])
    errors = lint_profiles.lint(data)
    assert any("unknown/unexpected profile token" in e and "luna-legacy" in e for e in errors)


def test_invalid_provider_flagged():
    data = _valid_registry()
    data["profiles"]["stamina"]["provider"] = "gemini"
    errors = lint_profiles.lint(data)
    assert any("stamina.provider" in e for e in errors)


def test_missing_provider_flagged():
    data = _valid_registry()
    del data["profiles"]["ultimate-depth"]["provider"]
    errors = lint_profiles.lint(data)
    assert any("ultimate-depth.provider" in e for e in errors)


def test_empty_model_flagged():
    data = _valid_registry()
    data["profiles"]["working-audit"]["model"] = "   "
    errors = lint_profiles.lint(data)
    assert any("working-audit.model" in e for e in errors)


def test_missing_model_flagged():
    data = _valid_registry()
    del data["profiles"]["systemic-mgmt"]["model"]
    errors = lint_profiles.lint(data)
    assert any("systemic-mgmt.model" in e for e in errors)


def test_missing_construct_flagged():
    data = _valid_registry()
    del data["profiles"]["stamina"]["construct"]
    errors = lint_profiles.lint(data)
    assert any("stamina.construct" in e for e in errors)


def test_multiline_construct_flagged():
    data = _valid_registry()
    data["profiles"]["stamina"]["construct"] = "line one\nline two"
    errors = lint_profiles.lint(data)
    assert any("single line" in e for e in errors)


def test_wrong_effort_flagged():
    data = _valid_registry()
    data["profiles"]["ultimate-depth"]["effort"] = "medium"
    errors = lint_profiles.lint(data)
    assert any("ultimate-depth.effort" in e for e in errors)


def test_missing_effort_flagged():
    data = _valid_registry()
    del data["profiles"]["working-audit"]["effort"]
    errors = lint_profiles.lint(data)
    assert any("working-audit.effort" in e for e in errors)


def test_invalid_measurability_flagged():
    data = _valid_registry()
    data["profiles"]["systemic-mgmt"]["measurability"] = "sort-of"
    errors = lint_profiles.lint(data)
    assert any("systemic-mgmt.measurability" in e for e in errors)


def test_measurability_is_optional():
    data = _valid_registry()
    del data["profiles"]["systemic-mgmt"]["measurability"]
    errors = lint_profiles.lint(data)
    assert errors == []


def test_wrong_schema_flagged():
    data = _valid_registry()
    data["schema"] = "profiles-v0"
    errors = lint_profiles.lint(data)
    assert any("schema" in e for e in errors)


def test_root_not_mapping_flagged():
    errors = lint_profiles.lint(["not", "a", "mapping"])
    assert errors and "not a mapping" in errors[0]


def test_profiles_key_not_mapping_flagged():
    data = {"schema": "profiles-v1", "profiles": ["not", "a", "mapping"]}
    errors = lint_profiles.lint(data)
    assert any("profiles" in e and "mapping" in e for e in errors)


def test_entry_not_mapping_flagged():
    data = _valid_registry()
    data["profiles"]["stamina"] = "not-a-mapping"
    errors = lint_profiles.lint(data)
    assert any("stamina" in e and "not a mapping" in e for e in errors)


def test_multiple_violations_all_reported():
    data = _valid_registry()
    del data["profiles"]["stamina"]
    data["profiles"]["systemic-mgmt"]["provider"] = "gemini"
    errors = lint_profiles.lint(data)
    assert len(errors) >= 2


# ---- file-level / CLI error paths ------------------------------------------------------------------

def test_lint_file_missing():
    errors = lint_profiles.lint_file(Path("does") / "not" / "exist.yaml")
    assert errors and "not found" in errors[0]


def test_lint_file_invalid_yaml(tmp_path):
    bad = tmp_path / "profiles.yaml"
    bad.write_text("profiles: [unterminated\n", encoding="utf-8")
    errors = lint_profiles.lint_file(bad)
    assert errors and "not valid YAML" in errors[0]


def test_cli_main_exits_nonzero_on_broken_registry(tmp_path, capsys):
    bad = tmp_path / "profiles.yaml"
    bad.write_text(
        yaml.safe_dump({"schema": "profiles-v1", "profiles": {}}),
        encoding="utf-8",
    )
    rc = lint_profiles.main(["--file", str(bad)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "LINT-FAIL" in err
