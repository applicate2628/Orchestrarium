from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ROOT_OWNER = ROOT / "scripts" / "provider_prompt.py"
CLAUDE_SCRIPTS = ROOT / "src.claude" / "agents" / "scripts"


def test_root_is_the_only_authored_transport_owner() -> None:
    assert ROOT_OWNER.is_file()
    assert not (CLAUDE_SCRIPTS / "provider_prompt.py").exists()


def test_codex_and_claude_host_wrappers_remain_thin_adjacent_consumers() -> None:
    for provider in ("codex", "claude"):
        python_wrapper = CLAUDE_SCRIPTS / f"invoke-{provider}-prompt.py"
        shell_wrapper = CLAUDE_SCRIPTS / f"invoke-{provider}-prompt.sh"
        assert python_wrapper.is_file()
        assert shell_wrapper.is_file()
        python_text = python_wrapper.read_text(encoding="utf-8")
        assert "from provider_prompt import launch" in python_text
        assert f'launch("{provider}", sys.argv[1:])' in python_text
        assert "provider_prompt.py" not in shell_wrapper.read_text(encoding="utf-8")


def _load_owner(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_role_taxonomy_rejects_a_malicious_cwd_resolver_before_secret_or_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the exact sibling is a trust input; cwd is never a resolver fallback."""

    owner = _load_owner(ROOT_OWNER, "provider_prompt_taxonomy_cwd")
    malicious = tmp_path / "cwd" / "scripts" / "resolve-agents-mode.py"
    malicious.parent.mkdir(parents=True)
    marker = tmp_path / "resolver-side-effect"
    malicious.write_text(
        "from pathlib import Path\n"
        "import os\n"
        f"Path({str(marker)!r}).write_text(os.environ['TAXONOMY_SECRET'])\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(owner, "__file__", str(tmp_path / "isolated" / "provider_prompt.py"))
    monkeypatch.chdir(malicious.parent.parent)
    monkeypatch.setenv("TAXONOMY_SECRET", "must-not-be-read")
    monkeypatch.setattr(
        owner.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no process")),
    )

    with pytest.raises(ValueError, match="^E_EXTERNAL_PROVENANCE_ROLE_INVALID: role taxonomy"):
        owner.external_role_provenance(
            owner.Control(ledger_role="qa-engineer", ledger_role_explicit=True), "codex"
        )

    assert not marker.exists()


def test_role_taxonomy_rejects_malformed_or_linked_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner(ROOT_OWNER, "provider_prompt_taxonomy_degraded")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    sibling = scripts / "external-role-taxonomy.v1.json"
    sibling.write_text('{"schemaVersion": 1, "roles": {}}\n', encoding="utf-8")
    monkeypatch.setattr(owner, "__file__", str(scripts / "provider_prompt.py"))

    with pytest.raises(
        ValueError, match="^E_EXTERNAL_PROVENANCE_ROLE_TAXONOMY_INTEGRITY$"
    ):
        owner._external_role_taxonomy()

    linked = scripts / "linked-taxonomy.json"
    linked.write_bytes((ROOT / "shared" / "external-role-taxonomy.v1.json").read_bytes())
    sibling.unlink()
    try:
        sibling.symlink_to(linked)
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    with pytest.raises(ValueError, match="^E_EXTERNAL_PROVENANCE_ROLE_INVALID: role taxonomy"):
        owner._external_role_taxonomy()


def test_role_taxonomy_loads_only_the_structured_sibling_taxonomy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner(ROOT_OWNER, "provider_prompt_taxonomy_attested")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    sibling = scripts / "external-role-taxonomy.v1.json"
    payload = (ROOT / "shared" / "external-role-taxonomy.v1.json").read_bytes()
    sibling.write_bytes(payload)
    monkeypatch.setattr(owner, "__file__", str(scripts / "provider_prompt.py"))

    roles, reviewers, workers, unsupported = owner._external_role_taxonomy()

    assert "qa-engineer" in roles
    assert "frontend-engineer" in roles
    assert "qa-engineer" in reviewers
    assert workers
    assert unsupported == {
        "product-manager",
        "lead",
        "knowledge-archivist",
        "external-worker",
        "external-reviewer",
    }


@pytest.mark.parametrize("mutation", ("lane", "whitespace"))
def test_role_taxonomy_rejects_schema_valid_byte_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    owner = _load_owner(ROOT_OWNER, f"provider_prompt_taxonomy_drift_{mutation}")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    payload = (ROOT / "shared" / "external-role-taxonomy.v1.json").read_bytes()
    if mutation == "lane":
        payload = payload.replace(b'"external-worker"', b'"external-reviewer"', 1)
    else:
        payload += b"\n"
    (scripts / "external-role-taxonomy.v1.json").write_bytes(payload)
    monkeypatch.setattr(owner, "__file__", str(scripts / "provider_prompt.py"))

    with pytest.raises(
        ValueError,
        match="^E_EXTERNAL_PROVENANCE_ROLE_TAXONOMY_INTEGRITY$",
    ):
        owner._external_role_taxonomy()


def test_roleless_provenance_still_attests_taxonomy_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner(ROOT_OWNER, "provider_prompt_taxonomy_roleless_drift")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    payload = (ROOT / "shared" / "external-role-taxonomy.v1.json").read_bytes() + b"\n"
    (scripts / "external-role-taxonomy.v1.json").write_bytes(payload)
    monkeypatch.setattr(owner, "__file__", str(scripts / "provider_prompt.py"))

    with pytest.raises(
        ValueError,
        match="^E_EXTERNAL_PROVENANCE_ROLE_TAXONOMY_INTEGRITY$",
    ):
        owner.external_role_provenance(owner.Control(), "claude")


def test_packed_capsule_view_needs_manifest_and_digest_not_shared_agents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack_root = tmp_path / ".agents" / "skills"
    scripts = pack_root / "lead" / "scripts"
    scripts.mkdir(parents=True)
    (pack_root / "shared").mkdir()
    for name in (
        "provider_prompt.py",
        "external-prompt-governance.md",
        "external-role-taxonomy.v1.json",
    ):
        source = ROOT / (
            "shared"
            if name in {"external-prompt-governance.md", "external-role-taxonomy.v1.json"}
            else "scripts"
        ) / name
        (scripts / name).write_bytes(source.read_bytes())
    (pack_root / "shared" / "provider-prompt-projections.v1.json").write_bytes(
        (ROOT / "shared" / "provider-prompt-projections.v1.json").read_bytes()
    )
    owner = _load_owner(scripts / "provider_prompt.py", "provider_prompt_packed_view")
    monkeypatch.setattr(
        owner.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no process")),
    )

    assert owner.external_governance_capsule_snapshot() == (
        ROOT / "shared" / "external-prompt-governance.md"
    ).read_bytes()
    assert owner.launch("kimi", ["ignored-invalid-input"]) == 1
