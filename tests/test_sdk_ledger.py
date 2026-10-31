"""Synthetic SDK receiving through the existing ledger writer and validator."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from test_agent_run_ledger import (
    load_ledger_module,
    prepare_valid_work_item,
    run_ledger,
    run_validator,
)


SDK_CONFIG = {
    "schemaVersion": 1,
    "adapter": "openai-codex",
    "sdkVersion": "0.163.0",
    "runtimeVersion": "0.163.0",
    "model": "gpt-5.6-sol",
    "effort": "high",
    "sandboxMode": "read-only",
    "approvalPolicy": "deny_all",
    "accountBinding": "synthetic-account",
}
LAUNCH_ID = "sdk-dispatch-0001"
TERMINAL_ID = "sdk-terminal-0001"


def create_fixture_symlink(link, target, *, target_is_directory=False):
    """Skip unavailable Windows fixture setup, never a tested link mutation."""
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows symlink fixture privilege unavailable (WinError 1314)")
        raise


@pytest.mark.parametrize("winerror", [1314, 5, None])
def test_fixture_symlink_skips_only_missing_windows_privilege(monkeypatch, tmp_path, winerror):
    failure = OSError("synthetic symlink fixture failure")
    if winerror is not None:
        failure.winerror = winerror

    def unavailable(*args, **kwargs):
        raise failure

    monkeypatch.setattr(Path, "symlink_to", unavailable)
    if winerror == 1314:
        with pytest.raises(pytest.skip.Exception, match="WinError 1314"):
            create_fixture_symlink(tmp_path / "alias", "target")
    else:
        with pytest.raises(OSError) as caught:
            create_fixture_symlink(tmp_path / "alias", "target")
        assert caught.value is failure


def sdk_launch_args(config=None):
    return [
        "append", "--run-id", LAUNCH_ID,
        "--role", "external-reviewer", "--execution-role", "external-reviewer",
        "--assigned-role", "qa-engineer", "--provider", "codex",
        "--model", SDK_CONFIG["model"], "--effort", SDK_CONFIG["effort"],
        "--scope", "synthetic repository review", "--status", "running", "--gate", "none",
        "--event-kind", "launch", "--actual-execution-path", "direct-external-sdk",
        "--sdk-execution-json", json.dumps(SDK_CONFIG if config is None else config),
        "--artifact-identity", "sha256:" + "c" * 64,
        "--external-dispatch-id", LAUNCH_ID,
        "--external-evidence-run-id", TERMINAL_ID,
        "--effort-mapping-loss", "none",
        "--started-at", "2026-10-23T10:00:00Z", "--updated-at", "2026-10-23T10:00:00Z",
    ]


def sdk_settle_args(item):
    artifact_bytes = (item / "reviews/qa.md").read_bytes()
    return [
        "settle-launch", "--launch-run-id", LAUNCH_ID, "--run-id", TERMINAL_ID,
        "--expected-launch-sha256", load_ledger_module().launch_event_sha256(read_events(item)[0]),
        "--status", "completed", "--gate", "PASS", "--artifact", "reviews/qa.md",
        "--artifact-revision", hashlib.sha256(artifact_bytes).hexdigest(),
        "--artifact-size-bytes", str(len(artifact_bytes)),
        "--evidence", "artifact:reviews/qa.md",
        "--started-at", "2026-10-23T10:01:00Z", "--updated-at", "2026-10-23T10:01:00Z",
    ]


def read_events(item):
    return [json.loads(line) for line in (item / "agent-runs.jsonl").read_text().splitlines()]


def test_sdk_launch_settle_roundtrip_remains_nonauthorizing(tmp_path):
    item = prepare_valid_work_item(tmp_path)
    launch = run_ledger(item, *sdk_launch_args())
    assert launch.returncode == 0, launch.stdout + launch.stderr
    settled = run_ledger(item, *sdk_settle_args(item))
    assert settled.returncode == 0, settled.stdout + settled.stderr
    events = read_events(item)
    assert len(events) == 2
    launch_event, terminal = events
    for field in ("sdkExecution", "actualExecutionPath", "artifactIdentity",
                  "externalDispatchId", "externalEvidenceRunId", "effortMappingLoss"):
        assert terminal[field] == launch_event[field]
    assert terminal["sdkExecution"] == SDK_CONFIG
    assert terminal["schemaVersion"] == 2
    assert terminal["authorizing"] is False
    assert terminal["terminalClass"] == "external-nonauthorizing"
    assert terminal["closesRunIds"] == []
    assert terminal["runId"] == terminal["externalEvidenceRunId"]
    assert "launchFlags" not in terminal
    assert "terminalClass" not in launch_event
    checked = run_validator(item)
    assert checked.returncode == 0, checked.stdout + checked.stderr


@pytest.mark.parametrize("field,value", [
    ("schemaVersion", 2), ("schemaVersion", True), ("adapter", "unknown-sdk"),
    ("model", "other-model"), ("effort", "medium"), ("sandboxMode", "workspace-write"),
    ("approvalPolicy", "auto_review"), ("sdkVersion", ""), ("runtimeVersion", ""),
    ("accountBinding", "secret\nvalue"), ("unknown", "value"),
])
def test_sdk_invalid_configuration_refused_without_write(tmp_path, field, value):
    item = prepare_valid_work_item(tmp_path)
    before = (item / "agent-runs.jsonl").read_bytes() if (item / "agent-runs.jsonl").exists() else None
    config = dict(SDK_CONFIG, **{field: value})
    result = run_ledger(item, *sdk_launch_args(config))
    assert result.returncode != 0
    assert "sdkExecution" in result.stdout + result.stderr
    after = (item / "agent-runs.jsonl").read_bytes() if (item / "agent-runs.jsonl").exists() else None
    assert after == before


@pytest.mark.parametrize("missing", list(SDK_CONFIG))
def test_sdk_configuration_fields_are_required(tmp_path, missing):
    item = prepare_valid_work_item(tmp_path)
    config = dict(SDK_CONFIG)
    del config[missing]
    result = run_ledger(item, *sdk_launch_args(config))
    assert result.returncode != 0
    assert "sdkExecution" in result.stdout + result.stderr


@pytest.mark.parametrize("option,value", [
    ("--actual-execution-path", "direct-external-cli"),
    ("--provider", "claude"), ("--event-kind", "standalone"),
    ("--status", "completed"), ("--gate", "advisory"),
])
def test_sdk_configuration_cannot_be_mixed_into_legacy_or_other_routes(tmp_path, option, value):
    item = prepare_valid_work_item(tmp_path)
    args = sdk_launch_args()
    args[args.index(option) + 1] = value
    result = run_ledger(item, *args)
    assert result.returncode != 0


def test_sdk_configuration_forbids_fabricated_launch_flags(tmp_path):
    item = prepare_valid_work_item(tmp_path)
    result = run_ledger(item, *sdk_launch_args(), "--launch-flags-json", "[]")
    assert result.returncode != 0
    assert "launchFlags" in result.stdout + result.stderr


def test_sdk_replay_is_idempotent_and_conflicting_settlement_is_refused(tmp_path):
    item = prepare_valid_work_item(tmp_path)
    assert run_ledger(item, *sdk_launch_args()).returncode == 0
    assert run_ledger(item, *sdk_settle_args(item)).returncode == 0
    before = (item / "agent-runs.jsonl").read_bytes()
    replay = run_ledger(item, *sdk_settle_args(item))
    assert replay.returncode == 0, replay.stdout + replay.stderr
    assert "already-settled" in replay.stdout
    assert (item / "agent-runs.jsonl").read_bytes() == before
    conflict = run_ledger(item, *sdk_settle_args(item), "--notes", "changed result")
    assert conflict.returncode != 0
    assert (item / "agent-runs.jsonl").read_bytes() == before


@pytest.mark.parametrize("option,value", [
    ("--actual-execution-path", "direct-external-cli"),
    ("--artifact-identity", "sha256:" + "d" * 64),
    ("--external-dispatch-id", "other-dispatch"),
    ("--external-evidence-run-id", "other-evidence"),
    ("--effort-mapping-loss", "changed"),
    ("--authorizing", "true"), ("--terminal-class", "internal-authorizing"),
    ("--run-id", "other-terminal-id"),
])
def test_sdk_settlement_cannot_rebind_admitted_identity(tmp_path, option, value):
    item = prepare_valid_work_item(tmp_path)
    assert run_ledger(item, *sdk_launch_args()).returncode == 0
    before = (item / "agent-runs.jsonl").read_bytes()
    result = run_ledger(item, *sdk_settle_args(item), option, value)
    assert result.returncode != 0
    assert (item / "agent-runs.jsonl").read_bytes() == before


@pytest.mark.parametrize("field,value", [
    ("sdkExecution", dict(SDK_CONFIG, accountBinding="changed-account")),
    ("actualExecutionPath", "direct-external-cli"),
    ("artifactIdentity", "changed-artifact"), ("externalDispatchId", "changed-dispatch"),
    ("externalEvidenceRunId", "changed-evidence"), ("effortMappingLoss", "changed"),
])
def test_sdk_launch_terminal_binding_uses_exact_configuration_and_domain_ids(field, value):
    validator = load_ledger_module().load_validator()
    launch = {"actualExecutionPath": "direct-external-sdk", "sdkExecution": SDK_CONFIG,
              "artifactIdentity": "original", "externalDispatchId": "original",
              "externalEvidenceRunId": TERMINAL_ID, "effortMappingLoss": "none"}
    terminal = copy.deepcopy(launch)
    terminal[field] = value
    assert field in validator.launch_terminal_binding_mismatches(launch, terminal)


def test_sdk_duplicate_configuration_keys_are_rejected(tmp_path):
    item = prepare_valid_work_item(tmp_path)
    args = sdk_launch_args()
    key = args.index("--sdk-execution-json") + 1
    args[key] = args[key][:-1] + ', "model": "other"}'
    result = run_ledger(item, *args)
    assert result.returncode != 0
    assert "duplicate" in result.stdout + result.stderr


@pytest.mark.parametrize("field,value", [
    ("sdkExecution", None), ("sdkExecution", []), ("sdkExecution", {"schemaVersion": 1}),
    ("externalDispatchId", []), ("externalEvidenceRunId", {}),
    ("assignedRole", ""), ("artifactIdentity", ""), ("effortMappingLoss", ""),
])
def test_sdk_malformed_persisted_rows_fail_closed_without_validator_crash(tmp_path, field, value):
    item = prepare_valid_work_item(tmp_path)
    assert run_ledger(item, *sdk_launch_args()).returncode == 0
    event = read_events(item)[0]
    event[field] = value
    (item / "agent-runs.jsonl").write_text(json.dumps(event) + "\n")
    result = run_validator(item)
    assert result.returncode != 0
    assert "Traceback" not in result.stdout + result.stderr


def test_sdk_schema_and_canonical_shape_validator_share_positive_contract():
    import jsonschema
    validator = load_ledger_module().load_validator()
    schema = validator.AGENT_RUN_SCHEMA["properties"]["sdkExecution"]
    for effort in ("low", "medium", "high", "xhigh", "max"):
        config = dict(SDK_CONFIG, effort=effort)
        jsonschema.validate(config, schema)
        result = validator.validate_sdk_execution(config, provider="codex", model=config["model"], effort=effort)
        assert result == config
        assert result is not config


@pytest.mark.parametrize("field,value", [
    ("schemaVersion", True), ("schemaVersion", 0), ("adapter", "unknown"),
    ("effort", "ultra"), ("sdkVersion", "has space"),
    ("accountBinding", "x" * 129), ("sandboxMode", "workspace-write"),
    ("approvalPolicy", "auto_review"), ("unknown", "value"),
])
def test_sdk_schema_and_canonical_shape_validator_agree_on_invalid_shapes(field, value):
    import jsonschema
    validator = load_ledger_module().load_validator()
    config = dict(SDK_CONFIG, **{field: value})
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(config, validator.AGENT_RUN_SCHEMA["properties"]["sdkExecution"])
    with pytest.raises(ValueError, match="sdkExecution"):
        validator.validate_sdk_execution(config, provider="codex", model=config.get("model"), effort=config.get("effort"))


def test_sdk_event_schema_matches_durable_pair(tmp_path):
    import jsonschema
    item = prepare_valid_work_item(tmp_path)
    assert run_ledger(item, *sdk_launch_args()).returncode == 0
    assert run_ledger(item, *sdk_settle_args(item)).returncode == 0
    schema = load_ledger_module().load_validator().AGENT_RUN_SCHEMA
    for event in read_events(item):
        jsonschema.validate(event, schema)


@pytest.mark.parametrize("field,value", [
    ("sdkExecution", dict(SDK_CONFIG, accountBinding="changed-account")),
    ("sdkExecution", dict(SDK_CONFIG, sdkVersion="0.155.0")),
    ("sdkExecution", dict(SDK_CONFIG, runtimeVersion="0.155.0")),
    ("artifactIdentity", "sha256:" + "d" * 64),
    ("externalDispatchId", "changed-dispatch"),
    ("effortMappingLoss", "changed"),
])
def test_sdk_persisted_terminal_drift_is_rejected_on_readback(tmp_path, field, value):
    item = prepare_valid_work_item(tmp_path)
    assert run_ledger(item, *sdk_launch_args()).returncode == 0
    assert run_ledger(item, *sdk_settle_args(item)).returncode == 0
    events = read_events(item)
    events[1][field] = value
    (item / "agent-runs.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events))
    result = run_validator(item)
    assert result.returncode != 0
    expected = (
        "SDK terminal launchRunId must equal externalDispatchId"
        if field == "externalDispatchId" else "WI-LEDGER-LAUNCH-BINDING"
    )
    assert expected in result.stdout + result.stderr


def test_sdk_duplicate_terminal_is_rejected_by_persisted_readback(tmp_path):
    item = prepare_valid_work_item(tmp_path)
    assert run_ledger(item, *sdk_launch_args()).returncode == 0
    assert run_ledger(item, *sdk_settle_args(item)).returncode == 0
    terminal = read_events(item)[1]
    with (item / "agent-runs.jsonl").open("a") as output:
        output.write(json.dumps(terminal) + "\n")
    result = run_validator(item)
    assert result.returncode != 0


def test_sdk_route_cannot_omit_versioned_configuration(tmp_path):
    item = prepare_valid_work_item(tmp_path)
    args = sdk_launch_args()
    index = args.index("--sdk-execution-json")
    del args[index:index + 2]
    result = run_ledger(item, *args)
    assert result.returncode != 0
    assert "sdkExecution" in result.stdout + result.stderr


@pytest.mark.parametrize("option,value", [
    ("--terminal-class", "external-nonauthorizing"), ("--authorizing", "false"),
    ("--closer-run-id", "synthetic-closer"), ("--closes", "synthetic-prior-run"),
])
def test_sdk_launch_cannot_claim_terminal_authority(tmp_path, option, value):
    item = prepare_valid_work_item(tmp_path)
    result = run_ledger(item, *sdk_launch_args(), option, value)
    assert result.returncode != 0


def test_sdk_terminal_cannot_gain_internal_closure_authority(tmp_path):
    item = prepare_valid_work_item(tmp_path)
    assert run_ledger(item, *sdk_launch_args()).returncode == 0
    assert run_ledger(item, *sdk_settle_args(item)).returncode == 0
    events = read_events(item)
    events[1].update(authorizing=True, terminalClass="internal-authorizing", closesRunIds=["synthetic-prior-run"])
    (item / "agent-runs.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events))
    result = run_validator(item)
    assert result.returncode != 0
    assert "SDK terminal" in result.stdout + result.stderr


@pytest.mark.parametrize("status", ["planned", "running"])
def test_sdk_terminal_per_event_contract_requires_terminal_status(tmp_path, status):
    item = prepare_valid_work_item(tmp_path)
    assert run_ledger(item, *sdk_launch_args()).returncode == 0
    assert run_ledger(item, *sdk_settle_args(item)).returncode == 0
    event = read_events(item)[1]
    event.update(status=status, gate="none")
    errors = []
    validator = load_ledger_module().load_validator()
    validator.validate_event(event, item, set(), errors)
    assert any("SDK terminal requires terminal status" in value for value in errors)


def test_sdk_launch_reuses_dispatch_identity_without_third_unbound_id(tmp_path):
    item = prepare_valid_work_item(tmp_path)
    result = run_ledger(item, *sdk_launch_args(), "--run-id", "unbound-extra-launch")
    assert result.returncode != 0
    assert "SDK launch runId must equal externalDispatchId" in result.stdout + result.stderr


def test_sdk_terminal_reference_is_the_recorded_dispatch_identity(tmp_path):
    item = prepare_valid_work_item(tmp_path)
    assert run_ledger(item, *sdk_launch_args()).returncode == 0
    assert run_ledger(item, *sdk_settle_args(item)).returncode == 0
    event = read_events(item)[1]
    event["launchRunId"] = "unbound-extra-launch"
    errors = []
    load_ledger_module().load_validator().validate_event(event, item, set(), errors)
    assert any("SDK terminal launchRunId must equal externalDispatchId" in value for value in errors)


def test_sdk_execution_schema_does_not_expand_existing_target_tuple():
    import jsonschema
    schema = load_ledger_module().load_validator().AGENT_RUN_SCHEMA["properties"]["targetTuple"]
    assert set(schema["properties"]) == {
        "workItem", "assignedInternalRole", "artifactIdentity", "externalDispatchId"
    }
    target = {"workItem": "fixture", "assignedInternalRole": "qa-engineer",
              "artifactIdentity": "fixture", "sdkExecution": SDK_CONFIG}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(target, schema)


def test_sdk_settlement_requires_admitted_launch_digest(tmp_path):
    item = prepare_valid_work_item(tmp_path)
    assert run_ledger(item, *sdk_launch_args()).returncode == 0
    args = sdk_settle_args(item)
    index = args.index("--expected-launch-sha256")
    del args[index:index + 2]
    before = (item / "agent-runs.jsonl").read_bytes()
    result = run_ledger(item, *args)
    assert result.returncode != 0
    assert "WI-LEDGER-SETTLE-LAUNCH-DRIFT" in result.stdout + result.stderr
    assert (item / "agent-runs.jsonl").read_bytes() == before


def test_sdk_settlement_rechecks_launch_inside_existing_atomic_owner(tmp_path, monkeypatch, capsys):
    item = prepare_valid_work_item(tmp_path)
    assert run_ledger(item, *sdk_launch_args()).returncode == 0
    args = sdk_settle_args(item)
    writer = load_ledger_module()
    capture = writer._capture_ledger_preimage
    changed_bytes = None

    def changed_before_locked_read(path, validator, budget):
        nonlocal changed_bytes
        assert (item / "agent-runs.jsonl.lock").is_file()
        event = read_events(item)[0]
        event["scope"] = ["valid different admitted scope"]
        event["sdkExecution"]["accountBinding"] = "valid-other-account"
        changed_bytes = (json.dumps(event) + "\n").encode()
        path.write_bytes(changed_bytes)
        return capture(path, validator, budget)

    monkeypatch.setattr(writer, "_capture_ledger_preimage", changed_before_locked_read)
    assert writer.main(["--work-item", str(item), *args]) == 1
    assert "WI-LEDGER-SETTLE-LAUNCH-DRIFT" in capsys.readouterr().err
    assert (item / "agent-runs.jsonl").read_bytes() == changed_bytes
    assert len(read_events(item)) == 1
    assert not (item / "agent-runs.jsonl.lock").exists()


CLAUDE_CONFIG = dict(SDK_CONFIG, adapter="claude-agent-sdk", sdkVersion="0.2.173",
                     runtimeVersion="2.1.309", model="claude-sonnet-4-6",
                     sandboxMode="tool-restricted-read-only", approvalPolicy="deny_unadmitted")


def test_claude_sdk_uses_same_contract_without_claiming_os_sandbox(tmp_path):
    import jsonschema
    item = prepare_valid_work_item(tmp_path)
    args = sdk_launch_args(CLAUDE_CONFIG)
    args[args.index("--provider") + 1] = "claude"
    args[args.index("--model") + 1] = CLAUDE_CONFIG["model"]
    result = run_ledger(item, *args)
    assert result.returncode == 0, result.stdout + result.stderr
    settled = run_ledger(item, *sdk_settle_args(item))
    assert settled.returncode == 0, settled.stdout + settled.stderr
    validator = load_ledger_module().load_validator()
    for event in read_events(item):
        jsonschema.validate(event, validator.AGENT_RUN_SCHEMA)
    terminal = read_events(item)[1]
    assert terminal["sdkExecution"] == CLAUDE_CONFIG
    assert terminal["authorizing"] is False
    assert run_validator(item).returncode == 0


@pytest.mark.parametrize("provider,config", [
    ("codex", CLAUDE_CONFIG), ("claude", SDK_CONFIG),
    ("claude", dict(CLAUDE_CONFIG, sandboxMode="read-only")),
    ("claude", dict(CLAUDE_CONFIG, approvalPolicy="deny_all")),
    ("codex", dict(SDK_CONFIG, sandboxMode="tool-restricted-read-only")),
    ("codex", dict(SDK_CONFIG, approvalPolicy="deny_unadmitted")),
])
def test_sdk_provider_controls_cannot_be_mixed(provider, config):
    validator = load_ledger_module().load_validator()
    with pytest.raises(ValueError, match="sdkExecution"):
        validator.validate_sdk_execution(config, provider=provider, model=config["model"], effort=config["effort"])


@pytest.mark.parametrize("status,gate", [("completed", "PASS"), ("blocked", "none")])
def test_sdk_artifact_bytes_are_durable_for_success_and_failure(tmp_path, status, gate):
    item = prepare_valid_work_item(tmp_path)
    assert run_ledger(item, *sdk_launch_args()).returncode == 0
    result = run_ledger(item, *sdk_settle_args(item), "--status", status, "--gate", gate)
    assert result.returncode == 0, result.stdout + result.stderr
    raw = (item / "reviews/qa.md").read_bytes()
    event = read_events(item)[1]
    assert event["artifactRevision"] == hashlib.sha256(raw).hexdigest()
    assert event["artifactSizeBytes"] == len(raw)
    assert run_validator(item).returncode == 0
    (item / "reviews/qa.md").write_bytes(b"x" * len(raw))
    checked = run_validator(item)
    assert checked.returncode != 0
    assert "WI-SDK-ARTIFACT-BINDING" in checked.stdout + checked.stderr


@pytest.mark.parametrize("option,value", [
    ("--artifact-revision", None), ("--artifact-size-bytes", None),
    ("--artifact-revision", "a" * 64), ("--artifact-revision", "not-a-digest"),
    ("--artifact-size-bytes", "0"), ("--artifact-size-bytes", "99999"),
    ("--artifact-size-bytes", "-1"),
])
def test_sdk_artifact_binding_refuses_missing_or_different_bytes(tmp_path, option, value):
    item = prepare_valid_work_item(tmp_path)
    assert run_ledger(item, *sdk_launch_args()).returncode == 0
    args = sdk_settle_args(item)
    index = args.index(option)
    if value is None:
        del args[index:index + 2]
    else:
        args[index + 1] = value
    before = (item / "agent-runs.jsonl").read_bytes()
    result = run_ledger(item, *args)
    assert result.returncode != 0
    assert "WI-SDK-ARTIFACT-BINDING" in result.stdout + result.stderr
    assert (item / "agent-runs.jsonl").read_bytes() == before


@pytest.mark.parametrize("retarget_alias", [False, True])
def test_sdk_artifact_change_between_capture_and_receiving_refuses_write(
    tmp_path, monkeypatch, capsys, retarget_alias
):
    item = prepare_valid_work_item(tmp_path)
    assert run_ledger(item, *sdk_launch_args()).returncode == 0
    args = sdk_settle_args(item)
    artifact = item / "reviews/qa.md"
    alias = item / "reviews/sdk-alias.md"
    replacement = item / "reviews/same-bytes.md"
    if retarget_alias:
        replacement.write_bytes(artifact.read_bytes())
        create_fixture_symlink(alias, artifact.name)
        args[args.index("--artifact") + 1] = "reviews/sdk-alias.md"
    before = (item / "agent-runs.jsonl").read_bytes()
    writer = load_ledger_module()
    receive = writer._receive_append_operation
    changed = False

    def mutate_before_receiving(*a, **kw):
        nonlocal changed
        assert (item / "agent-runs.jsonl.lock").is_file()
        if retarget_alias:
            alias.unlink()
            alias.symlink_to(replacement.name)
        else:
            artifact.write_bytes(b"x" * artifact.stat().st_size)
        changed = True
        return receive(*a, **kw)

    monkeypatch.setattr(writer, "_receive_append_operation", mutate_before_receiving)
    assert writer.main(["--work-item", str(item), *args]) == 1
    assert changed
    diagnostic = capsys.readouterr().err
    assert "WI-SDK-ARTIFACT-BINDING" in diagnostic, diagnostic
    assert (item / "agent-runs.jsonl").read_bytes() == before
    assert not (item / "agent-runs.jsonl.lock").exists()


def test_sdk_artifact_admits_existing_in_root_symlink_locator(tmp_path):
    item = prepare_valid_work_item(tmp_path)
    assert run_ledger(item, *sdk_launch_args()).returncode == 0
    create_fixture_symlink(item / "reviews/sdk-alias.md", "qa.md")
    args = sdk_settle_args(item)
    args[args.index("--artifact") + 1] = "reviews/sdk-alias.md"
    result = run_ledger(item, *args)
    assert result.returncode == 0, result.stdout + result.stderr
    assert read_events(item)[1]["artifact"] == "reviews/sdk-alias.md"
    assert run_validator(item).returncode == 0


def test_sdk_failure_without_persisted_artifact_does_not_invent_byte_evidence(tmp_path):
    item = prepare_valid_work_item(tmp_path)
    assert run_ledger(item, *sdk_launch_args()).returncode == 0
    args = sdk_settle_args(item)
    for option in ("--artifact", "--artifact-revision", "--artifact-size-bytes", "--evidence"):
        index = args.index(option)
        del args[index:index + 2]
    result = run_ledger(item, *args, "--status", "blocked", "--gate", "none")
    assert result.returncode == 0, result.stdout + result.stderr
    event = read_events(item)[1]
    assert not {"artifact", "artifactRevision", "artifactSizeBytes"} & set(event)


@pytest.mark.parametrize("size", [True, "10", -1, 1.5])
def test_sdk_artifact_size_schema_and_validator_reject_nonnatural_values(tmp_path, size):
    import jsonschema
    item = prepare_valid_work_item(tmp_path)
    assert run_ledger(item, *sdk_launch_args()).returncode == 0
    assert run_ledger(item, *sdk_settle_args(item)).returncode == 0
    event = read_events(item)[1]
    event["artifactSizeBytes"] = size
    validator = load_ledger_module().load_validator()
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(event, validator.AGENT_RUN_SCHEMA)
    errors = []
    validator.validate_event(event, item, set(), errors)
    assert any("WI-SDK-ARTIFACT-BINDING" in entry for entry in errors)



def test_sdk_request_commitment_is_optional_for_existing_records_and_bound_when_present(tmp_path):
    import jsonschema
    validator = load_ledger_module().load_validator()
    for config in (SDK_CONFIG, dict(SDK_CONFIG, requestSha256="b" * 64)):
        jsonschema.validate(config, validator.AGENT_RUN_SCHEMA["properties"]["sdkExecution"])
        assert validator.validate_sdk_execution(config, provider="codex", model=config["model"], effort=config["effort"]) == config
    item = prepare_valid_work_item(tmp_path)
    config = dict(SDK_CONFIG, requestSha256="b" * 64)
    result = run_ledger(item, *sdk_launch_args(config))
    assert result.returncode == 0, result.stdout + result.stderr
    settled = run_ledger(item, *sdk_settle_args(item))
    assert settled.returncode == 0, settled.stdout + settled.stderr
    launch, terminal = read_events(item)
    assert terminal["sdkExecution"]["requestSha256"] == config["requestSha256"]
    assert run_validator(item).returncode == 0
    terminal["sdkExecution"]["requestSha256"] = "c" * 64
    assert "sdkExecution" in validator.launch_terminal_binding_mismatches(launch, terminal)
    del terminal["sdkExecution"]["requestSha256"]
    assert "sdkExecution" in validator.launch_terminal_binding_mismatches(launch, terminal)


@pytest.mark.parametrize("digest", [None, True, 123, "", "a" * 63, "a" * 65, "A" * 64, "g" * 64, "a" * 63 + "\n"])
def test_sdk_request_commitment_rejects_malformed_digest(digest):
    import jsonschema
    validator = load_ledger_module().load_validator()
    config = dict(SDK_CONFIG, requestSha256=digest)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(config, validator.AGENT_RUN_SCHEMA["properties"]["sdkExecution"])
    with pytest.raises(ValueError, match="sdkExecution"):
        validator.validate_sdk_execution(config, provider="codex", model=config["model"], effort=config["effort"])


def selected_sdk_config():
    return {**{key: value for key, value in SDK_CONFIG.items() if key not in {"sdkVersion", "runtimeVersion"}},
            "schemaVersion": 2, "requestSha256": "b" * 64}


def test_versionless_selected_schema_survives_launch_settlement_and_readback(tmp_path):
    import jsonschema
    config = selected_sdk_config()
    validator = load_ledger_module().load_validator()
    jsonschema.validate(config, validator.AGENT_RUN_SCHEMA["properties"]["sdkExecution"])
    assert validator.validate_sdk_execution(config, provider="codex", model=config["model"], effort=config["effort"]) == config
    item = prepare_valid_work_item(tmp_path)
    launched = run_ledger(item, *sdk_launch_args(config))
    assert launched.returncode == 0, launched.stdout + launched.stderr
    settled = run_ledger(item, *sdk_settle_args(item))
    assert settled.returncode == 0, settled.stdout + settled.stderr
    launch, terminal = read_events(item)
    assert launch["sdkExecution"] == terminal["sdkExecution"] == config
    for event in (launch, terminal):
        jsonschema.validate(event, validator.AGENT_RUN_SCHEMA)
    assert run_validator(item).returncode == 0


@pytest.mark.parametrize("change", [
    {"sdkVersion": "9.0"}, {"runtimeVersion": "10.0"}, {"unknown": "field"},
    {"requestSha256": None}, {"schemaVersion": True}, {"schemaVersion": 2.0},
])
def test_selected_schema_rejects_fabricated_versions_and_malformed_fields(change):
    import jsonschema
    config = {**selected_sdk_config(), **change}
    validator = load_ledger_module().load_validator()
    if change != {"schemaVersion": 2.0}:
        # JSON Schema treats integral JSON numbers as integers; the Python
        # boundary additionally refuses a non-integral representation type.
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(config, validator.AGENT_RUN_SCHEMA["properties"]["sdkExecution"])
    with pytest.raises(ValueError, match="sdkExecution"):
        validator.validate_sdk_execution(config, provider="codex", model=config["model"], effort=config["effort"])


def test_selected_schema_requires_request_commitment():
    import jsonschema
    config = selected_sdk_config()
    del config["requestSha256"]
    validator = load_ledger_module().load_validator()
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(config, validator.AGENT_RUN_SCHEMA["properties"]["sdkExecution"])
    with pytest.raises(ValueError, match="sdkExecution"):
        validator.validate_sdk_execution(config, provider="codex", model=config["model"], effort=config["effort"])


def test_observed_version_schema_accepts_unpinned_build_and_epoch_metadata():
    import jsonschema
    config = {**SDK_CONFIG, "sdkVersion": "2!11.2.0+vendor", "runtimeVersion": "34.5.0-preview+build"}
    validator = load_ledger_module().load_validator()
    jsonschema.validate(config, validator.AGENT_RUN_SCHEMA["properties"]["sdkExecution"])
    assert validator.validate_sdk_execution(config, provider="codex", model=config["model"], effort=config["effort"]) == config
