"""Offline route and credential-isolation regression; no SDK or model is used."""
import asyncio
from dataclasses import replace
import os

import pytest

from test_sdk_copilot import FakeSdk, request
from test_sdk_copilot_runtime import selection
import provider_prompt as owner
from sdk_execution import copilot, runtime

ENDPOINT = "https://api.example.invalid/v1"
KEY = "fixture-provider-key"


def byok_source(**overrides):
    return {
        "COPILOT_AUTH_MODE": "byok",
        "COPILOT_BYOK_BASE_URL": ENDPOINT,
        "COPILOT_BYOK_API_KEY": KEY,
        **overrides,
    }


def test_explicit_byok_auth_reuses_existing_secret_transport_and_drops_ambient_keys():
    auth = owner.resolve_provider_auth_configuration("copilot", byok_source(
        GH_TOKEN="not selected", OPENAI_API_KEY="not selected"))
    assert auth.mode == "copilot-byok-openai"
    assert auth.child_environment["COPILOT_BYOK_API_KEY"] == KEY
    assert auth.child_environment["COPILOT_AUTH_MODE"] == "byok"
    assert auth.child_environment["COPILOT_BYOK_BASE_URL"] == ENDPOINT
    assert "GH_TOKEN" not in auth.child_environment and "OPENAI_API_KEY" not in auth.child_environment
    assert KEY.encode() in owner.resolve_provider_output_context(auth).needles


@pytest.mark.parametrize("changes", [
    {"COPILOT_AUTH_MODE": "", "COPILOT_GITHUB_TOKEN": "token"},
    {"COPILOT_AUTH_MODE": "unknown"},
    {"COPILOT_BYOK_API_KEY": "", "OPENAI_API_KEY": "not selected"},
    {"COPILOT_GITHUB_TOKEN": "other-route"},
    {"COPILOT_BYOK_BASE_URL": ""},
    {"COPILOT_BYOK_BASE_URL": "http://api.example.invalid/v1"},
    {"COPILOT_BYOK_BASE_URL": "https://private@api.example.invalid/v1"},
    {"COPILOT_BYOK_BASE_URL": ENDPOINT + "?token=private"},
    {"COPILOT_BYOK_BASE_URL": ENDPOINT + "#private"},
    {"COPILOT_BYOK_BASE_URL": ENDPOINT + "/../other"},
    {"COPILOT_BYOK_BASE_URL": "https://api.example.invalid:99999/v1"},
    {"COPILOT_BYOK_BASE_URL": ENDPOINT + "\\foo"},
    {"COPILOT_BYOK_BASE_URL": "https://other.example.invalid/" + KEY},
])
def test_invalid_or_mixed_auth_never_falls_into_the_other_route(changes):
    with pytest.raises(ValueError) as error:
        owner.resolve_provider_auth_configuration("copilot", byok_source(**changes))
    assert KEY not in str(error.value)
    assert "private" not in str(error.value)


def test_legacy_token_selection_retains_old_wire_shape(tmp_path):
    selected = selection(tmp_path)
    assert "byok_base_url" not in selected.to_dict()
    assert copilot.CopilotRuntimeSelection.from_dict(selected.to_dict()) == selected
    assert owner.resolve_provider_auth_configuration("copilot", {
        "COPILOT_GITHUB_TOKEN": "fixture-github-token"}).mode == "copilot-explicit-token"
    with pytest.raises(ValueError):
        runtime.prepare_environment(selected, byok_source())


def test_selected_endpoint_binds_request_and_receiving_context(tmp_path):
    req = request()
    base = selection(tmp_path)
    selected = replace(base, auth_mode="copilot-byok-openai", byok_base_url=ENDPOINT)
    moved = replace(selected, byok_base_url="https://other.example.invalid/v1")
    assert copilot.CopilotRuntimeSelection.from_dict(selected.to_dict()) == selected
    assert runtime.request_sha256(req, selected) != runtime.request_sha256(req, moved)
    assert runtime.continuation_context_sha256(req, selected) != runtime.continuation_context_sha256(req, moved)
    assert runtime.continuation_context_sha256(req, selected) != runtime.continuation_context_sha256(req, base)
    assert KEY not in repr(selected) and KEY not in repr(runtime.selected_sdk_execution(req, selected))
    with pytest.raises(ValueError):
        runtime.prepare_environment(moved, byok_source())


