"""Phase A contracts for the future disabled-by-default route registry."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MATRICES = (
    ROOT / "tests" / "fixtures" / "solution-attempt-v3" / "contract-matrices.json"
)
EXPECTED_ROUTES = {
    "claude.native-agent",
    "claude.external.codex",
    "claude.external.claude",
    "codex.native-subagent",
    "codex.root",
    "codex.external.codex",
    "codex.external.claude",
}


def _matrices() -> dict:
    return json.loads(MATRICES.read_text(encoding="utf-8"))


def _load_owner(path: Path, module_name: str, contract: str):
    if not path.is_file():
        pytest.fail(f"missing-contract: {path.relative_to(ROOT)} must own {contract}")
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.fail(f"missing-contract: cannot load owner {path.relative_to(ROOT)}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_provider_route_catalog_is_exactly_seven() -> None:
    routes = _matrices()["routeCatalog"]
    assert len(routes) == len(set(routes)) == 7
    assert set(routes) == EXPECTED_ROUTES


def test_route_registry_binding_matrix_covers_each_identity_dimension() -> None:
    fields = _matrices()["routeBindingFields"]
    assert len(fields) == len(set(fields))
    assert {
        "routeId",
        "originRuntime",
        "provider",
        "commandPath",
        "commandVersion",
        "commandIdentity",
        "hookEvent",
        "hookMatcher",
        "hookHandler",
        "hookCommand",
        "hookSource",
        "trustDigest",
        "adapterSha256",
        "reducerSha256",
        "storeSha256",
        "registrySha256",
        "launcherSha256",
        "sandboxDigest",
        "installationId",
        "generation",
        "probeVersion",
        "challengeDigest",
        "fileOwner",
        "fileMode",
        "reparseIdentity",
    } == set(fields)


def test_route_projection_is_ephemeral_and_minimal() -> None:
    assert _matrices()["routeProjectionFields"] == [
        "routeId",
        "installationId",
        "generation",
        "bindingDigest",
        "probeId",
    ]


def test_install_generation_and_rollback_stay_disabled() -> None:
    cases = {
        row["case"]: row["expected"]
        for row in _matrices()["versionInstallRollback"]
    }
    assert cases["reinstall-generation"] == "ROTATED_ALL_DISABLED"
    assert cases["failed-install"] == "OLD_OR_NEW_VALID_DISABLED"


def test_red_registry_owner_missing() -> None:
    owner = _load_owner(
        ROOT / "scripts" / "route_activation_registry.py",
        "route_activation_registry_phase_a",
        "the seven-route disabled-by-default activation registry",
    )
    assert callable(getattr(owner, "check_route", None)), (
        "missing-contract: scripts/route_activation_registry.py must expose check_route"
    )


def test_all_catalog_routes_are_disabled_even_when_binding_matches() -> None:
    owner = _load_owner(
        ROOT / "scripts" / "route_activation_registry.py",
        "route_activation_registry_disabled",
        "the seven-route disabled-by-default activation registry",
    )
    digest = "a" * 64
    assert set(owner.ROUTE_IDS) == EXPECTED_ROUTES
    assert len(owner.ROUTE_IDS) == 7
    for route_id in owner.ROUTE_IDS:
        decision = owner.check_route(
            route_id,
            expected_binding=digest,
            observed_binding=digest,
        )
        assert decision == {
            "routeId": route_id,
            "enabled": False,
            "bindingMatches": True,
            "result": "SOL-E007-ENFORCEMENT-UNAVAILABLE",
        }


@pytest.mark.parametrize(
    ("route_id", "expected", "observed"),
    [
        ("missing.route", "a" * 64, "a" * 64),
        ("codex.root", "a" * 64, "b" * 64),
        ("codex.root", None, "a" * 64),
    ],
)
def test_missing_or_stale_route_binding_denies(route_id, expected, observed) -> None:
    owner = _load_owner(
        ROOT / "scripts" / "route_activation_registry.py",
        "route_activation_registry_stale",
        "the seven-route disabled-by-default activation registry",
    )
    decision = owner.check_route(
        route_id,
        expected_binding=expected,
        observed_binding=observed,
    )
    assert decision["enabled"] is False
    assert decision["bindingMatches"] is False
    assert decision["result"] == "SOL-E007-ENFORCEMENT-UNAVAILABLE"
