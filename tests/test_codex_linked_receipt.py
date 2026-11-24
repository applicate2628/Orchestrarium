"""Receipt paths retain the existing global Codex storage authorities."""
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from _module_loading_support import load_module
from test_selected_claude_linked_physical import _link

ROOT = Path(__file__).resolve().parents[1]
installer = load_module(ROOT / "scripts/production_installer.py", "codex_linked_receipt_backend")
codec = load_module(ROOT / "scripts/installation/ownership.py", "codex_linked_receipt_codec")


@pytest.mark.parametrize("layout", [
    "separate", "nested-independent", "native-alias", "native-under-skills",
    "ordinary-contract-alias", "wrong-transaction",
])
def test_codex_linked_receipt_uses_only_disjoint_admitted_payloads(tmp_path, monkeypatch, layout):
    home = tmp_path / "home"
    target = home / ".codex"
    target.mkdir(parents=True)
    backing = target / "contracts" if layout == "ordinary-contract-alias" else tmp_path / "canonical"
    skill = backing / "skills/demo"
    skill.mkdir(parents=True)
    body = skill / "SKILL.md"
    body.write_bytes(b"owned skill\n")
    vendor = backing / "vendor.txt"
    vendor.write_bytes(b"protected vendor content\n")
    contract = backing / "contracts/example.json"
    contract.parent.mkdir()
    contract.write_bytes(b"{}\n")
    skill_receipt = backing / "skills" / installer._NONLEAD_RECEIPT_NAME
    skill_receipt.write_bytes(b"managed skill receipt\n")
    native = {
        "nested-independent": backing / "vendor-native",
        "native-alias": backing / "skills",
        "native-under-skills": backing / "skills/native",
    }.get(layout, tmp_path / "native")
    native.mkdir(parents=True, exist_ok=True)
    role = native / "worker.toml"
    role.write_bytes(b'name = "worker"\n')
    _link(home / ".agents", backing)
    _link(target / "agents", native)
    authority_type = installer._linked_runtime_subroots_module(ROOT).LinkedRuntimeSubrootAuthority
    canonical_authority = authority_type.bind(home / ".agents", scope="global", trusted_global_roots=(home / ".agents",))
    native_authority = authority_type.bind(target / "agents", scope="global", trusted_global_roots=(target / "agents",))
    prior = {".agents/skills/demo/SKILL.md": hashlib.sha256(body.read_bytes()).hexdigest(),
             ".agents/contracts/example.json": hashlib.sha256(contract.read_bytes()).hexdigest(),
             ".agents/skills/" + skill_receipt.name: hashlib.sha256(skill_receipt.read_bytes()).hexdigest(),
             ".codex/agents/worker.toml": hashlib.sha256(role.read_bytes()).hexdigest()}
    receipt = target / codec.RECEIPT_NAME
    before = codec.encode_record(prior, "codex", "global", configs={})
    receipt.write_bytes(before)
    plan = SimpleNamespace(skills=(SimpleNamespace(name="demo", managed_before=None),),
        nonlead_expected=(("demo", installer._stage_tree_manifest(skill)),), lead_receipt=None)
    monkeypatch.setattr(installer, "_capture_provider_configs", lambda *args: {})
    with installer._InstallTransaction([receipt, skill, contract, skill_receipt, role], enabled=True) as transaction:
        owner = installer._CreateOnlyMutablePath(home, transaction, dry_run=False)
        canonical_owner = installer._CreateOnlyMutablePath(backing, transaction,
            dry_run=False, linked_authority=canonical_authority)
        native_owner = installer._CreateOnlyMutablePath(native, transaction,
            dry_run=False, linked_authority=native_authority)
        if layout == "wrong-transaction":
            canonical_owner = installer._CreateOnlyMutablePath(backing,
                installer._InstallTransaction([], enabled=False), dry_run=False,
                linked_authority=canonical_authority)
        def record():
            installer._record_provider_install(ROOT, "codex", "global", target, home,
                transaction, owner, before.decode(), {}, target / "AGENTS.md", None,
                target / "hooks.json", backing / "skills/lead", False,
                canonical_plan=plan, canonical_target=backing / "skills",
                payload_owners=(canonical_owner, native_owner))
        if layout in {"separate", "nested-independent"}:
            record()
            received = codec.decode_record(receipt.read_bytes(), "codex", "global")
            assert received["files"] == prior
            assert ".agents/skills/demo" in received["directories"]
        else:
            with pytest.raises(ValueError, match="E_PROVIDER_RECEIPT_INVALID"):
                record()
            assert receipt.read_bytes() == before
        assert vendor.read_bytes() == b"protected vendor content\n"
        canonical_authority.assert_current()
        native_authority.assert_current()
        transaction.commit()