@pytest.mark.parametrize("reported_provider,reported_model,can_send", [
    ("orche-byok", "qualified", True),
    ("orche-byok", "bare", True),
    ("orche-byok", "wrong", False),
    ("github", "qualified", False),
    (None, "bare", False),
])
def test_fresh_worker_forwards_only_one_official_backend_and_checks_the_readback(
    tmp_path, monkeypatch, reported_provider, reported_model, can_send,
):
    from types import SimpleNamespace

    selected = replace(selection(tmp_path), auth_mode="copilot-byok-openai", byok_base_url=ENDPOINT)
    req = request()
    sdk = FakeSdk()
    model = {"qualified": f"orche-byok/{req.model}", "bare": req.model, "wrong": "different"}[reported_model]
    sdk.rpc.model.get_current = lambda **_: _profile(req, reported_provider, model)
    monkeypatch.setattr(runtime, "assert_current_launch", lambda *_: None)
    monkeypatch.setattr(copilot, "_load_sdk", lambda: sdk)
    monkeypatch.setattr(copilot, "require_supported_byok_sdk", lambda: None)
    for name, value in byok_source().items():
        monkeypatch.setenv(name, value)

    async def authorize(*_):
        pass

    executor = copilot.create_copilot_adapter(req, SimpleNamespace(authorize=authorize, record=authorize), selected)
    assert "COPILOT_BYOK_API_KEY" not in os.environ
    result = asyncio.run(executor.execute(req))
    assert sdk.client_options["github"] == {"use_logged_in_user": False}
    assert sdk.client_options["observability"] == {"log_level": "none"}
    assert sdk.options["model"] == f"orche-byok/{req.model}"
    assert sdk.options["github"] == {"capi": {"enabled": False}, "telemetry_enabled": False}
    inference = sdk.options["inference"]
    assert inference["default_provider"] == "orche-byok"
    assert inference["providers"] == [{
        "name": "orche-byok", "type": "openai", "wire_api": "responses",
        "base_url": ENDPOINT, "api_key": KEY,
    }]
    assert len(inference["models"]) == 1
    assert inference["models"][0]["id"] == req.model
    assert inference["models"][0]["provider"] == "orche-byok"
    assert "COPILOT_BYOK_API_KEY" not in sdk.runtime["env"]
    assert KEY not in repr(result.to_dict()) and KEY not in repr(selected.to_dict())
    assert result.status == ("completed" if can_send else "incomplete")
    assert ("send" in sdk.calls) == can_send


async def _profile(req, provider, model):
    from types import SimpleNamespace

    return SimpleNamespace(model_id=model, reasoning_effort=req.effort, provider_id=provider)


def test_byok_continuation_is_held_before_worker(tmp_path):
    from sdk_execution.contracts import NativeContinuation

    selected = replace(selection(tmp_path), auth_mode="copilot-byok-openai", byok_base_url=ENDPOINT)
    with pytest.raises(ValueError, match="copilot_byok_continuation_unqualified"):
        runtime.validate_admitted_request(request(context_mode="continuation",
            native_continuation=NativeContinuation("prior-dispatch", "prior-evidence", "a" * 64,
                                                   "native-session", "native-turn")), selected)


