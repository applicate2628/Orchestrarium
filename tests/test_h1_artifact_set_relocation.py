import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SUPPORT_PATH = ROOT / "tests" / "test_ledger_h1_activation_writer.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def artifact_set_digest(
    root: Path,
    *,
    base: Path | None = None,
    version: int = 2,
) -> str:
    members = (
        ("work-items/decision-h1-compatibility.json", "file"),
        ("work-items/legacy-ledger-projection-manifests", "directory"),
        ("work-items/legacy-ledger-projections.jsonl", "file"),
        ("work-items/legacy-ledger-projection-receipts", "directory"),
    )
    if version not in {1, 2}:
        raise ValueError(f"unsupported artifact-set digest version: {version}")
    physical_base = root / "work-items" if base is None else base
    rows = []
    for logical_path, kind in members:
        row = {"kind": kind, "logicalPath": logical_path}
        physical = physical_base / Path(logical_path).name
        if kind == "file":
            raw = physical.read_bytes()
            row.update({"byteLength": len(raw), "sha256": digest(raw)})
        elif version == 2:
            directory_rows = []
            for child in sorted(
                physical.iterdir(), key=lambda path: path.name.encode("utf-8")
            ):
                raw = child.read_bytes()
                directory_rows.append(
                    {
                        "name": child.name,
                        "byteLength": len(raw),
                        "sha256": digest(raw),
                    }
                )
            row.update(
                {
                    "byteLength": sum(
                        int(child["byteLength"]) for child in directory_rows
                    ),
                    "sha256": digest(
                        b"orchestrarium:ledger-h1-artifact-directory:v1\0"
                        + canonical(directory_rows)
                    ),
                }
            )
        rows.append(row)
    rows.sort(key=lambda row: str(row["logicalPath"]).encode("utf-8"))
    return digest(
        f"orchestrarium:ledger-h1-artifact-set:v{version}\0".encode("ascii")
        + canonical(rows)
    )


