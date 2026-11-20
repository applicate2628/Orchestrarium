"""Provider request identity does not authorize a provider runtime or alias."""
from dataclasses import replace
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sdk_execution.contracts import ExecutionRequest
from sdk_execution.runtime import RuntimeBindingError, runtime_selection_from_dict


@pytest.fixture(params=[
    pytest.param(("mimo", "fixture-provider/fixture-model", "opencode"), id="mimo"),
    pytest.param(("minimax", "fixture-model", "mcode"), id="minimax"),
])
def provider_identity(request):
    provider, model, alias = request.param
    execution_request = ExecutionRequest(
        work_item_id="item", provider=provider, external_dispatch_id="dispatch",
        external_evidence_run_id="evidence", artifact_id="artifact", role="architecture-reviewer",
        model=model, effort="low", cwd="fixture-project",
        account_binding="subscription-fixture", prompt="Review the admitted scope.",
        coordinator_binding="lead", scope=("src/example.py",),
    )
    return execution_request, provider, model, alias


def test_request_roundtrip_preserves_exact_identity(provider_identity):
    request, provider, model, _alias = provider_identity
    restored = ExecutionRequest.from_dict(request.to_dict())
    assert restored == request
    assert restored.provider == provider
    assert restored.model == model
    assert restored.account_binding == "subscription-fixture"


def test_identity_does_not_activate_runtime_selection(provider_identity):
    _request, provider, _model, _alias = provider_identity
    with pytest.raises(RuntimeBindingError, match="unsupported_runtime_provider"):
        runtime_selection_from_dict(provider, {})


def test_upstream_or_binary_name_is_not_a_provider_alias(provider_identity):
    request, _provider, _model, alias = provider_identity
    with pytest.raises(ValueError, match="invalid provider"):
        replace(request, provider=alias)