@pytest.mark.parametrize("selected_version,layout", [
    (None, "ordinary"), ("1.0.0", "ordinary"), ("2.0.2", "ordinary"),
    ("2.0.1", "ordinary"), ("2.0.1", "shadow"), ("2.0.1", "legacy"), ("2.0.1", "missing-record"),
])
def test_byok_sdk_gate_qualifies_exact_package_and_import_origin_without_sdk_import(
    tmp_path, monkeypatch, selected_version, layout,
):
    import importlib.metadata
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace

    package = tmp_path / "copilot"
    package.mkdir()
    origin = package / "__init__.py"
    origin.write_text("raise AssertionError('must not import vendor')", encoding="utf-8")

    def distribution(name):
        assert name in {"microsoft-copilot-sdk", "github-copilot-sdk"}
        if name == "github-copilot-sdk":
            if layout == "legacy":
                return object()
            raise importlib.metadata.PackageNotFoundError(name)
        if selected_version is None:
            raise importlib.metadata.PackageNotFoundError(name)
        return SimpleNamespace(version=selected_version,
            files=[] if layout == "missing-record" else [Path("copilot/__init__.py")],
            locate_file=lambda entry: tmp_path / entry)

    def find_spec(name):
        assert name == "copilot"
        return SimpleNamespace(
            origin=str(origin if layout != "shadow" else tmp_path / "foreign/copilot/__init__.py"),
            submodule_search_locations=[str(package)],
        )

    monkeypatch.setattr(importlib.metadata, "distribution", distribution)
    monkeypatch.setattr(importlib.util, "find_spec", find_spec)
    if selected_version == "2.0.1" and layout == "ordinary":
        copilot.require_supported_byok_sdk()
    else:
        reason = ("copilot_byok_sdk_version_unqualified" if selected_version != "2.0.1"
                  else "copilot_byok_sdk_import_owner_unqualified")
        with pytest.raises(ValueError, match=reason):
            copilot.require_supported_byok_sdk()


def test_public_dispatch_to_receiving_retains_only_nonsecret_byok_binding(tmp_path, monkeypatch):
    from test_sdk_copilot_dispatch import execute_offline, prepare

    monkeypatch.setattr(copilot, "require_supported_byok_sdk", lambda: None)
    operation = prepare(tmp_path, monkeypatch, authentication=byok_source())
    assert operation.selection.byok_base_url == ENDPOINT
    assert KEY not in repr(operation.selection.to_dict())
    sdk = FakeSdk()
    sdk.rpc.model.get_current = lambda **_: _profile(operation.request, "orche-byok", operation.request.model)
    _sdk, calls = execute_offline(operation, monkeypatch, sdk=sdk)
    result = operation.receive()
    assert len(calls) == 1
    assert result.terminal["status"] == "completed"
    assert result.terminal["sdkExecution"]["requestSha256"] == runtime.request_sha256(
        operation.request, operation.selection)
    assert KEY not in repr(result.terminal)
    assert not result.terminal["authorizing"]


def test_public_dispatch_rejects_later_private_endpoint_or_credential_drift(tmp_path, monkeypatch):
    from test_sdk_copilot_dispatch import prepare

    monkeypatch.setattr(copilot, "require_supported_byok_sdk", lambda: None)
    op = prepare(tmp_path, monkeypatch, authentication=byok_source())
    for name, changed in (
        ("COPILOT_BYOK_BASE_URL", "https://alternate.example.invalid/v1"),
        ("COPILOT_BYOK_API_KEY", "rotated-fixture-key"),
    ):
        original = op._environment[name]
        op._environment[name] = changed
        with pytest.raises(ValueError, match="E_COPILOT_SDK_AUTH_CONTEXT_CHANGED"):
            op._check_auth_context()
        op._environment[name] = original


def test_byok_sdk_client_logging_is_suppressed_and_key_not_returned_on_failure(
    tmp_path, monkeypatch, caplog,
):
    import logging
    from types import SimpleNamespace

    selected = replace(selection(tmp_path), auth_mode="copilot-byok-openai", byok_base_url=ENDPOINT)
    req = request()

    class Fault(FakeSdk):
        async def create_session(self, **options):
            logger.warning("invalid request %r", options)
            raise RuntimeError(KEY)

    logger = logging.getLogger("copilot.client")
    assert not logger.disabled
    monkeypatch.setattr(runtime, "assert_current_launch", lambda *_: None)
    monkeypatch.setattr(copilot, "_load_sdk", lambda: Fault())
    monkeypatch.setattr(copilot, "require_supported_byok_sdk", lambda: None)
    for name, value in byok_source().items():
        monkeypatch.setenv(name, value)

    async def authorize(*_):
        pass

    executor = copilot.create_copilot_adapter(req, SimpleNamespace(authorize=authorize, record=authorize), selected)
    result = asyncio.run(executor.execute(req))
    assert not logger.disabled  # Local suppression must not survive the operation.
    assert result.status == "incomplete" and result.execution_error == "copilot_sdk_failed"
    assert KEY not in caplog.text and KEY not in repr(result.to_dict())
