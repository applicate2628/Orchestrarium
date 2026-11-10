"""Exact modified-Lead selection and real canonical-owner regressions.

The physical cases use synthetic Windows homes and the real stage, plan,
transaction and finalizer. They do not launch a public installer, provider,
model, hook, network client or a subprocess. POSIX mutation holds are not
patched out; physical cases skip there. Reentry is a separate transaction in
the same process, not a claim of separate-process/public-entrypoint receiving.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
ERROR = "E_CANONICAL_LEAD_SELECTION_INVALID"
RECEIPT = ".orchestrarium-lead-receipt.v1.json"
DIGESTS = ("1" * 64, "2" * 64, "3" * 64)
TOKEN = "v1:" + ":".join(DIGESTS)
def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def parse():
    return _load(
        "modified_lead_selection_contract", "scripts/installation/lead_selection.py"
    ).parse_modified_lead_selection


def test_empty_and_exact_selection(parse):
    assert parse(()) is None
    values = (TOKEN,)
    assert parse(values) == DIGESTS
    assert values == (TOKEN,)


@pytest.mark.parametrize("values", [
    None, [], TOKEN, {"value": TOKEN}, (None,), (True,), (b"token",),
    (TOKEN, TOKEN), ("",), ("v2:" + ":".join(DIGESTS),),
    (":".join(DIGESTS),), (TOKEN + ":extra",),
    (TOKEN + "\n",), (" " + TOKEN,), (TOKEN + " ",),
    ("v1:" + ":".join(("A" * 64, *DIGESTS[1:])),),
    ("v1:" + ":".join(("g" * 64, *DIGESTS[1:])),),
    ("v1:" + ":".join(("1" * 63, *DIGESTS[1:])),),
    ("v1:" + ":".join(("1" * 65, *DIGESTS[1:])),),
    ("v1:" + ":".join((DIGESTS[0], "2" * 63, DIGESTS[2])),),
    ("v1:" + ":".join((DIGESTS[0], DIGESTS[1], "３" * 64)),),
])
def test_selection_has_strict_versioned_single_value_grammar(parse, values):
    with pytest.raises(ValueError, match=ERROR):
        parse(values)


@pytest.mark.parametrize("provider", ["codex", "claude"])
def test_public_parser_retains_each_explicit_occurrence(provider, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    installer = _load("modified_lead_cli_contract", "scripts/production_installer.py")
    args = installer._parser(provider).parse_args([
        "--global", "--replace-modified-lead", TOKEN,
    ])
    assert args.replace_modified_lead == [TOKEN]
    duplicate = installer._parser(provider).parse_args([
        "--global", "--replace-modified-lead", TOKEN,
        "--replace-modified-lead", TOKEN,
    ])
    with pytest.raises(ValueError, match=ERROR):
        installer._parse_modified_lead_selection(tuple(duplicate.replace_modified_lead))
    assert installer._parser(provider).parse_args([]).replace_modified_lead == []


def _bytes_tree(root: Path) -> dict[str, bytes | None]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None
        for path in sorted(root.rglob("*"))
    }


@pytest.fixture
def state(tmp_path, monkeypatch):
    if os.name != "nt":
        pytest.skip("Real canonical mutation uses the admitted Windows backend")
    home = tmp_path / "home"
    temporary = tmp_path / "temp"
    home.mkdir()
    temporary.mkdir()
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(home))
    for name in ("TEMP", "TMP", "TMPDIR"):
        monkeypatch.setenv(name, str(temporary))
    monkeypatch.setenv("LOCALAPPDATA", str(home / "AppData" / "Local"))
    monkeypatch.setenv("APPDATA", str(home / "AppData" / "Roaming"))
    monkeypatch.setattr(tempfile, "tempdir", str(temporary))
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.syspath_prepend(str(ROOT))
    installer = _load("modified_lead_installer_contract", "scripts/production_installer.py")

    def no_process(*_args, **_kwargs):
        raise AssertionError("These helper tests must not launch subprocesses")

    monkeypatch.setattr(installer.subprocess, "Popen", no_process)
    source = tmp_path / "source"
    source.mkdir()
    shutil.copytree(
        ROOT / "src.codex" / "skills" / "lead", source / "lead",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    skills = home / ".agents" / "skills"
    skills.mkdir(parents=True)
    stage = installer._stage_canonical_lead_tree(
        ROOT, source / "lead", skills / "lead" / "scripts"
    )
    try:
        shutil.copytree(stage.path, skills / "lead")
        (skills / RECEIPT).write_bytes(installer._lead_receipt_bytes(stage.digest))
    finally:
        shutil.rmtree(stage.path)
    assert json.loads((skills / RECEIPT).read_bytes())["schema"] == (
        "orchestrarium.canonical-lead-install.v2"
    )
    return SimpleNamespace(
        installer=installer, source=source, home=home, skills=skills,
        lead=skills / "lead", receipt=skills / RECEIPT, temporary=temporary,
    )


def _customize(state, *, also_source=False):
    suffix = b"\n<!-- synthetic local Goal correction -->\n"
    target = state.lead / "SKILL.md"
    target.write_bytes(target.read_bytes() + suffix)
    if also_source:
        source = state.source / "lead" / "SKILL.md"
        source.write_bytes(source.read_bytes() + suffix)


def _selection(state):
    installer = state.installer
    stage = installer._stage_canonical_lead_tree(
        ROOT, state.source / "lead", state.lead / "scripts"
    )
    try:
        triple = (
            hashlib.sha256(state.receipt.read_bytes()).hexdigest(),
            installer._tree_sha256(state.lead, ignore_runtime_cache=True),
            stage.digest,
        )
        assert all(type(value) is str for value in triple)
        return "v1:" + ":".join(triple)
    finally:
        shutil.rmtree(stage.path)


@contextmanager
def _plan(state, *, selection=True, **kwargs):
    values = (_selection(state),) if selection is True else selection
    plan = state.installer._preflight_canonical_skills(
        state.source, state.skills, root=ROOT, global_install=True,
        replace_modified_lead=values, **kwargs,
    )
    try:
        yield plan
    finally:
        state.installer._discard_canonical_skills_plan(plan)


def _apply(state, plan, *, fail_after=None, reclaim=None):
    installer = state.installer
    with installer._InstallTransaction([state.skills], enabled=True) as transaction:
        owner = installer._CreateOnlyMutablePath(
            state.home, transaction, dry_run=False
        )
        installer._apply_canonical_skills_plan(
            plan, state.skills, owner, root=ROOT
        )
        if fail_after == "tree":
            raise RuntimeError("controlled exception after tree replacement")
        reclaimed = ()
        if reclaim is not None:
            path = state.lead / reclaim
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            owner.remove_exact_file(path.relative_to(state.home), digest)
            reclaimed = ((path, digest),)
        installer._finalize_canonical_lead_receipt(
            plan, state.skills, owner, reclaimed
        )
        if fail_after == "receipt":
            raise RuntimeError("controlled exception after receipt finalization")
        transaction.commit()


def test_normal_drift_refuses_and_emits_nonauthorizing_selection(state, capsys):
    _customize(state)
    expected = _selection(state)
    before = _bytes_tree(state.skills)
    capsys.readouterr()
    with pytest.raises(ValueError, match="E_CANONICAL_LEAD_RECEIPT_DRIFT"):
        with _plan(state, selection=()):
            pytest.fail("A diagnostic must not authorize mutation")
    output = capsys.readouterr().out
    assert expected in re.findall(r"v1:(?:[0-9a-f]{64}:){2}[0-9a-f]{64}", output)
    assert re.search(r"non.?authoriz|not authorization|does not authorize|not approval", output, re.I)
    assert "SKILL.md" in output
    assert _bytes_tree(state.skills) == before


def test_exact_selection_is_retained_in_immutable_plan(state):
    _customize(state)
    token = _selection(state)
    before = _bytes_tree(state.skills)
    with _plan(state, selection=(token,)) as plan:
        assert plan.lead_receipt.selection == tuple(token.split(":")[1:])
        lead = next(member for member in plan.skills if member.name == "lead")
        assert lead.installed_digest == token.split(":")[2]
        assert lead.accepted_prior == lead.installed_digest
        assert plan.stage.digest == token.split(":")[3]
    assert _bytes_tree(state.skills) == before


@pytest.mark.parametrize("component", [0, 1, 2], ids=["receipt", "current", "source"])
def test_any_changed_selection_identity_refuses(state, component):
    _customize(state)
    parts = _selection(state).split(":")
    parts[component + 1] = "0" * 64
    before = _bytes_tree(state.skills)
    with pytest.raises(ValueError, match=ERROR):
        with _plan(state, selection=(":".join(parts),)):
            pytest.fail("Wrong identity admitted")
    assert _bytes_tree(state.skills) == before


@pytest.mark.parametrize("drift", ["byte", "extra", "missing", "source"])
def test_selection_cannot_be_reused_after_authored_drift(state, drift):
    _customize(state)
    token = _selection(state)
    if drift == "byte":
        path = state.lead / "SKILL.md"
        path.write_bytes(path.read_bytes() + b"x")
    elif drift == "extra":
        (state.lead / "extra-user.md").write_bytes(b"unselected authored data")
    elif drift == "missing":
        (state.lead / "SKILL.md").unlink()
    else:
        path = state.source / "lead" / "SKILL.md"
        path.write_bytes(path.read_bytes() + b"source changed")
    before = _bytes_tree(state.skills)
    with pytest.raises(ValueError, match=ERROR):
        with _plan(state, selection=(token,)):
            pytest.fail("Stale selection admitted")
    assert _bytes_tree(state.skills) == before


@pytest.mark.parametrize("condition", ["absent", "invalid", "legacy", "clean"])
def test_receipt_shape_and_actual_modification_are_required(state, condition):
    if condition != "clean":
        _customize(state)
    token = _selection(state)
    if condition == "absent":
        state.receipt.unlink()
    elif condition == "invalid":
        state.receipt.write_bytes(b"{}\n")
    elif condition == "legacy":
        legacy = state.installer._legacy_tree_sha256(
            state.lead, ignore_runtime_cache=True
        )
        state.receipt.write_bytes(state.installer._lead_receipt_bytes(
            legacy, schema=state.installer._LEAD_LEGACY_RECEIPT_SCHEMA
        ))
        token = _selection(state)
    before = _bytes_tree(state.skills)
    with pytest.raises(ValueError, match=ERROR + "|E_CANONICAL_LEAD_RECEIPT_INVALID"):
        with _plan(state, selection=(token,)):
            pytest.fail("Unqualified receipt or unused selection admitted")
    assert _bytes_tree(state.skills) == before


@pytest.mark.parametrize("kind", ["project", "unreceipted", "members", "duplicate", "malformed"])
def test_scope_conflicts_and_ambiguous_selections_refuse(state, kind):
    _customize(state)
    token = _selection(state)
    kwargs = {"root": ROOT, "global_install": True, "replace_modified_lead": (token,)}
    if kind == "project":
        kwargs["global_install"] = False
    elif kind == "unreceipted":
        kwargs["replace_unreceipted_lead_sha256"] = "tree-v2:" + token.split(":")[2]
    elif kind == "members":
        kwargs["member_selection"] = (("analyst", ("SKILL.md",)),)
    elif kind == "duplicate":
        kwargs["replace_modified_lead"] = (token, token)
    else:
        kwargs["replace_modified_lead"] = ("v1:invalid",)
    before = _bytes_tree(state.skills)
    with pytest.raises(ValueError, match=ERROR):
        state.installer._preflight_canonical_skills(
            state.source, state.skills, **kwargs
        )
    assert _bytes_tree(state.skills) == before


@pytest.mark.parametrize("which", ["receipt", "tree"])
def test_linked_receipt_or_lead_is_not_admitted(state, which):
    _customize(state)
    token = _selection(state)
    path = state.receipt if which == "receipt" else state.lead
    retained = path.with_name(path.name + ".fixture-original")
    path.rename(retained)
    try:
        path.symlink_to(retained, target_is_directory=which == "tree")
    except OSError as error:
        retained.rename(path)
        pytest.skip(f"Synthetic symbolic link unavailable: {error}")
    before = _bytes_tree(state.skills)
    with pytest.raises(ValueError, match=(
        ERROR + "|E_CANONICAL_LEAD_RECEIPT_INVALID|E_ACCEPTED_PRIOR_COLLISION"
    )):
        with _plan(state, selection=(token,)):
            pytest.fail("Linked input admitted")
    assert _bytes_tree(state.skills) == before


@pytest.mark.parametrize("where", ["installed", "receipt", "source", "stage"])
def test_post_plan_drift_refuses_before_applying_any_change(state, where):
    _customize(state)
    with _plan(state) as plan:
        if where == "receipt":
            state.receipt.write_bytes(state.installer._lead_receipt_bytes("0" * 64))
        else:
            path = {
                "installed": state.lead / "SKILL.md",
                "source": state.source / "lead" / "SKILL.md",
                "stage": plan.stage.path / "SKILL.md",
            }[where]
            path.write_bytes(path.read_bytes() + b"\nconcurrent fixture modification\n")
        before = _bytes_tree(state.skills)
        with pytest.raises(ValueError, match="DRIFT|COLLISION|SELECTION_INVALID"):
            state.installer._assert_canonical_skills_plan_current(
                plan, state.skills, root=ROOT, claude_transport_root=None
            )
        assert _bytes_tree(state.skills) == before


def test_selection_does_not_borrow_nonlead_ownership(state):
    _customize(state)
    (state.source / "analyst").mkdir()
    (state.source / "analyst" / "SKILL.md").write_bytes(b"factory analyst\n")
    (state.skills / "analyst").mkdir()
    (state.skills / "analyst" / "SKILL.md").write_bytes(b"private analyst\n")
    before = _bytes_tree(state.skills)
    with pytest.raises(ValueError, match="E_CANONICAL_SKILL_ADOPTION_REQUIRED"):
        with _plan(state):
            pytest.fail("Lead selection borrowed unrelated skill ownership")
    assert _bytes_tree(state.skills) == before


def test_optional_peer_and_unlisted_skill_stay_unclaimed(state):
    _customize(state)
    protected = state.skills / "operator-only"
    protected.mkdir()
    (protected / "SKILL.md").write_bytes(b"private unlisted skill\n")
    peer = state.home / ".claude" / "agents" / "scripts"
    peer.mkdir(parents=True)
    (peer / "provider_prompt.py").write_bytes(b"private peer implementation\n")
    peer_before = _bytes_tree(peer.parent)
    protected_before = _bytes_tree(protected)
    assert state.installer._transport_predecessor(ROOT, state.skills, peer) is None
    with _plan(state, claude_transport_root=peer, claude_transport_optional=True) as plan:
        assert plan.transport_stage is None
        _apply(state, plan)
    assert _bytes_tree(peer.parent) == peer_before
    assert _bytes_tree(protected) == protected_before


@pytest.mark.parametrize("scenario", ["restore-recorded", "new-source", "source-equal"])
def test_success_finalizes_actual_source_and_normal_repeat(state, scenario):
    _customize(state, also_source=scenario == "source-equal")
    if scenario == "new-source":
        source_skill = state.source / "lead" / "SKILL.md"
        source_skill.write_bytes(
            source_skill.read_bytes() + b"\n<!-- synthetic replacement source -->\n"
        )
    old_receipt = state.receipt.read_bytes()
    with _plan(state) as plan:
        triple = plan.lead_receipt.selection
        assert (triple[1] == triple[2]) is (scenario == "source-equal")
        expected = plan.stage.manifest
        _apply(state, plan)
        assert state.installer._stage_tree_manifest(state.lead) == expected
        assert json.loads(state.receipt.read_bytes()) == {
            "schema": state.installer._LEAD_RECEIPT_SCHEMA,
            "treeSha256": state.installer._tree_manifest_sha256(expected),
        }
    # Restoring the originally recorded source legitimately retains its receipt.
    assert (state.receipt.read_bytes() == old_receipt) is (scenario == "restore-recorded")
    before_repeat = _bytes_tree(state.skills)
    with _plan(state, selection=()) as plan:
        assert plan.lead_receipt.selection is None
        _apply(state, plan)
    assert _bytes_tree(state.skills) == before_repeat


@pytest.mark.parametrize("fail_after", ["tree", "receipt"])
def test_failure_rolls_back_actual_custom_tree_and_original_receipt(state, fail_after):
    _customize(state)
    (state.lead / "operator-note.md").write_bytes(b"preserve on failed replacement\n")
    before = _bytes_tree(state.skills)
    with _plan(state) as plan:
        with pytest.raises(RuntimeError, match="controlled exception after"):
            _apply(state, plan, fail_after=fail_after)
    assert _bytes_tree(state.skills) == before
    assert state.receipt.read_bytes() == before[RECEIPT]


@pytest.mark.parametrize("already_source", [False, True], ids=["replace-tree", "source-equal"])
def test_finalizer_receipts_stage_minus_proven_removal(state, already_source):
    """Exercise the existing exact-removal owner, not a new retirement policy."""
    relative = "synthetic-retired.txt"
    (state.source / "lead" / relative).write_bytes(b"owned source member\n")
    if already_source:
        (state.lead / relative).write_bytes(b"owned source member\n")
    _customize(state, also_source=already_source)
    with _plan(state) as plan:
        expected = tuple((name, digest) for name, digest in plan.stage.manifest
                         if name != relative)
        assert (plan.lead_receipt.selection[1] == plan.lead_receipt.selection[2]) is already_source
        _apply(state, plan, reclaim=relative)
        assert state.installer._stage_tree_manifest(state.lead) == expected
        assert json.loads(state.receipt.read_bytes())["treeSha256"] == (
            state.installer._tree_manifest_sha256(expected)
        )
        assert json.loads(state.receipt.read_bytes())["treeSha256"] != plan.stage.digest


def test_reclamation_cannot_claim_a_different_source_member_hash(state):
    _customize(state)
    with _plan(state) as plan:
        with pytest.raises(ValueError, match="unbound Lead reclamation"):
            state.installer._canonical_lead_expected_manifest(
                plan.stage.manifest, state.lead,
                ((state.lead / "SKILL.md", "0" * 64),),
            )


def test_existing_unreceipted_adoption_still_has_its_own_path(state):
    _customize(state)
    state.receipt.unlink()
    observed = state.installer._tree_sha256(state.lead, ignore_runtime_cache=True)
    plan = state.installer._preflight_canonical_skills(
        state.source, state.skills, root=ROOT, global_install=True,
        replace_unreceipted_lead_sha256="tree-v2:" + observed,
    )
    try:
        assert plan.lead_receipt.selection is None
        _apply(state, plan)
        assert json.loads(state.receipt.read_bytes())["treeSha256"] == plan.stage.digest
    finally:
        state.installer._discard_canonical_skills_plan(plan)


def test_absent_lead_is_not_reconciled_from_a_receipt_alone(state):
    _customize(state)
    token = _selection(state)
    shutil.rmtree(state.lead)
    before = _bytes_tree(state.skills)
    with pytest.raises(ValueError, match=ERROR):
        with _plan(state, selection=(token,)):
            pytest.fail("A receipt did not supply a current Lead tree")
    assert _bytes_tree(state.skills) == before


def test_modified_selection_does_not_authorize_required_peer_transport(state):
    _customize(state)
    peer = state.home / ".claude" / "agents" / "scripts"
    peer.mkdir(parents=True)
    (peer / "provider_prompt.py").write_bytes(b"private incompatible peer\n")
    before = _bytes_tree(state.home)
    with pytest.raises(ValueError, match="E_TRANSPORT_PROJECTION_PARITY"):
        with _plan(state, claude_transport_root=peer, claude_transport_optional=False):
            pytest.fail("Modified Lead selection qualified a peer transport")
    assert _bytes_tree(state.home) == before


def test_clean_receipted_source_upgrade_needs_no_modified_selection(state):
    source = state.source / "lead" / "SKILL.md"
    source.write_bytes(source.read_bytes() + b"\n<!-- synthetic next source -->\n")
    old_receipt = state.receipt.read_bytes()
    with _plan(state, selection=()) as plan:
        assert plan.lead_receipt.selection is None
        _apply(state, plan)
        assert state.installer._tree_sha256(state.lead) == plan.stage.digest
        assert json.loads(state.receipt.read_bytes())["treeSha256"] == plan.stage.digest
    assert state.receipt.read_bytes() != old_receipt


def test_selected_dry_run_reports_bounded_member_changes_without_writing(state, capsys):
    _customize(state)
    for index in range(27):
        (state.lead / f"operator-{index:02}.md").write_bytes(b"selected custom member\n")
    token = _selection(state)
    before = _bytes_tree(state.skills)
    capsys.readouterr()
    with _plan(state, selection=(token,)) as plan:
        installer = state.installer
        with installer._InstallTransaction([state.skills], enabled=False) as transaction:
            owner = installer._CreateOnlyMutablePath(
                state.home, transaction, dry_run=True
            )
            installer._apply_canonical_skills_plan(
                plan, state.skills, owner, root=ROOT
            )
            installer._finalize_canonical_lead_receipt(plan, state.skills, owner)
            transaction.commit()
    output = capsys.readouterr().out
    assert token in output
    assert "not approval" in output
    summaries = [
        line.split("staged member changes: ", 1)[1]
        for line in output.splitlines() if "staged member changes: " in line
    ]
    assert len(summaries) == 1
    summary = json.loads(summaries[0])
    assert summary["removed"]["count"] == 27
    assert len(summary["removed"]["paths"]) == 20
    assert summary["modified"] == {"count": 1, "paths": ["SKILL.md"]}
    assert all(len(item["paths"]) <= 20 for item in summary.values())
    assert "operator-26.md" not in output
    assert _bytes_tree(state.skills) == before


def test_project_drift_refuses_without_advertising_a_global_selection(state, capsys):
    _customize(state)
    before = _bytes_tree(state.skills)
    capsys.readouterr()
    with pytest.raises(ValueError, match="E_CANONICAL_LEAD_RECEIPT_DRIFT"):
        state.installer._preflight_canonical_skills(
            state.source, state.skills, root=ROOT, global_install=False
        )
    output = capsys.readouterr().out
    assert "--replace-modified-lead" not in output
    assert not re.search(r"v1:(?:[0-9a-f]{64}:){2}[0-9a-f]{64}", output)
    assert "staged member changes: " not in output
    assert _bytes_tree(state.skills) == before