def prepare_relocation_request(root: Path, writer):
    archive_owner = root / "work-items" / "archive" / "2026-09" / "h1-owner"
    archive_owner.mkdir(parents=True)
    (archive_owner / "closure.md").write_text(
        "Closed: 2026-09-10T02:00:00Z\n"
        "Outcome: Synthetic H1 artifact owner.\n"
        "Residual risk: None in fixture.\n",
        encoding="utf-8",
    )
    root_contract = root / "work-items" / "root-contract.json"
    root_contract.write_text(
        json.dumps(
            {
                "schema": "work-items-root-contract",
                "version": 2,
                "auxiliaryRoots": {
                    "legacy-ledger-projection-manifests": {"kind": "flat-json"},
                    "legacy-ledger-projection-receipts": {"kind": "flat-json"},
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    request = writer.LedgerH1ArtifactSetRelocationRequestV1(
        archive_owner="work-items/archive/2026-09/h1-owner",
        expected_artifact_set_sha256=artifact_set_digest(root),
        expected_root_contract_sha256=digest(root_contract.read_bytes()),
        operation_id="relocate-h1-set-test",
        recorded_at="2026-09-10T03:00:00Z",
    )
    return request


def activated_relocation_fixture(root: Path):
    support = load_module(
        SUPPORT_PATH,
        f"h1_relocation_support_{id(root)}",
    )
    writer, reader, activation, items, paths = support.fixture(root)
    writer.apply_sealed_prefix_activation(root, activation)
    request = prepare_relocation_request(root, writer)
    return support, writer, reader, request, items, paths


def large_obligation_relocation_fixture(root: Path):
    support = load_module(
        SUPPORT_PATH,
        f"h1_large_relocation_support_{id(root)}",
    )
    reader_fixture = load_module(
        ROOT / "tests" / "test_ledger_h1_effective_view.py",
        f"h1_large_reader_fixture_{id(root)}",
    )
    reader = reader_fixture.load_validator()
    writer = load_module(
        ROOT / "scripts" / "mutate-work-item.py",
        f"h1_large_writer_{id(root)}",
    )
    paths = []
    entries = []
    reductions = []
    for slug, count in (("reader-a", 10), ("reader-b", 121)):
        item = root / "work-items" / "active" / slug
        item.mkdir(parents=True)
        (item / "target.md").write_text("synthetic artifact\n", encoding="utf-8")
        events = [
            reader_fixture.event(
                f"revise-{slug}-{index:03d}",
                slug,
                gate="REVISE",
                status="revise",
                artifact="target.md",
                findingClass="correctness",
            )
            for index in range(1, count + 1)
        ]
        raw = reader_fixture.ledger_bytes(events)
        ledger_path = f"work-items/active/{slug}/agent-runs.jsonl"
        (item / "agent-runs.jsonl").write_bytes(raw)
        view, reduction = reader_fixture.authority_view(
            ledger_path,
            raw,
            events,
            [
                reader_fixture.mask(
                    reviseTargetEligible=True,
                    artifactEvidenceEligible=True,
                )
                for _event in events
            ],
        )
        paths.append(ledger_path)
        reductions.append(reduction)
        entries.append(
            {
                "entryId": f"large-{slug}",
                "profileId": reader_fixture.PROFILE,
                "profileVersion": 1,
                "workItem": f"work-items/active/{slug}",
                "ledgerPath": ledger_path,
                "prefixLineCount": len(events),
                "prefixByteLength": len(raw),
                "prefixSha256": digest(raw),
                "projectedViewSha256": reader_fixture.domain_digest(
                    "orchestrarium:ledger-h1:projected-view:v1",
                    view,
                ),
            }
        )
    identities = sorted(
        (
            f"{entry['workItem'].split('/')[-1]}\0{run_id}"
            for entry, reduction in zip(entries, reductions)
            for run_id in reduction["openReviseRunIds"]
        ),
        key=lambda value: value.encode("utf-8"),
    )
    oracle = {
        "schemaVersion": 1,
        "ledgerPrefixes": [
            {
                "ledgerPath": entry["ledgerPath"],
                "prefixSha256": entry["prefixSha256"],
            }
            for entry in entries
        ],
        "openReviseIdentities": identities,
    }
    manifest_bytes = canonical(
        {
            "schemaVersion": 2,
            "manifestId": "large-h1-ledgers",
            "policyDecision": support.POLICY,
            "profiles": [
                {
                    "profileId": reader_fixture.PROFILE,
                    "profileVersion": 1,
                }
            ],
            "entries": entries,
            "openReviseIdentitySha256": digest(
                "\n".join(identities).encode("utf-8")
            ),
            "openReviseOracleSha256": reader_fixture.domain_digest(
                "orchestrarium:ledger-h1:open-revise-oracle:v1",
                oracle,
            ),
        }
    ) + b"\n"
    activation = writer.SealedPrefixActivationRequestV1(
        h1_manifest_path="work-items/decision-h1-compatibility.json",
        h1_manifest_bytes=support.h1_manifest(root),
        ledger_manifest_path=(
            "work-items/legacy-ledger-projection-manifests/large-h1-ledgers.json"
        ),
        ledger_manifest_bytes=manifest_bytes,
        expected_registry_sha256=digest(b""),
        recorded_at="2026-09-10T02:30:00Z",
    )
    writer.apply_sealed_prefix_activation(root, activation)
    request = prepare_relocation_request(root, writer)
    return writer, reader, request, tuple(paths)


def artifact_member_bytes(base: Path) -> dict[str, bytes]:
    captured: dict[str, bytes] = {}
    for logical_path, _kind in (
        ("decision-h1-compatibility.json", "file"),
        ("legacy-ledger-projection-manifests", "directory"),
        ("legacy-ledger-projections.jsonl", "file"),
        ("legacy-ledger-projection-receipts", "directory"),
    ):
        member = base / logical_path
        if member.is_file():
            captured[logical_path] = member.read_bytes()
        else:
            for child in sorted(member.iterdir(), key=lambda path: path.name):
                captured[f"{logical_path}/{child.name}"] = child.read_bytes()
    return captured


def test_relocate_h1_set_defaults_to_non_mutating_preflight(tmp_path: Path) -> None:
    root = tmp_path / "preflight"
    support, writer, _reader, request, _items, _paths = (
        activated_relocation_fixture(root)
    )
    before = support.tree_state(root)

    result = writer.relocate_ledger_h1_artifact_set(root, request)

    assert isinstance(result, dict)
    assert support.tree_state(root) == before


def test_h1_v2_digest_rejects_directory_member_drift_before_intent(
    tmp_path: Path,
) -> None:
    root = tmp_path / "directory-content"
    support, writer, _reader, request, _items, _paths = activated_relocation_fixture(
        root
    )

    ready = writer.relocate_ledger_h1_artifact_set(root, request)
    assert ready["artifactSetSha256"] == request.expected_artifact_set_sha256
    manifests = root / "work-items" / "legacy-ledger-projection-manifests"
    member = sorted(manifests.iterdir(), key=lambda path: path.name.encode("utf-8"))[0]
    before = member.read_bytes()
    assert before.endswith(b"\n")
    member.write_bytes(before[:-1] + b" ")
    assert artifact_set_digest(root) != request.expected_artifact_set_sha256
    drifted_tree = support.tree_state(root)

    with pytest.raises(writer.LifecycleError) as rejected:
        writer.relocate_ledger_h1_artifact_set(root, request)

    assert rejected.value.failure_id == "WI-LEDGER-COMPAT-SET-TOPOLOGY"
    assert support.tree_state(root) == drifted_tree


def test_relocation_digest_inputs_are_case_normalized_and_exact(
    tmp_path: Path,
) -> None:
    root = tmp_path / "digest-case"
    support, writer, _reader, request, _items, _paths = activated_relocation_fixture(
        root
    )
    before = support.tree_state(root)
    mixed_artifact = "".join(
        character.upper() if index % 2 else character
        for index, character in enumerate(request.expected_artifact_set_sha256)
    )
    equivalent = replace(
        request,
        expected_artifact_set_sha256=mixed_artifact,
        expected_root_contract_sha256=request.expected_root_contract_sha256.upper(),
    )

    writer.relocate_ledger_h1_artifact_set(root, equivalent)

    assert support.tree_state(root) == before
    for invalid in (
        replace(request, expected_artifact_set_sha256="g" * 64),
        replace(request, expected_root_contract_sha256="0" * 64),
    ):
        with pytest.raises(writer.LifecycleError) as rejected:
            writer.relocate_ledger_h1_artifact_set(root, invalid)
        assert rejected.value.failure_id == "WI-LEDGER-COMPAT-SET-TOPOLOGY"
        assert support.tree_state(root) == before
    applied = writer.relocate_ledger_h1_artifact_set(
        root,
        equivalent,
        apply=True,
    )
    replay = writer.relocate_ledger_h1_artifact_set(root, request, apply=True)
    assert applied["artifactSetSha256"] == request.expected_artifact_set_sha256
    assert replay["replay"] is True


def test_selector_ignores_unrelated_legacy_projection_roots(tmp_path: Path) -> None:
    root = tmp_path / "unrelated-v1"
    work_items = root / "work-items"
    manifests = work_items / "legacy-ledger-projection-manifests"
    receipts = work_items / "legacy-ledger-projection-receipts"
    manifests.mkdir(parents=True)
    receipts.mkdir()
    (manifests / "unrelated.json").write_bytes(b'{"schemaVersion":1}\n')
    (work_items / "legacy-ledger-projections.jsonl").write_bytes(
        b'{"operationId":"unrelated-v1"}\n'
    )
    (receipts / "unrelated.json").write_bytes(b'{"schemaVersion":1}\n')
    writer = load_module(
        ROOT / "scripts" / "mutate-work-item.py",
        f"unrelated_v1_writer_{id(root)}",
    )
    reader_fixture = load_module(
        ROOT / "tests" / "test_ledger_h1_effective_view.py",
        f"unrelated_v1_reader_fixture_{id(root)}",
    )
    reader = reader_fixture.load_validator()

    assert writer.resolve_ledger_h1_artifact_set_location(root) is None
    assert reader._ledger_h1_live_participants_exist(root) is False


def test_relocate_h1_set_preserves_bytes_paths_and_views(tmp_path: Path) -> None:
    root = tmp_path / "preservation"
    _support, writer, reader, request, _items, paths = activated_relocation_fixture(
        root
    )
    root_base = root / "work-items"
    expected_bytes = artifact_member_bytes(root_base)
    before_contexts = reader._load_effective_ledger_group(root)
    before_views = {path: before_contexts[path].view for path in paths}

    result = writer.relocate_ledger_h1_artifact_set(root, request, apply=True)

    target_base = (
        root
        / "work-items"
        / "archive"
        / "2026-09"
        / "h1-owner"
        / "ledger-h1-compatibility"
    )
    assert result["event"] == "WI-LEDGER-H1-ARTIFACT-SET-RELOCATED"
    assert result["applied"] is True
    assert result["replay"] is False
    assert artifact_member_bytes(target_base) == expected_bytes
    assert not (root_base / "decision-h1-compatibility.json").exists()
    assert not (root_base / "legacy-ledger-projection-manifests").exists()
    assert not (root_base / "legacy-ledger-projections.jsonl").exists()
    assert not (root_base / "legacy-ledger-projection-receipts").exists()
    assert not (root_base / "root-contract.json").exists()
    receipt = json.loads((target_base / "relocation-receipt.json").read_bytes())
    assert receipt == {
        "schemaVersion": 2,
        "status": "settled",
        "operationId": request.operation_id,
        "archiveOwner": request.archive_owner,
        "artifactBase": (
            "work-items/archive/2026-09/h1-owner/ledger-h1-compatibility"
        ),
        "artifactSetSha256": request.expected_artifact_set_sha256,
        "rootContractBeforeSha256": request.expected_root_contract_sha256,
        "rootContractAfterSha256": None,
        "recordedAt": request.recorded_at,
    }
    location = writer.resolve_ledger_h1_artifact_set_location(root)
    assert location.physical_base == receipt["artifactBase"]
    assert location.phase == "settled-archive"
    artifacts = reader._load_live_ledger_h1_artifacts(root)
    assert artifacts.h1_manifest_path == "work-items/decision-h1-compatibility.json"
    assert artifacts.ledger_manifest_path.startswith(
        "work-items/legacy-ledger-projection-manifests/"
    )
    assert all(
        path.startswith("work-items/legacy-ledger-projection-receipts/")
        for path in artifacts.receipt_bytes_by_path
    )
    after_contexts = reader._load_effective_ledger_group(root)
    assert {path: after_contexts[path].view for path in paths} == before_views


def test_h1_v1_receipt_is_immutable_but_replay_requires_current_v2_digest(
    tmp_path: Path,
) -> None:
    root = tmp_path / "legacy-receipt"
    _support, writer, _reader, request, _items, _paths = activated_relocation_fixture(
        root
    )
    writer.relocate_ledger_h1_artifact_set(root, request, apply=True)
    target_base = (
        root
        / "work-items"
        / "archive"
        / "2026-09"
        / "h1-owner"
        / "ledger-h1-compatibility"
    )
    receipt_path = target_base / "relocation-receipt.json"
    legacy_digest = artifact_set_digest(root, base=target_base, version=1)
    legacy_receipt = json.loads(receipt_path.read_bytes())
    legacy_receipt["schemaVersion"] = 1
    legacy_receipt["artifactSetSha256"] = legacy_digest
    legacy_bytes = json.dumps(
        legacy_receipt, ensure_ascii=False, indent=2, sort_keys=True
    ).encode("utf-8") + b"\n"
    receipt_path.write_bytes(legacy_bytes)

    location = writer.resolve_ledger_h1_artifact_set_location(root)
    replay = writer.relocate_ledger_h1_artifact_set(root, request, apply=True)

    assert location is not None
    assert location.artifact_set_sha256 == request.expected_artifact_set_sha256
    assert replay["artifactSetSha256"] == request.expected_artifact_set_sha256
    assert replay["replay"] is True
    assert receipt_path.read_bytes() == legacy_bytes
    with pytest.raises(writer.LifecycleError) as rejected:
        writer.relocate_ledger_h1_artifact_set(
            root,
            replace(request, expected_artifact_set_sha256=legacy_digest),
            apply=True,
        )
    assert rejected.value.failure_id == "WI-LEDGER-COMPAT-SET-TOPOLOGY"


def test_relocation_removes_only_h1_root_contract_declarations(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root-contract"
    _support, writer, _reader, request, _items, _paths = activated_relocation_fixture(
        root
    )
    contract_path = root / "work-items" / "root-contract.json"
    contract = json.loads(contract_path.read_bytes())
    contract["auxiliaryRoots"]["repair-receipts"] = {"kind": "flat-json"}
    contract_path.write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    request = replace(
        request,
        expected_root_contract_sha256=digest(contract_path.read_bytes()),
    )

    writer.relocate_ledger_h1_artifact_set(root, request, apply=True)

    assert json.loads(contract_path.read_bytes()) == {
        "schema": "work-items-root-contract",
        "version": 2,
        "auxiliaryRoots": {"repair-receipts": {"kind": "flat-json"}},
    }


def test_h1_reader_accepts_exactly_one_complete_root_or_archive(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root-or-archive"
    _support, writer, reader, request, _items, paths = activated_relocation_fixture(
        root
    )
    root_contexts = reader._load_effective_ledger_group(root)

    writer.relocate_ledger_h1_artifact_set(root, request, apply=True)
    archive_contexts = reader._load_effective_ledger_group(root)

    assert set(root_contexts) == set(paths)
    assert set(archive_contexts) == set(paths)
    assert {
        path: archive_contexts[path].view for path in paths
    } == {path: root_contexts[path].view for path in paths}


def test_relocated_h1_set_preserves_obligation_identities(tmp_path: Path) -> None:
    root = tmp_path / "obligations"
    support = load_module(
        SUPPORT_PATH,
        f"h1_relocation_obligation_support_{id(root)}",
    )
    writer, reader, _items, paths, _archive_receipt = (
        support.archive_first_activated_h1_member(root)
    )
    request = prepare_relocation_request(root, writer)
    operation_id = "h1-relocation-member-a"
    before_errors = []
    before_receipts = reader._transfer_receipts(root, before_errors)
    before_obligation = before_receipts[operation_id][1]["obligations"][0]
    before = reader._resolve_transferred_obligation(
        root,
        before_receipts,
        operation_id,
        before_obligation,
        before_errors,
        frozenset(),
    )
    assert before_errors == []
    assert before is not None
    before_identity = (
        before.event.get("runId"),
        before.raw_line_ordinal,
        before.raw_line_sha256,
        before.raw_event_sha256,
        before.obligation_id,
    )

    writer.relocate_ledger_h1_artifact_set(root, request, apply=True)

    after_errors = []
    after_receipts = reader._transfer_receipts(root, after_errors)
    after = reader._resolve_transferred_obligation(
        root,
        after_receipts,
        operation_id,
        after_receipts[operation_id][1]["obligations"][0],
        after_errors,
        frozenset(),
    )
    assert after_errors == before_errors
    assert after is not None
    assert (
        after.event.get("runId"),
        after.raw_line_ordinal,
        after.raw_line_sha256,
        after.raw_event_sha256,
        after.obligation_id,
    ) == before_identity
    contexts = reader._load_effective_ledger_group(root)
    assert set(contexts) == set(paths)


def test_relocated_h1_set_preserves_10_plus_121_fixture_cardinality(
    tmp_path: Path,
) -> None:
    root = tmp_path / "large-obligations"
    writer, reader, request, paths = large_obligation_relocation_fixture(root)
    before = reader._load_effective_ledger_group(root)
    before_identities = before[paths[0]].group_open_revise_ids
    assert len(before_identities) == 10 + 121
    assert len(set(before_identities)) == 10 + 121

    writer.relocate_ledger_h1_artifact_set(root, request, apply=True)

    after = reader._load_effective_ledger_group(root)
    assert after[paths[0]].group_open_revise_ids == before_identities


def test_relocate_h1_set_rejects_partial_dual_and_second_archive(
    tmp_path: Path,
) -> None:
    partial_root = tmp_path / "partial"
    partial_support, partial_writer, _reader, partial_request, _items, _paths = (
        activated_relocation_fixture(partial_root)
    )
    (partial_root / "work-items" / "legacy-ledger-projections.jsonl").unlink()
    partial_before = partial_support.tree_state(partial_root)
    with pytest.raises(partial_writer.LifecycleError) as partial:
        partial_writer.relocate_ledger_h1_artifact_set(partial_root, partial_request)
    assert partial.value.failure_id == "WI-LEDGER-COMPAT-SET-TOPOLOGY"
    assert partial_support.tree_state(partial_root) == partial_before

    mixed_root = tmp_path / "mixed"
    _support, mixed_writer, _reader, _request, _items, _paths = (
        activated_relocation_fixture(mixed_root)
    )
    mixed_target = (
        mixed_root
        / "work-items"
        / "archive"
        / "2026-09"
        / "h1-owner"
        / "ledger-h1-compatibility"
    )
    mixed_target.mkdir()
    os.replace(
        mixed_root / "work-items" / "decision-h1-compatibility.json",
        mixed_target / "decision-h1-compatibility.json",
    )
    with pytest.raises(mixed_writer.LifecycleError) as mixed:
        mixed_writer.resolve_ledger_h1_artifact_set_location(mixed_root)
    assert mixed.value.failure_id == "WI-LEDGER-COMPAT-SET-TOPOLOGY"

    duplicate_root = tmp_path / "duplicate"
    _support, duplicate_writer, _reader, duplicate_request, _items, _paths = (
        activated_relocation_fixture(duplicate_root)
    )
    duplicate_writer.relocate_ledger_h1_artifact_set(
        duplicate_root,
        duplicate_request,
        apply=True,
    )
    first = (
        duplicate_root
        / "work-items"
        / "archive"
        / "2026-09"
        / "h1-owner"
        / "ledger-h1-compatibility"
    )
    second_owner = (
        duplicate_root / "work-items" / "archive" / "2026-09" / "second-owner"
    )
    second_owner.mkdir()
    shutil.copytree(first, second_owner / "ledger-h1-compatibility")
    with pytest.raises(duplicate_writer.LifecycleError) as duplicate:
        duplicate_writer.resolve_ledger_h1_artifact_set_location(duplicate_root)
    assert duplicate.value.failure_id == "WI-LEDGER-COMPAT-SET-TOPOLOGY"


def test_selector_rejects_nonexact_receipt_as_set_topology(tmp_path: Path) -> None:
    root = tmp_path / "receipt"
    _support, writer, _reader, request, _items, _paths = activated_relocation_fixture(
        root
    )
    writer.relocate_ledger_h1_artifact_set(root, request, apply=True)
    receipt = (
        root
        / "work-items"
        / "archive"
        / "2026-09"
        / "h1-owner"
        / "ledger-h1-compatibility"
        / "relocation-receipt.json"
    )
    receipt.write_bytes(b'{"schemaVersion":1,"schemaVersion":1}\n')

    with pytest.raises(writer.LifecycleError) as rejected:
        writer.resolve_ledger_h1_artifact_set_location(root)

    assert rejected.value.failure_id == "WI-LEDGER-COMPAT-SET-TOPOLOGY"


def test_selector_requires_persistent_archived_owner_identity(tmp_path: Path) -> None:
    root = tmp_path / "owner-identity"
    _support, writer, _reader, request, _items, _paths = activated_relocation_fixture(
        root
    )
    writer.relocate_ledger_h1_artifact_set(root, request, apply=True)
    owner = root.joinpath(*request.archive_owner.split("/"))
    (owner / "closure.md").unlink()

    with pytest.raises(writer.LifecycleError) as rejected:
        writer.resolve_ledger_h1_artifact_set_location(root)

    assert rejected.value.failure_id == "WI-LEDGER-COMPAT-SET-TOPOLOGY"


def test_preflight_rejects_noncalendar_archive_month(tmp_path: Path) -> None:
    root = tmp_path / "archive-month"
    support, writer, _reader, request, _items, _paths = activated_relocation_fixture(
        root
    )
    original = root.joinpath(*request.archive_owner.split("/"))
    invalid = root / "work-items" / "archive" / "2026-13" / "h1-owner"
    invalid.parent.mkdir()
    os.replace(original, invalid)
    request = replace(
        request,
        archive_owner="work-items/archive/2026-13/h1-owner",
    )
    before = support.tree_state(root)

    with pytest.raises(writer.LifecycleError) as rejected:
        writer.relocate_ledger_h1_artifact_set(root, request)

    assert rejected.value.failure_id == "WI-LEDGER-COMPAT-SET-TOPOLOGY"
    assert support.tree_state(root) == before


@pytest.mark.parametrize(
    "boundary",
    (
        "after-intent",
        "after-member-1",
        "after-member-2",
        "after-member-3",
        "after-member-4",
        "after-root-contract",
    ),
)
def test_relocation_failure_boundaries_restore_contract_and_members(
    tmp_path: Path,
    boundary: str,
) -> None:
    root = tmp_path / boundary
    support, writer, _reader, request, _items, _paths = activated_relocation_fixture(
        root
    )
    before = support.tree_state(root)

    with pytest.raises(writer.LifecycleError) as failed:
        writer.relocate_ledger_h1_artifact_set(
            root,
            request,
            apply=True,
            inject_failure=boundary,
        )

    assert failed.value.failure_id == "WI-LEDGER-COMPAT-COMMIT-INDETERMINATE"
    assert support.tree_state(root) == before
    assert writer.resolve_ledger_h1_artifact_set_location(root).phase == "root"


def test_relocate_h1_set_replay_is_exact(tmp_path: Path) -> None:
    root = tmp_path / "replay"
    support, writer, _reader, request, _items, _paths = activated_relocation_fixture(
        root
    )
    plan = writer._ledger_h1_relocation_preflight(root, request)
    intent = writer._ledger_h1_relocation_intent(plan, request)
    intent_path = writer._transition_intent_path(root, request.operation_id)
    intent_path.parent.mkdir(parents=True, exist_ok=True)
    writer._atomic_write(intent_path, writer._migration_receipt_bytes(intent))
    plan.artifact_base.mkdir()
    for member in plan.members[:2]:
        os.replace(
            root.joinpath(*str(member["sourcePath"]).split("/")),
            root.joinpath(*str(member["targetPath"]).split("/")),
        )

    recovered = writer.relocate_ledger_h1_artifact_set(root, request, apply=True)
    settled = support.tree_state(root)
    replay = writer.relocate_ledger_h1_artifact_set(root, request, apply=True)

    assert recovered["event"] == "WI-LEDGER-H1-ARTIFACT-SET-RELOCATED"
    assert replay["replay"] is True
    assert support.tree_state(root) == settled
    changed = replace(request, recorded_at="2026-09-10T03:00:01Z")
    with pytest.raises(writer.LifecycleError) as mismatch:
        writer.relocate_ledger_h1_artifact_set(root, changed, apply=True)
    assert mismatch.value.failure_id == "WI-LEDGER-COMPAT-SET-TOPOLOGY"
    assert support.tree_state(root) == settled


def test_post_receipt_failure_never_reverses_and_replay_settles(
    tmp_path: Path,
) -> None:
    root = tmp_path / "post-receipt"
    support, writer, _reader, request, _items, _paths = activated_relocation_fixture(
        root
    )

    with pytest.raises(writer.LifecycleError) as interrupted:
        writer.relocate_ledger_h1_artifact_set(
            root,
            request,
            apply=True,
            inject_failure="after-receipt",
        )

    assert interrupted.value.failure_id == "WI-LEDGER-COMPAT-COMMIT-INDETERMINATE"
    settled = support.tree_state(root)
    assert not (root / "work-items" / "decision-h1-compatibility.json").exists()
    replay = writer.relocate_ledger_h1_artifact_set(root, request, apply=True)
    assert replay["replay"] is True
    assert support.tree_state(root) == settled
    assert not writer._transition_intent_path(root, request.operation_id).exists()


def test_relocation_cli_requires_positive_apply(tmp_path: Path) -> None:
    root = tmp_path / "cli"
    support, _writer, _reader, request, _items, _paths = activated_relocation_fixture(
        root
    )
    common = [
        sys.executable,
        "-B",
        str(ROOT / "scripts" / "mutate-work-item.py"),
        "relocate-ledger-h1-artifact-set",
        "--root",
        str(root),
        "--archive-owner",
        request.archive_owner,
        "--expected-artifact-set-sha256",
        request.expected_artifact_set_sha256,
        "--expected-root-contract-sha256",
        request.expected_root_contract_sha256,
        "--operation-id",
        request.operation_id,
        "--recorded-at",
        request.recorded_at,
    ]
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    before = support.tree_state(root)

    preflight = subprocess.run(
        common,
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert preflight.returncode == 0, preflight.stdout
    assert support.tree_state(root) == before

    applied = subprocess.run(
        [*common, "--apply"],
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert applied.returncode == 0, applied.stdout
    assert "WI-LEDGER-H1-ARTIFACT-SET-RELOCATED" in applied.stdout
